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
        self.master_secret = effective_secret.encode('utf-8')
        
        # Ephemeral active connection session key registry
        self.active_session_key: Optional[bytes] = None
        
        self._processed_signatures: Set[str] = set()
        self._signature_history_ledger: list = []
        
        logging.info(f"Sovereign Omni-Protocol Core active. Bound to: {self.node_id} (KDF Engine Engaged)")

    def derive_session_key(self, session_salt: str) -> None:
        """Derives a short-lived ephemeral session key using the master root secret and a wire salt."""
        self.active_session_key = hmac.new(
            self.master_secret, 
            session_salt.encode('utf-8'), 
            hashlib.sha256
        ).digest()
        logging.info("New ephemeral session key derived successfully. Root key shielded.")

    def verify_signature(self, payload_str: str, signature: str) -> bool:
        # Fall back to master secret if an ephemeral socket handshake hasn't provisioned a session key
        signing_key = self.active_session_key if self.active_session_key is not None else self.master_secret
        expected = hmac.new(signing_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def generate_payload_signature(self, payload_str: str) -> str:
        """Helper method to sign outbound payloads using the active key layer."""
        signing_key = self.active_session_key if self.active_session_key is not None else self.master_secret
        return hmac.new(signing_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

    def _purge_expired_ledger_entries(self, current_time: float) -> None:
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
        
        self._purge_expired_ledger_entries(current_time)
        
        if provided_sig in self._processed_signatures:
            logging.error("DEDUPLICATION BLOCK: Identical signature reuse detected!")
            return {"status": "REJECTED", "error": "Duplicate transaction hash detected."}
        
        # Runs evaluation using dynamic active key layer selection rules
        if not self.verify_signature(payload_string, provided_sig):
            logging.error("SECURITY DISALIGNMENT: Cryptographic layer validation failure.")
            return {"status": "REJECTED", "error": "Invalid signature. Packet dropped."}
        
        timestamp = payload_data.get("timestamp", 0)
        time_delta = current_time - timestamp
        
        if time_delta > 60 or time_delta < -5:
            logging.error(f"REPLAY DETECTION: Stale frame dropped. Delta: {time_delta:.2f}s")
            return {"status": "REJECTED", "error": f"Message expired."}
            
        self._processed_signatures.add(provided_sig)
        self._signature_history_ledger.append((current_time, provided_sig))
        
        logging.info(f"Signature and Key Layer Verified. Action: {payload_data.get('command_id')}")
        return {"status": "ALIGNED", "node": self.node_id, "processed": True}
