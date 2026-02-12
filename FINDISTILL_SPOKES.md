# Findistill 엔진 및 Spoke A~E 구현 상세 (Preciso 코드 기준)

작성 기준 경로: `C:\Users\Administrator\Desktop\preciso`

## 1. 전체 파이프라인 흐름 (입력 -> 출력)

### 진입점
- 파일: `C:\Users\Administrator\Desktop\preciso\app\services\distill_engine.py`
- 클래스: `FinDistillAdapter`

### 입력
`document` 딕셔너리 필드:
- `filename` (기본값 `document.txt`)
- `mime_type` (기본값 `text/plain`)
- `file_bytes` 또는 `content_base64` 또는 `content`
- `source`, `doc_id` (메타)

### 처리 흐름
1) `ingestion_service.process_file(file_bytes, filename, mime_type)`
2) `normalizer.normalize(extracted)`
3) `facts`, `reasoning_qa`, `jsonl_data` 추출
4) `cot_markdown` 생성:
   - `jsonl_data` 있으면 줄바꿈으로 합침
   - 없으면 `reasoning_qa.response` 합침

### 출력
- `DistillResult` (facts, cot_markdown, metadata)


## 2. Spoke별 상세

### Spoke A (CoT + Scenario)
- 코드 위치: `C:\Users\Administrator\Desktop\preciso\vendor\findistill\services\xbrl_semantic_engine.py`
- 입력: `SemanticFact` 리스트
- 출력:
  - `reasoning_qa` (Q/A)
  - `jsonl_data` (JSONL)

#### 핵심 수학/로직
- YoY 성장률:
  - `Growth = (CY - PY) / |PY| * 100`
- 산업별 민감도 베타(β_ir):
  - 업종별 고정값 (Automotive/Industrial/Aerospace=2.4, Tech/IT=0.8, Financial=-1.5 등)
- 시나리오 시뮬레이션:
  - Automotive/Industrial/Aerospace + NetIncome일 때
  - `NetIncome_shock = CY * 0.85` (유가 +20% 가정)

#### PY 데이터 없을 때
- Dynamic Industry Proxy로 PY 추정:
  - `PY = CY / growth_factor` (업종별 고정 성장률)


### Spoke B (Confidence / Quant Meta)
- 코드 위치:
  - `C:\Users\Administrator\Desktop\preciso\vendor\findistill\services\xbrl_semantic_engine.py`
  - `C:\Users\Administrator\Desktop\preciso\vendor\findistill\services\runtime_manager.py`
- 입력: `raw_val` 문자열, 단위, 컨텍스트
- 출력: `confidence_score`, `tags`

#### 핵심 수학/로직
- Billion 단위 고정:
  - `normalized = raw / 1e9`
- Trillion 이상치 보정:
  - `abs(normalized) > 1000`이면 `normalized /= 1000` 반복
- Micro-scale 보정:
  - `0 < |normalized| < 0.0001`이면 `normalized *= 1000`
- Confidence 필터:
  - `score < 0.5`는 low-confidence로 분리

#### Geo-Quant
- `geo_sentiment` 필드만 정의되어 있음
- 실제 계산 로직은 코드에 없음


### Spoke C (RAG / Hybrid Flow)
- 코드 위치: `C:\Users\Administrator\Desktop\preciso\vendor\findistill\services\ingestion.py`
- 입력: 파일 바이트, MIME
- 출력: facts, reasoning_qa, jsonl_data, tables

#### 처리 우선순위 (Hybrid Flow)
- XBRL -> iXBRL -> PDF -> CSV
- iXBRL facts 없으면 Unstructured HTML로 fallback

#### RAG 관련
- DB 테이블 정의 있음: `spoke_c_rag_context`
  - `C:\Users\Administrator\Desktop\preciso\supabase_spokes.sql`
- 실제 RAG 저장/연동 로직 구현됨: Spoke C context 저장 + Retrieval API + 인과 체인 응답


### Spoke D (Graph)
- Graph 처리 로직 구현됨: Spoke D graph 저장 + causal chain 구성


### Spoke E
- 코드 내 구현 없음
- `ai_training_sets` 테이블만 존재
  - `C:\Users\Administrator\Desktop\preciso\supabase_spokes.sql`


## 3. 주요 수학/정규화 요약

### ScaleProcessor (xbrl_semantic_engine.py)
- 기본: Billion 단위 고정
- 이상치 보정: Trillion 오류 자동 교정
- Micro-scale 보정

### Arithmetic Self-Healing
- CAL 규칙으로 부모/자식 합산 비교
- 스케일 차이가 크면 자동 보정

### YoY 공식
- `(CY - PY) / |PY| * 100`

### Dynamic Industry Proxy
- 업종별 성장률 테이블로 PY 역산


## 4. DB Spoke 테이블 (Supabase)
- `spoke_a_strategy`
- `spoke_b_quant_meta`
- `spoke_c_rag_context`
- `spoke_d_graph`
- `ai_training_sets`
- 파일: `C:\Users\Administrator\Desktop\preciso\supabase_spokes.sql`
