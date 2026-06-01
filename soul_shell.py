import json
import hmac
import hashlib
from omni_core import OmniCoreProtocol

class UnauthenticatedCommandError(Exception):
    """Raised when an execution payload fails cryptographic signature verification."""
    pass

# Initialize the protocol core object locally
_core = OmniCoreProtocol(node_id="soul_shell_engine")

def prepare_envelope(command_id: str, params: dict, sequence: int) -> dict:
    """Packages and signs an outbound instruction string using OmniCoreProtocol secrets."""
    payload = {
        "command_id": command_id,
        "params": params,
        "sequence": sequence
    }
    canonical_payload = json.dumps(payload, sort_keys=True)
    
    # Generate signature using the bound protocol secret
    signature = hmac.new(_core.secret, canonical_payload.encode('utf-8'), hashlib.sha256).hexdigest()
    
    return {
        "version": "1.0",
        "signature": signature,
        "payload": payload
    }

def execute_envelope(envelope: dict) -> str:
    """Verifies the cryptographic signature before allowing local command execution."""
    payload_data = envelope.get("payload", {})
    canonical_payload = json.dumps(payload_data, sort_keys=True)
    signature = envelope.get("signature", "")
    
    # Use the class-based verification method
    if not _core.verify_signature(canonical_payload, signature):
        raise UnauthenticatedCommandError("Security Breach: Token invalid or payload tampered. Command dropped.")
    
    return f"Execution Success: Command {payload_data['command_id']} running with parameters {payload_data['params']}"
