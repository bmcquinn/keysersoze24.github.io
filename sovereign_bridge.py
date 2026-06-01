import json
import logging
import asyncio
import struct
import time
import hmac
import hashlib
from omni_core import OmniCoreProtocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

class BridgeRoutingError(Exception):
    """Raised when network data transport fails cryptographic validation or framing requirements."""
    pass

class SovereignBridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=f"core_via_tcp_{port}")
        self.server = None

    def _local_execute(self, command_id: str, params: dict) -> dict:
        """Simulates secure localized node execution handlers based on routing IDs."""
        if command_id == "SYS_TELEMETRY":
            return {"status": "SUCCESS", "cpu_load": "12%", "memory_available": "14.2GB", "integrity": "NOMINAL"}
        elif command_id == "CORE_PING":
            return {"status": "SUCCESS", "latency": "0.4ms", "state": "ONLINE"}
        else:
            return {"status": "UNKNOWN_COMMAND", "error": f"No dispatch mapping for {command_id}"}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logging.info("New inbound network socket connection established on boundary.")
        try:
            while True:
                header = await reader.readexactly(4)
                if not header:
                    break
                
                payload_length = struct.unpack("!I", header)[0]
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                logging.info(f"Received network packet ({payload_length} bytes). Running validation...")
                
                # Verify incoming envelope path
                validation_result = self._core.process_message(envelope)
                if validation_result.get("status") != "ALIGNED":
                    response = {"status": "REJECTED", "error": validation_result.get("error")}
                    writer.write(json.dumps(response).encode('utf-8'))
                    await writer.drain()
                    raise BridgeRoutingError(f"Network Packet Dropped: {validation_result.get('error')}")
                
                # Fetch payload instruction metadata
                incoming_payload = envelope.get("payload", {})
                command_id = incoming_payload.get("command_id")
                params = incoming_payload.get("params", {})
                
                # Core Handshake: Dispatch task and execute locally
                execution_output = self._local_execute(command_id, params)
                
                # Structure the signed outbound feedback response block
                response_payload = {
                    "origin_node": f"bridge_server_{self.port}",
                    "execution_result": execution_output,
                    "timestamp": time.time(),
                    "echo_sequence": incoming_payload.get("sequence", 0)
                }
                
                # Serialize response and generate server-side validation token
                canonical_response = json.dumps(response_payload, sort_keys=True)
                response_signature = hmac.new(self._core.secret, canonical_response.encode('utf-8'), hashlib.sha256).hexdigest()
                
                server_envelope = {
                    "version": "1.0",
                    "signature": response_signature,
                    "payload": response_payload
                }
                
                # Write back signed envelope over wire
                response_bytes = json.dumps(server_envelope).encode('utf-8')
                writer.write(response_bytes)
                await writer.drain()
                logging.info("Execution complete. Signed receipt feedback pushed down-stream.")
                
        except asyncio.IncompleteReadError:
            logging.info("Client disconnected from socket stream gracefully.")
        except Exception as e:
            logging.error(f"Transport boundary exception caught: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign TCP Bridge active and listening on tcp://{self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()
            
    def stop(self) -> None:
        if self.server:
            self.server.close()
