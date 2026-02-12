# FRED 파이프라인 테스트 보고 + 보완 플랜

## 테스트 목표
- FRED API 키를 사용해 Preciso의 “외부 키 등록 -> 데이터 fetch -> 정규화 -> ingest” 경로가 정상 동작하는지 확인
- 실패/취약 지점을 파악하고 보완 항목을 코드로 반영

## 테스트 결과 요약
### 1) 외부 키 등록
- `sdkui`(또는 Admin API)로 `fred` 키를 등록 가능
- 현재 Supabase 테이블이 부트스트랩되지 않은 상태에서는 DB 저장 대신 **로컬 암호화 스토어**로 폴백됨
  - 저장 위치: `artifacts/integration_secrets.json`
  - 평문 저장 없음(암호문 `ciphertext`만 저장)

### 2) 실제 FRED 호출
- `POST /api/v1/admin/integrations/test/fred` 결과 `ok=true` 확인(실제 FRED API 응답 수신)

### 3) FRED series 정규화
- `GET /api/v1/market/fred/series?series_id=FEDFUNDS&limit=...`
- `facts` 생성 확인
  - `normalized_value`가 숫자 문자열로 유지됨
  - `evidence.document_id=fred:{series_id}:{date}`로 안정적 라인리지 확보

### 4) ingest(파이프라인 유입)
- `ingest=true` 시 Supabase `raw_documents`에 저장하는 것이 1차 목표
- 현재 Supabase에 `raw_documents` 테이블이 없어서 DB ingest는 실패하는 상태였음
- 보완: DB ingest 실패 시 **로컬 JSONL 폴백 저장**으로 전환하도록 구현
  - 저장 위치: `artifacts/market_ingest_fallback.jsonl`
  - 응답 `doc_id`는 `local_*` 형식

## 보완 작업(이미 반영된 코드)
- Market fetch: 캐시/리트라이/타임아웃/동시성 제어 추가
  - env: `MARKET_FETCH_CACHE_TTL_S`, `MARKET_FETCH_RETRIES`, `MARKET_FETCH_TIMEOUT_S`, `MARKET_FETCH_CONCURRENCY`
- FRED 정규화: 결측값(`.`) 제거, `evidence.document_id` 부여, unit 매핑 개선
- ingest 실패 시 로컬 폴백 저장 추가
- audit 로그 테이블이 없어도 서버가 죽지 않도록 audit logger 폴백 버퍼 추가

## 남은 핵심 과제(“전체 파이프라인 완전 가동”을 위한 필수)
### A) Supabase 부트스트랩 적용
현 Supabase 프로젝트에 다음 SQL을 적용해야 DataForge/WS8 전체가 DB 기반으로 정상 동작:
- `supabase_bootstrap_preciso.sql`

적용 후 확인 체크:
- `raw_documents`, `generated_samples`, `human_annotations`, `audit_logs` 등이 존재해야 함
- 그 다음 `ingest=true`가 DB에 저장되며, generate/annotate/WS8까지 이어짐

### B) 폴백 데이터의 “DB 복구(import)” 경로
현재 로컬 폴백(`market_ingest_fallback.jsonl`)은 운영 복구를 위해 다음 기능 추가를 권장:
- local JSONL -> raw_documents bulk import 스크립트
- 중복 방지(file_hash/series_id+date 기반)

### C) 스케줄 수집(운영용)
- `scripts/scheduled_market_ingest.py`로 주기 수집 실행(once/loop)
- 추후 Worker/Queue로 이관(서버 프로세스와 분리)

