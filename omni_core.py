import os
import json
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, Optional, Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OMNI-CORE] - %(levelname)s - %(message)s')

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    raise RuntimeError("OMNI_CORE_SECRET environment variable is not set. Refusing to start.")

class OmniCoreProtocol:
    def __init__(self, node_id: str = "architect_1.0", shared_secret: Optional[str] = None):
        self.node_id = node_id
        effective_secret = shared_secret if shared_secret is not None else SECRET_KEY
        if not effective_secret:
            raise RuntimeError("OmniCoreProtocol requires a non-empty shared secret.")
        self.secret = effective_secret.encode('utf-8')
        
        # Initialize an in-memory tracking cache for processed signatures to handle deduplication
        self._processed_signatures: Set[str] = set()
        # Track signatures along with their arrival timestamps for cleanup sorting
        self._signature_history_ledger: list = []
        
        logging.info(f"Sovereign Omni-Protocol Core active. Bound to: {self.node_id} (Deduplication Layer Engaged)")

    def verify_signature(self, payload_str: str, signature: str) -> bool:
        expected = hmac.new(self.secret, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _purge_expired_ledger_entries(self, current_time: float) -> None:
        """Sweeps memory blocks to evict signatures that have passed outside the 60-second validity window."""
        while self._signature_history_ledger and (current_time - self._signature_history_ledger[0][0]) > 60:
            _, expired_sig = self._signature_history_ledger.pop(0)
            self._processed_signatures.discard(expired_sig)

    def process_message(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not all(k in envelope for k in ("version", "signature", "payload")):
            return {"status": "REJECTED", "error": "Malformed protocol envelope structure."}
        
        payload_data = envelope.get("payload", {})
        payload_string = json.dumps(payload_data, sort_keys=True)
        provided_sig = envelope.get("signature", "")
        current_time = time.time()
        
        # Run memory garbage collection sweep before checking the new incoming signature
        self._purge_expired_ledger_entries(current_time)
        
        # Guard 1: Deduplication Check (Prevent duplicate submissions within the valid window)
        if provided_sig in self._processed_signatures:
            logging.error(f"DEDUPLICATION BLOCK: Identical payload packet detected within window! Dropping duplicate.")
            return {"status": "REJECTED", "error": "Duplicate transaction hash detected. Operation aborted."}
        
        # Guard 2: Cryptographic Integrity
        if not self.verify_signature(payload_string, provided_sig):
            logging.error("SECURITY DISALIGNMENT: Payload cryptographic verification failed.")
            return {"status": "REJECTED", "error": "Invalid signature. Packet dropped."}
        
        # Guard 3: Replay Protection (Time Window Validation)
        timestamp = payload_data.get("timestamp", 0)
        time_delta = current_time - timestamp
        
        if time_delta > 60 or time_delta < -5:
            logging.error(f"REPLAY DETECTION: Stale or future packet dropped. Delta: {time_delta:.2f}s")
            return {"status": "REJECTED", "error": f"Message expired. Stale by {time_delta:.2f} seconds."}
            
        # Log payload signature verification history states to block sub-window spamming
        self._processed_signatures.add(provided_sig)
        self._signature_history_ledger.append((current_time, provided_sig))
        
        logging.info(f"Signature and Timestamp Verified. Action: {payload_data.get('command_id')}")
        return {"status": "ALIGNED", "node": self.node_id, "processed": True}
