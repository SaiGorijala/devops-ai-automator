#!/usr/bin/env python3
"""
EC2 Deployment Helper
Deploys DevOps AI Automator to AWS EC2 instance via SSH
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description, shell=False):
    """Run a command and return success status"""
    print(f"\n📌 {description}...")
    try:
        if shell:
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        else:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"   ✅ Success")
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Failed: {e.stderr}")
        return False, str(e)

def main():
    print("="*60)
    print("🚀 DevOps AI Automator - EC2 Deployment Helper")
    print("="*60)
    
    # Input validation
    print("\n📝 Configuration:")
    ec2_ip = input("  EC2 IP Address (e.g., 16.16.128.193): ").strip()
    ec2_user = input("  EC2 Username (default: ubuntu): ").strip() or "ubuntu"
    pem_file = input("  PEM Key file path (e.g., C:\\Users\\anude\\Downloads\\windows.pem): ").strip()
    
    # Validate PEM file exists
    pem_path = Path(pem_file)
    if not pem_path.exists():
        print(f"\n❌ Error: PEM file not found at {pem_file}")
        sys.exit(1)
    
    ec2_host = f"{ec2_user}@{ec2_ip}"
    print(f"\n  Target: {ec2_host}")
    print(f"  Key: {pem_file}")
    
    # Step 1: Test SSH connection
    success, output = run_command(
        f'ssh -i "{pem_file}" -o "StrictHostKeyChecking=no" {ec2_host} "echo SSH_OK"',
        "Testing SSH connection",
        shell=True
    )
    
    if not success or "SSH_OK" not in output:
        print("\n❌ Failed to connect via SSH")
        print("   Troubleshooting:")
        print("   1. Check PEM file permissions: icacls <pem_file> /inheritance:r")
        print("   2. Verify EC2 Security Group allows SSH (port 22)")
        print("   3. Verify SSH key matches EC2 instance")
        sys.exit(1)
    
    # Step 2: Deploy via SSH
    script_dir = Path(__file__).parent
    deploy_script = script_dir / "deploy-to-ec2.sh"
    
    if not deploy_script.exists():
        print(f"\n❌ Error: Deployment script not found at {deploy_script}")
        sys.exit(1)
    
    # Upload script
    success, output = run_command(
        f'scp -i "{pem_file}" -o "StrictHostKeyChecking=no" "{deploy_script}" {ec2_host}:/home/{ec2_user}/',
        "Uploading deployment script",
        shell=True
    )
    
    if not success:
        sys.exit(1)
    
    # Execute deployment
    success, output = run_command(
        f'ssh -i "{pem_file}" -o "StrictHostKeyChecking=no" {ec2_host} "bash ~/deploy-to-ec2.sh"',
        "Running deployment on EC2",
        shell=True
    )
    
    if not success:
        print("\n⚠️  Deployment may have failed. Check EC2 instance logs.")
        sys.exit(1)
    
    # Verify deployment
    print("\n" + "="*60)
    print("🔍 Verifying deployment...")
    print("="*60)
    
    success, output = run_command(
        f'ssh -i "{pem_file}" -o "StrictHostKeyChecking=no" {ec2_host} "sudo systemctl status devops-ai.service"',
        "Checking service status",
        shell=True
    )
    
    print("\n" + "="*60)
    print("✅ DEPLOYMENT COMPLETE!")
    print("="*60)
    print(f"\n🌐 Access your application at:")
    print(f"   http://{ec2_ip}:8000/api/health")
    print(f"\n📡 WebSocket endpoint:")
    print(f"   ws://{ec2_ip}:8000/ws/agent-activity/{{session_id}}")
    print(f"\n📋 Useful commands:")
    print(f"   View logs:   ssh -i \"{pem_file}\" {ec2_host} \"sudo journalctl -u devops-ai -f\"")
    print(f"   Restart:     ssh -i \"{pem_file}\" {ec2_host} \"sudo systemctl restart devops-ai\"")
    print("\n")

if __name__ == "__main__":
    main()
