import json
import logging
import asyncio
import struct
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

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Processes continuous client connection streams using a 4-byte length prefix framing handler."""
        logging.info("New inbound network socket connection established on boundary.")
        try:
            while True:
                # Read the 4-byte length prefix header
                header = await reader.readexactly(4)
                if not header:
                    break
                
                # Unpack big-endian unsigned integer
                payload_length = struct.unpack("!I", header)[0]
                
                # Read the exact block of payload bytes
                payload_bytes = await reader.readexactly(payload_length)
                envelope = json.loads(payload_bytes.decode('utf-8'))
                
                logging.info(f"Received network packet ({payload_length} bytes). Running validation...")
                
                # Direct cryptographic pass-through to OmniCore
                validation_result = self._core.process_message(envelope)
                
                if validation_result.get("status") != "ALIGNED":
                    response = {"status": "REJECTED", "error": validation_result.get("error")}
                    writer.write(json.dumps(response).encode('utf-8'))
                    await writer.drain()
                    raise BridgeRoutingError(f"Network Packet Dropped: {validation_result.get('error')}")
                
                # Acknowledge successful receipt over the wire
                response = {"status": "DELIVERED", "bridge_node": self.port}
                writer.write(json.dumps(response).encode('utf-8'))
                await writer.drain()
                logging.info("Network routing transaction complete. Connection flushed.")
                
        except asyncio.IncompleteReadError:
            logging.info("Client disconnected from socket stream gracefully.")
        except Exception as e:
            logging.error(f"Transport boundary exception caught: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def start(self) -> None:
        """Starts the asynchronous TCP server daemon loop."""
        self.server = await asyncio.start_server(self.handle_client, self.host, self.port)
        logging.info(f"Sovereign TCP Bridge active and listening on tcp://{self.host}:{self.port}")
        async with self.server:
            await self.server.serve_forever()
            
    def stop(self) -> None:
        """Terminates the active listening sockets."""
        if self.server:
            self.server.close()
