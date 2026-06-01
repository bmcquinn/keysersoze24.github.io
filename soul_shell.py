import json
import hmac
import hashlib
import time
import socket
import struct
from typing import Optional
from omni_core import OmniCoreProtocol

class UnauthenticatedCommandError(Exception):
    """Raised when an execution payload or return receipt fails authenticity checks."""
    pass

_core = OmniCoreProtocol(node_id="soul_shell_engine")

def transmit_and_verify(command_id: str, params: dict, sequence: int, host: str = "127.0.0.1", port: int = 8080) -> dict:
    """Establishes stream connection, captures handshake salt, derives dynamic keys, and transmits payload."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        
        # 1. Read the handshake salt line from the server socket buffer
        file_obj = sock.makefile('r', encoding='utf-8')
        handshake_line = file_obj.readline().strip()
        handshake_data = json.loads(handshake_line)
        
        session_salt = handshake_data.get("handshake_salt")
        if not session_salt:
            raise UnauthenticatedCommandError("Failed network coupling negotiation: missing session salt initialization.")
            
        # 2. Dynamically update local core key configuration status
        _core.derive_session_key(session_salt)
        
        # 3. Assemble application payload package
        payload = {
            "command_id": command_id,
            "params": params,
            "sequence": sequence,
            "timestamp": time.time()
        }
        
        canonical_payload = json.dumps(payload, sort_keys=True)
        signature = _core.generate_payload_signature(canonical_payload)
        
        envelope = {
            "version": "1.0",
            "signature": signature,
            "payload": payload
        }
        
        # 4. Frame message block and transmit down line
        packet_bytes = json.dumps(envelope).encode('utf-8')
        header = struct.pack("!I", len(packet_bytes))
        sock.sendall(header + packet_bytes)
        
        # 5. Intercept and parse incoming server-side return packet response
        response_bytes = sock.recv(4096)
        server_envelope = json.loads(response_bytes.decode('utf-8'))
        
        if "signature" not in server_envelope or "payload" not in server_envelope:
            raise UnauthenticatedCommandError("Security Exception: Server response malformed.")
            
        server_payload = server_envelope.get("payload", {})
        canonical_response = json.dumps(server_payload, sort_keys=True)
        provided_sig = server_envelope.get("signature", "")
        
        # 6. Validate receipt utilizing the active dynamic key layer configuration
        if not _core.verify_signature(canonical_response, provided_sig):
            raise UnauthenticatedCommandError("CRITICAL RISK: Response validation failure on dynamic session stream!")
            
        return server_payload
