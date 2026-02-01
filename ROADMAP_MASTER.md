# Preciso Master Roadmap (6하 원칙)

## 1) Who (누가)
- **Master(주인님)**: 제품 전략/품질 기준/핵심 의사결정
- **클로**: 기술 설계, 개발 보조, 벤치마킹, 문서화
- **외부 협력(필요 시)**: UI/UX 디자이너, 프론트엔드 전담, 데이터 엔지니어

---

## 2) What (무엇을)
**목표:**
- Findistill 엔진 + FinRobot 4단계 레이어를 묶은 **B2B용 툴킷**을 제작/판매
- 팔란티어·ScaleAI급 **데이터 품질 + 운영 안정성 + 제품/사이트 퀄리티** 확보

**핵심 구성:**
1. **Findistill Pro (데이터 전처리/정제)**
2. **FinRobot Core (AI 의사결정)**
3. **툴킷 패키지화 (SDK + API + Template)**
4. **고퀄리티 웹 UI (Palantir급 대시보드)**
5. **엔터프라이즈 운영/보안/감사/권한 체계**
6. **무오류 파이프라인 + 최고 데이터 품질**

---

## 3) When (언제)
**로드맵 (12개월 기준)**
- **Phase 0 (1~2주)**: 경쟁사 벤치마킹 + 시스템 설계
- **Phase 1 (1~2개월)**: 데이터 정제 엔진 고도화 (무오류·품질 강화)
- **Phase 2 (2~4개월)**: FinRobot 4단계 레이어 완전 통합
- **Phase 3 (4~6개월)**: 엔터프라이즈 UI/UX 개선 + 운영 시스템
- **Phase 4 (6~9개월)**: 상용 툴킷 패키징 + SaaS 배포
- **Phase 5 (9~12개월)**: 유통/데이터 마켓 확대

---

## 4) Where (어디서)
**기술 배치**
- **Backend/AI**: Oracle + GPU 서버
- **DB**: Supabase (Postgres + Storage)
- **배포**: Cloudflare + Docker + CI/CD
- **Frontend**: Next.js / React 대시보드
- **운영**: OpenTelemetry + Loki (로그/감사)

---

## 5) Why (왜)
- **데이터 품질 = 경쟁력**
- **무오류 파이프라인 없으면 B2B 도입 불가**
- **UI/UX가 기업 신뢰도 결정**
- **AI 결정은 설명 가능성이 핵심**

---

## 6) How (어떻게)

### (A) 데이터 전처리 최적화 (Findistill Pro)
- 스케일 보정 + 다중 소스 교차검증
- Confidence Score 기반 품질 측정
- Spoke C(RAG) 고도화: 청크/키워드/벡터 검색

### (B) FinRobot 4단계 레이어 완성
- Agents: Market Forecaster, Analyst, Strategist 완성
- LLMs: 금융특화 프롬프트/튜닝
- LLMOps/DataOps: Task별 모델 라우팅
- Foundation: GPT/Claude 등 플러그앤플레이

### (C) 엔터프라이즈급 UI/UX
- Palantir/ScaleAI/Databricks/OpenAI/Anthropic/Stripe/Vercel 벤치마킹
- 다크 테마 + 고밀도 정보 구조 + 모듈형 UI
- Next.js + Tailwind + shadcn/ui + Radix UI + Framer Motion

### (D) 툴킷 상품화 (B2B)
- Python SDK + REST API
- Case 템플릿 + Ingest Pipeline
- Agent Config UI

### (E) 운영 안정성 (무오류 목표)
- 데이터 검증 규칙 자동화
- 에러 재시도/롤백
- 정합성 로그 + 자동 감사 기록

---

## 즉시 착수 우선순위
1. UI 벤치마킹 목록 작성
2. Findistill 품질 강화 (오류 제거/Confidence 강화)
3. Spoke C/D/E 구현 마무리
4. FinRobot 의사결정 파이프라인 정리
5. Preciso 전용 고급 UI 디자인 시작
