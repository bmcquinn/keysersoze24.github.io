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
    """Orchestrates asynchronous loop hosting inside a dedicated structural background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server_instance.start())

def run_integration_suite():
    print("=== BEGIN PHASE 4 DISTRIBUTED SOCKET INTEGRATION MATRIX ===")
    
    # 1. Spin up the Socket Server Link in the background
    bridge_server = SovereignBridgeServer(host="127.0.0.1", port=8080)
    server_thread = threading.Thread(target=run_server_in_thread, args=(bridge_server,), daemon=True)
    server_thread.start()
    
    # Allow socket bindings to settle
    time.sleep(0.5)
    
    try:
        # Vector A: Valid Live-Wire Handshake Execution
        print("\nTesting Valid Path Over Socket Line...")
        envelope = soul_shell.prepare_envelope("NET_SOCKET_INIT", {"encrypted": True}, 401)
        receipt = soul_shell.transmit_over_wire(envelope)
        print(f" -> SERVER RESPONSE: {receipt}")
        if receipt.get("status") != "DELIVERED":
            print(" -> FAILURE: Server dropped standard connection path.")
            return False

        # Vector B: Tampered Data Verification Over Socket
        print("\nTesting Tampered Data Payload Over Socket Line...")
        tampered_envelope = envelope.copy()
        tampered_payload = tampered_envelope["payload"].copy()
        tampered_payload["sequence"] = 99999 # Alter data mid-transit
        tampered_envelope["payload"] = tampered_payload
        
        receipt = soul_shell.transmit_over_wire(tampered_envelope)
        print(f" -> SERVER RESPONSE: {receipt}")
        if receipt.get("status") == "DELIVERED":
            print(" -> FAILURE: Server allowed tampered network data payload to route.")
            return False
        print(" -> REJECTED: Server caught transit injection attempt.")

        # Vector C: Expired Packet Attack Over Socket
        print("\nTesting Replay Protection Over Socket Line...")
        stale_timestamp = time.time() - 120 # 2 minutes old
        stale_envelope = soul_shell.prepare_envelope("REPLAY_ATTACK", {"exploit": True}, 402, custom_timestamp=stale_timestamp)
        
        receipt = soul_shell.transmit_over_wire(stale_envelope)
        print(f" -> SERVER RESPONSE: {receipt}")
        if receipt.get("status") == "DELIVERED":
            print(" -> FAILURE: Server accepted expired network transport frame.")
            return False
        print(" -> REJECTED: Anti-replay protocol systematically dropped expired packet.")

        print("\nDistributed Network Protocol Verification: SUCCESS. Live-wire transport secured.")
        return True

    except Exception as e:
        print(f" -> CRITICAL INTERFACE COUPLING FAIL: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
