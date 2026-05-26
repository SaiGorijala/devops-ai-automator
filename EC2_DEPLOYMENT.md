# 🚀 Deploy to AWS EC2 Instance

## Option 1: Using AWS EC2 Instance Connect (Easiest - No SSH Required)

### Step 1: Open EC2 Instance Connect in AWS Console

1. Go to AWS Console → EC2 → Instances
2. Select instance `16.16.128.193` (eu-north-1)
3. Click **Connect** → **EC2 Instance Connect**
4. Click **Connect** to open browser terminal

### Step 2: Run Deployment Script

In the browser terminal, paste and run:

```bash
cd /home/ubuntu && curl -o deploy.sh https://raw.githubusercontent.com/SaiGorijala/devops-ai-automator/main/deploy-to-ec2.sh && bash deploy.sh
```

Or if you have a local copy:

```bash
# Copy script to EC2
scp -i /path/to/key.pem deploy-to-ec2.sh ubuntu@16.16.128.193:/home/ubuntu/

# SSH and run
ssh -i /path/to/key.pem ubuntu@16.16.128.193 'bash ~/deploy-to-ec2.sh'
```

---

## Option 2: Using SSH from Your Machine

### Step 1: Fix PEM File Permissions

```powershell
# On your Windows machine
$pemPath = "C:\Users\anude\Downloads\windows.pem"
icacls $pemPath /inheritance:r /grant:r "$($env:USERNAME):(F)"
```

### Step 2: SSH into EC2

```powershell
# Test SSH connection
$pem = "C:\Users\anude\Downloads\windows.pem"
$ec2 = "ubuntu@16.16.128.193"

# Simple SSH test
ssh -i $pem $ec2 "echo 'SSH connection successful!'"
```

### Step 3: Deploy

```powershell
# Copy deployment script
scp -i $pem "C:\Users\anude\OneDrive\Desktop\devops-ai-automator\deploy-to-ec2.sh" `
    ubuntu@16.16.128.193:/home/ubuntu/

# Execute on EC2
ssh -i $pem ubuntu@16.16.128.193 'bash ~/deploy-to-ec2.sh'
```

---

## Option 3: Manual Deployment (Copy-Paste Commands)

If SSH is not working, you can manually run commands in AWS EC2 Instance Connect:

```bash
# 1. Update system
sudo apt-get update && sudo apt-get install -y python3-pip python3-venv git

# 2. Clone repo
cd /opt
sudo git clone https://github.com/SaiGorijala/devops-ai-automator.git devops-ai-automator
cd devops-ai-automator
sudo chown -R $USER:$USER .

# 3. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -q --upgrade pip setuptools
pip install -q -r requirements.txt

# 5. Run server (in foreground for testing)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# If it works, create systemd service to keep it running
# (See Option 4 below)
```

---

## Option 4: Create Systemd Service (Keep App Running)

After deployment, create a service to auto-start the app:

```bash
# Create service file
sudo tee /etc/systemd/system/devops-ai.service > /dev/null <<'EOF'
[Unit]
Description=DevOps AI Automator Backend
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/devops-ai-automator
Environment="PATH=/opt/devops-ai-automator/.venv/bin"
ExecStart=/opt/devops-ai-automator/.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable devops-ai.service
sudo systemctl start devops-ai.service

# Check status
sudo systemctl status devops-ai.service
```

---

## ✅ Verify Deployment

After deployment, test from your local machine:

```powershell
# Test health endpoint
Invoke-WebRequest -Uri "http://16.16.128.193:8000/api/health" -UseBasicParsing | Select-Object -ExpandProperty Content

# Expected response:
# {"status":"ok","ollama_host":"http://localhost:11434","model":"deepseek-coder:6.7b"}
```

---

## 🛠️ Useful EC2 Commands

```bash
# Check if server is running
sudo systemctl status devops-ai.service

# View recent logs
sudo journalctl -u devops-ai -n 50

# Follow logs in real-time
sudo journalctl -u devops-ai -f

# Restart service
sudo systemctl restart devops-ai.service

# Stop service
sudo systemctl stop devops-ai.service

# View port 8000 usage
sudo netstat -tuln | grep 8000
# or
sudo ss -tuln | grep 8000
```

---

## 🔒 AWS Security Group Configuration

Make sure your EC2 security group allows inbound traffic:

1. Go to AWS Console → EC2 → Security Groups
2. Find the security group for your instance
3. Click **Inbound Rules** → **Edit inbound rules**
4. Add rule:
   - Type: **Custom TCP**
   - Port Range: **8000**
   - Source: **0.0.0.0/0** (or your specific IP)
5. Click **Save rules**

---

## 📊 Expected Endpoints

Once deployed, you should be able to access:

```
✅ http://16.16.128.193:8000/api/health
✅ http://16.16.128.193:8000/api/agents/health
✅ http://16.16.128.193:8000/api/multi-agent/deploy
✅ ws://16.16.128.193:8000/ws/agent-activity/{session_id}
```

---

## ❌ Troubleshooting

### "Connection timed out"
- Check AWS Security Group inbound rules for port 8000
- Verify EC2 instance is running
- Check if service is active: `sudo systemctl status devops-ai.service`

### "Module not found"
- Ensure requirements.txt dependencies are installed
- Check venv is activated: `which python`
- Reinstall: `pip install -r requirements.txt`

### "Address already in use"
```bash
# Find process on port 8000
sudo lsof -i :8000

# Kill it
sudo kill -9 <PID>
```

### Check Ollama Health
```bash
# Test Ollama endpoint
curl http://localhost:11434/api/tags
```

---

## 🎯 Next Steps

1. Deploy using one of the options above
2. Test `/api/health` endpoint
3. Check AWS Security Group allows port 8000
4. Use `/api/multi-agent/deploy` to start multi-agent pipeline
5. Connect to WebSocket for real-time monitoring

---

**Questions?** Check `/opt/devops-ai-automator/backend/main.py` for all available endpoints.
