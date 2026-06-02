import sys
import time
import json
from soul_shell import SecureSessionChannel
from mesh_tunnel import MeshTunnelInterface

def launch_panel():
    print("====================================================")
    print("      SOVEREIGN MESH OPERATOR ADMINISTRATIVE PANEL   ")
    print("====================================================")
    print(" Secure Channel Status: BURST MODE (TUNNEL ACTIVE)  ")
    print(" Active Topology Pool: node_alpha, node_gamma       ")
    print(" Commands: PING, SYS_TELEMETRY, ROUTE_TUNNEL, EXIT  \n")

    # Initialize Virtual Layer 3 Interface Config Parameters Locally
    v_tun = MeshTunnelInterface(interface_name="sov_tun0", virtual_ip="10.0.14.1")

    while True:
        try:
            user_input = input("omni-operator> ").strip()
            if not user_input:
                continue

            parts = user_input.split(maxsplit=2)
            target_node = parts[0].lower()

            if target_node.upper() == "EXIT":
                print("[*] Terminating operator session framework. Goodbye.")
                break

            if len(parts) < 2:
                print("[-] Invalid syntax. Usage: [target_node_id] [command_id]")
                continue

            command_id = parts[1].upper()
            
            channel = SecureSessionChannel()
            channel.connect_and_handshake_resilient()
            
            if command_id == "ROUTE_TUNNEL":
                print("[*] Intercepting raw application packet traffic stream...")
                simulated_payload = b"GET /index.html HTTP/1.1\r\nHost: mesh.internal\r\n\r\n"
                # Package raw simulated data through the virtual interface core
                raw_frame = v_tun.encapsulate_ip_packet(destination_ip="10.0.14.2", payload_bytes=simulated_payload)
                
                print(f"[*] Dispatching {len(raw_frame)} bytes of encapsulated tunnel traffic through [{channel.active_gateway}]...")
                response = channel.transmit_command_routed(target_node=target_node, command_id=f"TUNNEL_DATA:{raw_frame.hex()}")
            else:
                response = channel.transmit_command_routed(target_node=target_node, command_id=command_id)
            
            print(f"[+] Response received from [{target_node}]:")
            print(json.dumps(response, indent=4))
            print("")
            
            channel.close()

        except KeyboardInterrupt:
            print("\n[*] Intercepted termination signal. Exiting.")
            break
        except Exception as e:
            print(f"[-] Execution transaction failure across line: {e}\n")

if __name__ == "__main__":
    launch_panel()
