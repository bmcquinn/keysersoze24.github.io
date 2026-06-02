import json
import logging
import asyncio
import struct
import time
import hmac
import hashlib
import os
import subprocess
from omni_core import OmniCoreProtocol
from mesh_tunnel import MeshTunnelInterface
from obfuscation_matrix import TrafficObfuscator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

CONFIG_PATH = "mesh_config.json"
AUDIT_LOG_PATH = "mesh_audit.bin"
DH_PRIME = 0xFFFFFFFFFFFFFFFFC90FFAA7ED91923641216727E282D639171164B826770944A66616A6635B494499FA695630F27A9757434353051A6FFD96B8799337765771281F229188EA671C9F65D55247716509352B51410300250377B7928509755B1C661CE12674975422E0A1B1605A60308917044893844147432180F551512307B28B3154562A735B5A93D6B2FEB1350148E06A1435801741757D225D45667F9351A3C4E02B6D44D5C5581D05125597
DH_GENERATOR = 2

NODE_ROUTING_TABLE = {}
GLOBAL_SETTINGS = {"fixed_payload_size": 512}

# Active volatile RAM register cache to track ephemeral state keys across the handshake lifecycle
SESSION_KEY_CACHE = {}

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
        self.v_tun = MeshTunnelInterface(interface_name=f"sov_{node_id}", virtual_ip="10.0.14.2")
        self.obfuscator = TrafficObfuscator()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            # === STEP 1: RESOLVE CONTROL PLANE PHASE (KEX_INIT) ===
            header = await reader.readexactly(4)
            if not header: return
            payload_length = struct.unpack("!I", header)[0]
            raw_fec_bytes = await reader.readexactly(payload_length)
            
            healed_json_bytes = self._core.decode_and_heal_fec_bytes(raw_fec_bytes)
            envelope = json.loads(healed_json_bytes.decode('utf-8'))
            
            target_node = envelope.get("target_node")
            kex_step = envelope.get("kex_step")
            
            # Forwarding Proxy Logic for Mid-Hop Transits
            if target_node != self.node_id and target_node in NODE_ROUTING_TABLE:
                proxy_port = NODE_ROUTING_TABLE[target_node]
                logging.info(f"[{self.node_id}] Proxying KEX/DATA Stream directly to target node: {target_node}...")
                p_reader, p_writer = await asyncio.open_connection(self.host, proxy_port)
                
                # Pipe KEX INIT
                p_writer.write(header + raw_fec_bytes)
                await p_writer.drain()
                
                # Receive and forward server public key return frame
                resp_header = await p_reader.readexactly(4)
                resp_len = struct.unpack("!I", resp_header)[0]
                resp_fec_bytes = await p_reader.readexactly(resp_len)
                writer.write(resp_header + resp_fec_bytes)
                await writer.drain()
                
                # Pipe following DATA segment transparently
                data_header = await reader.readexactly(4)
                data_len = struct.unpack("!I", data_header)[0]
                data_fec_bytes = await reader.readexactly(data_len)
                p_writer.write(data_header + data_fec_bytes)
                await p_writer.drain()
                
                # Receive and return executed output back to operator panel
                data_resp_header = await p_reader.readexactly(4)
                data_resp_len = struct.unpack("!I", data_resp_header)[0]
                data_resp_fec_bytes = await p_reader.readexactly(data_resp_len)
                writer.write(data_resp_header + data_resp_fec_bytes)
                await writer.drain()
                
                p_writer.close()
                await p_writer.wait_closed()
                return

            # local processing logic if this endpoint is the targeted receiver node
            if kex_step == "INIT":
                client_dh_public = int(envelope.get("dh_public", 0))
                
                srv_private = int.from_bytes(os.urandom(32), byteorder='big')
                srv_public = pow(DH_GENERATOR, srv_private, DH_PRIME)
                
                shared_secret_int = pow(client_dh_public, srv_private, DH_PRIME)
                shared_bytes = shared_secret_int.to_bytes((shared_secret_int.bit_length() + 7) // 8, byteorder='big')
                ephemeral_session_key = hashlib.sha256(shared_bytes).digest()
                
                # Cache key dynamically in memory to bind against next arriving payload block
                SESSION_KEY_CACHE[self.node_id] = ephemeral_session_key
                
                response_envelope = {"dh_public": str(srv_public)}
                fec_out = self._core.encode_fec_bytes(json.dumps(response_envelope).encode('utf-8'))
                writer.write(struct.pack("!I", len(fec_out)) + fec_out)
                await writer.drain()
                
            # === STEP 2: RE-DEOBFUSCATE AND DECRYPT COHERENT PAYLOAD LAYER ===
            data_header = await reader.readexactly(4)
            data_payload_len = struct.unpack("!I", data_header)[0]
            raw_data_fec_bytes = await reader.readexactly(data_payload_len)
            
            healed_data_bytes = self._core.decode_and_heal_fec_bytes(raw_data_fec_bytes)
            obfuscated_package = json.loads(healed_data_bytes.decode('utf-8'))
            
            chosen_medium = "UDP_BLAST"
            if "url" in obfuscated_package: chosen_medium = "HTTPS_SIM"
            elif "query" in obfuscated_package: chosen_medium = "DNS_TXT"
                
            native_json_bytes = self.obfuscator.decamouflage_fragment(obfuscated_package, chosen_medium)
            data_envelope = json.loads(native_json_bytes.decode('utf-8'))
            
            ephemeral_session_key = SESSION_KEY_CACHE.get(self.node_id)
            if not ephemeral_session_key:
                logging.error(f"[{self.node_id}] Active context validation exception. Key missing.")
                return
                
            encrypted_block = data_envelope.get("encrypted_data")
            if not hmac.compare_digest(hmac.new(ephemeral_session_key, json.dumps(encrypted_block, sort_keys=True).encode('utf-8'), hashlib.sha256).hexdigest(), data_envelope.get("signature", "")):
                logging.error(f"[{self.node_id}] Dynamic payload MAC signature violation. Dropping packet.")
                return

            self._core.active_session_key = ephemeral_session_key
            decrypted_bytes = self._core.decrypt_payload_padded(encrypted_block)
            command_string = decrypted_bytes.get('command_id', '')
            
            logging.info(f"[{self.node_id}] Validated Packet Delivery Processed: {command_string[:30]}")
            
            if command_string.startswith("TUNNEL_DATA:"):
                execution_output = subprocess.check_output("echo Mesh Packet Injection Verified Core Output Track", shell=True)
                response_payload = {"executed_at": self.node_id, "status": "TUNNEL_SUCCESS", "output": execution_output.decode('utf-8').strip(), "timestamp": time.time()}
            else:
                response_payload = {"executed_at": self.node_id, "status": "SUCCESS", "timestamp": time.time()}
                
            encrypted_response_data = self._core.encrypt_payload_padded(response_payload)
            response_signature = hmac.new(ephemeral_session_key, json.dumps(encrypted_response_data, sort_keys=True).encode('utf-8'), hashlib.sha256).hexdigest()
            
            server_envelope = {
                "signature": response_signature,
                "encrypted_data": encrypted_response_data
            }
            
            fec_outbound_bytes = self._core.encode_fec_bytes(json.dumps(server_envelope).encode('utf-8'))
            writer.write(struct.pack("!I", len(fec_outbound_bytes)) + fec_outbound_bytes)
            await writer.drain()
            
            # Volatile memory scrubbing lifecycle
            if self.node_id in SESSION_KEY_CACHE:
                del SESSION_KEY_CACHE[self.node_id]
                
        except Exception as e:
            logging.error(f"[{self.node_id}] Mesh engine tracking processing exception: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Multi-Hop Server [{self.node_id}] live on port {self.port}")
        async with self.server:
            await self.server.serve_forever()
