import json
import hmac
import hashlib
import time
from typing import Optional
from omni_core import OmniCoreProtocol

class UnauthenticatedCommandError(Exception):
    """Raised when an execution payload fails validation or replication checks."""
    pass

_core = OmniCoreProtocol(node_id="soul_shell_engine")

def prepare_envelope(command_id: str, params: dict, sequence: int, custom_timestamp: Optional[float] = None) -> dict:
    """Packages, timestamps, and signs an outbound instruction string."""
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

def execute_envelope(envelope: dict) -> str:
    """Verifies cryptographic signature and freshness before allowing execution."""
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
