import json
import os
import socket
import struct
import time
import hmac
import hashlib
from obfuscation_matrix import TrafficObfuscator

CONFIG_PATH = "mesh_config.json"
DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

class SecureSessionChannel:
    def __init__(self):
        self.sock = None
        self.active_gateway = None
        self.obfuscator = TrafficObfuscator()

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

    def _crypt_stream(self, data_bytes: bytes, iv: bytes, target_key: bytes) -> bytes:
        out = bytearray()
        counter = 0
        for i in range(0, len(data_bytes), 32):
            block = data_bytes[i:i+32]
            keystream_block = hmac.new(target_key, iv + counter.to_bytes(4, byteorder='big'), hashlib.sha256).digest()
            for b, k in zip(block, keystream_block): out.append(b ^ k)
            counter += 1
        return bytes(out)

    def connect_and_handshake_resilient(self) -> None:
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            routes = config.get("NODE_ROUTING_TABLE", {})
        except Exception:
            routes = {"node_alpha": 9090}

        for node_id in ["node_alpha", "node_gamma"]:
            if node_id in routes:
                try:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.sock.settimeout(3.0)
                    self.sock.connect(("127.0.0.1", routes[node_id]))
                    self.active_gateway = node_id
                    return
                except Exception:
                    continue
        raise RuntimeError("CRITICAL BLACKOUT: All accessible gateway lines are offline.")

    def transmit_command_routed(self, target_node: str, command_id: str) -> dict:
        # 1. GENERATE EPHEMERAL INLINE KEY PAIR
        cl_private = int.from_bytes(os.urandom(32), byteorder='big')
        cl_public = pow(DH_GENERATOR, cl_private, DH_PRIME)
        cl_public_bytes = str(cl_public).encode('utf-8')

        # 2. EXECUTE EXPLICIT CONTROL PLANE HANDSHAKE ROUTE
        # Packet Envelope Layout: Target Node + DH Key Length + Public Key String
        kex_init_envelope = {
            "target_node": target_node,
            "kex_step": "INIT",
            "dh_public": cl_public_bytes.decode('utf-8')
        }
        
        kex_fec = self.encode_fec_bytes(json.dumps(kex_init_envelope).encode('utf-8'))
        self.sock.sendall(struct.pack("!I", len(kex_fec)) + bytes(kex_fec))

        # Read Server Public Key Response
        resp_header = self.sock.recv(4)
        if not resp_header or len(resp_header) < 4:
            raise RuntimeError("Truncated handshake stream response.")
        server_fec_len = struct.unpack("!I", resp_header)[0]
        raw_srv_fec = self.sock.recv(server_fec_len)
        
        server_envelope = json.loads(self.decode_and_heal_fec_bytes(raw_srv_fec).decode('utf-8'))
        server_dh_public = int(server_envelope.get("dh_public", 0))

        # 3. DERIVE DYNAMIC SYMMETRIC SESSION KEY FOR PERFECT FORWARD SECRECY
        shared_secret_int = pow(server_dh_public, cl_private, DH_PRIME)
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        ephemeral_session_key = hashlib.sha256(shared_bytes).digest()

        # 4. ENCRYPT AND DISPATCH DATA LAYER SEGMENT
        payload = {"command_id": command_id, "params": {}, "timestamp": time.time()}
        raw_payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        
        padded_buffer = bytearray()
        padded_buffer.extend(len(raw_payload_bytes).to_bytes(4, byteorder='big'))
        padded_buffer.extend(raw_payload_bytes)
        padding_needed = 512 - len(padded_buffer)
        if padding_needed > 0: padded_buffer.extend(os.urandom(padding_needed))
            
        iv = os.urandom(16)
        ciphertext = self._crypt_stream(bytes(padded_buffer), iv, ephemeral_session_key)
        encrypted_data_block = {"iv": iv.hex(), "ciphertext": ciphertext.hex()}
        
        signature = hmac.new(ephemeral_session_key, json.dumps(encrypted_data_block, sort_keys=True).encode('utf-8'), hashlib.sha256).hexdigest()
        
        data_envelope = {
            "target_node": target_node,
            "kex_step": "DATA",
            "signature": signature,
            "encrypted_data": encrypted_data_block
        }

        # Apply polymorphic obfuscator structures to data envelope
        client_json_bytes = json.dumps(data_envelope).encode('utf-8')
        chosen_medium = ["HTTPS_SIM", "DNS_TXT", "UDP_BLAST"][int(time.time()) % 3]
        obfuscated_package = self.obfuscator.camouflage_fragment(client_json_bytes, chosen_medium)
        print(f"[*] PFS Session Key Aligned. Routing command via cover medium: [{chosen_medium}]")
        
        fec_bytes = self.encode_fec_bytes(json.dumps(obfuscated_package).encode('utf-8'))
        self.sock.sendall(struct.pack("!I", len(fec_bytes)) + bytes(fec_bytes))
        
        # Read final execution output data back from target machine
        data_resp_header = self.sock.recv(4)
        if not data_resp_header or len(data_resp_header) < 4:
            raise RuntimeError("Truncated response payload block stream.")
            
        server_payload_length = struct.unpack("!I", data_resp_header)[0]
        raw_srv_data_fec = self.sock.recv(server_payload_length)
        
        server_data_envelope = json.loads(self.decode_and_heal_fec_bytes(raw_srv_data_fec).decode('utf-8'))
        server_enc_block = server_data_envelope.get("encrypted_data")
        
        if not hmac.compare_digest(hmac.new(ephemeral_session_key, json.dumps(server_enc_block, sort_keys=True).encode('utf-8'), hashlib.sha256).hexdigest(), server_data_envelope.get("signature", "")):
            raise RuntimeError("PFS Session key integrity mismatch on response stream.")
            
        srv_iv = bytes.fromhex(server_enc_block["iv"])
        srv_ciphertext = bytes.fromhex(server_enc_block["ciphertext"])
        decrypted_bytes = self._crypt_stream(srv_ciphertext, srv_iv, ephemeral_session_key)
        
        data_len = int.from_bytes(decrypted_bytes[0:4], byteorder='big')
        return json.loads(decrypted_bytes[4:4+data_len].decode('utf-8'))

    def close(self) -> None:
        if self.sock:
            self.sock.close()
