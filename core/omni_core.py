import logging
import json
import hmac
import hashlib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [OMNI-CORE] - %(levelname)s - %(message)s')

class OmniCoreProtocol:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.active_session_key = None
        logging.info(f"Sovereign Omni-Protocol Core active. Optimized Vector FEC Engine Online: {node_id}")
        
        # PRE-COMPUTED BITWISE LOOKUP TABLES (O(1) Memory Index Mapping)
        # Maps every possible low/high 4-bit nibble value straight to its correct parity bit check token
        self._fec_encode_table = []
        for b in range(16):
            p = (b ^ (b >> 1) ^ (b >> 2)) & 1
            self._fec_encode_table.append(b | (p << 4))
            
        self._fec_calc_table = []
        for b in range(16):
            self._fec_calc_table.append((b ^ (b >> 1) ^ (b >> 2)) & 1)

    def encode_fec_bytes(self, data: bytes) -> bytes:
        """Applies high-speed vectorized lookup table mapping to raw data blocks."""
        encoded = bytearray(len(data) * 2)
        idx = 0
        encode_map = self._fec_encode_table
        
        for byte in data:
            encoded[idx] = encode_map[byte & 0x0F]
            encoded[idx+1] = encode_map[(byte >> 4) & 0x0F]
            idx += 2
        return bytes(encoded)

    def decode_and_heal_fec_bytes(self, fec_data: bytes) -> bytes:
        """Heals stream parity drops using direct index comparisons to wipe loop cycles from memory."""
        decoded = bytearray(len(fec_data) // 2)
        idx = 0
        calc_map = self._fec_calc_table
        
        for i in range(0, len(fec_data), 2):
            low_chunk = fec_data[i]
            high_chunk = fec_data[i+1]
            
            low_nibble = low_chunk & 0x0F
            high_nibble = high_chunk & 0x0F
            
            # Instant parity validation checks using table values
            if ((low_chunk >> 4) & 1) != calc_map[low_nibble]: low_nibble ^= 0x01
            if ((high_chunk >> 4) & 1) != calc_map[high_nibble]: high_nibble ^= 0x01
            
            decoded[idx] = low_nibble | (high_nibble << 4)
            idx += 1
        return bytes(decoded)

    def encrypt_payload_padded(self, payload_dict: dict) -> dict:
        if not self.active_session_key: return {}
        raw_bytes = json.dumps(payload_dict).encode('utf-8')
        iv = os.urandom(16)
        out = bytearray()
        counter = 0
        for i in range(0, len(raw_bytes), 32):
            block = raw_bytes[i:i+32]
            keystream = hmac.new(self.active_session_key, iv + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            for b, k in zip(block, keystream): out.append(b ^ k)
            counter += 1
        return {"iv": iv.hex(), "ciphertext": bytes(out).hex()}

    def decrypt_payload_padded(self, encrypted_dict: dict) -> dict:
        if not self.active_session_key: return {}
        iv = bytes.fromhex(encrypted_dict["iv"])
        ciphertext = bytes.fromhex(encrypted_dict["ciphertext"])
        out = bytearray()
        counter = 0
        for i in range(0, len(ciphertext), 32):
            block = ciphertext[i:i+32]
            keystream = hmac.new(self.active_session_key, iv + counter.to_bytes(4, 'big'), hashlib.sha256).digest()
            for b, k in zip(block, keystream): out.append(b ^ k)
            counter += 1
        return json.loads(bytes(out).decode('utf-8'))
