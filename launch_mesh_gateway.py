import asyncio
import os
import sys
import threading
import time

sys.path.append(os.getcwd())

if not os.environ.get("OMNI_CORE_SECRET"):
    os.environ["OMNI_CORE_SECRET"] = "DefaultTemporaryMasterKeyRingToken101"

from sovereign_bridge import SovereignBridgeServer

def boot_node_alpha():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = SovereignBridgeServer(node_id="node_alpha", host="127.0.0.1", port=9090)
    loop.run_until_complete(server.start())

def boot_node_beta():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = SovereignBridgeServer(node_id="node_beta", host="127.0.0.1", port=9091)
    loop.run_until_complete(server.start())

def boot_node_gamma():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = SovereignBridgeServer(node_id="node_gamma", host="127.0.0.1", port=9092)
    loop.run_until_complete(server.start())

if __name__ == "__main__":
    print("[*] Launching High-Availability Multi-Node Sovereign Mesh Topologies...")
    
    t1 = threading.Thread(target=boot_node_alpha, daemon=True)
    t2 = threading.Thread(target=boot_node_beta, daemon=True)
    t3 = threading.Thread(target=boot_node_gamma, daemon=True)
    
    t1.start()
    t2.start()
    t3.start()
    
    print("[+] Primary Edge Gateway [node_alpha] deployed on port 9090.")
    print("[+] Hidden Target Mesh Node [node_beta] deployed on port 9091.")
    print("[+] Backup Hot-Standby Gateway [node_gamma] deployed on port 9092.")
    print("[*] Systems armed. Press Ctrl+C to stop container blocks.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Tearing down multi-node process mesh environment components safely.")
