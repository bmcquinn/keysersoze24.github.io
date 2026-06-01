import os
import sys
import time

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    print("Test Failure: OMNI_CORE_SECRET environment variable must be set externally.")
    sys.exit(1)

import soul_shell
import sovereign_bridge

def run_integration_suite():
    print("=== BEGIN PHASE 3 GLOBAL HARDENING INTEGRATION MATRIX ===")
    bridge = sovereign_bridge.SovereignBridge(bridge_id="bridge_nexus_7")
    
    # Test A: Valid Real-Time Pipeline Execution
    print("\nTesting Valid Path (Fresh Packet)...")
    envelope = soul_shell.prepare_envelope("SYSTEM_DIAGNOSTIC", {"verbose": False}, 301)
    try:
        transport_receipt = bridge.ingest_and_route(envelope)
        print(f" -> BRIDGE DELIVERED: {transport_receipt['transport_status']}")
        execution_result = soul_shell.execute_envelope(envelope)
        print(f" -> SHELL EXECUTED: {execution_result}")
    except Exception as e:
        print(f" -> FAILED: Fresh pipeline failed unexpected: {e}")
        return False

    # Test B: Tampered Data on Bridge Transit
    print("\nTesting Tampered Path...")
    tampered_envelope = envelope.copy()
    tampered_payload = tampered_envelope["payload"].copy()
    tampered_payload["sequence"] = 999
    tampered_envelope["payload"] = tampered_payload
    try:
        bridge.ingest_and_route(tampered_envelope)
        print(" -> FAILURE: Manipulated packet bypassed signature verification.")
        return False
    except sovereign_bridge.BridgeRoutingError:
        print(" -> REJECTED: Bridge correctly caught signature mismatch.")

    # Test C: Replay Attack Verification (Stale Packet Rejection)
    print("\nTesting Replay Attack Path (Expired Packet)...")
    # Simulate a packet captured 5 minutes ago (300 seconds)
    stale_timestamp = time.time() - 300
    stale_envelope = soul_shell.prepare_envelope("MALICIOUS_REPLAY", {"exploit": True}, 302, custom_timestamp=stale_timestamp)
    
    try:
        bridge.ingest_and_route(stale_envelope)
        print(" -> FAILURE: Network allowed a stale replayed packet to pass.")
        return False
    except sovereign_bridge.BridgeRoutingError as e:
        print(f" -> REJECTED: Anti-replay protocol blocked packet. Reason: {e}")
        
    print("\nProtocol Behavior Tests: SUCCESS. Replay protection actively shielding network.")
    return True

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
