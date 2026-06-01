import os
import json
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OMNI-CORE] - %(levelname)s - %(message)s')

# Fetch the secret key from environment variables. No insecure in-source default:
# if the operator hasn't provisioned a secret, the module refuses to run.
SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    raise RuntimeError(
        "OMNI_CORE_SECRET environment variable is not set. "
        "Refusing to start without a provisioned shared secret. "
        "Set it via: export OMNI_CORE_SECRET='<your-secret>'"
    )


class OmniCoreProtocol:
    def __init__(self, node_id: str = "architect_1.0", shared_secret: Optional[str] = None):
        self.node_id = node_id
        # Constructor arg overrides the env var (useful for tests passing an explicit
        # secret); otherwise we use the module-level SECRET_KEY validated above.
        effective_secret = shared_secret if shared_secret is not None else SECRET_KEY
        if not effective_secret:
            raise RuntimeError("OmniCoreProtocol requires a non-empty shared secret.")
        self.secret = effective_secret.encode('utf-8')
        logging.info(f"Sovereign Omni-Protocol Core active. Cryptographic layer bound to: {self.node_id}")

    def verify_signature(self, payload_str: str, signature: str) -> bool:
        """Computes HMAC-SHA256 over incoming payloads to guarantee zero tampering."""
        expected = hmac.new(self.secret, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def process_message(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Validates incoming message structure and strictly checks cryptographic proof."""
        if not all(k in envelope for k in ("version", "signature", "payload")):
            return {"status": "REJECTED", "error": "Malformed protocol envelope structure."}
        payload_data = envelope.get("payload", {})

        payload_string = json.dumps(payload_data, sort_keys=True)
        provided_sig = envelope.get("signature", "")
        # Behavior Check: Enforce cryptography
        if not self.verify_signature(payload_string, provided_sig):
            logging.error("SECURITY DISALIGNMENT: Payload cryptographic verification failed.")
            return {"status": "REJECTED", "error": "Invalid signature. Packet dropped."}
        logging.info(f"Signature verified. Executing protocol payload action: {payload_data.get('action')}")
        return {"status": "ALIGNED", "node": self.node_id, "processed": True}


if __name__ == "__main__":
    # Internal baseline validation check
    core = OmniCoreProtocol()
    sample_payload = {"action": "INITIALIZE_HANDSHAKE"}
    payload_str = json.dumps(sample_payload, sort_keys=True)
    valid_sig = hmac.new(core.secret, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
    test_envelope = {"version": "1.0", "signature": valid_sig, "payload": sample_payload}

    print(json.dumps(core.process_message(test_envelope), indent=2))
