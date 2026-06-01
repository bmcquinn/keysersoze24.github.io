import os
import json
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OMNI-CORE] - %(levelname)s - %(message)s')

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    raise RuntimeError("OMNI_CORE_SECRET environment variable is not set. Refusing to start.")

class ExpiredMessageError(Exception):
    """Raised when an incoming packet's timestamp falls outside the valid time window."""
    pass

class OmniCoreProtocol:
    def __init__(self, node_id: str = "architect_1.0", shared_secret: Optional[str] = None):
        self.node_id = node_id
        effective_secret = shared_secret if shared_secret is not None else SECRET_KEY
        if not effective_secret:
            raise RuntimeError("OmniCoreProtocol requires a non-empty shared secret.")
        self.secret = effective_secret.encode('utf-8')
        logging.info(f"Sovereign Omni-Protocol Core active. Bound to: {self.node_id}")

    def verify_signature(self, payload_str: str, signature: str) -> bool:
        expected = hmac.new(self.secret, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def process_message(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not all(k in envelope for k in ("version", "signature", "payload")):
            return {"status": "REJECTED", "error": "Malformed protocol envelope structure."}
        
        payload_data = envelope.get("payload", {})
        payload_string = json.dumps(payload_data, sort_keys=True)
        provided_sig = envelope.get("signature", "")
        
        # Guard 1: Cryptographic Integrity
        if not self.verify_signature(payload_string, provided_sig):
            logging.error("SECURITY DISALIGNMENT: Payload cryptographic verification failed.")
            return {"status": "REJECTED", "error": "Invalid signature. Packet dropped."}
        
        # Guard 2: Replay Protection (Time Window Validation)
        timestamp = payload_data.get("timestamp", 0)
        current_time = time.time()
        time_delta = current_time - timestamp
        
        # Reject packets older than 60 seconds or messages post-dated from the future
        if time_delta > 60 or time_delta < -5:
            logging.error(f"REPLAY DETECTION: Stale or future packet dropped. Delta: {time_delta:.2f}s")
            return {"status": "REJECTED", "error": f"Message expired. Stale by {time_delta:.2f} seconds."}
            
        logging.info(f"Signature and Timestamp Verified. Action: {payload_data.get('command_id')}")
        return {"status": "ALIGNED", "node": self.node_id, "processed": True}
