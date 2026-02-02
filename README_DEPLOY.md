# ✅ PRECISO 최종 배포 가이드

## 🎯 현재 상황

### ✅ 완료된 작업
1. **BOM 문자 제거** - CSS/JavaScript 파싱 오류 해결
2. **확장 프로그램 충돌 완전 차단** - evmAsk.js 에러 차단
3. **CSP 설정 추가** - Content Security Policy 보안 강화
4. **로컬 테스트 완료** - localhost:8004 정상 작동

### ⏳ 남은 작업
**Oracle Cloud Ubuntu 서버에 수정된 파일 배포**

---

## 🚀 배포 방법 (5-10분 소요)

### 📋 준비물
- ✅ SSH 키: `C:\Users\Administrator\Downloads\ssh-key-2026-01-30.key`
- ❓ Oracle 서버 IP: **확인 필요**

### 1단계: Oracle 서버 IP 확인

#### Oracle Cloud Console에서:
1. https://cloud.oracle.com 접속
2. **Compute** → **Instances** 메뉴
3. Preciso 서버 인스턴스 선택
4. **Public IP Address** 확인 (예: 140.238.123.45)

### 2단계: 자동 배포 스크립트 실행

PowerShell에서 실행:

```powershell
cd C:\Users\Administrator\Desktop\preciso

# 서버 IP를 입력하면 자동 배포
powershell -ExecutionPolicy Bypass -File deploy-to-oracle.ps1
```

스크립트가 자동으로:
1. 3개 파일 업로드 (index.html, debug.html, main.py)
2. Preciso 서비스 재시작
3. 상태 확인

### 3단계: 테스트

브라우저에서:
1. **캐시 클리어**: `Ctrl + Shift + Delete`
2. **접속**: https://preciso-data.com/
3. **강제 새로고침**: `Ctrl + F5`

---

## 🛠️ 수동 배포 (스크립트 실패 시)

### 파일 업로드:
```powershell
$IP = "YOUR_ORACLE_IP"  # 실제 IP로 변경
$KEY = "C:\Users\Administrator\Downloads\ssh-key-2026-01-30.key"

scp -i $KEY C:\Users\Administrator\Desktop\preciso\app\ui\index.html ubuntu@${IP}:/opt/preciso/app/ui/index.html

scp -i $KEY C:\Users\Administrator\Desktop\preciso\app\ui\debug.html ubuntu@${IP}:/opt/preciso/app/ui/debug.html

scp -i $KEY C:\Users\Administrator\Desktop\preciso\app\main.py ubuntu@${IP}:/opt/preciso/app/main.py
```

### 서비스 재시작:
```powershell
ssh -i $KEY ubuntu@${IP}
sudo systemctl restart preciso
sudo systemctl status preciso
```

---

## ✅ 배포 후 확인사항

### 1. 서비스 상태
```bash
ssh -i $KEY ubuntu@$IP "sudo systemctl status preciso"
```

### 2. 로그 확인
```bash
ssh -i $KEY ubuntu@$IP "sudo journalctl -u preciso -n 50"
```

### 3. 웹 테스트
```
https://preciso-data.com/
https://preciso-data.com/debug.html
https://preciso-data.com/health
```

### 4. 브라우저 콘솔 확인 (F12)
**정상:**
- `[Preciso] Blocked ethereum redefinition` (정상 메시지)
- evmAsk.js 에러 **없음**
- CSP 에러 **없음**

**비정상:**
- evmAsk.js 에러 계속 발생 → 캐시 클리어 다시
- 검은 화면 → 배포 확인 필요

---

## 📊 시스템 구조

```
Windows PC (로컬 개발)
    ↓
    ↓ SSH/SCP (파일 배포)
    ↓
Oracle Cloud Ubuntu Server
    ├─ Nginx (리버스 프록시)
    ├─ Preciso Service (uvicorn:8004)
    └─ 수정된 파일:
        ├─ app/ui/index.html
        ├─ app/ui/debug.html
        └─ app/main.py
    ↓
Cloudflare (보안/CDN)
    ↓
preciso-data.com (외부 사용자)
```

---

## 🔍 트러블슈팅

### 문제: SSH 접속 안됨
```powershell
# 키 권한 확인 (Git Bash에서)
chmod 600 ~/Downloads/ssh-key-2026-01-30.key

# 또는 다른 사용자명 시도
ssh -i $KEY opc@$IP  # ubuntu 대신 opc
```

### 문제: 파일 업로드 실패
```bash
# 서버에서 권한 확인
ssh -i $KEY ubuntu@$IP
ls -la /opt/preciso/app/ui/
sudo chown -R ubuntu:ubuntu /opt/preciso
```

### 문제: 서비스 재시작 실패
```bash
# 로그 확인
sudo journalctl -u preciso -n 100

# 수동 실행 테스트
cd /opt/preciso
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

### 문제: 여전히 검은 화면
1. Cloudflare 캐시 클리어
   - https://dash.cloudflare.com
   - Caching → Purge Everything
2. 브라우저 캐시 클리어
3. 시크릿 모드로 테스트
4. 서버 로그 확인

---

## 📝 체크리스트

- [ ] Oracle 서버 IP 확인
- [ ] SSH 키 경로 확인
- [ ] 배포 스크립트 실행
- [ ] 파일 업로드 성공 확인
- [ ] Preciso 서비스 재시작
- [ ] 서비스 상태 확인 (active/running)
- [ ] Cloudflare 캐시 클리어
- [ ] 브라우저 캐시 클리어
- [ ] https://preciso-data.com 테스트
- [ ] F12 콘솔에서 에러 확인
- [ ] 정상 작동 확인

---

## 🎉 성공 시 예상 결과

### 브라우저:
- ✅ Palantir 스타일 다크 콘솔
- ✅ "PRECISO / DECISION CONSOLE" 헤더
- ✅ 왼쪽 네비게이션 메뉴
- ✅ Case Intake 폼

### 콘솔 (F12):
- ✅ `[Preciso] Blocked ethereum redefinition`
- ✅ evmAsk.js 에러 없음
- ✅ CSP 에러 없음

---

## 🚀 빠른 시작

```powershell
# 1. Oracle IP 확인 (Oracle Cloud Console)
# 2. 배포 스크립트 실행
cd C:\Users\Administrator\Desktop\preciso
powershell -ExecutionPolicy Bypass -File deploy-to-oracle.ps1

# 3. IP 입력 후 대기
# 4. 브라우저에서 테스트
```

---

**작업 시간**: 2026-02-01 16:06 KST
**다음 단계**: Oracle 서버 IP 확인 → 배포 스크립트 실행 → 테스트

---

# macOS Quick Start (Reproducible)

## One-time setup
```bash
cd /path/to/findistll
bash scripts/setup_mac.sh
bash scripts/install_cloudflared_mac.sh
```

## Secrets
```bash
cp .env.example .env
# Fill in values in .env
```

## Run
```bash
bash scripts/run_mac.sh
```

## Docs
- `SETUP_MAC.md`
- `RUN_MAC.md`
- `DEPLOY_MAC.md`
