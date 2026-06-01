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

def transmit_to_mesh_node(target_node_id: str, command_id: str, params: dict, sequence: int, gateway_port: int = 8080) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect(("127.0.0.1", gateway_port))
        
        file_obj = sock.makefile('r', encoding='utf-8')
        handshake_line = file_obj.readline().strip()
        handshake_data = json.loads(handshake_line)
        
        session_salt = handshake_data.get("handshake_salt")
        if not session_salt:
            raise UnauthenticatedCommandError("Failed mesh negotiation.")
            
        # Select appropriate signing ring depending on target destination route constraints
        if target_node_id == "node_alpha":
            _core.derive_session_key(session_salt)
            signing_key = _core.active_session_key
        else:
            # End-to-End Path: Use master secret key directly so downstream proxy destinations can verify it
            signing_key = _core.master_secret
        
        payload = {
            "target_node_id": target_node_id,
            "command_id": command_id,
            "params": params,
            "sequence": sequence,
            "timestamp": time.time()
        }
        
        canonical_payload = json.dumps(payload, sort_keys=True)
        signature = hmac.new(signing_key, canonical_payload.encode('utf-8'), hashlib.sha256).hexdigest()
        
        envelope = {
            "version": "1.0",
            "signature": signature,
            "payload": payload
        }
        
        packet_bytes = json.dumps(envelope).encode('utf-8')
        header = struct.pack("!I", len(packet_bytes))
        sock.sendall(header + packet_bytes)
        
        response_bytes = sock.recv(4096)
        server_response = json.loads(response_bytes.decode('utf-8'))
        
        if "payload" in server_response:
            return server_response.get("payload")
        return server_response
