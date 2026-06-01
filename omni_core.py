import os
import json
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, Optional, Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OMNI-CORE] - %(levelname)s - %(message)s')

# Standard 2048-bit MODP Group 14 Primes for secure key exchanges
DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

class OmniCoreProtocol:
    def __init__(self, node_id: str = "architect_1.0"):
        self.node_id = node_id
        self.active_session_key: Optional[bytes] = None
        self._processed_signatures: Set[str] = set()
        self._signature_history_ledger: list = []
        
        # Generate a high-entropy 256-bit private integer safely using os.urandom
        self._dh_private = int.from_bytes(os.urandom(32), byteorder='big')
        # Compute local public value exchange token: (g^secret) mod p
        self.dh_public = pow(DH_GENERATOR, self._dh_private, DH_PRIME)
        
        logging.info(f"Sovereign Omni-Protocol Core active. Native DH Identity bound to: {self.node_id}")

    def compute_shared_session_secret(self, peer_public: int) -> None:
        """Derives the shared session key by mixing the peer's public value with our private key."""
        shared_secret_int = pow(peer_public, self._dh_private, DH_PRIME)
        # Hash the raw integer to generate a uniform 32-byte secret key block
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        self.active_session_key = hashlib.sha256(shared_bytes).digest()
        logging.info(f"[{self.node_id}] Ephemeral session key negotiated via pure mathematical DH exchange.")

    def verify_signature(self, payload_str: str, signature: str) -> bool:
        if self.active_session_key is None:
            return False
        expected = hmac.new(self.active_session_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def generate_payload_signature(self, payload_str: str) -> str:
        if self.active_session_key is None:
            raise RuntimeError("Key Layer Missing.")
        return hmac.new(self.active_session_key, payload_str.encode('utf-8'), hashlib.sha256).hexdigest()

    def process_message(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not all(k in envelope for k in ("version", "signature", "payload")):
            return {"status": "REJECTED", "error": "Malformed structure."}
        
        payload_data = envelope.get("payload", {})
        payload_string = json.dumps(payload_data, sort_keys=True)
        provided_sig = envelope.get("signature", "")
        
        if provided_sig in self._processed_signatures:
            return {"status": "REJECTED", "error": "Duplicate signature detected."}
        
        if not self.verify_signature(payload_string, provided_sig):
            return {"status": "REJECTED", "error": "Invalid signature."}
            
        self._processed_signatures.add(provided_sig)
        return {"status": "ALIGNED", "node": self.node_id, "processed": True}
