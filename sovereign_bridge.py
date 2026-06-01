import json
import logging
import asyncio
import struct
import time
import hmac
import hashlib
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
        logging.info(f"[{self.node_id}] Client runtime connected. Performing encrypted DH setup...")
        try:
            handshake_packet = {
                "node_id": self.node_id,
                "dh_public": self._core.dh_public,
                "status": "AWAITING_DH_EXCHANGE"
            }
            writer.write(json.dumps(handshake_packet).encode('utf-8') + b"\n")
            await writer.drain()
            
            client_packet_bytes = await reader.readline()
            client_packet = json.loads(client_packet_bytes.decode('utf-8'))
            client_public = int(client_packet.get("dh_public", 0))
            
            self._core.compute_shared_session_secret(client_public)
            
            # Read length-prefixed encrypted wire transmission block
            header = await reader.readexactly(4)
            if header:
                payload_length = struct.unpack("!I", header)[0]
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                logging.info(f"[{self.node_id}] Ciphertext packet arrived. Running MAC authentication check...")
                
                validation_result = self._core.process_message(envelope)
                if validation_result.get("status") != "ALIGNED":
                    writer.write(json.dumps({"status": "REJECTED", "error": "Signature failure."}).encode('utf-8'))
                    return
                
                # Decrypt wire contents down to standard readable structures safely
                decrypted_payload = self._core.decrypt_payload(envelope.get("encrypted_data"))
                logging.info(f"[{self.node_id}] Decryption successful. Action command parsed: {decrypted_payload.get('command_id')}")
                
                response_payload = {
                    "executed_at": self.node_id,
                    "status": "SUCCESS",
                    "timestamp": time.time(),
                    "secret_telemetry_echo": "CONFIDENTIAL_METRICS_CLEAR_CHANNEL_SHIELDED"
                }
                
                # Encrypt response block before pushing back to the socket pipeline
                encrypted_response_data = self._core.encrypt_payload(response_payload)
                canonical_resp_str = json.dumps(encrypted_response_data, sort_keys=True)
                response_signature = hmac.new(self._core.active_session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest()
                
                server_envelope = {
                    "version": "1.0",
                    "signature": response_signature,
                    "encrypted_data": encrypted_response_data
                }
                writer.write(json.dumps(server_envelope).encode('utf-8'))
                await writer.drain()
                logging.info(f"[{self.node_id}] Outbound transaction encrypted and returned cleanly.")
                
        except Exception as e:
            logging.error(f"[{self.node_id}] Encrypted processing loop error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Encrypted Server [{self.node_id}] deployed on port {self.port}")
        async with self.server:
            await self.server.serve_forever()
