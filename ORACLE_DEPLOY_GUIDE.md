# Oracle Cloud Ubuntu 서버 배포 가이드

## 🎯 목표
로컬에서 수정한 파일을 Oracle Cloud Ubuntu 서버에 배포하여
preciso-data.com이 정상 작동하도록 함

## 📋 배포할 파일
1. app/ui/index.html (BOM 제거 + 확장 프로그램 보호 + CSP)
2. app/ui/debug.html (디버그 페이지 + 보호 코드)
3. app/main.py (debug.html 라우트 추가)

## 🔑 필요한 정보
- Oracle 서버 IP 주소
- SSH 사용자명 (보통 ubuntu 또는 opc)
- SSH 키 또는 비밀번호

## 🚀 배포 방법

### 방법 1: SCP로 파일 업로드 (권장)

#### 1단계: Oracle 서버 정보 확인
Oracle Cloud Console에서:
- Compute → Instances → preciso 서버 선택
- Public IP 주소 확인 (예: 140.238.123.45)

#### 2단계: SSH 키 확인
SSH 키 위치 확인:
```powershell
# 일반적인 위치
C:\Users\Administrator\.ssh\id_rsa
# 또는 Oracle Cloud에서 다운로드한 키
C:\Users\Administrator\Downloads\ssh-key-*.key
```

#### 3단계: 파일 업로드
```powershell
# 변수 설정 (실제 값으로 변경)
$SERVER_IP = "YOUR_ORACLE_SERVER_IP"
$SSH_KEY = "C:\Users\Administrator\.ssh\id_rsa"  # 또는 실제 키 경로
$USER = "ubuntu"  # 또는 opc

# 파일 업로드
scp -i $SSH_KEY C:\Users\Administrator\Desktop\preciso\app\ui\index.html ${USER}@${SERVER_IP}:/opt/preciso/app/ui/index.html

scp -i $SSH_KEY C:\Users\Administrator\Desktop\preciso\app\ui\debug.html ${USER}@${SERVER_IP}:/opt/preciso/app/ui/debug.html

scp -i $SSH_KEY C:\Users\Administrator\Desktop\preciso\app\main.py ${USER}@${SERVER_IP}:/opt/preciso/app/main.py
```

#### 4단계: 서버 재시작
```powershell
# SSH 접속
ssh -i $SSH_KEY ${USER}@${SERVER_IP}

# 서버에서 실행:
sudo systemctl restart preciso
sudo systemctl status preciso
```

### 방법 2: 전체 프로젝트 압축 업로드

```powershell
# 로컬에서 압축
cd C:\Users\Administrator\Desktop
Compress-Archive -Path preciso\app -DestinationPath preciso_app_update.zip -Force

# 서버로 전송
scp -i $SSH_KEY preciso_app_update.zip ${USER}@${SERVER_IP}:/tmp/

# SSH 접속
ssh -i $SSH_KEY ${USER}@${SERVER_IP}

# 서버에서 실행:
cd /opt/preciso
sudo systemctl stop preciso
unzip -o /tmp/preciso_app_update.zip
sudo systemctl start preciso
sudo systemctl status preciso
```

### 방법 3: Git 사용 (저장소가 있는 경우)

```bash
# 로컬에서 커밋 & 푸시
cd C:\Users\Administrator\Desktop\preciso
git add app/ui/index.html app/ui/debug.html app/main.py
git commit -m "Fix: Remove BOM, add extension protection, add CSP"
git push origin main

# 서버에서 풀
ssh -i $SSH_KEY ${USER}@${SERVER_IP}
cd /opt/preciso
git pull origin main
sudo systemctl restart preciso
```

## 🔍 배포 후 확인

### 1. 서비스 상태 확인
```bash
ssh ${USER}@${SERVER_IP}
sudo systemctl status preciso
```

### 2. 로그 확인
```bash
sudo journalctl -u preciso -f
```

### 3. 웹 테스트
```bash
curl http://localhost:8004/health
```

### 4. 브라우저 테스트
```
https://preciso-data.com/
https://preciso-data.com/debug.html
```

## 🛠️ 트러블슈팅

### 문제: SSH 접속 안됨
```powershell
# SSH 키 권한 확인 (Git Bash 또는 WSL에서)
chmod 600 ~/.ssh/id_rsa

# 또는 비밀번호로 접속
ssh ${USER}@${SERVER_IP}
```

### 문제: 파일 권한 에러
```bash
# 서버에서 실행
sudo chown -R ubuntu:ubuntu /opt/preciso
sudo chmod -R 755 /opt/preciso
```

### 문제: 서비스 재시작 실패
```bash
# 로그 확인
sudo journalctl -u preciso -n 50

# 수동 실행 테스트
cd /opt/preciso
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
```

## 📊 현재 구조

```
Windows PC (로컬)
    ↓ (수정한 파일)
    ↓ SCP/Git
    ↓
Oracle Cloud Ubuntu Server
    ↓ (Nginx + Preciso 서비스)
    ↓
Cloudflare (보안/프록시)
    ↓
preciso-data.com (외부 사용자)
```

## ✅ 체크리스트

- [ ] Oracle 서버 IP 주소 확인
- [ ] SSH 키 또는 비밀번호 확인
- [ ] 파일 업로드 (SCP 또는 Git)
- [ ] Preciso 서비스 재시작
- [ ] 서비스 상태 확인
- [ ] https://preciso-data.com 테스트
- [ ] 브라우저 캐시 클리어
- [ ] 정상 작동 확인

## 🎯 다음 단계

1. Oracle Cloud Console에서 서버 IP 확인
2. SSH 키 위치 확인
3. 위의 배포 방법 중 하나 선택
4. 파일 업로드 및 서비스 재시작
5. 브라우저에서 테스트

## 💡 빠른 배포 스크립트

아래 정보를 입력하면 자동 배포 스크립트를 만들어드립니다:
- Oracle 서버 IP: ?
- SSH 키 경로: ?
- SSH 사용자명: ubuntu 또는 opc?
