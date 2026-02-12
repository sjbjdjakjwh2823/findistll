#!/usr/bin/env bash
set -euo pipefail

sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx build-essential zlib1g-dev libjpeg-dev

sudo mkdir -p /opt/preciso
sudo chown -R $USER:$USER /opt/preciso

echo "Upload the project to /opt/preciso before continuing."
