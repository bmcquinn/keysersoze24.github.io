import asyncio
import json
import socket
import time

async def simulate_single_estimator(worker_id: int, port: int = 8999):
    """Simulates a rapid, concurrent field data submission over the network bridge loop."""
    payload = {
        "type": "PII_SECURE_VAULT",
        "meta": {
            "loss_date": "2026-05-15",
            "storm_type": "High Wind Event",
            "roof_squares": 24.0 + (worker_id * 1.5),
            "latitude": 39.0997,
            "longitude": -94.5786
        },
        "confidential_payload": {
            "policyholder_name": f"Test Worker Holder {worker_id}",
            "policy_number": f"POL-STRESS-{worker_id:04d}"
        }
    }
    
    try:
        # Establish low-level non-blocking stream connections
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        
        writer.write(json.dumps(payload).encode('utf-8'))
        await writer.drain()
        
        raw_resp = await reader.read(4096)
        resp = json.loads(raw_resp.decode('utf-8'))
        
        writer.close()
        await writer.wait_closed()
        return True
    except Exception as e:
        print(f"[-] Worker [{worker_id}] Transaction Failure: {e}")
        return False

async def execute_load_test(total_bursts: int = 50):
    print(f"[*] Initializing production stress test harness. Dispatching {total_bursts} concurrent worker bursts...")
    start_time = time.time()
    
    # Pack tasks into a concurrent execution group
    tasks = [simulate_single_estimator(i) for i in range(total_bursts)]
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    elapsed = end_time - start_time
    success_count = sum(1 for r in results if r)
    
    print("\n==========================================================================")
    print("                    AGENTIC SERVICE STRESS TEST RESULTS                   ")
    print("==========================================================================")
    print(f"Total Transactions Dispatched : {total_bursts}")
    print(f"Successful Pipe Resolutions   : {success_count}")
    print(f"Failed Connections/Timeouts   : {total_bursts - success_count}")
    print(f"Gross Benchmarking Duration   : {elapsed:.4f} seconds")
    print(f"System Operational Throughput : {success_count / elapsed:.2f} transactions/sec")
    print("==========================================================================")

if __name__ == "__main__":
    asyncio.run(execute_load_test(50))
