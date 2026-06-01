import os
import json
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, Optional, Set

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OMNI-CORE] - %(levelname)s - %(message)s')

DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

class OmniCoreProtocol:
    def __init__(self, node_id: str = "architect_1.0"):
        self.node_id = node_id
        self.active_session_key: Optional[bytes] = None
        self._processed_signatures: Set[str] = set()
        self._signature_history_ledger: list = []
        
        self._dh_private = int.from_bytes(os.urandom(32), byteorder='big')
        self.dh_public = pow(DH_GENERATOR, self._dh_private, DH_PRIME)
        
        logging.info(f"Sovereign Omni-Protocol Core active. Confidentiality Layer Enabled: {self.node_id}")

    def compute_shared_session_secret(self, peer_public: int) -> None:
        shared_secret_int = pow(peer_public, self._dh_private, DH_PRIME)
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        self.active_session_key = hashlib.sha256(shared_bytes).digest()
        logging.info(f"[{self.node_id}] Shared symmetric key realized. Core payload encryption primed.")

    def _crypt_stream(self, data_bytes: bytes, iv: bytes) -> bytes:
        """A pure-Python deterministic counter keystream generator (SHA-256 CTR Mode simulation)."""
        if self.active_session_key is None:
            raise RuntimeError("Session key must be derived before encryption operations.")
        
        out = bytearray()
        counter = 0
        # Process data in 32-byte blocks matching the SHA-256 output footprint
        for i in range(0, len(data_bytes), 32):
            block = data_bytes[i:i+32]
            # Generate key block: HMAC(SessionKey, IV + Counter)
            keystream_block = hmac.new(
                self.active_session_key, 
                iv + counter.to_bytes(4, byteorder='big'), 
                hashlib.sha256
            ).digest()
            
            # XOR input data against the generated key block
            for b, k in zip(block, keystream_block):
                out.append(b ^ k)
            counter += 1
        return bytes(out)

    def encrypt_payload(self, payload_dict: dict) -> Dict[str, str]:
        """Encrypts a structural dictionary data layout into a secure initialization vector and ciphertext pair."""
        raw_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        iv = os.urandom(16)
        ciphertext = self._crypt_stream(raw_bytes, iv)
        return {
            "iv": iv.hex(),
            "ciphertext": ciphertext.hex()
        }

    def decrypt_payload(self, encrypted_envelope: dict) -> dict:
        """Decrypts an inbound hexadecimal structural packet back into standard JSON dictionary parameters."""
        iv = bytes.fromhex(encrypted_envelope["iv"])
        ciphertext = bytes.fromhex(encrypted_envelope["ciphertext"])
        dec_bytes = self._crypt_stream(ciphertext, iv)
        return json.loads(dec_bytes.decode('utf-8'))

    def process_message(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not all(k in envelope for k in ("version", "signature", "encrypted_data")):
            return {"status": "REJECTED", "error": "Malformed protocol encryption layout."}
        
        enc_data = envelope.get("encrypted_data", {})
        provided_sig = envelope.get("signature", "")
        
        if provided_sig in self._processed_signatures:
            return {"status": "REJECTED", "error": "Duplicate signature signature block dropped."}
        
        # Guard: Authenticate the encrypted payload before attempting decryption (Mac-then-Encrypt validation)
        canonical_target = json.dumps(enc_data, sort_keys=True)
        expected_sig = hmac.new(self.active_session_key, canonical_target.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected_sig, provided_sig):
            logging.error("CONFIDENTIALITY BREACH: Inbound envelope integrity validation failed.")
            return {"status": "REJECTED", "error": "Invalid signature packet."}
            
        self._processed_signatures.add(provided_sig)
        return {"status": "ALIGNED", "node": self.node_id}
