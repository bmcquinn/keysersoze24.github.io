import json
import logging
from omni_core import OmniCoreProtocol

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SOVEREIGN-BRIDGE] - %(levelname)s - %(message)s')

class BridgeRoutingError(Exception):
    """Raised when data transport fails verification or routing requirements."""
    pass

class SovereignBridge:
    def __init__(self, bridge_id: str = "bridge_alpha"):
        self.bridge_id = bridge_id
        # Bind the bridge directly to the OmniCore validation engine
        self._core = OmniCoreProtocol(node_id=f"core_via_{bridge_id}")
        logging.info(f"Sovereign Bridge Transport Link active: {self.bridge_id}")

    def ingest_and_route(self, envelope: dict) -> dict:
        """Receives a cross-boundary envelope, validates integrity, and routes to system core."""
        logging.info("Inbound payload detected on transport boundary. Processing validation sequence...")
        
        # Convert envelope to match the dictionary layout omni_core expects
        core_envelope = {
            "version": envelope.get("version", "1.0"),
            "signature": envelope.get("signature", ""),
            "payload": envelope.get("payload", {})
        }
        
        # Route through omni_core validation logic
        validation_result = self._core.process_message(core_envelope)
        
        if validation_result.get("status") != "ALIGNED":
            raise BridgeRoutingError(f"Transport Blocked: {validation_result.get('error', 'Unknown routing error')}")
            
        logging.info("Transport routing successful. Payload aligned and pushed to node.")
        return {
            "transport_status": "DELIVERED",
            "bridge": self.bridge_id,
            "core_response": validation_result
        }
