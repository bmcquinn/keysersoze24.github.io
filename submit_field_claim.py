import socket
import json
import sys

def transmit_claim_to_bridge(claim_payload: dict, port: int = 8999):
    """Establishes a socket connection to the local bridge to dispatch the claim."""
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("127.0.0.1", port))
        
        # Serialize and send the claim transaction data string
        client_socket.sendall(json.dumps(claim_payload).encode('utf-8'))
        
        # Read back the agent routing decision response
        response = client_socket.recv(1024).decode('utf-8')
        print(f"\n[+] Bridge Response Received:\n{json.dumps(json.loads(response), indent=4)}")
        
        client_socket.close()
    except ConnectionRefusedError:
        print("[-] Error: The Core Agent Bridge daemon is not running on port 8999.")
    except Exception as e:
        print(f"[-] Transmission exception encountered: {e}")

if __name__ == "__main__":
    print("=== STORM RESTORATION FIELD INGESTION CLIENT ===")
    
    # Mocking an intense field estimate scenario (e.g., Catastrophic Hail Damage)
    sample_claim = {
        "type": "PII_SECURE_VAULT",
        "meta": {
            "loss_date": "2026-05-28",
            "storm_type": "Hail & High Winds",
            "roof_squares": 32.5,
            "tarping_required": True
        },
        "confidential_payload": {
            "policyholder_name": "Alice Smith",
            "policy_number": "POL-994821-X7",
            "deductible_amount": 2500.00,
            "homeowner_phone": "555-019-2834",
            "estimated_payout_target": 18450.00
        }
    }
    
    print("[*] Simulating storm estimator data dump into the local pipeline...")
    transmit_claim_to_bridge(sample_claim)
