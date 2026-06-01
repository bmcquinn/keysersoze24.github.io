import os
import sys

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    print("Test Failure: OMNI_CORE_SECRET environment variable must be set externally.")
    sys.exit(1)

import soul_shell

def run_integration_suite():
    print("=== BEGIN PHASE 1 INTEGRATION MATRIX ===")
    
    print("Testing Valid Path...")
    envelope = soul_shell.prepare_envelope("SYS_REBOOT", {"force": True}, 101)
    try:
        result = soul_shell.execute_envelope(envelope)
        print(f" -> ALIGNED: {result}")
    except Exception as e:
        print(f" -> FAILED: Unexpected exception {e}")
        return False

    print("Testing Tampered/Negative Path...")
    tampered_envelope = envelope.copy()
    # Deep copy payload modification to force signature misalignment
    tampered_payload = tampered_envelope["payload"].copy()
    tampered_payload["sequence"] = 102
    tampered_envelope["payload"] = tampered_payload
    
    try:
        soul_shell.execute_envelope(tampered_envelope)
        print(" -> FAILURE: Tampered packet bypassed validation boundaries.")
        return False
    except soul_shell.UnauthenticatedCommandError:
        print(" -> REJECTED: Tampered packet blocked successfully.")
    except Exception as e:
        print(f" -> FAILURE: Wrong error type raised: {e}")
        return False
        
    print("Protocol Behavior Tests: SUCCESS. Failure modes successfully enforced.")
    return True

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
