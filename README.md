# FinDistill - 금융 데이터 정제 엔진

PDF 파일에서 금융 표 데이터를 자동으로 추출하고 회계 수식을 검증하는 FastAPI 기반 엔진입니다.

## 🚀 주요 기능

- **PDF to Image**: PDF 파일을 고해상도 이미지로 변환
- **Vision AI 파싱**: OpenAI GPT-4o Vision API를 사용한 표 데이터 추출
- **데이터 정제**: 콤마 제거, 숫자 변환, 병합된 셀 플래트닝
- **회계 검증**: 대차대조표, 손익계산서 수식 자동 검증
- **상세 리포트**: 검증 실패 시 행 번호와 상세 정보 제공

## 📁 프로젝트 구조

```
project_1/
├── app/
│   ├── __init__.py
│   └── main.py              # FastAPI 애플리케이션
├── core/
│   ├── __init__.py
│   ├── parser.py            # VisionParser (GPT-4o Vision)
│   └── validator.py         # FinancialValidator (회계 검증)
├── models/
│   ├── __init__.py
│   └── schemas.py           # FinancialTable Pydantic 스키마
├── utils/
│   ├── __init__.py
│   ├── pdf_processor.py     # PDF 처리 유틸리티
│   └── image_converter.py   # 이미지 변환 유틸리티
├── requirements.txt
└── README.md
```

## 🛠️ 설치 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

OpenAI API 키를 환경 변수로 설정합니다:

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=your-api-key-here
```

**Linux/Mac:**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### 3. 서버 실행

```bash
cd app
python main.py
```

또는:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 http://localhost:8000 에서 접근 가능합니다.

## 📖 API 사용법

### 엔드포인트 목록

- `GET /` - API 정보
- `GET /health` - 헬스 체크
- `POST /extract` - PDF에서 금융 데이터 추출 및 검증

### POST /extract

PDF 파일에서 금융 표 데이터를 추출하고 검증합니다.

**요청 파라미터:**

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|--------|------|
| file | File | ✅ | - | PDF 파일 |
| page_number | int | ❌ | 0 | 추출할 페이지 번호 (0부터 시작) |
| currency | str | ❌ | "KRW" | 통화 단위 |
| unit | int | ❌ | 1 | 금액 단위 |
| validate | bool | ❌ | true | 회계 검증 수행 여부 |
| tolerance | float | ❌ | 0.01 | 검증 허용 오차 |

**cURL 예제:**

```bash
curl -X POST "http://localhost:8000/extract" \
  -F "file=@financial_report.pdf" \
  -F "page_number=0" \
  -F "currency=KRW" \
  -F "unit=1000" \
  -F "validate=true" \
  -F "tolerance=0.01"
```

**Python 예제:**

```python
import requests

url = "http://localhost:8000/extract"

with open("financial_report.pdf", "rb") as f:
    files = {"file": f}
    data = {
        "page_number": 0,
        "currency": "KRW",
        "unit": 1000,
        "validate": True,
        "tolerance": 0.01
    }
    
    response = requests.post(url, files=files, data=data)
    result = response.json()
    
    print(result)
```

**응답 예제:**

```json
{
  "success": true,
  "message": "데이터 추출 완료",
  "data": {
    "title": "2024년 분기별 매출",
    "headers": ["구분", "1분기", "2분기", "3분기", "4분기"],
    "rows": [
      ["매출액", 1234567.0, 2345678.0, 3456789.0, 4567890.0],
      ["영업이익", 234567.0, 345678.0, 456789.0, 567890.0],
      ["순이익", 123456.0, 234567.0, 345678.0, 456789.0]
    ],
    "currency": "KRW",
    "unit": 1000
  },
  "metadata": {
    "page_number": 0,
    "total_pages": 5,
    "filename": "financial_report.pdf"
  },
  "validation": {
    "is_valid": true,
    "errors": [],
    "report": "✅ 모든 검증을 통과했습니다."
  }
}
```

**검증 실패 시 응답:**

```json
{
  "success": true,
  "message": "데이터 추출 완료",
  "data": { ... },
  "validation": {
    "is_valid": false,
    "errors": [
      {
        "row_index": 0,
        "error_type": "EQUATION_MISMATCH",
        "message": "대차대조표 균형 검증 실패: {자산} = {부채} + {자본}",
        "details": {
          "좌변 값": 1000000.0,
          "우변 값": 999999.0,
          "차이": 1.0,
          "허용 오차": 0.01,
          "행 데이터": ["2024", 1000000.0, 500000.0, 499999.0]
        }
      }
    ],
    "report": "❌ 검증 실패: 1개의 오류가 발견되었습니다.\n\n[오류 1]\n  행 번호: 0\n  ..."
  }
}
```

## 🧪 API 문서

서버 실행 후 다음 URL에서 자동 생성된 API 문서를 확인할 수 있습니다:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔍 핵심 컴포넌트

### 1. FinancialTable (models/schemas.py)

금융 표 데이터를 담는 Pydantic 모델

**필드:**
- `title`: 표 제목
- `headers`: 테이블 헤더 목록
- `rows`: 테이블 행 데이터
- `currency`: 통화 단위
- `unit`: 금액 단위

**자동 검증:**
- 헤더 비어있지 않은지 확인
- 각 행의 길이가 헤더 길이와 일치하는지 확인
- 콤마가 포함된 숫자 자동 변환 (예: "1,234,567" → 1234567.0)

### 2. VisionParser (core/parser.py)

OpenAI GPT-4o Vision API를 사용하여 이미지에서 표 데이터 추출

**주요 메서드:**
- `extract_table_from_image(image_path, currency, unit)`: 이미지에서 표 추출

**특징:**
- 병합된 셀 자동 플래트닝
- 표 구조 정확히 유지
- JSON 형식으로 파싱

### 3. FinancialValidator (core/validator.py)

회계 수식 검증 및 상세 리포트 생성

**주요 메서드:**
- `validate(table, rules)`: 일반 검증
- `validate_balance_sheet(table)`: 대차대조표 검증 (자산 = 부채 + 자본)
- `validate_income_statement(table)`: 손익계산서 검증 (매출 - 원가 = 이익)

**특징:**
- 1원 단위까지 정확한 검증
- 자동 규칙 감지
- 상세 에러 리포트 (행 번호, 차이값, 원본 데이터)

### 4. PDFProcessor (utils/pdf_processor.py)

PDF를 고해상도 이미지로 변환

**주요 메서드:**
- `pdf_to_images(pdf_path)`: 모든 페이지를 이미지로 변환
- `pdf_page_to_image(pdf_path, page_num)`: 특정 페이지만 변환
- `get_pdf_page_count(pdf_path)`: 페이지 수 확인

## ⚠️ 에러 처리

API는 다음과 같은 에러를 반환합니다:

- `400 Bad Request`: 잘못된 요청 (PDF 파일이 아님, 페이지 범위 초과 등)
- `404 Not Found`: 파일을 찾을 수 없음
- `422 Unprocessable Entity`: 데이터 파싱 실패
- `500 Internal Server Error`: 서버 내부 오류

모든 에러는 상세한 메시지와 함께 반환됩니다.

## 📝 라이선스

MIT License

## 🤝 기여

이슈와 풀 리퀘스트를 환영합니다!
