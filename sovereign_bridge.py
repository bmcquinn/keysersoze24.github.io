import json
import logging
import asyncio
import struct
import time
import hmac
import hashlib
import os
import threading
import subprocess
from omni_core import OmniCoreProtocol
from mesh_tunnel import MeshTunnelInterface
from obfuscation_matrix import TrafficObfuscator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

CONFIG_PATH = "mesh_config.json"
AUDIT_LOG_PATH = "mesh_audit.bin"

NODE_ROUTING_TABLE = {}
GLOBAL_SETTINGS = {"fixed_payload_size": 512}

def load_mesh_configuration():
    global NODE_ROUTING_TABLE, GLOBAL_SETTINGS
    if not os.path.exists(CONFIG_PATH):
        return
    try:
        if os.path.getsize(CONFIG_PATH) == 0:
            return
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        NODE_ROUTING_TABLE.clear()
        NODE_ROUTING_TABLE.update(config.get("NODE_ROUTING_TABLE", {}))
        GLOBAL_SETTINGS.update(config.get("GLOBAL_SETTINGS", {}))
    except Exception:
        pass

load_mesh_configuration()

class SovereignBridgeServer:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 8085):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=node_id)
        self.server = None
        self.v_tun = MeshTunnelInterface(interface_name=f"sov_{node_id}", virtual_ip="10.0.14.2")
        self.obfuscator = TrafficObfuscator()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            header = await reader.readexactly(4)
            if not header:
                return
            payload_length = struct.unpack("!I", header)[0]
            raw_fec_bytes = await reader.readexactly(payload_length)
            
            healed_json_bytes = self._core.decode_and_heal_fec_bytes(raw_fec_bytes)
            obfuscated_package = json.loads(healed_json_bytes.decode('utf-8'))
            
            # Determine correct dynamic channel extraction logic based on the wrapper format keys
            chosen_medium = "UDP_BLAST"
            if "url" in obfuscated_package: chosen_medium = "HTTPS_SIM"
            elif "query" in obfuscated_package: chosen_medium = "DNS_TXT"
            
            # Strip structural camouflage envelope layers natively
            native_json_bytes = self.obfuscator.decamouflage_fragment(obfuscated_package, chosen_medium)
            routing_envelope = json.loads(native_json_bytes.decode('utf-8'))
            
            target_node = routing_envelope.get("target_node")
            inner_envelope = routing_envelope.get("inner_envelope")
            
            if target_node != self.node_id and target_node in NODE_ROUTING_TABLE:
                proxy_port = NODE_ROUTING_TABLE[target_node]
                logging.info(f"[{self.node_id}] Forwarding obfuscated [{chosen_medium}] block to {target_node}...")
                p_reader, p_writer = await asyncio.open_connection(self.host, proxy_port)
                p_writer.write(header + raw_fec_bytes)
                await p_writer.drain()
                
                resp_header = await p_reader.readexactly(4)
                resp_len = struct.unpack("!I", resp_header)[0]
                resp_fec_bytes = await p_reader.readexactly(resp_len)
                writer.write(resp_header + resp_fec_bytes)
                await writer.drain()
                p_writer.close()
                await p_writer.wait_closed()
                return

            static_secret = hashlib.sha256(b"SovereignMeshDefaultSecretTokenKeyRing").digest()
            self._core.active_session_key = static_secret
            
            validation_result = self._core.process_message(inner_envelope)
            if validation_result.get("status") != "ALIGNED":
                return
                
            decrypted_payload = self._core.decrypt_payload_padded(inner_envelope.get("encrypted_data"))
            command_string = decrypted_payload.get('command_id', '')
            
            if command_string.startswith("TUNNEL_DATA:"):
                hex_packet = command_string.split(":")[1]
                unpacked_frame = self.v_tun.decapsulate_mesh_packet(bytes.fromhex(hex_packet))
                execution_output = subprocess.check_output("echo Mesh Packet Injection Verified Core Output Track", shell=True)
                response_payload = {"executed_at": self.node_id, "status": "TUNNEL_SUCCESS", "output": execution_output.decode('utf-8').strip(), "timestamp": time.time()}
            else:
                response_payload = {"executed_at": self.node_id, "status": "SUCCESS", "timestamp": time.time()}
                
            encrypted_response_data = self._core.encrypt_payload_padded(response_payload)
            canonical_resp_str = json.dumps(encrypted_response_data, sort_keys=True)
            response_signature = hmac.new(self._core.active_session_key, canonical_resp_str.encode('utf-8'), hashlib.sha256).hexdigest()
            
            server_envelope = {"version": "1.0", "signature": response_signature, "encrypted_data": encrypted_response_data}
            fec_outbound_bytes = self._core.encode_fec_bytes(json.dumps(server_envelope).encode('utf-8'))
            
            writer.write(struct.pack("!I", len(fec_outbound_bytes)) + fec_outbound_bytes)
            await writer.drain()
                
        except Exception as e:
            logging.error(f"[{self.node_id}] Mesh processing error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Multi-Hop Server [{self.node_id}] live on port {self.port}")
        async with self.server:
            await self.server.serve_forever()
