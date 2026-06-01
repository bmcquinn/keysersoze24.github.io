import os
import sys

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    print("Test Failure: OMNI_CORE_SECRET environment variable must be set externally.")
    sys.exit(1)

import soul_shell
import sovereign_bridge

def run_integration_suite():
    print("=== BEGIN PHASE 2 END-TO-END INTEGRATION MATRIX ===")
    
    # Initialize the new active transport bridge
    bridge = sovereign_bridge.SovereignBridge(bridge_id="bridge_nexus_7")
    
    # Test A: Valid End-to-End Pipeline
    print("\nTesting Valid Path (Shell -> Bridge -> Core)...")
    envelope = soul_shell.prepare_envelope("DATA_SYNC", {"records": 50}, 201)
    try:
        # Route payload across the bridge link
        transport_receipt = bridge.ingest_and_route(envelope)
        print(f" -> BRIDGE DELIVERED: {transport_receipt['transport_status']} via {transport_receipt['bridge']}")
        
        # Execute payload locally at the shell to confirm consistency
        execution_result = soul_shell.execute_envelope(envelope)
        print(f" -> SHELL EXECUTED: {execution_result}")
    except Exception as e:
        print(f" -> FAILED: Unexpected pipeline collapse: {e}")
        return False

    # Test B: Tampered Data on Bridge Transit
    print("\nTesting Tampered Path on Bridge Boundary...")
    tampered_envelope = envelope.copy()
    tampered_payload = tampered_envelope["payload"].copy()
    tampered_payload["records"] = 99999  # Malicious manipulation of transport data
    tampered_envelope["payload"] = tampered_payload
    
    try:
        bridge.ingest_and_route(tampered_envelope)
        print(" -> FAILURE: Transport bridge allowed a manipulated packet to pass.")
        return False
    except sovereign_bridge.BridgeRoutingError:
        print(" -> REJECTED: Bridge caught transit tampering and dropped the packet cleanly.")
    except Exception as e:
        print(f" -> FAILURE: Unexpected error type caught on bridge boundary: {e}")
        return False
        
    print("\nProtocol Behavior Tests: SUCCESS. Complete multi-tier network pipeline enforced.")
    return True

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
