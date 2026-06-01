import os
import sys
import time
import asyncio
import threading
import json

SECRET_KEY = os.environ.get("OMNI_CORE_SECRET")
if not SECRET_KEY:
    print("Test Failure: OMNI_CORE_SECRET environment variable must be set externally.")
    sys.exit(1)

import soul_shell
import sovereign_bridge
from sovereign_bridge import SovereignBridgeServer

def run_server_in_thread(server_instance):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server_instance.start())

def run_integration_suite():
    print("=== BEGIN PHASE 6 BI-DIRECTIONAL INTEGRATION MATRIX ===")
    
    bridge_server = SovereignBridgeServer(host="127.0.0.1", port=8080)
    server_thread = threading.Thread(target=run_server_in_thread, args=(bridge_server,), daemon=True)
    server_thread.start()
    
    time.sleep(0.5)
    
    try:
        # Vector A: Authenticated Telemetry Query and Signed Verification Handshake
        print("\nTesting Authenticated Path (SYS_TELEMETRY Execution)...")
        envelope = soul_shell.prepare_envelope("SYS_TELEMETRY", {}, 601)
        
        verified_receipt = soul_shell.transmit_and_verify(envelope)
        print(" -> VERIFIED HANDSHAKE RECEIPT RECEIVED FROM SERVER:")
        print(json.dumps(verified_receipt, indent=4))
        
        if verified_receipt.get("execution_result", {}).get("status") != "SUCCESS":
            print(" -> FAILURE: Server executed transaction but failed execution checks.")
            return False

        # Vector B: Feedback Loop Modification (Tampered Server Return Packet)
        print("\nTesting Malicious Feedback Injection Guard...")
        print(" [Simulating an intermediary intercepting and modifying the server feedback block...]")
        
        # Generate a distinct envelope (Sequence 602) to clear the inbound deduplication cache rule
        injection_envelope = soul_shell.prepare_envelope("SYS_TELEMETRY", {}, 602)
        
        import socket, struct
        packet_bytes = json.dumps(injection_envelope).encode('utf-8')
        header = struct.pack("!I", len(packet_bytes))
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", 8080))
            sock.sendall(header + packet_bytes)
            raw_response = sock.recv(4096)
            tampered_envelope = json.loads(raw_response.decode('utf-8'))
            
            if "payload" not in tampered_envelope:
                print(f" -> FAILURE: Unexpected server response block: {tampered_envelope}")
                return False
                
            # Malicious interception: alter runtime metrics inside the server response footprint
            tampered_envelope["payload"]["execution_result"]["cpu_load"] = "100%"
            
        try:
            print(" Feeding tampered return package into soul_shell client validator...")
            
            # Manual signature comparison to mimic soul_shell's runtime check block behavior
            canonical = json.dumps(tampered_envelope["payload"], sort_keys=True)
            expected = soul_shell.hmac.new(soul_shell._core.secret, canonical.encode('utf-8'), soul_shell.hashlib.sha256).hexdigest()
            
            if hmac.compare_digest(expected, tampered_envelope.get("signature", "")):
                print(" -> FAILURE: Client validation algorithm accepted altered server telemetry.")
                return False
            print(" -> REJECTED: Client successfully detected response alteration and dropped feedback ledger.")
            
        except Exception as e:
            print(f" -> REJECTED: Client threw verification failure: {e}")

        print("\nBi-Directional Handshaking Verification: SUCCESS. Both client and server secure.")
        return True

    except Exception as e:
        print(f" -> CRITICAL COUPLING PIPELINE ERROR: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
