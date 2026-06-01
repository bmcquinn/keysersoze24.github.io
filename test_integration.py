import os
import sys
import time
import asyncio
import threading

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    print("Test Failure: OMNI_CORE_SECRET environment variable must be set externally.")
    sys.exit(1)

import soul_shell
from sovereign_bridge import SovereignBridgeServer

def run_server_in_thread(server_instance):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server_instance.start())

def run_integration_suite():
    print("=== BEGIN PHASE 5 DEDUPLICATION INTEGRATION MATRIX ===")
    
    bridge_server = SovereignBridgeServer(host="127.0.0.1", port=8080)
    server_thread = threading.Thread(target=run_server_in_thread, args=(bridge_server,), daemon=True)
    server_thread.start()
    
    time.sleep(0.5)
    
    try:
        # Vector A: Valid Initial Wire Action
        print("\nTesting Transmission Path (Initial Packet Verification)...")
        envelope = soul_shell.prepare_envelope("SECURE_TRANSFER", {"amount": 1000}, 501)
        receipt_one = soul_shell.transmit_over_wire(envelope)
        print(f" -> PRIMARY SERVER RESPONSE: {receipt_one}")
        if receipt_one.get("status") != "DELIVERED":
            print(" -> FAILURE: Primary connection sequence dropped.")
            return False

        # Vector B: Double-Spend / Intra-Window Replay Vector
        print("\nTesting Fast Sub-Window Replay Path (Identical Packet Double-Spend Verification)...")
        receipt_two = soul_shell.transmit_over_wire(envelope)
        print(f" -> SECONDARY SERVER RESPONSE: {receipt_two}")
        
        if receipt_two.get("status") == "DELIVERED":
            print(" -> FAILURE: Core allowed identical sub-window replay exploit transaction to run twice.")
            return False
        print(" -> REJECTED: Core internal deduplication cache blocked the duplicate signature safely.")

        # Vector C: Tampered Variant Check
        print("\nTesting Tampered Data Vector...")
        tampered_envelope = envelope.copy()
        tampered_payload = tampered_envelope["payload"].copy()
        tampered_payload["amount"] = 5000000
        tampered_envelope["payload"] = tampered_payload
        
        receipt_three = soul_shell.transmit_over_wire(tampered_envelope)
        print(f" -> TAMPERED RESPONSE: {receipt_three}")
        if receipt_three.get("status") == "DELIVERED":
            return False
            
        print("\nState-Tracked Deduplication Verification: SUCCESS. Core cannot be double-spent.")
        return True

    except Exception as e:
        print(f" -> CRITICAL DISALIGNMENT ERROR: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
