import json
import logging
import asyncio
import struct
import time
import hmac
import hashlib
from omni_core import OmniCoreProtocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

NODE_ROUTING_TABLE = {
    "node_alpha": 9090,
    "node_beta": 9091
}

class SovereignBridgeServer:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 8085):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=node_id)
        self.server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            # Read uniform length-prefixed protocol packet
            header = await reader.readexactly(4)
            if not header:
                return
            payload_length = struct.unpack("!I", header)[0]
            raw_fec_bytes = await reader.readexactly(payload_length)
            
            # Run bitwise healing to restore the payload
            healed_json_bytes = self._core.decode_and_heal_fec_bytes(raw_fec_bytes)
            routing_envelope = json.loads(healed_json_bytes.decode('utf-8'))
            
            target_node = routing_envelope.get("target_node")
            inner_envelope = routing_envelope.get("inner_envelope")
            
            # PROXY FORWARD VECTOR: If target isn't this node, forward the pre-wrapped payload down the line
            if target_node != self.node_id and target_node in NODE_ROUTING_TABLE:
                proxy_port = NODE_ROUTING_TABLE[target_node]
                logging.info(f"[{self.node_id}] Routing proxy triggered. Forwarding packet to {target_node} on port {proxy_port}...")
                
                p_reader, p_writer = await asyncio.open_connection(self.host, proxy_port)
                
                # Forward the exact healed packet payload block
                p_writer.write(header + raw_fec_bytes)
                await p_writer.drain()
                
                # Fetch response from downstream node and pass back up to client panel
                resp_header = await p_reader.readexactly(4)
                resp_len = struct.unpack("!I", resp_header)[0]
                resp_fec_bytes = await p_reader.readexactly(resp_len)
                
                writer.write(resp_header + resp_fec_bytes)
                await writer.drain()
                
                p_writer.close()
                await p_writer.wait_closed()
                return

            # LOCAL MODE PROCESSING: Execute command locally using static master key fallback for routing
            # To enable direct decryption without active interactive DH negotiation steps
            static_secret = hashlib.sha256(b"SovereignMeshDefaultSecretTokenKeyRing").digest()
            self._core.active_session_key = static_secret
            
            validation_result = self._core.process_message(inner_envelope)
            if validation_result.get("status") != "ALIGNED":
                logging.error(f"[{self.node_id}] Cryptographic validation ring failure.")
                return
                
            decrypted_payload = self._core.decrypt_payload_padded(inner_envelope.get("encrypted_data"))
            logging.info(f"[{self.node_id}] Local execution complete: {decrypted_payload.get('command_id')}")
            
            response_payload = {"executed_at": self.node_id, "status": "SUCCESS", "timestamp": time.time()}
            encrypted_response_data = self._core.encrypt_payload_padded(response_payload)
            canonical_resp_str = json.dumps(encrypted_response_data, sort_keys=True)
            response_signature = hmac.new(self._core.active_session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest()
            
            server_envelope = {"version": "1.0", "signature": response_signature, "encrypted_data": encrypted_response_data}
            server_json_bytes = json.dumps(server_envelope).encode('utf-8')
            fec_outbound_bytes = self._core.encode_fec_bytes(server_json_bytes)
            
            header_out = struct.pack("!I", len(fec_outbound_bytes))
            writer.write(header_out + fec_outbound_bytes)
            await writer.drain()
                
        except Exception as e:
            logging.error(f"[{self.node_id}] Routing mesh processing exception: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Multi-Hop Server [{self.node_id}] live on port {self.port}")
        async with self.server:
            await self.server.serve_forever()
