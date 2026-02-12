# 서버 요구사항 (Oracle Cloud + preciso-data.com)

## 필수 인프라
- Oracle Cloud Compute (Linux VM 권장)
- PostgreSQL (Supabase 사용) + Storage
- Reverse Proxy (Nginx)
- TLS 인증서 (Let’s Encrypt)

## 권장 구성
- VM 스펙: 2 vCPU / 8GB RAM 이상
- OS: Ubuntu 22.04 LTS
- 프로세스 매니저: systemd 또는 PM2

## 도메인/SSL
- 도메인: preciso-data.com
- DNS: A 레코드 → Oracle VM 공인 IP
- SSL: certbot 사용하여 TLS 적용

## 환경변수 (중요.txt 기반)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`
- `HF_TOKEN`
- `HF_DATASET`
- `CLOUDFLARE_TUNNEL_TOKEN` (필요 시)
- `PUBLIC_DOMAIN=preciso-data.com`

## 실행 포트
- API: 8000
- Frontend: 3000
- Nginx: 80/443
