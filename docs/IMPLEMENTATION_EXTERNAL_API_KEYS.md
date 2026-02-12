# 외부 API 키 등록 UI (SDK UI) 구현 보고서

## 목표
- 운영자가 기업 배포형 Preciso UI(`sdkui`)에서 외부 데이터 제공자 API 키를 등록할 수 있게 함
- 등록된 키를 사용해 외부 데이터가 들어오면, Preciso 파이프라인으로 처리되도록 연결

## 구현 내용
### 1) DB 테이블 (암호문 저장)
- `integration_secrets`
  - `ciphertext`에 Fernet 토큰 저장(평문 저장 없음)
  - UI 노출용 `hint`(예: `...abcd`)
  - `revoked_at`, `last_tested_at`, `last_test_status`

SQL:
- `supabase_integration_secrets.sql`
- `supabase_bootstrap_preciso.sql`에 포함 및 `tenant_id` 인덱싱 추가

### 2) 백엔드 Admin API
- `GET /api/v1/admin/integrations/keys`
- `POST /api/v1/admin/integrations/keys` (provider + api_key 저장)
- `DELETE /api/v1/admin/integrations/keys/{provider}` (폐기)
- `POST /api/v1/admin/integrations/test/{provider}` (연결 테스트)

보호:
- `ADMIN_API_TOKEN`(헤더 `X-Admin-Token`) 또는 `RBAC_ENFORCED=1` + role=admin

### 3) Market 데이터 처리 연결
- `MarketDataService`가 env 키가 없으면 DB 등록 키를 폴백으로 사용하도록 개선
- Market API에서 요청 단위로 DB를 전달하여 등록 키를 사용할 수 있게 함

### 4) 프론트엔드(sdkui) UI
- `/sdkui`에 “External API Keys (Admin)” 섹션 추가
  - provider 선택
  - key 저장(저장 후 입력값 비움)
  - 등록된 키 목록(힌트/상태만)
  - 테스트 및 revoke

## 환경변수
- `INTEGRATION_KEYS_MASTER_KEY` (필수, Fernet key)
  - 예: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

## 테스트
- `pytest -q`: 통과(cryptography 미설치 환경 대비 일부 테스트 skip)
- `web/ npm run build`: 통과

## 파일/경로
- 백엔드
  - `app/api/v1/admin_integrations.py`
  - `app/services/secret_store.py`
  - `app/services/integration_keys.py`
  - `app/services/market_data.py`
  - `app/api/v1/market.py`
- 프론트
  - `web/app/sdkui/page.tsx`
- SQL
  - `supabase_integration_secrets.sql`

