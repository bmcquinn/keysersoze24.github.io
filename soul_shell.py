import json
import hmac
import hashlib
import time
import socket
import struct
from typing import Optional
from omni_core import OmniCoreProtocol

class UnauthenticatedCommandError(Exception):
    """Raised when a localized network execution payload fails authentication or expiration gates."""
    pass

_core = OmniCoreProtocol(node_id="soul_shell_engine")

def prepare_envelope(command_id: str, params: dict, sequence: int, custom_timestamp: Optional[float] = None) -> dict:
    """Packages, timestamps, and signs an outbound network instruction envelope."""
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

def transmit_over_wire(envelope: dict, host: str = "127.0.0.1", port: int = 8080) -> dict:
    """Establishes raw TCP socket connection, frames message with length headers, and transmits."""
    packet_bytes = json.dumps(envelope).encode('utf-8')
    # Package length into a 4-byte big-endian prefix
    header = struct.pack("!I", len(packet_bytes))
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((host, port))
        # Write length prefix followed by raw packet payload
        sock.sendall(header + packet_bytes)
        
        # Read server receipt response back from the line
        response_bytes = sock.recv(1024)
        return json.loads(response_bytes.decode('utf-8'))

def execute_envelope(envelope: dict) -> str:
    """Verifies internal integrity checks before processing execution requests."""
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
