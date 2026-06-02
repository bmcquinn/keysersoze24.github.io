import json
import logging
import asyncio
import struct
import time
import hmac
import hashlib
import os
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

CONFIG_PATH = "mesh_config.json"
AUDIT_LOG_PATH = "mesh_audit.bin"

NODE_ROUTING_TABLE = {}
GLOBAL_SETTINGS = {"fixed_payload_size": 512}

def load_mesh_configuration():
    """Reads the JSON footprint from disk with empty-file validation protections."""
    global NODE_ROUTING_TABLE, GLOBAL_SETTINGS
    if not os.path.exists(CONFIG_PATH):
        return
    try:
        # ATOMIC VALIDATION VECTOR: Ensure the file size is greater than zero before attempting a parse loop
        if os.path.getsize(CONFIG_PATH) == 0:
            return

        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        NODE_ROUTING_TABLE.clear()
        NODE_ROUTING_TABLE.update(config.get("NODE_ROUTING_TABLE", {}))
        GLOBAL_SETTINGS.update(config.get("GLOBAL_SETTINGS", {}))
        logging.info(f"[*] Configuration hot-swapped in memory. Routes: {list(NODE_ROUTING_TABLE.keys())}")
    except json.JSONDecodeError:
        # Suppress race-condition read blips silently while file-system writes complete
        pass
    except Exception as e:
        logging.error(f"[-] Configuration hot-reload extraction failure: {e}")

def watch_config_lifecycle():
    last_mtime = 0
    while True:
        try:
            if os.path.exists(CONFIG_PATH):
                current_mtime = os.path.getmtime(CONFIG_PATH)
                if current_mtime != last_mtime:
                    # Brief structural pause to let the external OS process flush text to disk cleanly
                    time.sleep(0.1)
                    load_mesh_configuration()
                    last_mtime = current_mtime
        except Exception:
            pass
        time.sleep(0.5)

load_mesh_configuration()
threading.Thread(target=watch_config_lifecycle, daemon=True).start()

def write_binary_audit_entry(node_id: str, event_type: str, status_code: int):
    timestamp = time.time()
    node_bytes = node_id.encode('utf-8')[:12].ljust(12, b'\x00')
    event_bytes = event_type.encode('utf-8')[:12].ljust(12, b'\x00')
    
    last_hash = b"\x00" * 36
    if os.path.exists(AUDIT_LOG_PATH) and os.path.getsize(AUDIT_LOG_PATH) >= 72:
        with open(AUDIT_LOG_PATH, "rb") as f:
            f.seek(-72, os.SEEK_END)
            last_entry = f.read(72)
            last_hash = hashlib.sha256(last_entry).hexdigest()[:36].encode('utf-8')
            
    packed_entry = struct.pack("!d12s12sI36s", timestamp, node_bytes, event_bytes, status_code, last_hash)
    with open(AUDIT_LOG_PATH, "ab") as f:
        f.write(packed_entry)

from omni_core import OmniCoreProtocol

class SovereignBridgeServer:
    def __init__(self, node_id: str, host: str = "127.0.0.1", port: int = 8085):
        self.node_id = node_id
        self.host = host
        self.port = port
        self._core = OmniCoreProtocol(node_id=node_id)
        self.server = None

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        event_action = "EXECUTE"
        status_flag = 200
        try:
            header = await reader.readexactly(4)
            if not header:
                return
            payload_length = struct.unpack("!I", header)[0]
            raw_fec_bytes = await reader.readexactly(payload_length)
            
            healed_json_bytes = self._core.decode_and_heal_fec_bytes(raw_fec_bytes)
            routing_envelope = json.loads(healed_json_bytes.decode('utf-8'))
            
            target_node = routing_envelope.get("target_node")
            inner_envelope = routing_envelope.get("inner_envelope")
            
            if target_node != self.node_id and target_node in NODE_ROUTING_TABLE:
                event_action = "FORWARD"
                proxy_port = NODE_ROUTING_TABLE[target_node]
                logging.info(f"[{self.node_id}] Routing proxy triggered. Forwarding packet to {target_node} on port {proxy_port}...")
                
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
                write_binary_audit_entry(self.node_id, event_action, status_flag)
                return

            static_secret = hashlib.sha256(b"SovereignMeshDefaultSecretTokenKeyRing").digest()
            self._core.active_session_key = static_secret
            
            validation_result = self._core.process_message(inner_envelope)
            if validation_result.get("status") != "ALIGNED":
                status_flag = 400
                write_binary_audit_entry(self.node_id, event_action, status_flag)
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
            
            write_binary_audit_entry(self.node_id, event_action, status_flag)
                
        except Exception as e:
            logging.error(f"[{self.node_id}] Routing mesh processing exception: {e}")
            write_binary_audit_entry(self.node_id, event_action, 500)
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign Multi-Hop Server [{self.node_id}] live on port {self.port}")
        async with self.server:
            await self.server.serve_forever()
