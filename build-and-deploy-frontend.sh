#!/bin/bash
# Frontend Build and Deployment Script

set -e

echo "=========================================="
echo "🚀 Building and Deploying Frontend"
echo "=========================================="

# Configuration
FRONTEND_DIR="/opt/devops-ai-automator/frontend"
BUILD_DIR="${FRONTEND_DIR}/dist"
BACKEND_STATIC="${FRONTEND_DIR}/../backend/frontend_static"
EC2_IP="16.16.128.193"
EC2_USER="ubuntu"
SSH_KEY="/home/ubuntu/pair.pem"

# Step 1: Install dependencies
echo "[1/6] Installing frontend dependencies..."
cd $FRONTEND_DIR
npm install --silent

# Step 2: Build frontend
echo "[2/6] Building frontend with Vite..."
npm run build

# Step 3: Create static directory
echo "[3/6] Creating backend static directory..."
mkdir -p $BACKEND_STATIC
rm -rf $BACKEND_STATIC/*

# Step 4: Copy built files
echo "[4/6] Copying built files to backend..."
cp -r $BUILD_DIR/* $BACKEND_STATIC/

# Step 5: Update backend config
echo "[5/6] Configuring backend to serve frontend..."
python3 << 'EOF'
import os

backend_config = "/opt/devops-ai-automator/backend/config.py"
content = open(backend_config).read()

# Check if frontend config exists
if "frontend_build_dir" not in content:
    # Add frontend config
    new_config = content.replace(
        'class Settings:',
        '''class Settings:
    frontend_build_dir = Path(__file__).parent.parent / "backend" / "frontend_static"'''
    )
    with open(backend_config, 'w') as f:
        f.write(new_config)
    print("✓ Frontend config added")
else:
    print("✓ Frontend config already present")
EOF

# Step 6: Restart backend
echo "[6/6] Restarting backend service..."
sudo systemctl restart devops-ai.service

sleep 2

echo ""
echo "=========================================="
echo "✅ Frontend Deployment Complete!"
echo "=========================================="
echo ""
echo "🌐 Access application at:"
echo "   http://${EC2_IP}:8000/"
echo ""
echo "📡 API Endpoints:"
echo "   http://${EC2_IP}:8000/api/health"
echo "   http://${EC2_IP}:8000/api/agents/health"
echo ""
echo "Useful commands:"
echo "  View logs:     sudo journalctl -u devops-ai -f"
echo "  Restart app:   sudo systemctl restart devops-ai.service"
echo ""
