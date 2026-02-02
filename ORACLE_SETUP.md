# Oracle Cloud Deployment (preciso-data.com)

## 0) Prerequisites
- Oracle Cloud VM (Ubuntu 22.04 LTS)
- Public IP attached
- DNS A record: preciso-data.com -> VM Public IP

## 1) Open Ports (Security List / NSG)
- TCP 22: SSH
- TCP 80: HTTP
- TCP 443: HTTPS
- (Optional) TCP 8004: direct API test

## 2) OS Packages
```bash
sudo apt update && sudo apt install -y \
  python3.11 python3.11-venv python3-pip \
  nginx certbot python3-certbot-nginx \
  build-essential zlib1g-dev libjpeg-dev
```

## 3) App Directory
```bash
sudo mkdir -p /opt/preciso
sudo chown -R $USER:$USER /opt/preciso
```

## 4) Upload Project
```bash
scp -r C:\Users\Administrator\Desktop\preciso ubuntu@<PUBLIC_IP>:/opt/preciso
```

## 5) Python venv
```bash
cd /opt/preciso
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements_full.txt
```

## 6) Secrets
- Copy `중요.txt` to `/opt/preciso/중요.txt`
- Ensure `OAI_CONFIG_LIST` and `config_api_keys` exist in `/opt/preciso/`

## 7) Supabase SQL
- Run `supabase_schema.sql` and `supabase_spokes.sql` in Supabase SQL Editor.

## 8) systemd Service
- Use `preciso.service` from this folder:
```bash
sudo cp /opt/preciso/preciso.service /etc/systemd/system/preciso.service
sudo systemctl daemon-reload
sudo systemctl enable preciso
sudo systemctl start preciso
```

## 9) Nginx
- Use `nginx_preciso.conf` from this folder:
```bash
sudo cp /opt/preciso/nginx_preciso.conf /etc/nginx/sites-available/preciso
sudo ln -s /etc/nginx/sites-available/preciso /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 10) SSL
```bash
sudo certbot --nginx -d preciso-data.com
```

## 11) Health Check
```bash
curl https://preciso-data.com/health
```
