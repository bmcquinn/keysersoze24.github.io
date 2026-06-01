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
        logging.info(f"[{self.node_id}] Direct stream session established.")
        try:
            # 1. Primary Initial Handshake Phase
            handshake_packet = {"dh_public": self._core.dh_public, "status": "AWAITING_DH_EXCHANGE"}
            writer.write(json.dumps(handshake_packet).encode('utf-8') + b"\n")
            await writer.drain()
            
            client_packet_bytes = await reader.readline()
            client_packet = json.loads(client_packet_bytes.decode('utf-8'))
            self._core.compute_shared_session_secret(int(client_packet.get("dh_public")))
            
            # 2. Main Processing Loop Over the Persistent Channel Stream
            while True:
                header = await reader.readexactly(4)
                if not header:
                    break
                
                payload_length = struct.unpack("!I", header)[0]
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                validation_result = self._core.process_message(envelope)
                if validation_result.get("status") != "ALIGNED":
                    break
                
                decrypted_payload = self._core.decrypt_payload(envelope.get("encrypted_data"))
                logging.info(f"[{self.node_id}] Handled payload command: {decrypted_payload.get('command_id')}")
                
                # Check metrics lifecycle rules to flag an incoming rotation state
                rekey_required = self._core.requires_rekey(max_messages=2)
                
                response_payload = {
                    "executed_at": self.node_id,
                    "status": "SUCCESS",
                    "timestamp": time.time(),
                    "lifecycle_state": "ROTATE_PENDING" if rekey_required else "NOMINAL"
                }
                
                # If a re-keying rotation is required, generate fresh public primitives to append down-stream
                if rekey_required:
                    self._core.cycle_dh_keypair()
                    response_payload["next_dh_public"] = self._core.dh_public
                
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
                
                # 3. Secure Interception: Pause application data parsing to process the new secret exchange
                if rekey_required:
                    logging.info(f"[{self.node_id}] Synchronizing in-band key rotation handshakes...")
                    client_rekey_bytes = await reader.readline()
                    client_rekey_packet = json.loads(client_rekey_bytes.decode('utf-8'))
                    
                    # Compute and register the next lifecycle validation ring key
                    self._core.compute_shared_session_secret(int(client_rekey_packet.get("dh_public")))
                    logging.info(f"[{self.node_id}] In-band re-key transaction execution successful.")
                
        except asyncio.IncompleteReadError:
            logging.info(f"[{self.node_id}] Session channel closed gracefully.")
        except Exception as e:
            logging.error(f"[{self.node_id}] Stream engine boundary failure: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Lifecycle Server [{self.node_id}] bound to port {self.port}")
        async with self.server:
            await self.server.serve_forever()
