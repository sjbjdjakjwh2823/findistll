# WS8 Spoke A/B “실사용” 구현 보고서 (코드 반영 완료)

## 구현 범위
- WS8. Spoke A/B 실사용(Downstream Consumption) 플랜(v1.1) 기준으로 **승인 이벤트 → Spoke A(JSONL) 생성 + Spoke B(Parquet) 생성 → 다운로드 API 제공**까지 연결.
- 기존 로직은 최대한 유지하고, WS8 기능은 **비침투적(non-blocking)**으로 추가했다(실패해도 승인/HITL 동작은 계속 진행).

## 핵심 결과
- HITL 승인/수정 승인 시점에:
  - `spoke_a_samples`에 SFT JSONL 레코드가 누적된다(품질 게이트 결과 포함).
  - `spoke_b_artifacts`에 `facts|tables|features` Parquet 바이트가 저장된다(MVP: base64 DB 저장).
- 관리 API:
  - Dataset versions 생성/조회/봉인(seal)
  - Dataset version별 Spoke A 샘플 조회 및 `candidate`만 JSONL 다운로드
  - Spoke B artifacts 다운로드
- 테스트:
  - 기존 테스트 깨짐(Spoke C 평가 타입 불일치)을 “호환 레이어”로 복구
  - WS8 전용 유닛 테스트 추가
  - `pytest` 전체 통과

## 변경 파일(주요)
- Spoke C 테스트 호환 레이어:
  - `app/services/spoke_c_rag.py`
- WS8 서비스(품질 게이트, Parquet 생성, 저장):
  - `app/services/spoke_ab_service.py`
- WS8 API:
  - `app/api/v1/datasets.py`
  - `app/api/v1/quant.py`
- 승인(approval) 플로우 WS8 연동:
  - `app/api/v1/approval.py`
  - 수정: 잘못된 `distill = DecisionResult` 대입 제거, 누락 import 보강
- DataForge HITL 승인 이벤트 WS8 연동:
  - `app/api/v1/annotate.py`
- Supabase 스키마:
  - `supabase_ws8_spoke_ab.sql` (신규)
  - `supabase_bootstrap_preciso.sql` (WS8 테이블 섹션 추가)
- WS8 테스트:
  - `tests/test_ws8_spoke_ab.py`

## Supabase 적용(필수)
WS8 기능이 Supabase에서 정상 동작하려면 아래 SQL을 Supabase SQL Editor에 적용해야 한다.
- 파일: `supabase_ws8_spoke_ab.sql`
- 포함 테이블:
  - `dataset_versions`
  - `spoke_a_samples`
  - `spoke_b_artifacts`

중요:
- Preciso는 tenant-aware client를 사용하므로, 위 테이블들에 `tenant_id` 컬럼이 반드시 필요하다(이미 DDL에 포함).

## 품질 게이트(현재 MVP)
`app/services/spoke_ab_service.py`
- Self-check score: `>= 0.70`
- Evidence count: `>= 2` (현재 DataForge 경로는 placeholder evidence를 넣음)
- Weak supervision noise: `<= 0.35`
- Data quality: `>= 0.70`
- Numeric preservation(중요): output의 숫자 토큰이 facts에서 재현되는지(현재는 보수적 휴리스틱)

## 사용 방법(로컬/서버)
1. Supabase에 `supabase_ws8_spoke_ab.sql` 적용
2. DataForge 문서 추출:
  - `/api/v1/extract`
3. 생성:
  - `/api/v1/generate`
4. HITL 승인/수정 승인:
  - `/api/v1/annotate/submit` (`action=approved|corrected`)
5. Dataset 확인/다운로드:
  - `/api/v1/datasets/versions`
  - `/api/v1/datasets/versions/{id}/download`
6. Spoke B 다운로드:
  - `/api/v1/quant/artifact?doc_id=...&kind=facts|tables|features`

## 알려진 한계(다음 개선 후보)
- DataForge 경로에서 Spoke C 실제 `chunk_id` 참조 무결성은 아직 “placeholder” 수준.
  - 다음 단계: UnifiedConversionEngine의 `spokes["rag_contexts"]`를 저장/인덱싱하고, WS8의 `evidence_chunk_ids`를 그 chunk_id로 연결.
- Spoke B artifacts 저장을 DB(base64)로 했기 때문에 대용량 문서는 비용/성능 이슈가 생길 수 있음.
  - 다음 단계: Supabase Storage/S3로 이전 + DB에는 pointer만 저장.

## 테스트 결과
- `pytest` 전체 통과(WS8 신규 테스트 포함).

## 노션 업데이트 상태
- 현재 Codex의 Notion MCP가 `Auth required`로 막혀 있어 자동 업로드는 불가.
- 이 보고서 내용을 Notion의 “📘 Preciso Master Plan” 하위에 붙여넣으면 된다.

