# MEMORY.md - 클로의 장기 기억

## 주인님 정보
- 이름: 이상민 (Lee Sangmin)
- 호칭: 주인님 (Master)
- 언어: 한국어 (격식체)
- 타임존: Asia/Seoul (KST)

## Preciso 프로젝트

### 개요
- **목표:** 팔란티어급 금융 AI 플랫폼
- **도메인:** preciso-data.com
- **GitHub:** https://github.com/sjbjdjakjwh2823/findistll.git

### 핵심 엔진: FinDistill + FinRobot

---

## 🏗️ Spoke 구조 (A~E)

| Spoke | 기능 | 상태 | 연구 기둥 (Pillars) |
|-------|------|------|-------------------|
| **A** | CoT + 시나리오 시뮬레이션 | ✅ 구현 | Pillar 1 (Self-Reflection) |
| **B** | Confidence 점수 + 수치 정규화 | ✅ 구현 | - |
| **C** | RAG + Hybrid Flow | ⚠️ 부분 구현 | Pillar 4 (Multi-stage RAG) |
| **D** | Graph 엔진 (지식그래프) | ❌ DB만 존재 | Pillar 1 (Agentic Construction) |
| **E** | 미래 예측 & 인과 추론 (The Oracle) | ❌ 설계 완료 | Pillar 2, 3 (Causal, Temporal) |

---

## 📚 핵심 연구 로드맵 (4 Pillars)

주인님께서 하달하신 **Preciso 고도화 4대 핵심 기둥**입니다.

### 1. Agentic Construction (지식 자율 생성)
- **목표:** AI가 스스로 SEC 보고서를 읽고 지식그래프 구축 및 오류 수정.
- **연구:** *FinReflectKG (2025)*, *Frontiers (2025)*.
- **핵심 기술:** Self-Reflection (자아 성찰), Hallucination 교정.

### 2. Advanced Causal Inference (심화 인과 추론)
- **목표:** 상관관계를 넘어선 "진짜 시장 엔진" 발견.
- **연구:** *FinCARE (2026)*, *CISTF (2025)*.
- **핵심 기술:** PC 알고리즘, NOTEARS, Confounder(교란 변수) 처리.

### 3. Temporal & Dynamic Reasoning (시계열 동적 추론)
- **목표:** 시간에 따라 변하는 지식과 시장 파급력 계산.
- **연구:** *TimeGate (2025)*, *T-RGCN (MDPI)*.
- **핵심 기술:** Time-Sensitive Graph Attention (GAT), T-RGCN.

### 4. Operationalized AI (실전 운용 및 추천)
- **목표:** 분석 결과를 개인화된 투자 추천 및 브리핑으로 연결.
- **연구:** *RAG-FLARKO (2025)*.
- **핵심 기술:** RAG-FLARKO (Multi-stage Retrieval).

---

## FinDistill 엔진 (문서 추출)

### 파이프라인
```
문서 입력 → ingestion_service.process_file() → normalizer.normalize() → DistillResult
```

### 핵심 수학
- **YoY 성장률:** `(CY - PY) / |PY| × 100`
- **산업별 베타(β):** Automotive=2.4, Tech=0.8, Financial=-1.5
- **스케일 정규화:** Billion 단위 고정, Trillion 오류 자동 보정

---

## FinRobot 엔진 (AI 의사결정)

### 아키텍처 (4 레이어)
1. **Financial AI Agents Layer:** CoT 기반 에이전트들 (Market Forecasting, Document Analysis, Trading Strategies)
2. **Financial LLMs Algorithms Layer:** 도메인 특화 LLM 구성
3. **LLMOps/DataOps Layer:** 다중 LLM 통합 전략
4. **Multi-source LLM Foundation Layer:** 플러그앤플레이 LLM 지원

### Agent Workflow
```
Perception(데이터 인식) → Brain(LLM 추론) → Action(실행)
```

---

## Preciso 통합 흐름

```
[문서 업로드]
     ↓
[FinDistill] → facts + CoT 추출
     ↓
[FinRobot] → AI 의사결정 생성 (Pillar 1, 2, 3 적용)
     ↓
[Supabase DB] → 저장 (Spoke D, E 업데이트)
     ↓
[웹 UI] → 팔란티어 스타일 대시보드 (Pillar 4 브리핑)
```

---

## 철칙 (Rules)
1. ❌ API 키, 계정 사용 시 **반드시 허락** 받기
2. ❌ 주인님의 **개인정보 및 서버 IP, SSH Key 절대 유출 금지** (최우선 보안 사항)
3. ✅ SNS(Reddit, X)에 글 작성 → 반응 모니터링 → 보고

---

*마지막 업데이트: 2026-02-02 (월)*
