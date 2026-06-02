import json
import os
import socket
import struct
import time
import hmac
import hashlib

CONFIG_PATH = "mesh_config.json"

class SecureSessionChannel:
    def __init__(self):
        self.sock = None
        self.session_key = hashlib.sha256(b"SovereignMeshDefaultSecretTokenKeyRing").digest()
        self.active_gateway = None

    @staticmethod
    def encode_fec_bytes(data: bytes) -> bytes:
        encoded = bytearray()
        for byte in data:
            low_nibble = byte & 0x0F
            high_nibble = (byte >> 4) & 0x0F
            p1 = (low_nibble ^ (low_nibble >> 1) ^ (low_nibble >> 2)) & 1
            p2 = (high_nibble ^ (high_nibble >> 1) ^ (high_nibble >> 3)) & 1
            encoded.append(low_nibble | (p1 << 4))
            encoded.append(high_nibble | (p2 << 4))
        return bytes(encoded)

    @staticmethod
    def decode_and_heal_fec_bytes(fec_data: bytes) -> bytes:
        decoded = bytearray()
        for i in range(0, len(fec_data), 2):
            low_chunk = fec_data[i]
            high_chunk = fec_data[i+1]
            low_nibble = low_chunk & 0x0F
            high_nibble = high_chunk & 0x0F
            p1_check = (low_chunk >> 4) & 1
            p2_check = (high_chunk >> 4) & 1
            p1_calc = (low_nibble ^ (low_nibble >> 1) ^ (low_nibble >> 2)) & 1
            p2_calc = (high_nibble ^ (high_nibble >> 1) ^ (high_nibble >> 3)) & 1
            if p1_check != p1_calc: low_nibble ^= 0x01
            if p2_check != p2_calc: high_nibble ^= 0x01
            decoded.append(low_nibble | (high_nibble << 4))
        return bytes(decoded)

    def _crypt_stream(self, data_bytes: bytes, iv: bytes) -> bytes:
        out = bytearray()
        counter = 0
        for i in range(0, len(data_bytes), 32):
            block = data_bytes[i:i+32]
            keystream_block = hmac.new(self.session_key, iv + counter.to_bytes(4, byteorder='big'), hashlib.sha256).digest()
            for b, k in zip(block, keystream_block): out.append(b ^ k)
            counter += 1
        return bytes(out)

    def connect_and_handshake_resilient(self) -> None:
        """Reads configuration maps to build path lines to active nodes."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            routes = config.get("NODE_ROUTING_TABLE", {})
        except Exception:
            routes = {"node_alpha": 9090}

        # Dynamically evaluate the topology based on your configuration priorities
        for node_id in ["node_alpha", "node_gamma"]:
            if node_id in routes:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(2.0)
                    self.sock.connect(("127.0.0.1", routes[node_id]))
                    self.active_gateway = node_id
                    return
                except Exception:
                    continue
        raise RuntimeError("CRITICAL BLACKOUT: All accessible gateway lines are offline.")

    def transmit_command_routed(self, target_node: str, command_id: str) -> dict:
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            payload_size = config.get("GLOBAL_SETTINGS", {}).get("fixed_payload_size", 512)
        except Exception:
            payload_size = 512

        payload = {"command_id": command_id, "params": {}, "timestamp": time.time()}
        raw_payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        
        padded_buffer = bytearray()
        padded_buffer.extend(len(raw_payload_bytes).to_bytes(4, byteorder='big'))
        padded_buffer.extend(raw_payload_bytes)
        padding_needed = payload_size - len(padded_buffer)
        if padding_needed > 0: padded_buffer.extend(os.urandom(padding_needed))
            
        iv = os.urandom(16)
        ciphertext = self._crypt_stream(bytes(padded_buffer), iv)
        encrypted_data_block = {"iv": iv.hex(), "ciphertext": ciphertext.hex()}
        
        canonical_target = json.dumps(encrypted_data_block, sort_keys=True)
        signature = hmac.new(self.session_key, canonical_target.encode('utf-8'), hashlib.sha256).hexdigest()
        
        inner_envelope = {"version": "1.0", "signature": signature, "encrypted_data": encrypted_data_block}
        routing_envelope = {"target_node": target_node, "inner_envelope": inner_envelope}
        
        client_json_bytes = json.dumps(routing_envelope).encode('utf-8')
        fec_bytes = self.encode_fec_bytes(client_json_bytes)
            
        header = struct.pack("!I", len(fec_bytes))
        self.sock.sendall(header + bytes(fec_bytes))
        
        resp_header = self.sock.recv(4096)
        if not resp_header or len(resp_header) < 4:
            raise RuntimeError("Truncated response payload block stream.")
            
        server_payload_length = struct.unpack("!I", resp_header[0:4])[0]
        raw_srv_fec = resp_header[4:4+server_payload_length]
        
        healed_srv_bytes = self.decode_and_heal_fec_bytes(raw_srv_fec)
        server_envelope = json.loads(healed_srv_bytes.decode('utf-8'))
        
        server_enc_block = server_envelope.get("encrypted_data")
        canonical_resp_str = json.dumps(server_enc_block, sort_keys=True)
        if not hmac.compare_digest(hmac.new(self.session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest(), server_envelope.get("signature", "")):
            raise RuntimeError("Outer packet MAC validation anomaly.")
            
        srv_iv = bytes.fromhex(server_enc_block["iv"])
        srv_ciphertext = bytes.fromhex(server_enc_block["ciphertext"])
        decrypted_bytes = self._crypt_stream(srv_ciphertext, srv_iv)
        
        data_len = int.from_bytes(decrypted_bytes[0:4], byteorder='big')
        return json.loads(decrypted_bytes[4:4+data_len].decode('utf-8'))

    def close(self) -> None:
        if self.sock:
            self.sock.close()
