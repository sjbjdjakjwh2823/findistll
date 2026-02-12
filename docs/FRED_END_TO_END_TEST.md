# FRED API: End-to-End Pipeline Test (Preciso)

## 목적
FRED 키를 사용해 아래가 실제로 동작하는지 확인:
- 외부 데이터 fetch (FRED)
- 정규화(normalize) 결과에 `facts`가 생성되는지
- `ingest=true`로 `raw_documents`에 저장되는지
- (옵션) 이후 DataForge/HITL/WS8까지 이어지는지

## 사전 조건
- 백엔드가 Supabase 설정을 가지고 실행 중이어야 함
  - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- FRED 키가 다음 중 하나로 설정되어야 함:
  - 서버 환경변수 `FRED_API_KEY`
  - 또는 SDK UI에서 “External API Keys (Admin)”로 `fred` 등록
- Admin 보호 조건:
  - `ADMIN_API_TOKEN`을 서버에 설정했다면, 스모크 스크립트에도 동일 토큰을 env로 제공해야 함

## 빠른 확인 (UI)
1. `/sdkui` -> External API Keys (Admin)
2. provider=`fred`로 키 저장
3. Test 눌러 ok=true 확인
4. `Market Data`:
   - `GET /api/v1/market/fred/series?series_id=FEDFUNDS&limit=5&ingest=true`
   - 결과에 `doc_id`와 `facts`가 있는지 확인

## 빠른 확인 (CLI Smoke)
```bash
export PRECISO_BASE_URL=http://localhost:8000
export ADMIN_API_TOKEN=...            # 서버에 설정한 경우에만
python3 scripts/smoke_fred_pipeline.py
```

## 파이프라인 확장 검증 (권장)
- `raw_documents`에 저장된 doc_id를 대상으로:
  - generate/annotate/approval 경로를 수행
  - WS8 spoke A/B 산출물 생성 여부 확인

주의: 이 단계는 LLM 키(OpenAI 등)와 스케줄/큐가 필요할 수 있음.

