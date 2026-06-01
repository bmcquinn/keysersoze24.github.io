import json
import os
import socket
import struct
import time
import hmac
import hashlib

DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

def _crypt_stream(data_bytes: bytes, key: bytes, iv: bytes) -> bytes:
    out = bytearray()
    counter = 0
    for i in range(0, len(data_bytes), 32):
        block = data_bytes[i:i+32]
        keystream_block = hmac.new(key, iv + counter.to_bytes(4, byteorder='big'), hashlib.sha256).digest()
        for b, k in zip(block, keystream_block):
            out.append(b ^ k)
        counter += 1
    return bytes(out)

def transmit_encrypted_command(host: str, port: int, command_id: str, params: dict) -> dict:
    """Performs DH key negotiation, encrypts the command packet, and handles encrypted response blocks."""
    client_private = int.from_bytes(os.urandom(32), byteorder='big')
    client_public = pow(DH_GENERATOR, client_private, DH_PRIME)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        file_obj = sock.makefile('r', encoding='utf-8')
        
        server_data = json.loads(file_obj.readline().strip())
        server_public = int(server_data["dh_public"])
        
        exchange_packet = {"dh_public": client_public}
        sock.sendall(json.dumps(exchange_packet).encode('utf-8') + b"\n")
        
        shared_secret_int = pow(server_public, client_private, DH_PRIME)
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        session_key = hashlib.sha256(shared_bytes).digest()
        
        # 1. Structure the cleartext dictionary data block layout
        payload = {
            "command_id": command_id,
            "params": params,
            "timestamp": time.time()
        }
        
        # 2. Encrypt cleartext block into opaque ciphertext payload parameters natively
        raw_payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        iv = os.urandom(16)
        ciphertext = _crypt_stream(raw_payload_bytes, session_key, iv)
        
        encrypted_data_block = {
            "iv": iv.hex(),
            "ciphertext": ciphertext.hex()
        }
        
        # 3. Compute structural MAC authentication signature token across the encrypted parameters
        canonical_target = json.dumps(encrypted_data_block, sort_keys=True)
        signature = hmac.new(session_key, canonical_target.encode('utf-8'), hashlib.sha256).hexdigest()
        
        envelope = {
            "version": "1.0",
            "signature": signature,
            "encrypted_data": encrypted_data_block
        }
        
        # 4. Transmit data packet over socket using big-endian length prefixing
        packet_bytes = json.dumps(envelope).encode('utf-8')
        header = struct.pack("!I", len(packet_bytes))
        sock.sendall(header + packet_bytes)
        
        # 5. Capture encrypted response packet back from node listener
        response_bytes = sock.recv(4096)
        server_envelope = json.loads(response_bytes.decode('utf-8'))
        
        # Verify server transmission block MAC integrity before decrypting
        server_enc_block = server_envelope.get("encrypted_data")
        canonical_resp_str = json.dumps(server_enc_block, sort_keys=True)
        expected_srv_sig = hmac.new(session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected_srv_sig, server_envelope.get("signature", "")):
            raise RuntimeError("CRITICAL ERROR: Server response failed integrity verification checks.")
            
        # Decrypt response bytes cleanly back to cleartext dictionary
        srv_iv = bytes.fromhex(server_enc_block["iv"])
        srv_ciphertext = bytes.fromhex(server_enc_block["ciphertext"])
        decrypted_response_bytes = _crypt_stream(srv_ciphertext, session_key, srv_iv)
        
        return json.loads(decrypted_response_bytes.decode('utf-8'))
