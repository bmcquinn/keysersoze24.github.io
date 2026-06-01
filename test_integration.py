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
    print("=== BEGIN PHASE 9 DH HANDSHAKE INTEGRATION MATRIX ===")
    
    server = SovereignBridgeServer(node_id="secure_dh_node_omega", host="127.0.0.1", port=8085)
    t = threading.Thread(target=run_server, args=(server,), daemon=True)
    t.start()
    
    time.sleep(0.5)
    
    try:
        print("\nInitiating Modular Arithmetic Diffie-Hellman Socket Handshake...")
        result = soul_shell.transmit_dh_handshake(
            host="127.0.0.1", port=8085, 
            command_id="DH_SECURE_TUNNEL", params={"native_math": True}
        )
        print("\n -> TUNNEL TRANSACTION CONFIRMATION:")
        print(json.dumps(result, indent=4))
        
        if result.get("payload", {}).get("status") == "SUCCESS":
            print("\nZero-Dependency Perfect Forward Secrecy: SUCCESS. Dynamic keys negotiated natively.")
            return True
        return False
    except Exception as e:
        print(f" -> INTEGRATION MATRIX REJECTED: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
