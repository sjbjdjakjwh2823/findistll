# Preciso Mathmatics 적용/품질 보고 (2026-02-08)

## 요약
- `PrecisoMathematicsService`를 통합 변환 엔진(`UnifiedConversionEngine`)에 연결했고, PDF/HTML 변환 품질을 실제 파일로 재검증했다.
- Gemini Vision 경로는 API 쿼터(`429 limit: 0`) 때문에 활성화되지 않아, 로컬 테이블 추출 강화로 품질을 보완했다.

## 변경 사항(핵심)
- PDF 로컬 테이블 추출 강화(`pdfplumber` 기반)
  - `vendor/findistill/services/unstructured_parser.py`
- PDF 다열(최대 3열) 컬럼 매핑 및 연도 헤더 감지
  - `vendor/findistill/services/unstructured_parser.py`
- HTML 테이블 추출 개선(pandas 제거, `bs4 + lxml` 파서 + `in millions` 스케일링 적용)
  - `vendor/findistill/services/unstructured_parser.py`
- `.pdf` 확장자지만 실제 PDF가 아닌(HTML 등) 입력을 PDF로 오인하지 않도록 매직바이트(`%PDF`) 검사 추가
  - `vendor/findistill/services/unstructured_parser.py`
- `reasoning_qa`가 비어도 JSONL export가 전체 파이프라인을 실패시키지 않도록 폴백 추가
  - `vendor/findistill/services/exporter.py`
- `reasoning_qa`가 비어도 `tables`를 결과에 포함하도록 반환 보강
  - `vendor/findistill/services/ingestion.py`
- `period_norm` 추가(시계열 계산 표준화)
  - `app/services/unified_engine.py`
  - `app/services/preciso_mathematics.py`
- Gemini SDK 마이그레이션(google.genai) 적용
  - `vendor/findistill/services/ingestion.py`
  - `vendor/findistill/services/unstructured_parser.py`

## 의존성 변경
- `requirements.txt`에 추가
  - `google-generativeai` (Gemini SDK, 현재 deprecated 경고 있음)
  - `pdfplumber` (PDF 테이블 추출)

## 테스트 결과(지정 PDF)
- 입력 PDF
  - `/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/10-Q4-2024-As-Filed.pdf`
- 실행 스크립트
  - `/Users/leesangmin/.openclaw/workspace/preciso/scripts/run_mathmatics_pdf.py`
- 결과 요약
  - `fact_count`: 204
  - `table_count`: 6
  - `mathematics.derived_keys`: 50
- 아티팩트
  - `/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/out/summary.json`
  - `/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/out/facts_sample.json`
  - `/Users/leesangmin/.openclaw/workspace/preciso/artifacts/mathmatics/out/math_derived_sample.json`

## 테스트 결과(다른 파일 타입)
- 배치 실행 스크립트
  - `/Users/leesangmin/.openclaw/workspace/preciso/scripts/run_unified_batch.py`
- 샘플 결과(요약)
  - CSV: facts 14, tables 3, math derived 6
  - XLSX: facts 10, tables 2, math derived 5
  - XBRL(XML): facts 505, tables 3, math derived 85, visibility graph 5
  - HTML(NVIDIA 샘플): facts 12, tables 2, math derived 5
- 아티팩트(예)
  - `/Users/leesangmin/.openclaw/workspace/preciso/artifacts/unified_batch/2026-02-08_v3/`
  - `/Users/leesangmin/.openclaw/workspace/preciso/artifacts/unified_batch/2026-02-08_v5/`

## 남은 리스크/개선 포인트
- Gemini Vision 사용 불가(현재 프로젝트 쿼터가 0) 상태라, 스캔 PDF/복잡 레이아웃은 로컬 OCR/테이블 재구성의 한계가 남아있다.
- PDF 3개년도 컬럼(2024/2023/2022 등) 매핑을 더 정확히 하기 위한 컬럼-연도 정합 로직이 필요하다.
- `google.generativeai` SDK는 deprecated라 `google.genai`로 교체하는 마이그레이션 계획이 필요하다.
  - 마이그레이션은 완료했으나, **쿼터(FreeTier limit: 0) 문제는 계정/프로젝트 설정 문제**라 코드로 해결 불가.
