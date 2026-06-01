import json
import os
import socket
import struct
import time
import hmac
import hashlib

# Match system modulus parameters natively
DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

def transmit_dh_handshake(host: str, port: int, command_id: str, params: dict) -> dict:
    """Performs a pure-Python standard library Diffie-Hellman key exchange over wire."""
    # Generate temporary client secrets
    client_private = int.from_bytes(os.urandom(32), byteorder='big')
    client_public = pow(DH_GENERATOR, client_private, DH_PRIME)
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        file_obj = sock.makefile('r', encoding='utf-8')
        
        # 1. Collect Server's public parameters (g^b mod p)
        server_data = json.loads(file_obj.readline().strip())
        server_public = int(server_data["dh_public"])
        
        # 2. Return our public parameter back to the server (g^a mod p)
        exchange_packet = {"dh_public": client_public}
        sock.sendall(json.dumps(exchange_packet).encode('utf-8') + b"\n")
        
        # 3. Mathematically resolve the matching symmetric secret key value block
        shared_secret_int = pow(server_public, client_private, DH_PRIME)
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        session_key = hashlib.sha256(shared_bytes).digest()
        
        # 4. Construct payload message package
        payload = {
            "command_id": command_id,
            "params": params,
            "timestamp": time.time()
        }
        canonical_payload = json.dumps(payload, sort_keys=True)
        signature = hmac.new(session_key, canonical_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        
        envelope = {"version": "1.0", "signature": signature, "payload": payload}
        packet_bytes = json.dumps(envelope).encode('utf-8')
        
        # 5. Output packet over transmission channel stream
        header = struct.pack("!I", len(packet_bytes))
        sock.sendall(header + packet_bytes)
        
        response_bytes = sock.recv(4096)
        return json.loads(response_bytes.decode('utf-8'))
