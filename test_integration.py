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
from sovereign_bridge import SovereignBridgeServer

def boot_node_async(node_instance):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(node_instance.start())

def run_integration_suite():
    print("=== BEGIN PHASE 8 MULTI-NODE ROUTING MESH MATRIX ===")
    
    # 1. Instantiate multi-node structural mesh layout topology
    node_alpha = SovereignBridgeServer(node_id="node_alpha", host="127.0.0.1", port=8080)
    node_beta  = SovereignBridgeServer(node_id="node_beta", host="127.0.0.1", port=8081)
    
    thread_alpha = threading.Thread(target=boot_node_async, args=(node_alpha,), daemon=True)
    thread_beta  = threading.Thread(target=boot_node_async, args=(node_beta,), daemon=True)
    
    thread_alpha.start()
    thread_beta.start()
    
    # Settle multi-port bindings
    time.sleep(0.7)
    
    try:
        # Vector A: Standard Direct Node Delivery Action
        print("\nTesting Direct Route Path (Client -> Node Alpha)...")
        receipt_alpha = soul_shell.transmit_to_mesh_node(target_node_id="node_alpha", command_id="PING", params={}, sequence=801, gateway_port=8080)
        print(" -> RESPONSE FROM ALPHA GATEWAY:")
        print(json.dumps(receipt_alpha, indent=4))
        
        if receipt_alpha.get("execution_result", {}).get("executed_at_node") != "node_alpha":
            print(" -> FAILURE: Local node execution boundary mapping error.")
            return False

        # Vector B: Multi-Hop Transparent Routing Jump Action
        print("\nTesting Multi-Hop Mesh Routing Path (Client -> Node Alpha Gateway -> Peer Forward -> Node Beta)...")
        receipt_beta = soul_shell.transmit_to_mesh_node(target_node_id="node_beta", command_id="SYS_TELEMETRY", params={}, sequence=802, gateway_port=8080)
        print(" -> RESPONSE RETURNED VIA ROUTING HOP PATH:")
        print(json.dumps(receipt_beta, indent=4))
        
        target_node = receipt_beta.get("execution_result", {}).get("executed_at_node")
        if target_node == "node_beta":
            print("\nDecentralized Mesh Routing Verification: SUCCESS. Packets successfully scaled across network hops.")
            return True
        else:
            print(f" -> FAILURE: Network packet dropped or misrouted inside mesh switchboard loop. Found: {target_node}")
            return False

    except Exception as e:
        print(f" -> CRITICAL MESH ORCHESTRATION PIPELINE FAILURE: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
