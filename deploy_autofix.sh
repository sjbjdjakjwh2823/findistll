#!/bin/bash

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"
SSH_CONFIG="$PROJECT_ROOT/../ssh_config"
REMOTE_HOST="oracle-preciso"
REMOTE_DIR="/opt/preciso/app/ui"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[1/6] Starting Self-Healing Deployment...${NC}"

# Check for SSH Config
if [ ! -f "$SSH_CONFIG" ]; then
    # Try finding it in current dir if script run from root
    if [ -f "ssh_config" ]; then
        SSH_CONFIG="ssh_config"
    else
        echo -e "${RED}Error: ssh_config not found!${NC}"
        exit 1
    fi
fi

# Step 1: Build Frontend
echo -e "${YELLOW}[2/6] Building Next.js Frontend...${NC}"
cd "$FRONTEND_DIR" || exit 1

# Ensure dependencies (skip if node_modules exists to save time, or run ci if needed)
if [ ! -d "node_modules" ]; then
    npm ci
fi

# Run Build
if npm run build; then
    echo -e "${GREEN}Build Successful!${NC}"
else
    echo -e "${RED}Build Failed! Aborting deployment.${NC}"
    exit 1
fi

# Verify Output
if [ ! -d "out" ]; then
    echo -e "${RED}Error: 'out' directory not found. Ensure 'output: export' is in next.config.ts${NC}"
    exit 1
fi

# Step 2: Prepare Server
echo -e "${YELLOW}[3/6] Preparing Remote Server...${NC}"
# Fix permissions to ensure we can write
ssh -F "$SSH_CONFIG" $REMOTE_HOST "sudo chown -R ubuntu:ubuntu /opt/preciso/app/ui"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to prepare server permissions.${NC}"
    exit 1
fi

# Backup current UI
TIMESTAMP=$(date +%s)
ssh -F "$SSH_CONFIG" $REMOTE_HOST "cp -r /opt/preciso/app/ui /opt/preciso/app/ui_backup_$TIMESTAMP"

# Step 3: Deploy Files
echo -e "${YELLOW}[4/6] Uploading Files...${NC}"
# Use rsync if available, else scp. We'll use scp recursively.
# We copy contents of out/ to /opt/preciso/app/ui/
scp -F "$SSH_CONFIG" -r out/* $REMOTE_HOST:$REMOTE_DIR/

if [ $? -ne 0 ]; then
    echo -e "${RED}Upload failed! Rolling back...${NC}"
    # Rollback
    ssh -F "$SSH_CONFIG" $REMOTE_HOST "rm -rf /opt/preciso/app/ui && mv /opt/preciso/app/ui_backup_$TIMESTAMP /opt/preciso/app/ui"
    exit 1
fi

# Step 4: Fix Permissions & Restart Services
echo -e "${YELLOW}[5/6] Restarting Services...${NC}"
ssh -F "$SSH_CONFIG" $REMOTE_HOST "sudo chown -R ubuntu:ubuntu /opt/preciso/app/ui && sudo chmod -R 755 /opt/preciso/app/ui && sudo systemctl restart preciso && sudo systemctl restart nginx"

# Step 5: Verify
echo -e "${YELLOW}[6/6] Verifying Deployment...${NC}"
# We check via curl on the server to localhost or public URL if reachable
# Checking public URL might be cached by Cloudflare, so check localhost or header
HTTP_STATUS=$(ssh -F "$SSH_CONFIG" $REMOTE_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:8004/decisions.html")

if [ "$HTTP_STATUS" == "200" ]; then
    echo -e "${GREEN}Verification Successful! (HTTP 200)${NC}"
    echo -e "${GREEN}Deployment Complete.${NC}"
else
    echo -e "${RED}Verification Failed! (HTTP $HTTP_STATUS)${NC}"
    echo -e "${YELLOW}Initiating Rollback...${NC}"
    ssh -F "$SSH_CONFIG" $REMOTE_HOST "rm -rf /opt/preciso/app/ui && mv /opt/preciso/app/ui_backup_$TIMESTAMP /opt/preciso/app/ui && sudo systemctl restart preciso"
    echo -e "${RED}Rollback Complete.${NC}"
    exit 1
fi
