# Windows PowerShell - Build and Deploy Frontend
# Run this script from the project root directory

$ErrorActionPreference = "Stop"

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "Building Frontend for Deployment" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# Configuration
$projectRoot = "C:\Users\anude\OneDrive\Desktop\devops-ai-automator"
$frontendDir = "$projectRoot\frontend"
$buildDir = "$frontendDir\dist"
$pem = "C:\Users\anude\Downloads\pair.pem"
$ec2 = "ubuntu@16.16.128.193"

# Step 1: Check Node.js
Write-Host "[1/5] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    Write-Host "  Node: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  Node.js not found!" -ForegroundColor Red
    exit 1
}

# Step 2: Install dependencies
Write-Host "[2/5] Installing dependencies..." -ForegroundColor Yellow
Push-Location $frontendDir
npm install --loglevel=warn
Write-Host "  Done" -ForegroundColor Green

# Step 3: Build frontend
Write-Host "[3/5] Building with Vite..." -ForegroundColor Yellow
npm run build
Write-Host "  Done" -ForegroundColor Green
Pop-Location

# Step 4: Deploy to EC2
Write-Host "[4/5] Uploading to EC2..." -ForegroundColor Yellow
scp -i $pem -r "$buildDir/*" "${ec2}:/opt/devops-ai-automator/backend/frontend_static/"
Write-Host "  Done" -ForegroundColor Green

# Step 5: Restart service
Write-Host "[5/5] Restarting service..." -ForegroundColor Yellow
ssh -i $pem $ec2 "sudo systemctl restart devops-ai.service"
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "==========================================="
Write-Host "SUCCESS!" -ForegroundColor Green
Write-Host "==========================================="
Write-Host ""
Write-Host "Your app is live at: http://16.16.128.193:8000/" -ForegroundColor Yellow
Write-Host ""
