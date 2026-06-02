import asyncio
import os
import sys
import threading
import time

sys.path.append(os.getcwd())

if not os.environ.get("OMNI_CORE_SECRET"):
    os.environ["OMNI_CORE_SECRET"] = "DefaultTemporaryMasterKeyRingToken101"

from sovereign_bridge import SovereignBridgeServer

def start_async_daemon():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Pivot host destination to port 9090
    server = SovereignBridgeServer(node_id="node_alpha", host="127.0.0.1", port=9090)
    loop.run_until_complete(server.start())

if __name__ == "__main__":
    print("[*] Spawning Sovereign Mesh Gateway Node Background Daemon...")
    daemon_thread = threading.Thread(target=start_async_daemon, daemon=True)
    daemon_thread.start()
    
    print("[+] Edge Gateway Online on tcp://127.0.0.1:9090. Press Ctrl+C to terminate server container.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down gateway node listener container framework.")
