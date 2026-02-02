# Preciso: End-to-End Technical Implementation Spec

기존 Preciso의 코드를 보존하면서, 로드맵의 B2B 툴킷 비전을 달성하기 위한 **엔드투엔드(End-to-End) 기술 구현 상세안**입니다.

---

## 1. Modular Pipeline Architecture (Orchestrator v2)
기존 `Orchestrator.run`을 확장하여 비동기 작업 및 단계별 검증 레이어를 추가합니다.

### 1.1 `app/services/toolkit.py` (신규)
각 엔진을 독립적인 B2B API로 노출하기 위한 인터페이스입니다.
```python
class PrecisoToolkit:
    """B2B용 툴킷 인터페이스"""
    async def process_raw_document(self, doc_bytes): # FinDistill 전용
        pass
    async def get_causal_prediction(self, graph_context): # Spoke E 전용
        pass
```

### 1.2 `app/services/orchestrator.py` 확장
- **Async Workflow**: 대용량 문서 처리를 위한 `background_tasks` 연동.
- **Audit Logging**: 모든 단계에서 `db.save_audit_event()` 호출.

---

## 2. Spoke E (The Oracle) 기술 구현
Pillar 2 & 3를 실제 예측 엔진으로 구현합니다.

### 2.1 `app/services/oracle.py` (신규)
- **PC 알고리즘**: 상관관계 필터링 로직.
- **Counterfactual Engine**: 유저가 특정 변수를 조정했을 때 그래프 가중치를 재계산하는 시뮬레이터.
```python
class OracleEngine:
    def simulate_what_if(self, node_id: str, value_delta: float):
        # Spoke D의 Temporal Edge 가중치를 사용하여 파급력 계산
        pass
```

---

## 3. High-End UI/UX (Frontend Specs)
팔란티어와 스케일 AI의 강점을 결합한 프론트엔드 기술 스택입니다.

### 3.1 기술 스택
- **Framework**: Next.js 14 (App Router)
- **State Management**: Zustand (실시간 에이전트 상태 관리)
- **Visualization**: 
  - **Graph**: React Force Graph (3D 모드 지원)
  - **Timeline**: Framer Motion (부드러운 마이크로 애니메이션)

### 3.2 핵심 컴포넌트 설계
- **Decision Matrix Component**: 에이전트의 CoT를 '카드' 형태가 아닌, 논리적 흐름도(Flowchart) 형태로 시각화.
- **Source-to-Fact Anchor**: 팩트를 클릭하면 원본 PDF의 해당 텍스트 하이라이트 위치로 즉시 스크롤되는 정밀 앵커링 기술.

---

## 4. End-to-End 데이터 흐름 (Technical Flow)

1.  **Ingestion**: `app/main.py` -> `/api/v1/upload`
2.  **Refinement (Pillar 1)**: `DistillEngine` -> `Self-Reflection Loop` (추출 데이터 자동 보정)
3.  **Ontology Construction (Pillar 3)**: `SpokeD` -> `Temporal Edge` 생성 (DB: `valid_from` 저장)
4.  **Reasoning**: `FinRobot` (4-Layer) -> 의사결정 권고안 생성
5.  **Simulation (Pillar 2)**: `OracleEngine` -> 미래 시나리오 확률 계산
6.  **Delivery**: Next.js UI -> `Decision Timeline` 및 `Interactive Graph` 렌더링

---

## 5. Zero-Error 인프라 구성
- **Database**: Supabase (PostgreSQL + pgvector)
- **Cache**: Redis (비동기 작업 상태 및 에이전트 메모리 저장)
- **Validation**: Pydantic 모델을 통한 모든 단계의 데이터 스키마 엄격 검증

---

## 🚀 구현 우선순위 (Next Action)

1.  **Backend**: `app/services/spokes.py` 내의 `Temporal Edge` 로직을 실제 DB 쿼리와 연동 (`valid_from` 필드 활용).
2.  **API**: `/api/v1/cases/{id}/simulate` 엔드포인트 신설 (What-if 분석용).
3.  **Frontend**: 팔란티어 스타일의 다크 테마 디자인 토큰(Design Tokens) 정의 및 기초 레이아웃 구축.
