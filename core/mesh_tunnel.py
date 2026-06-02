import struct
import json
import os
import time

class MeshTunnelInterface:
    def __init__(self, interface_name: str, virtual_ip: str):
        self.interface_name = interface_name
        self.virtual_ip = virtual_ip
        self.mtu = 1400
        
    def encapsulate_ip_packet(self, destination_ip: str, payload_bytes: bytes) -> bytes:
        """Encapsulates raw binary IP traffic into a standardized mesh tunnel transport block."""
        packet_len = len(payload_bytes)
        if packet_len > self.mtu:
            raise ValueError("Payload packet payload exceeds maximum transmission unit bounds.")
            
        # Standardized Layer 3 Tunnel Header Layout: 
        # Magic Token (2B) + Source IP Pointer (4B) + Dest IP Pointer (4B) + Packet Length (2B)
        magic_token = b"ST" # Sovereign Tunnel
        src_bytes = socket_to_bytes(self.virtual_ip)
        dest_bytes = socket_to_bytes(destination_ip)
        header = struct.pack("!2s4s4sH", magic_token, src_bytes, dest_bytes, packet_len)
        
        return header + payload_bytes

    def decapsulate_mesh_packet(self, raw_tunnel_bytes: bytes) -> dict:
        """Strips the tunnel envelope headers to expose raw application binary data payloads."""
        if len(raw_tunnel_bytes) < 12:
            return {"status": "MALFORMED"}
            
        magic_token, src_bytes, dest_bytes, packet_len = struct.unpack("!2s4s4sH", raw_tunnel_bytes[:12])
        if magic_token != b"ST":
            return {"status": "DROP"}
            
        payload = raw_tunnel_bytes[12:12+packet_len]
        return {
            "status": "UNPACKED",
            "source_ip": bytes_to_socket(src_bytes),
            "destination_ip": bytes_to_socket(dest_bytes),
            "payload": payload
        }

def socket_to_bytes(ip_str: str) -> bytes:
    return bytes(int(x) for x in ip_str.split('.'))

def bytes_to_socket(ip_bytes: bytes) -> str:
    return ".".join(str(b) for b in ip_bytes)
