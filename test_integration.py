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
    print("=== BEGIN PHASE 13 FEC FAULT-TOLERANCE INTEGRATION MATRIX ===")
    
    server = SovereignBridgeServer(node_id="fec_healed_node_omega", host="127.0.0.1", port=8085)
    t = threading.Thread(target=run_server, args=(server,), daemon=True)
    t.start()
    
    time.sleep(0.5)
    
    try:
        channel = soul_shell.SecureSessionChannel(host="127.0.0.1", port=8085)
        channel.connect_and_handshake()
        
        # Test Vector A: Nominal Transmission
        print("\nSending Payload Over Clean Path Sequence...")
        res_one = channel.transmit_command_with_noise("CLEAN_STREAM_VERIFY", inject_error=False)
        print(f" -> RESPONSE 1: {res_one.get('status')}")
        
        # Test Vector B: Damaged Wire Line Noise (Flipping bit boundaries mid-transit)
        print("\nSending Payload Over Damaged Wire Line Noise Path Sequence...")
        print(" [Simulating a single-bit flip on the socket buffer interface...]")
        res_two = channel.transmit_command_with_noise("HEALED_STREAM_VERIFY", inject_error=True)
        print(f" -> RESPONSE 2: {res_two.get('status')}")
        
        channel.close()
        
        if res_one.get("status") == "SUCCESS" and res_two.get("status") == "SUCCESS":
            print("\nForward Error Correction Resiliency: SUCCESS. Line noise auto-healed locally.")
            return True
        return False
        
    except Exception as e:
        print(f" -> FEC INTEGRATION RUNNER DISALIGNMENT: {e}")
        return False

if __name__ == "__main__":
    success = run_integration_suite()
    sys.exit(0 if success else 1)
