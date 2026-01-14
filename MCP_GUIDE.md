# FinDistill MCP Server 가이드

## 📡 MCP (Model Context Protocol) 소개

MCP는 AI 에이전트(Cursor, Claude 등)가 외부 도구를 호출할 수 있게 해주는 프로토콜입니다.
FinDistill MCP Server를 사용하면 AI 에이전트가 "이 PDF에서 재무제표 뽑아줘"와 같은 
자연어 명령으로 금융 데이터 추출 기능을 사용할 수 있습니다.

---

## 🛠️ 제공되는 MCP 도구

### 1. `extract_financial_table`

PDF에서 금융 표 데이터를 추출합니다.

**기능:**
- PDF에서 재무제표, 대차대조표, 손익계산서 등 추출
- 숫자 데이터 자동 정제 (콤마 제거, float 변환)
- 회계 수식 검증 (자산=부채+자본, 매출-원가=이익)
- 검증 실패 시 자가 교정 (최대 2회)
- 수동 검토 필요 여부 플래그 제공

**사용 예시 (AI 에이전트 명령):**
- "이 PDF에서 재무제표 뽑아줘"
- "대차대조표 데이터 추출해줘"
- "손익계산서 숫자 검증해줘"
- "이 파일의 2페이지에서 표 추출해줘"

**파라미터:**
| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|----------|------|------|--------|------|
| pdf_base64 | string | * | - | Base64 인코딩된 PDF 데이터 |
| pdf_path | string | * | - | PDF 파일 경로 |
| page_number | int | ❌ | 0 | 페이지 번호 |
| currency | string | ❌ | "KRW" | 통화 단위 |
| unit | int | ❌ | 1 | 금액 단위 |
| auto_correct | bool | ❌ | true | 자가 교정 활성화 |
| max_correction_attempts | int | ❌ | 2 | 최대 교정 횟수 |
| tolerance | float | ❌ | 0.01 | 검증 허용 오차 |

*pdf_base64 또는 pdf_path 중 하나 필수

---

### 2. `validate_financial_table`

금융 표 데이터의 회계 수식을 검증합니다.

**검증 규칙:**
- 대차대조표: 자산 = 부채 + 자본
- 손익계산서: 매출 - 원가 = 이익

**파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| title | string | ✅ | 표 제목 |
| headers | array | ✅ | 헤더 목록 |
| rows | array | ✅ | 행 데이터 |
| currency | string | ❌ | 통화 단위 |
| unit | int | ❌ | 금액 단위 |
| tolerance | float | ❌ | 허용 오차 |

---

### 3. `get_pdf_info`

PDF 파일의 기본 정보를 반환합니다.

**파라미터:**
| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| pdf_base64 | string | * | Base64 인코딩된 PDF |
| pdf_path | string | * | PDF 파일 경로 |

---

## 🚀 MCP 서버 설정 방법

### 1. 사전 준비

```powershell
# 의존성 설치
pip install -r requirements.txt

# .env 파일에 API 키 설정
# .env 파일을 열고 OPENAI_API_KEY를 실제 키로 변경
```

### 2. Cursor에서 설정

Cursor의 MCP 설정 파일에 다음을 추가하세요:

**Windows:**
`%APPDATA%\Cursor\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json`

```json
{
  "mcpServers": {
    "findistill": {
      "command": "python",
      "args": ["-m", "core.mcp_server"],
      "cwd": "c:\\Users\\Administrator\\Desktop\\project_1",
      "env": {
        "PYTHONPATH": "c:\\Users\\Administrator\\Desktop\\project_1"
      }
    }
  }
}
```

### 3. Claude Desktop에서 설정

Claude Desktop의 설정 파일에 추가:

**Windows:**
`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "findistill": {
      "command": "python",
      "args": ["-m", "core.mcp_server"],
      "cwd": "c:\\Users\\Administrator\\Desktop\\project_1",
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

### 4. 직접 테스트

```powershell
# MCP 서버 직접 실행
cd c:\Users\Administrator\Desktop\project_1
python -m core.mcp_server
```

---

## 💬 AI 에이전트 사용 예시

MCP 서버가 설정되면, AI 에이전트에게 다음과 같이 요청할 수 있습니다:

### 예시 1: PDF에서 재무제표 추출
```
"c:\reports\financial_2024.pdf 파일에서 재무제표 데이터를 추출해줘"
```

AI 에이전트가 `extract_financial_table` 도구를 호출하고 결과를 반환합니다.

### 예시 2: 특정 페이지 추출
```
"이 PDF의 3번째 페이지에서 대차대조표 뽑아줘"
```

### 예시 3: 데이터 검증
```
"이 표 데이터가 회계 수식에 맞는지 검증해줘"
```

### 예시 4: 자가 교정
```
"PDF에서 표를 추출하고, 숫자가 틀리면 자동으로 교정해줘"
```

---

## 🔒 보안 설정

### API 키 관리

API 키는 `.env` 파일에서 관리됩니다:

```env
# .env 파일
OPENAI_API_KEY=your-actual-api-key

# 보안 설정
ENABLE_AUDIT_LOG=true       # 감사 로그 활성화
MASK_SENSITIVE_DATA=true    # 민감한 데이터 마스킹
```

### 감사 로깅

모든 MCP 요청과 데이터 추출은 자동으로 로그에 기록됩니다:

```
logs/findistill.log    # 일반 로그
logs/audit.log         # 감사 로그 (JSON 형식)
```

**감사 로그 예시:**
```json
{
  "timestamp": "2024-01-13T14:56:37",
  "event_type": "MCP_REQUEST",
  "tool_name": "extract_financial_table",
  "arguments": {"pdf_path": "report.pdf", "page_number": 0},
  "success": true
}
```

### 민감한 데이터 마스킹

로그에서 다음 데이터는 자동으로 마스킹됩니다:
- API 키
- 카드 번호
- 주민번호 패턴

---

## 📁 프로젝트 구조

```
project_1/
├── core/
│   ├── mcp_server.py      # MCP 서버 (✨ 새로 추가)
│   ├── parser.py          # VisionParser
│   └── validator.py       # FinancialValidator
├── utils/
│   ├── logging_config.py  # 로깅 설정 (✨ 새로 추가)
│   └── pdf_processor.py   # PDF 처리
├── .env                   # 환경 변수 (✨ 새로 추가)
├── .env.example           # 환경 변수 템플릿
├── .gitignore             # Git 무시 파일 (✨ 새로 추가)
├── mcp.json               # MCP 설정 파일 (✨ 새로 추가)
└── MCP_GUIDE.md           # MCP 가이드 (✨ 이 파일)
```

---

## 🐛 문제 해결

### 1. "OPENAI_API_KEY가 설정되지 않았습니다"
→ `.env` 파일에 유효한 API 키를 설정하세요.

### 2. "모듈을 찾을 수 없습니다"
→ `PYTHONPATH`가 프로젝트 루트로 설정되어 있는지 확인하세요.

### 3. MCP 서버가 응답하지 않음
→ 로그 파일(`logs/findistill.log`)을 확인하세요.

### 4. 권한 오류
→ PDF 파일 및 로그 디렉토리에 대한 읽기/쓰기 권한을 확인하세요.

---

## 📚 참고 자료

- [MCP 공식 문서](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Cursor MCP 설정](https://docs.cursor.com/advanced/mcp)

---

## ✅ 체크리스트

- [ ] Python 3.10 이상 설치
- [ ] 의존성 설치 완료 (`pip install -r requirements.txt`)
- [ ] `.env` 파일에 `OPENAI_API_KEY` 설정
- [ ] MCP 서버 테스트 (`python -m core.mcp_server`)
- [ ] AI 에이전트 MCP 설정 완료
- [ ] 로그 디렉토리 생성 확인 (`logs/`)

---

Happy coding with AI! 🤖✨
