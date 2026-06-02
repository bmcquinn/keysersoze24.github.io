import sys
import time
import json
from soul_shell import SecureSessionChannel

def launch_panel():
    print("====================================================")
    print("      SOVEREIGN MESH OPERATOR ADMINISTRATIVE PANEL   ")
    print("====================================================")
    print(" Secure Channel Status: BURST MODE (DH / CTR / FEC) ")
    print(" Available Nodes: node_alpha                        ")
    print(" Commands: PING, SYS_TELEMETRY, HELP, EXIT          \n")

    gateway_host = "127.0.0.1"
    gateway_port = 9090

    while True:
        try:
            user_input = input("omni-operator> ").strip()
            if not user_input:
                continue

            parts = user_input.split(maxsplit=2)
            target_node = parts[0]

            if target_node.upper() == "EXIT":
                print("[*] Terminating operator session framework. Goodbye.")
                break

            if target_node.upper() == "HELP":
                print("\nFormat: [target_node_id] [command_id]")
                print("Example: node_alpha SYS_TELEMETRY\n")
                continue

            if len(parts) < 2:
                print("[-] Invalid syntax. Usage: [target_node_id] [command_id]")
                continue

            command_id = parts[1].upper()
            
            print(f"[*] Initializing ephemeral tunnel sequence to gateway port {gateway_port}...")
            
            # Burst Execution Vector: Instantiate fresh single-use dynamic session keys per transmission enter click
            channel = SecureSessionChannel(host=gateway_host, port=gateway_port)
            channel.connect_and_handshake()
            
            print(f"[*] Transmitting {command_id} over hardened, padded error-healing layer...")
            response = channel.transmit_command_with_noise(command_id, inject_error=False)
            
            print(f"[+] Response received from {target_node}:")
            print(json.dumps(response, indent=4))
            print("")
            
            # Gracefully clear local session key rings from memory cache footprints
            channel.close()

        except KeyboardInterrupt:
            print("\n[*] Intercepted termination signal. Exiting.")
            break
        except Exception as e:
            print(f"[-] Execution transaction failure across line: {e}\n")

if __name__ == "__main__":
    launch_panel()
