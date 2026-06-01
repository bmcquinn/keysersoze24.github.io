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

def prepare_envelope(command_id: str, params: dict, sequence: int, custom_timestamp: Optional[float] = None) -> dict:
    payload = {
        "command_id": command_id,
        "params": params,
        "sequence": sequence,
        "timestamp": custom_timestamp if custom_timestamp is not None else time.time()
    }
    canonical_payload = json.dumps(payload, sort_keys=True)
    signature = hmac.new(_core.secret, canonical_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    
    return {
        "version": "1.0",
        "signature": signature,
        "payload": payload
    }

def transmit_and_verify(envelope: dict, host: str = "127.0.0.1", port: int = 8080) -> dict:
    """Sends signed instruction package over wire and forces signature checks on return receipts."""
    packet_bytes = json.dumps(envelope).encode('utf-8')
    header = struct.pack("!I", len(packet_bytes))
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        sock.sendall(header + packet_bytes)
        
        # Read the raw server-side signature envelope
        response_bytes = sock.recv(4096)
        server_envelope = json.loads(response_bytes.decode('utf-8'))
        
        if "signature" not in server_envelope or "payload" not in server_envelope:
            raise UnauthenticatedCommandError("Security Exception: Server returned unauthenticated execution block.")
            
        server_payload = server_envelope.get("payload", {})
        canonical_response = json.dumps(server_payload, sort_keys=True)
        provided_sig = server_envelope.get("signature", "")
        
        # Guard 1: Verify server identity via shared HMAC key validation
        expected_sig = hmac.new(_core.secret, canonical_response.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise UnauthenticatedCommandError("CRITICAL EXPLOIT: Server return verification failed! Malicious packet detected.")
            
        # Guard 2: Enforce return stream timestamp freshness window
        time_delta = time.time() - server_payload.get("timestamp", 0)
        if time_delta > 60 or time_delta < -5:
            raise UnauthenticatedCommandError(f"Security Exception: Server response expired or replayed. Delta: {time_delta:.2f}s")
            
        return server_payload

def execute_envelope(envelope: dict) -> str:
    payload_data = envelope.get("payload", {})
    core_envelope = {
        "version": envelope.get("version", "1.0"),
        "signature": envelope.get("signature", ""),
        "payload": payload_data
    }
    
    validation_result = _core.process_message(core_envelope)
    if validation_result.get("status") != "ALIGNED":
        raise UnauthenticatedCommandError(f"Security Breach: {validation_result.get('error')}")
    
    return f"Execution Success: Command {payload_data['command_id']} running with parameters {payload_data['params']}"
