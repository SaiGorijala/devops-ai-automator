#!/bin/bash
# DevOps AI Automator - EC2 Deployment Script
# Run this on your EC2 instance as: bash deploy-to-ec2.sh

set -e

echo "=========================================="
echo "DevOps AI Automator - EC2 Deployment"
echo "=========================================="

# Variables
REPO_URL="https://github.com/SaiGorijala/devops-ai-automator.git"
APP_DIR="/opt/devops-ai-automator"
VENV_DIR="$APP_DIR/.venv"
PORT=8000

# Step 1: Update system packages
echo "[1/8] Updating system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv git curl > /dev/null 2>&1

# Step 2: Create app directory
echo "[2/8] Creating application directory..."
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR
cd $APP_DIR

# Step 3: Clone repository
echo "[3/8] Cloning repository..."
if [ -d ".git" ]; then
    echo "  Repository already exists, pulling latest..."
    git pull origin main 2>/dev/null || git pull
else
    echo "  Cloning fresh repository..."
    git clone $REPO_URL . 2>/dev/null
fi

# Step 4: Create virtual environment
echo "[4/8] Creating Python virtual environment..."
python3 -m venv $VENV_DIR

# Step 5: Activate venv and install dependencies
echo "[5/8] Installing Python dependencies..."
source $VENV_DIR/bin/activate
pip install --quiet --upgrade pip setuptools
pip install --quiet -r requirements.txt

# Step 6: Create systemd service
echo "[6/8] Creating systemd service..."
sudo tee /etc/systemd/system/devops-ai.service > /dev/null <<EOF
[Unit]
Description=DevOps AI Automator Backend
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Step 7: Enable and start service
echo "[7/8] Starting service..."
sudo systemctl daemon-reload
sudo systemctl enable devops-ai.service
sudo systemctl start devops-ai.service

# Step 8: Wait and verify
echo "[8/8] Verifying deployment..."
sleep 3

if sudo systemctl is-active --quiet devops-ai.service; then
    echo ""
    echo "=========================================="
    echo "✅ DEPLOYMENT SUCCESSFUL!"
    echo "=========================================="
    echo ""
    echo "Application URL:"
    echo "  http://16.16.128.193:$PORT/api/health"
    echo ""
    echo "Useful commands:"
    echo "  View logs:     sudo journalctl -u devops-ai -f"
    echo "  Restart:       sudo systemctl restart devops-ai"
    echo "  Stop:          sudo systemctl stop devops-ai"
    echo "  Status:        sudo systemctl status devops-ai"
    echo ""
else
    echo "❌ Service failed to start. Checking logs..."
    sudo systemctl status devops-ai.service
    echo ""
    echo "View full logs with:"
    echo "  sudo journalctl -u devops-ai -n 50"
    exit 1
fi
