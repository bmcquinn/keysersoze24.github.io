import json
import os
import socket
import struct
import time
import hmac
import hashlib

FIXED_PAYLOAD_SIZE = 512

class SecureSessionChannel:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.session_key = hashlib.sha256(b"SovereignMeshDefaultSecretTokenKeyRing").digest()

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

    def connect_and_handshake(self, target_node: str) -> None:
        """Establishes clear socket communication bounds to edge proxy gateways."""
        self.sock.connect((self.host, self.port))

    def transmit_command_routed(self, target_node: str, command_id: str) -> dict:
        """Assembles a nested routing structure package, then handles FEC error-correction encapsulation."""
        payload = {"command_id": command_id, "params": {}, "timestamp": time.time()}
        raw_payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        
        padded_buffer = bytearray()
        padded_buffer.extend(len(raw_payload_bytes).to_bytes(4, byteorder='big'))
        padded_buffer.extend(raw_payload_bytes)
        padding_needed = FIXED_PAYLOAD_SIZE - len(padded_buffer)
        if padding_needed > 0: padded_buffer.extend(os.urandom(padding_needed))
            
        iv = os.urandom(16)
        ciphertext = self._crypt_stream(bytes(padded_buffer), iv)
        encrypted_data_block = {"iv": iv.hex(), "ciphertext": ciphertext.hex()}
        
        canonical_target = json.dumps(encrypted_data_block, sort_keys=True)
        signature = hmac.new(self.session_key, canonical_target.encode('utf-8'), hashlib.sha256).hexdigest()
        
        inner_envelope = {"version": "1.0", "signature": signature, "encrypted_data": encrypted_data_block}
        
        # NESTED ROUTING WRAPPER ENVELOPE: Binds tracking properties outside the cryptographic layer
        routing_envelope = {
            "target_node": target_node,
            "inner_envelope": inner_envelope
        }
        
        client_json_bytes = json.dumps(routing_envelope).encode('utf-8')
        fec_bytes = self.encode_fec_bytes(client_json_bytes)
            
        header = struct.pack("!I", len(fec_bytes))
        self.sock.sendall(header + bytes(fec_bytes))
        
        # Read server response block
        resp_header = self.sock.recv(4096)
        if not resp_header or len(resp_header) < 4:
            raise RuntimeError("Truncated data response stream loop.")
            
        server_payload_length = struct.unpack("!I", resp_header[0:4])[0]
        raw_srv_fec = resp_header[4:4+server_payload_length]
        
        healed_srv_bytes = self.decode_and_heal_fec_bytes(raw_srv_fec)
        server_envelope = json.loads(healed_srv_bytes.decode('utf-8'))
        
        server_enc_block = server_envelope.get("encrypted_data")
        canonical_resp_str = json.dumps(server_enc_block, sort_keys=True)
        if not hmac.compare_digest(hmac.new(self.session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest(), server_envelope.get("signature", "")):
            raise RuntimeError("Outer packet MAC verification failure.")
            
        srv_iv = bytes.fromhex(server_enc_block["iv"])
        srv_ciphertext = bytes.fromhex(server_enc_block["ciphertext"])
        decrypted_bytes = self._crypt_stream(srv_ciphertext, srv_iv)
        
        data_len = int.from_bytes(decrypted_bytes[0:4], byteorder='big')
        return json.loads(decrypted_bytes[4:4+data_len].decode('utf-8'))

    def close(self) -> None:
        self.sock.close()
