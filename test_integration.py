import sys
import time
import asyncio
import threading
import json
import soul_shell
from sovereign_bridge import SovereignBridgeServer

def run_server(server_instance):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server_instance.start())

def run_integration_suite():
    print("=== BEGIN PHASE 11 IN-BAND RE-KEYING INTEGRATION MATRIX ===")
    
    server = SovereignBridgeServer(node_id="lifecycle_node_omega", host="127.0.0.1", port=8085)
    t = threading.Thread(target=run_server, args=(server,), daemon=True)
    t.start()
    
    time.sleep(0.5)
    
    try:
        print("\nOpening Persistent Socket Session Channel Tunnel...")
        channel = soul_shell.SecureSessionChannel(host="127.0.0.1", port=8085)
        channel.connect_and_handshake()
        
        # Packet iteration 1 (Nominal Key Utilization)
        print("\nFiring Transaction Packet 1 [Nominal Status Expectation]...")
        res_one = channel.transmit_command("AUTOMATION_TASK_A", {"index": 1})
        print(f" -> RESPONSE 1: Lifecycle State = {res_one.get('lifecycle_state')}")
        
        # Packet iteration 2 (Triggers Threshold Rule on the Core Boundary)
        print("\nFiring Transaction Packet 2 [Key Rotation Threshold Hit]...")
        res_two = channel.transmit_command("AUTOMATION_TASK_B", {"index": 2})
        print(f" -> RESPONSE 2: Lifecycle State = {res_two.get('lifecycle_state')}")
        if res_two.get("lifecycle_state") != "ROTATE_PENDING":
            print(" -> FAILURE: Core failed to intercept and flag rotation thresholds.")
            return False
            
        # Packet iteration 3 (Must validate perfectly under the newly negotiated Key_2 validation ring)
        print("\nFiring Transaction Packet 3 [Validating Fresh Post-Rotation Key Ring Execution]...")
        res_three = channel.transmit_command("AUTOMATION_TASK_C", {"index": 3})
        print(f" -> RESPONSE 3: Lifecycle State = {res_three.get('lifecycle_state')}")
        
        channel.close()
        
        if res_three.get("status") == "SUCCESS":
            print("\nIn-Band Symmetric Key Lifecycle Rotation: SUCCESS. Channel re-keyed seamlessly.")
            return True
        return False
        
    except Exception as e:
        print(f" -> LIFECYCLE RE-KEY TESTING FAILURE: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
