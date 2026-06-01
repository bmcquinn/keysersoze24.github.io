import json
import os
import socket
import struct
import time
import hmac
import hashlib

DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

class SecureSessionChannel:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.session_key = b""
        
    def _crypt_stream(self, data_bytes: bytes, iv: bytes) -> bytes:
        out = bytearray()
        counter = 0
        for i in range(0, len(data_bytes), 32):
            block = data_bytes[i:i+32]
            keystream_block = hmac.new(self.session_key, iv + counter.to_bytes(4, byteorder='big'), hashlib.sha256).digest()
            for b, k in zip(block, keystream_block):
                out.append(b ^ k)
            counter += 1
        return bytes(out)

    def connect_and_handshake(self) -> None:
        """Establishes stream connection and negotiates the initial channel session validation key."""
        self.sock.connect((self.host, self.port))
        file_obj = self.sock.makefile('r', encoding='utf-8')
        
        server_data = json.loads(file_obj.readline().strip())
        server_public = int(server_data["dh_public"])
        
        client_private = int.from_bytes(os.urandom(32), byteorder='big')
        client_public = pow(DH_GENERATOR, client_private, DH_PRIME)
        
        exchange_packet = {"dh_public": client_public}
        self.sock.sendall(json.dumps(exchange_packet).encode('utf-8') + b"\n")
        
        shared_secret_int = pow(server_public, client_private, DH_PRIME)
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        self.session_key = hashlib.sha256(shared_bytes).digest()

    def transmit_command(self, command_id: str, params: dict) -> dict:
        """Encrypts data payloads and handles automated in-band key rotation handshakes transparently."""
        payload = {"command_id": command_id, "params": params, "timestamp": time.time()}
        raw_payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        iv = os.urandom(16)
        ciphertext = self._crypt_stream(raw_payload_bytes, iv)
        
        encrypted_data_block = {"iv": iv.hex(), "ciphertext": ciphertext.hex()}
        canonical_target = json.dumps(encrypted_data_block, sort_keys=True)
        signature = hmac.new(self.session_key, canonical_target.encode('utf-8'), hashlib.sha256).hexdigest()
        
        envelope = {"version": "1.0", "signature": signature, "encrypted_data": encrypted_data_block}
        packet_bytes = json.dumps(envelope).encode('utf-8')
        header = struct.pack("!I", len(packet_bytes))
        self.sock.sendall(header + packet_bytes)
        
        # Parse return packet parameters
        response_bytes = self.sock.recv(4096)
        server_envelope = json.loads(response_bytes.decode('utf-8'))
        
        server_enc_block = server_envelope.get("encrypted_data")
        canonical_resp_str = json.dumps(server_enc_block, sort_keys=True)
        expected_srv_sig = hmac.new(self.session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected_srv_sig, server_envelope.get("signature", "")):
            raise RuntimeError("Integrity validation check failure on received packet stream.")
            
        srv_iv = bytes.fromhex(server_enc_block["iv"])
        srv_ciphertext = bytes.fromhex(server_enc_block["ciphertext"])
        decrypted_bytes = self._crypt_stream(srv_ciphertext, srv_iv)
        cleartext_response = json.loads(decrypted_bytes.decode('utf-8'))
        
        # IN-BAND REKEY MECHANIC CHECK:
        # If server declares rotation requirements, process the next generation secret handshake immediately
        if cleartext_response.get("lifecycle_state") == "ROTATE_PENDING":
            next_server_public = int(cleartext_response.get("next_dh_public", 0))
            
            # Generate next client parameters
            next_client_private = int.from_bytes(os.urandom(32), byteorder='big')
            next_client_public = pow(DH_GENERATOR, next_client_private, DH_PRIME)
            
            # Transmit our public parameter over the active stream
            rekey_exchange = {"dh_public": next_client_public}
            self.sock.sendall(json.dumps(rekey_exchange).encode('utf-8') + b"\n")
            
            # Calculate and roll onto the new validation key ring instantly
            shared_secret_int = pow(next_server_public, next_client_private, DH_PRIME)
            shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
            self.session_key = hashlib.sha256(shared_bytes).digest()
        
        return cleartext_response

    def close(self) -> None:
        self.sock.close()
