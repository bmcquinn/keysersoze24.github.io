import struct
import os
import hashlib

AUDIT_LOG_PATH = "mesh_audit.bin"

def verify_and_display_ledger():
    if not os.path.exists(AUDIT_LOG_PATH):
        print("[-] Audit ledger file path does not exist yet. Transmit data to initialize.")
        return

    print("==========================================================================")
    print("                      SOVEREIGN MESH OPERATIONAL LEDGER                   ")
    print("==========================================================================")
    print(f" Target File: {AUDIT_LOG_PATH} | Block Unit Footprint: 72 Bytes Per Entry \n")

    expected_hash = b"\x00" * 36
    integrity_valid = True

    with open(AUDIT_LOG_PATH, "rb") as f:
        entry_idx = 0
        while True:
            raw_bytes = f.read(72)
            if not raw_bytes or len(raw_bytes) < 72:
                break
                
            # Unpack the fixed binary sequence fields
            timestamp, node_raw, event_raw, status_code, prev_hash_raw = struct.unpack("!d12s12sI36s", raw_bytes)
            
            node_id = node_raw.decode('utf-8').strip('\x00')
            event_type = event_raw.decode('utf-8').strip('\x00')
            prev_hash = prev_hash_raw.decode('utf-8')

            # Live Integrity Validation Check
            if entry_idx > 0:
                if prev_hash_raw != expected_hash:
                    print(f" [!] CRYPTOGRAPHIC CHAIN BREAK DETECTED AT BLOCK INDEX {entry_idx}!")
                    integrity_valid = False
            
            print(f" [{entry_idx:03d}] Time: {timestamp:.4f} | Node: {node_id:<10} | Event: {event_type:<8} | Status: {status_code} ")
            
            # Compute current block's hash to check against the next entry's pointer
            expected_hash = hashlib.sha256(raw_bytes).hexdigest()[:36].encode('utf-8')
            entry_idx += 1

    print("--------------------------------------------------------------------------")
    if integrity_valid:
        print(" [+] SECURE CHAIN STATE: Aligned. No external mutation detected.\n")
    else:
        print(" [-] SECURE CHAIN STATE: CORRUPTED! Historic audit signatures broken.\n")

if __name__ == "__main__":
    verify_and_display_ledger()
