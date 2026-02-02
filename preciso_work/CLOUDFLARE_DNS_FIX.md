# Cloudflare DNS 설정 변경 가이드

## 🚨 현재 문제

**preciso-data.com**의 Cloudflare DNS가 HuggingFace Space를 가리키고 있어서, 
우리가 시작한 Cloudflare Tunnel이 작동하지 않습니다.

## 📋 해결 방법

### 방법 1: Cloudflare DNS 설정 변경 (권장)

1. **Cloudflare 대시보드 접속**:
   - https://dash.cloudflare.com 로그인

2. **preciso-data.com 도메인 선택**

3. **DNS 레코드 확인**:
   - DNS → Records 메뉴로 이동
   - 현재 설정 확인:
     ```
     Type: CNAME 또는 A
     Name: @ 또는 preciso-data.com
     Content: sdkfsklf-asura.hf.space (또는 IP 주소)
     ```

4. **DNS 레코드 수정**:
   - 기존 레코드 삭제 또는 수정
   - 새 CNAME 레코드 추가:
     ```
     Type: CNAME
     Name: @
     Content: 5a5103d3-b6cd-4702-ada9-b6558f326893.cfargotunnel.com
     Proxy status: Proxied (주황색 구름)
     ```

5. **저장 및 대기**:
   - DNS 전파까지 1-5분 소요

### 방법 2: 서브도메인 사용

메인 도메인 대신 서브도메인 사용:

1. **Cloudflare DNS에 새 레코드 추가**:
   ```
   Type: CNAME
   Name: app (또는 원하는 서브도메인)
   Content: 5a5103d3-b6cd-4702-ada9-b6558f326893.cfargotunnel.com
   Proxy status: Proxied
   ```

2. **Tunnel 설정 파일 수정**:
   - `cloudflare-config.yml` 파일 수정
   - hostname을 `app.preciso-data.com`으로 변경

3. **접속 URL**:
   ```
   https://app.preciso-data.com/
   ```

### 방법 3: 임시 테스트 (localhost 포트 직접 접속)

Cloudflare 설정 변경 전까지 로컬에서만 테스트:

```
http://localhost:8004/
http://localhost:8004/debug.html
```

## 🔍 현재 상태 확인

### DNS 현재 설정:
```
preciso-data.com → HuggingFace Space (sdkfsklf-asura.hf.space)
```

### Tunnel 대상:
```
Tunnel ID: 5a5103d3-b6cd-4702-ada9-b6558f326893
Target: localhost:8004 (Preciso 서버)
```

### 문제:
DNS가 Tunnel을 가리키지 않아서 HuggingFace Space가 표시됨

## ✅ 해결 후 확인

DNS 변경 후:

1. **DNS 전파 확인**:
   ```bash
   nslookup preciso-data.com
   ```

2. **브라우저 테스트**:
   ```
   https://preciso-data.com/
   ```

3. **캐시 클리어**:
   - Cloudflare: Purge Everything
   - 브라우저: Ctrl + Shift + Delete

## 📞 Cloudflare API로 DNS 변경 (고급)

API 토큰이 있다면:

```bash
# Zone ID와 Record ID 확인
curl -X GET "https://api.cloudflare.com/client/v4/zones" \
  -H "Authorization: Bearer YOUR_API_TOKEN"

# DNS 레코드 업데이트
curl -X PUT "https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}" \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "CNAME",
    "name": "@",
    "content": "5a5103d3-b6cd-4702-ada9-b6558f326893.cfargotunnel.com",
    "proxied": true
  }'
```

## 🎯 권장 조치

**가장 빠른 해결책**:

1. Cloudflare 대시보드에 로그인
2. DNS 레코드를 Tunnel CNAME으로 변경
3. 5분 대기
4. 브라우저 캐시 클리어 후 테스트

**또는**:

서브도메인 `app.preciso-data.com`을 사용하여 메인 도메인 설정을 건드리지 않고 테스트
