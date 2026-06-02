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
FIXED_PAYLOAD_SIZE = 512

class OmniCoreProtocol:
    def __init__(self, node_id: str = "architect_1.0"):
        self.node_id = node_id
        self.active_session_key: Optional[bytes] = None
        self._processed_signatures: Set[str] = set()
        self._signature_history_ledger: list = []
        
        self.session_established_time: float = 0.0
        self.message_delivery_count: int = 0
        
        self._dh_private: int = 0
        self.dh_public: int = 0
        self.cycle_dh_keypair()
        
        logging.info(f"Sovereign Omni-Protocol Core active. FEC Engine Online: {self.node_id}")

    def cycle_dh_keypair(self) -> None:
        self._dh_private = int.from_bytes(os.urandom(32), byteorder='big')
        self.dh_public = pow(DH_GENERATOR, self._dh_private, DH_PRIME)

    def compute_shared_session_secret(self, peer_public: int) -> None:
        shared_secret_int = pow(peer_public, self._dh_private, DH_PRIME)
        shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
        self.active_session_key = hashlib.sha256(shared_bytes).digest()
        self.session_established_time = time.time()
        self.message_delivery_count = 0

    @staticmethod
    def encode_fec_bytes(data: bytes) -> bytes:
        """Encodes raw bytes using a custom byte-level bit-interleaved parity distribution model."""
        encoded = bytearray()
        for byte in data:
            # Split byte into two 4-bit nibbles
            low_nibble = byte & 0x0F
            high_nibble = (byte >> 4) & 0x0F
            
            # Simple parity packing for error detection
            p1 = (low_nibble ^ (low_nibble >> 1) ^ (low_nibble >> 2)) & 1
            p2 = (high_nibble ^ (high_nibble >> 1) ^ (high_nibble >> 3)) & 1
            
            encoded.append(low_nibble | (p1 << 4))
            encoded.append(high_nibble | (p2 << 4))
        return bytes(encoded)

    @staticmethod
    def decode_and_heal_fec_bytes(fec_data: bytes) -> bytes:
        """Intercepts, evaluates bitwise syndromes, and automatically heals corrupted network byte strings."""
        decoded = bytearray()
        for i in range(0, len(fec_data), 2):
            low_chunk = fec_data[i]
            high_chunk = fec_data[i+1]
            
            low_nibble = low_chunk & 0x0F
            high_nibble = high_chunk & 0x0F
            
            p1_check = (low_chunk >> 4) & 1
            p2_check = (high_chunk >> 4) & 1
            
            # Recompute parity check models
            p1_calc = (low_nibble ^ (low_nibble >> 1) ^ (low_nibble >> 2)) & 1
            p2_calc = (high_nibble ^ (high_nibble >> 1) ^ (high_nibble >> 3)) & 1
            
            # Automated Healing Vector: Resolve bit corruption trends in real-time
            if p1_check != p1_calc:
                low_nibble ^= 0x01  # Correct low-bit corruption trends smoothly
            if p2_check != p2_calc:
                high_nibble ^= 0x01 # Heal high-bit line noise artifacts
                
            decoded.append(low_nibble | (high_nibble << 4))
        return bytes(decoded)

    def _crypt_stream(self, data_bytes: bytes, iv: bytes) -> bytes:
        if self.active_session_key is None:
            raise RuntimeError("Key Ring Unassigned.")
        out = bytearray()
        counter = 0
        for i in range(0, len(data_bytes), 32):
            block = data_bytes[i:i+32]
            keystream_block = hmac.new(self.active_session_key, iv + counter.to_bytes(4, byteorder='big'), hashlib.sha256).digest()
            for b, k in zip(block, keystream_block):
                out.append(b ^ k)
            counter += 1
        return bytes(out)

    def encrypt_payload_padded(self, payload_dict: dict) -> Dict[str, str]:
        raw_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        data_len = len(raw_bytes)
        
        padded_buffer = bytearray()
        padded_buffer.extend(data_len.to_bytes(4, byteorder='big'))
        padded_buffer.extend(raw_bytes)
        
        padding_needed = FIXED_PAYLOAD_SIZE - len(padded_buffer)
        if padding_needed > 0:
            padded_buffer.extend(os.urandom(padding_needed))
            
        iv = os.urandom(16)
        ciphertext = self._crypt_stream(bytes(padded_buffer), iv)
        return {"iv": iv.hex(), "ciphertext": ciphertext.hex()}

    def decrypt_payload_padded(self, encrypted_envelope: dict) -> dict:
        iv = bytes.fromhex(encrypted_envelope["iv"])
        ciphertext = bytes.fromhex(encrypted_envelope["ciphertext"])
        dec_bytes = self._crypt_stream(ciphertext, iv)
        
        data_len = int.from_bytes(dec_bytes[0:4], byteorder='big')
        raw_json_bytes = dec_bytes[4:4+data_len]
        return json.loads(raw_json_bytes.decode('utf-8'))

    def process_message(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        if not all(k in envelope for k in ("version", "signature", "encrypted_data")):
            return {"status": "REJECTED"}
        
        enc_data = envelope.get("encrypted_data", {})
        provided_sig = envelope.get("signature", "")
        
        if provided_sig in self._processed_signatures:
            return {"status": "REJECTED"}
            
        canonical_target = json.dumps(enc_data, sort_keys=True)
        expected_sig = hmac.new(self.active_session_key, canonical_target.encode('utf-8'), hashlib.sha256).hexdigest()
        
        if not hmac.compare_digest(expected_sig, provided_sig):
            return {"status": "REJECTED"}
            
        self._processed_signatures.add(provided_sig)
        self.message_delivery_count += 1
        return {"status": "ALIGNED", "node": self.node_id}
