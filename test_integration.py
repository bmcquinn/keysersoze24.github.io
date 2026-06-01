import os
import sys
import time
import asyncio
import threading
import json
import socket
import struct

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
    print("=== BEGIN PHASE 7 KEY ROTATION INTEGRATION MATRIX ===")
    
    bridge_server = SovereignBridgeServer(host="127.0.0.1", port=8080)
    server_thread = threading.Thread(target=run_server_in_thread, args=(bridge_server,), daemon=True)
    server_thread.start()
    
    time.sleep(0.5)
    
    try:
        # Vector A: Valid Dynamic Session Key Handshake
        print("\nTesting Rolling Key Generation Execution Pathway...")
        verified_receipt = soul_shell.transmit_and_verify("SYS_TELEMETRY", {}, 701)
        print(" -> VERIFIED METRICS HANDSHAKE RETURNED FROM KEY ROTATION TUNNEL:")
        print(json.dumps(verified_receipt, indent=4))
        
        if verified_receipt.get("execution_result", {}).get("status") != "SUCCESS":
            return False

        # Vector B: Static Master Root Key Bypass Attempt (Malicious Packet Signature Failure)
        print("\nTesting Static Root Bypass Attack Vector...")
        print(" [Simulating client attempting to sign application traffic using the Master Root Secret directly...]")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect(("127.0.0.1", 8080))
            
            # Read and discard salt data block line to mimic simple connection bypass
            file_obj = sock.makefile('r', encoding='utf-8')
            _ = file_obj.readline()
            
            # Craft static signed bypass payload block packet structure layout manual
            payload = {"command_id": "SYS_TELEMETRY", "params": {}, "sequence": 702, "timestamp": time.time()}
            canonical = json.dumps(payload, sort_keys=True)
            
            # Sign directly with the master secret, bypassing the derived session key rule requirement
            invalid_root_sig = soul_shell.hmac.new(SECRET_KEY.encode('utf-8'), canonical.encode('utf-8'), soul_shell.hashlib.sha256).hexdigest()
            
            bypass_envelope = {"version": "1.0", "signature": invalid_root_sig, "payload": payload}
            packet_bytes = json.dumps(bypass_envelope).encode('utf-8')
            header = struct.pack("!I", len(packet_bytes))
            
            sock.sendall(header + packet_bytes)
            raw_response = sock.recv(1024)
            server_response = json.loads(raw_response.decode('utf-8'))
            
            print(f" -> SERVER RESPONSE: {server_response}")
            if server_response.get("status") == "REJECTED":
                print(" -> REJECTED: Server successfully caught and dropped static key signature exploit attempt.")
                print("\nDynamic Key Rotation Verification: SUCCESS. Master root secret fully shielded.")
                return True
            else:
                print(" -> FAILURE: Server accepted a payload signed with the master root key directly.")
                return False

    except Exception as e:
        print(f" -> CRITICAL INTERFACE ERROR: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
