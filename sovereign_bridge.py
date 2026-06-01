import json
import logging
import asyncio
import struct
import time
from omni_core import OmniCoreProtocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

class SovereignBridgeServer:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 8085):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=node_id)
        self.server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logging.info(f"[{self.node_id}] Client connected. Initiating Diffie-Hellman handshake...")
        try:
            # 1. Dispatch our public exchange token (g^b mod p)
            handshake_packet = {
                "node_id": self.node_id,
                "dh_public": self._core.dh_public,
                "status": "AWAITING_DH_EXCHANGE"
            }
            writer.write(json.dumps(handshake_packet).encode('utf-8') + b"\n")
            await writer.drain()
            
            # 2. Ingest the client's public exchange token (g^a mod p)
            client_packet_bytes = await reader.readline()
            client_packet = json.loads(client_packet_bytes.decode('utf-8'))
            client_public = int(client_packet.get("dh_public", 0))
            
            # 3. Mathematically compute the identical shared key block locally
            self._core.compute_shared_session_secret(client_public)
            
            # 4. Ingest and validate standard application packet traffic
            header = await reader.readexactly(4)
            if header:
                payload_length = struct.unpack("!I", header)[0]
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                validation_result = self._core.process_message(envelope)
                if validation_result.get("status") != "ALIGNED":
                    writer.write(json.dumps({"status": "REJECTED"}).encode('utf-8'))
                    return
                
                response_payload = {
                    "executed_at": self.node_id,
                    "status": "SUCCESS",
                    "timestamp": time.time()
                }
                
                canonical_response = json.dumps(response_payload, sort_keys=True)
                server_envelope = {
                    "version": "1.0",
                    "signature": self._core.generate_payload_signature(canonical_response),
                    "payload": response_payload
                }
                writer.write(json.dumps(server_envelope).encode('utf-8'))
                await writer.drain()
                
        except Exception as e:
            logging.error(f"[{self.node_id}] Handshake failed: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign DH Server [{self.node_id}] listening on port {self.port}")
        async with self.server:
            await self.server.serve_forever()
