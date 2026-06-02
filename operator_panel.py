import sys
import time
import json
from soul_shell import SecureSessionChannel

def launch_panel():
    print("====================================================")
    print("      SOVEREIGN MESH OPERATOR ADMINISTRATIVE PANEL   ")
    print("====================================================")
    print(" Secure Channel Status: BURST MODE (HA FAILOVER)    ")
    print(" Active Topology Pool: node_alpha, node_gamma       ")
    print(" Commands: PING, SYS_TELEMETRY, HELP, EXIT          \n")

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

            if target_node.upper() == "HELP":
                print("\nFormat: [target_node_id] [command_id]")
                print("Example: node_beta SYS_TELEMETRY\n")
                continue

            if len(parts) < 2:
                print("[-] Invalid syntax. Usage: [target_node_id] [command_id]")
                continue

            command_id = parts[1].upper()
            
            channel = SecureSessionChannel()
            channel.connect_and_handshake_resilient()
            
            print(f"[*] Dispatching {command_id} targeting [{target_node}] via gateway line [{channel.active_gateway}]...")
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
