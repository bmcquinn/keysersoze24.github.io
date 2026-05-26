#!/bin/bash
set -e

echo "===================================================="
echo "      INITIALIZING SOUL SHELL ENGINE CORE           "
echo "   [ PRIVATE / PERSONAL NON-COMMERCIAL USE ONLY ]   "
echo "===================================================="
echo "WARNING: This architecture is a self-sovereign cryptographic"
echo "command plane. Distribution is intended solely for personal"
echo "infrastructure experimentation and individual privacy nodes."
echo "===================================================="
echo ""

# 1. Update system dependencies
sudo apt-get update && sudo apt-get install python3-pip python3-venv git -y

# 2. Establish project structural directories
TARGET_DIR="$HOME/soul-shell"
mkdir -p "$TARGET_DIR"

# 3. Provision isolated virtual environment
python3 -m venv "$TARGET_DIR/venv"
"$TARGET_DIR/venv/bin/pip" install --upgrade pip
"$TARGET_DIR/venv/bin/pip" install fastapi uvicorn cryptography pydantic

# 4. Prompt user directly for their Public Identity Key
echo ""
read -p "Enter your Base64 RSA Public Identity Key string: " USER_PUBLIC_KEY
echo ""

# 5. Emit the pristine gatekeeper verification runtime script
cat << 'INNER_EOF' > "$TARGET_DIR/main.py"
"""
SOUL SHELL ENGINE CORE - V2.0.0
--------------------------------------------------
LICENSING: SOVEREIGN PERSONAL-USE ONLY.
Any commercial distribution, enterprise licensing, or multi-tenant
monetization of this architecture protocol is strictly prohibited.
Designed exclusively for private, self-hosted node administration.
"""

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64
import xml.etree.ElementTree as ET
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

app = FastAPI(
    title="Soul Shell Engine",
    description="Sovereign Command Plane - Strictly Authorized For Personal Private Use Only."
)

ENCODED_PUBLIC_KEY = "REPLACE_WITH_KEY"

def load_public_key():
    try:
        xml_bytes = base64.b64decode(ENCODED_PUBLIC_KEY)
        root = ET.fromstring(xml_bytes.decode('utf-8'))
        modulus = int.from_bytes(base64.b64decode(root.find('Modulus').text), byteorder='big')
        exponent = int.from_bytes(base64.b64decode(root.find('Exponent').text), byteorder='big')
        public_numbers = RSAPublicNumbers(exponent, modulus)
        return public_numbers.public_key()
    except Exception as e:
        raise RuntimeError(f"Failed to parse public identity matrix: {e}")

try:
    PUBLIC_KEY = load_public_key()
except Exception:
    PUBLIC_KEY = None

class AgenticPayload(BaseModel):
    command: str
    signature: str

@app.post("/v1/execute")
async def execute_task(payload: AgenticPayload):
    import subprocess
    if not PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="Identity matrix uninitialized.")
    try:
        sig_bytes = bytes.fromhex(payload.signature)
        PUBLIC_KEY.verify(
            sig_bytes,
            payload.command.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
    except Exception:
        raise HTTPException(status_code=403, detail="Signature verification failed. Identity untrusted.")
    
    try:
        result = subprocess.run(payload.command, shell=True, capture_output=True, text=True, timeout=30)
        return {"status": "success", "stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/")
async def health_check():
    return {
        "status": "active", 
        "engine": "Soul Shell Core", 
        "version": "2.0.0", 
        "crypto": "asymmetric",
        "usage_scope": "private-personal"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
INNER_EOF

# Inject the runtime variable key safely
sed -i "s|REPLACE_WITH_KEY|$USER_PUBLIC_KEY|g" "$TARGET_DIR/main.py"

# 6. Configure the background systemd service daemon unit
cat << 'SYSTEMD_EOF' | sudo tee /etc/systemd/system/soul-shell.service > /dev/null
[Unit]
Description=Soul Shell Engine Core (Personal-Use Node)
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/soul-shell
ExecStart=$HOME/soul-shell/venv/bin/python3 main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

# 7. Start the system engines
sudo systemctl daemon-reload
sudo systemctl enable soul-shell --now

echo "===================================================="
echo "  SOUL SHELL DEPLOYMENT COMPLETE & ACTIVE ON PORT 8080"
echo "  [ LICENSE MATRIX SECURED: PRIVATE / PERSONAL-USE ]"
echo "===================================================="
