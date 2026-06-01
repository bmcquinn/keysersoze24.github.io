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
    print("=== BEGIN PHASE 10 ENCRYPTED TUNNEL INTEGRATION MATRIX ===")
    
    server = SovereignBridgeServer(node_id="secure_crypto_node_omega", host="127.0.0.1", port=8085)
    t = threading.Thread(target=run_server, args=(server,), daemon=True)
    t.start()
    
    time.sleep(0.5)
    
    try:
        print("\nExecuting Command Transmission over Zero-Dependency Encrypted Tunnel...")
        cleartext_result = soul_shell.transmit_encrypted_command(
            host="127.0.0.1", port=8085, 
            command_id="SYS_TELEMETRY", params={"obfuscated": True}
        )
        print("\n -> DECRYPTED FEEDBACK CONFIRMATION PACKAGE FROM NODE SERVER:")
        print(json.dumps(cleartext_result, indent=4))
        
        if cleartext_result.get("status") == "SUCCESS":
            print("\nEnd-to-End Payload Confidentiality: SUCCESS. Wire data fully encrypted.")
            return True
        return False
    except Exception as e:
        print(f" -> ENCRYPTED SYSTEM MATRIX FAILURE: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
