import json
import logging
import asyncio
import struct
import time
import secrets
import socket
from omni_core import OmniCoreProtocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-MESH] - %(levelname)s - %(message)s')

NODE_ROUTING_TABLE = {
    "node_alpha": {"host": "127.0.0.1", "port": 8080},
    "node_beta":  {"host": "127.0.0.1", "port": 8081}
}

class SovereignBridgeServer:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 8080):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=f"core_via_{node_id}")
        self.server = None

    def _local_execute(self, command_id: str, params: dict) -> dict:
        return {
            "status": "SUCCESS",
            "executed_at_node": self.node_id,
            "timestamp": time.time(),
            "telemetry": {"integrity": "NOMINAL", "active_port": self.port}
        }

    def _forward_to_peer(self, target_node: str, envelope: dict) -> dict:
        peer_config = NODE_ROUTING_TABLE.get(target_node)
        if not peer_config:
            return {"status": "MESH_ERROR", "error": f"Target destination {target_node} not found."}
            
        logging.info(f"NODE DISPATCH: Forwarding signed packet across mesh to {target_node} on port {peer_config['port']}")
        
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((peer_config["host"], peer_config["port"]))
                
                # Consume and clear cleartext hello handshake salt line from target node cleanly
                file_obj = sock.makefile('r', encoding='utf-8')
                _ = file_obj.readline() 
                
                # Forward the original client envelope with zero modification over the wire proxy
                packet_bytes = json.dumps(envelope).encode('utf-8')
                header = struct.pack("!I", len(packet_bytes))
                sock.sendall(header + packet_bytes)
                
                response_bytes = sock.recv(4096)
                return json.loads(response_bytes.decode('utf-8'))
        except Exception as e:
            return {"status": "MESH_TRANSPORT_FAILURE", "error": str(e)}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logging.info(f"[{self.node_id}] Inbound mesh socket connection established.")
        try:
            session_salt = secrets.token_hex(16)
            handshake_packet = {"handshake_salt": session_salt, "status": "INIT_KEY_ROTATION", "node": self.node_id}
            writer.write(json.dumps(handshake_packet).encode('utf-8') + b"\n")
            await writer.drain()
            
            self._core.derive_session_key(session_salt)
            
            while True:
                header = await reader.readexactly(4)
                if not header:
                    break
                
                payload_length = struct.unpack("!I", header)[0]
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                incoming_payload = envelope.get("payload", {})
                target_node = incoming_payload.get("target_node_id")
                
                logging.info(f"[{self.node_id}] Inbound packet parsed. Evaluating destination node: {target_node}")
                
                # MESH PROXY CHECK: Forward if designated for downstream nodes
                if target_node and target_node != self.node_id:
                    mesh_response = self._forward_to_peer(target_node, envelope)
                    writer.write(json.dumps(mesh_response).encode('utf-8'))
                    await writer.drain()
                    break
                
                # Direct Path Check: process and evaluate locally if target node home is hit
                validation_result = self._core.process_message(envelope)
                if validation_result.get("status") != "ALIGNED":
                    response = {"status": "REJECTED", "error": validation_result.get("error")}
                    writer.write(json.dumps(response).encode('utf-8'))
                    await writer.drain()
                    break
                
                execution_output = self._local_execute(incoming_payload.get("command_id"), incoming_payload.get("params", {}))
                
                response_payload = {
                    "origin_node": self.node_id,
                    "execution_result": execution_output,
                    "timestamp": time.time(),
                    "echo_sequence": incoming_payload.get("sequence", 0)
                }
                
                # Sign responses utilizing active channel secret layers
                canonical_response = json.dumps(response_payload, sort_keys=True)
                response_signature = self._core.generate_payload_signature(canonical_response)
                
                server_envelope = {
                    "version": "1.0",
                    "signature": response_signature,
                    "payload": response_payload
                }
                
                writer.write(json.dumps(server_envelope).encode('utf-8'))
                await writer.drain()
                logging.info(f"[{self.node_id}] Transaction processed locally. Response dispatched.")
                
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logging.error(f"[{self.node_id}] Exception inside mesh processing line: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Mesh Node [{self.node_id}] active and online on tcp://{self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()
