# 외부 API 키 등록 UI 및 데이터 처리 플랜 (Preciso)

## 목표
- 기업 배포형 Preciso에서 운영자가 UI로 외부 데이터 제공자 API 키를 등록/회전/폐기할 수 있게 한다.
- 등록된 키로 유입되는 데이터(시장/거시/공시)를 Preciso 파이프라인(`raw_documents -> UnifiedConversionEngine -> HITL -> WS8`)에 일관되게 태운다.

## 범위 (v1)
- 외부 키 관리 대상(Provider): `finnhub`, `fred`, `fmp`, `sec` (추가: `gemini`, `openai`는 현황 표시/저장만)
- UI: `sdkui` 내 “External API Keys (Admin)” 섹션
- 백엔드: Admin API + 암호화 저장 + MarketDataService에서 env 미설정 시 DB 등록 키를 사용
  - FRED 엔드포인트 추가로 실제 파이프라인 유입 경로 보장:
    - `GET /api/v1/market/fred/series`
    - `GET /api/v1/market/fred/key-rates`

## 설계 원칙
- 키는 절대 프론트에 평문 저장하지 않는다(화면 입력값은 저장 후 즉시 비움).
- DB에는 암호문만 저장(`ciphertext`), UI에는 안전한 힌트만 노출(`...abcd`).
- 운영 안전장치: Admin 토큰 또는 RBAC admin 없이 키를 등록할 수 없다.
- 기존 동작(환경변수 기반)은 유지하고, “등록 키”는 폴백 경로로 추가한다.

## 아키텍처
1. UI(`/sdkui`)에서 운영자가 provider + api_key 입력
2. 백엔드 Admin API가 `INTEGRATION_KEYS_MASTER_KEY`로 암호화(Fernet) 후 `integration_secrets`에 저장
3. Market API 호출 시:
   - 우선순위: `ENV(FRED_API_KEY/FINNHUB_API_KEY/...)` -> `DB(integration_secrets)` 순으로 키 해석
4. 성공적으로 fetch한 payload는 기존 로직대로 `normalize_market_snapshot(...)`로 정규화 가능
5. 선택적으로 `ingest=true` 시 `raw_documents`로 저장되어 DataForge/HITL/WS8 경로로 이어짐

## 운영 플로우 (사용자 관점)
- 1) `/sdkui` 접속
- 2) `ADMIN_API_TOKEN` 입력(또는 RBAC admin)
- 3) External API Keys에서 provider 선택 후 key 저장
- 4) “Test”로 연결 확인
- 5) `/api/v1/market/*?ingest=true`로 데이터 유입 확인
- 6) DataForge(/dataforge)에서 큐/리뷰 흐름으로 이어지는지 확인

## 품질/감사(Audit) 포인트
- 키 자체는 감사 로그/DB 어디에도 평문으로 남기지 않는다.
- 키 저장/폐기 이벤트는 향후 `audit_logs`에 action으로 남기는 확장 포인트(WS: Security Hardening).

## 다음 확장 (v1.1)
- “Scheduled ingestion” (크론/워크커)로 시장데이터 주기 수집
- Provider별 표준화(단위/통화/스케일) 룰 강화 및 Spoke B facts/features 자동 생산
- 사용자/팀 단위 키(권한/스코프) 분리 (현재는 tenant 단위 admin만)
 - Market fetch 결과 캐시(동일 series/symbol 요청 폭주 방지)
 - Provider별 Rate limit/Retry/Backoff 정책 표준화
