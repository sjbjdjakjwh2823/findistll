
# 🚀 Oracle Cloud Deployment Guide for FinDistill

This guide helps you deploy the **FinDistill** engine (Project 1) to an Oracle Cloud VM with a custom domain (`preciso-data.com`) and automatic SSL.

## 📋 Prerequisites

1.  **Oracle Cloud VM**: Ubuntu 22.04 or 24.04 (Ampere A1 or AMD).
2.  **Domain**: `preciso-data.com` pointing to your VM's Public IP.
    *   **A Record**: `preciso-data.com` -> `[Your Oracle IP]`
    *   **CNAME Record**: `www.preciso-data.com` -> `preciso-data.com`
3.  **Ports Open**: Ensure Ingress Rules allow ports `80` (HTTP) and `443` (HTTPS).

## 🛠️ Step-by-Step Deployment

### 1. Connect to Oracle Server
Open your terminal and SSH into your instance:
```bash
ssh -i /path/to/your/key.key ubuntu@[YOUR_ORACLE_IP]
```

### 2. Install Docker & Git
Run these commands to set up the environment:
```bash
# Update and install Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-compose

# Verify installation
sudo docker run hello-world
```

### 3. Clone Repository
```bash
git clone https://github.com/sjbjdjakjwh2823/findistll.git
cd findistll/project_1/deployment/oracle
```

### 4. Setup SSL Certificates (First Time Only)
This script generates free HTTPS certificates from Let's Encrypt.
```bash
chmod +x init-letsencrypt.sh
sudo ./init-letsencrypt.sh
```
*   Follow the prompts. It will spin up Nginx, request certs, and reload.

### 5. Start Services
Once certificates are generated, start the full stack:
```bash
sudo docker-compose up -d
```

## ✅ Verification
Visit `https://preciso-data.com` in your browser. You should see the FinDistill dashboard securely via HTTPS.

## 🔄 Updates
To update the code later:
```bash
cd ~/findistll
git pull origin main
cd project_1/deployment/oracle
sudo docker-compose up -d --build
```
