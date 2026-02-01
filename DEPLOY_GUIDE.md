# Preciso 배포 가이드 (Oracle Cloud)

## 현재 상황
- ✅ 로컬에서 수정 완료: BOM 문자 제거 + 확장 프로그램 충돌 방지 코드 추가
- ✅ 로컬 테스트 성공: `http://localhost:8004/debug.html` 정상 작동
- 🎯 목표: Oracle 서버에 배포하여 `https://preciso-data.com` 정상화

## 수정된 파일 목록
1. `app/ui/index.html` - BOM 제거 + 확장 프로그램 보호 코드
2. `app/ui/debug.html` - 새로 생성된 디버그 페이지
3. `app/main.py` - debug.html 라우트 추가

## 배포 방법

### 방법 1: SCP로 파일 업로드 (권장)

Oracle 서버 IP 주소를 확인하고 다음 명령을 실행하세요:

```powershell
# Oracle 서버 IP 주소 (preciso-data.com의 실제 IP)
$SERVER_IP = "172.67.143.202"  # 또는 실제 Oracle VM의 Public IP
$SERVER_USER = "ubuntu"  # 또는 opc

# 수정된 파일만 업로드
scp C:\Users\Administrator\Desktop\preciso\app\ui\index.html ${SERVER_USER}@${SERVER_IP}:/opt/preciso/app/ui/index.html
scp C:\Users\Administrator\Desktop\preciso\app\ui\debug.html ${SERVER_USER}@${SERVER_IP}:/opt/preciso/app/ui/debug.html
scp C:\Users\Administrator\Desktop\preciso\app\main.py ${SERVER_USER}@${SERVER_IP}:/opt/preciso/app/main.py

# 서버에서 서비스 재시작
ssh ${SERVER_USER}@${SERVER_IP} "sudo systemctl restart preciso"
```

### 방법 2: 전체 프로젝트 재배포

```powershell
# 전체 프로젝트 압축
cd C:\Users\Administrator\Desktop
Compress-Archive -Path preciso\* -DestinationPath preciso_update.zip -Force

# 서버로 전송
scp preciso_update.zip ${SERVER_USER}@${SERVER_IP}:/tmp/

# 서버에서 압축 해제 및 재시작
ssh ${SERVER_USER}@${SERVER_IP} @"
cd /opt/preciso
sudo systemctl stop preciso
unzip -o /tmp/preciso_update.zip
sudo systemctl start preciso
sudo systemctl status preciso
"@
```

### 방법 3: Git 사용 (프로젝트가 Git 저장소인 경우)

```bash
# 로컬에서 커밋
cd C:\Users\Administrator\Desktop\preciso
git add app/ui/index.html app/ui/debug.html app/main.py
git commit -m "Fix: Remove BOM characters and add extension conflict protection"
git push

# 서버에서 풀
ssh ${SERVER_USER}@${SERVER_IP} @"
cd /opt/preciso
git pull
sudo systemctl restart preciso
"@
```

## 배포 후 확인

1. **서비스 상태 확인**:
```bash
ssh ${SERVER_USER}@${SERVER_IP} "sudo systemctl status preciso"
```

2. **로그 확인**:
```bash
ssh ${SERVER_USER}@${SERVER_IP} "sudo journalctl -u preciso -f"
```

3. **Health Check**:
```bash
curl https://preciso-data.com/health
```

4. **브라우저 테스트**:
- https://preciso-data.com/debug.html
- https://preciso-data.com/

## Cloudflare 캐시 클리어

Cloudflare를 사용 중이므로 배포 후 캐시를 클리어해야 할 수 있습니다:

1. Cloudflare 대시보드 접속
2. preciso-data.com 도메인 선택
3. "Caching" → "Purge Cache" → "Purge Everything"

또는 API로:
```bash
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/purge_cache" \
  -H "Authorization: Bearer {cloudflare_api_token}" \
  -H "Content-Type: application/json" \
  --data '{"purge_everything":true}'
```

## 트러블슈팅

### 문제: 여전히 검은 화면
- Cloudflare 캐시 클리어
- 브라우저 캐시 클리어 (Ctrl+Shift+Delete)
- 시크릿 모드로 테스트

### 문제: 서비스 시작 실패
```bash
ssh ${SERVER_USER}@${SERVER_IP} "sudo journalctl -u preciso -n 50"
```

### 문제: Nginx 에러
```bash
ssh ${SERVER_USER}@${SERVER_IP} "sudo nginx -t"
ssh ${SERVER_USER}@${SERVER_IP} "sudo tail -f /var/log/nginx/error.log"
```

## 다음 단계

배포 완료 후:
1. ✅ https://preciso-data.com/debug.html 확인
2. ✅ https://preciso-data.com/ 메인 페이지 확인
3. ✅ 브라우저 콘솔에 에러 없는지 확인
