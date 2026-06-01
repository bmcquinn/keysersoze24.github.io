import json
import logging
import asyncio
import struct
import time
import secrets
from omni_core import OmniCoreProtocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

class SovereignBridgeServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=f"core_via_tcp_{port}")
        self.server = None

    def _local_execute(self, command_id: str, params: dict) -> dict:
        if command_id == "SYS_TELEMETRY":
            return {"status": "SUCCESS", "cpu_load": "4%", "memory_available": "15.1GB", "integrity": "NOMINAL"}
        return {"status": "UNKNOWN_COMMAND"}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logging.info("New inbound network socket connection established on boundary.")
        try:
            # 1. Generate unique random session initialization salt block
            session_salt = secrets.token_hex(16)
            handshake_packet = {"handshake_salt": session_salt, "status": "INIT_KEY_ROTATION"}
            
            # Send cleartext hello negotiation data first
            writer.write(json.dumps(handshake_packet).encode('utf-8') + b"\n")
            await writer.drain()
            
            # 2. Derive rolling transaction session key from master root
            self._core.derive_session_key(session_salt)
            
            while True:
                header = await reader.readexactly(4)
                if not header:
                    break
                
                payload_length = struct.unpack("!I", header)[0]
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                logging.info("Received network packet. Running dynamic signature validation...")
                
                validation_result = self._core.process_message(envelope)
                if validation_result.get("status") != "ALIGNED":
                    response = {"status": "REJECTED", "error": validation_result.get("error")}
                    writer.write(json.dumps(response).encode('utf-8'))
                    await writer.drain()
                    break
                
                incoming_payload = envelope.get("payload", {})
                execution_output = self._local_execute(incoming_payload.get("command_id"), incoming_payload.get("params", {}))
                
                response_payload = {
                    "origin_node": f"bridge_server_{self.port}",
                    "execution_result": execution_output,
                    "timestamp": time.time(),
                    "echo_sequence": incoming_payload.get("sequence", 0)
                }
                
                # Sign response utilizing the exact same dynamic session key layer
                canonical_response = json.dumps(response_payload, sort_keys=True)
                response_signature = self._core.generate_payload_signature(canonical_response)
                
                server_envelope = {
                    "version": "1.0",
                    "signature": response_signature,
                    "payload": response_payload
                }
                
                writer.write(json.dumps(server_envelope).encode('utf-8'))
                await writer.drain()
                logging.info("Execution complete. Ephemeral signed response dispatched.")
                
        except asyncio.IncompleteReadError:
            logging.info("Client disconnected from socket stream gracefully.")
        except Exception as e:
            logging.error(f"Transport boundary exception caught: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign TCP Bridge active with Key Rotation on tcp://{self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()
