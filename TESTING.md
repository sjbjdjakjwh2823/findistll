# FinDistill 테스트 가이드

## 🧪 통합 테스트 실행 방법

### 사전 준비

1. **의존성 설치**
```powershell
pip install -r requirements.txt
```

2. **OpenAI API 키 설정**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

3. **테스트용 PDF 파일 준비**
- 금융 표가 포함된 PDF 파일을 프로젝트 디렉토리에 준비
- 예: `financial_report.pdf`, `balance_sheet.pdf` 등

---

## 📝 테스트 실행 순서

### Step 1: 서버 실행

**터미널 1 (서버용):**

```powershell
# 프로젝트 디렉토리로 이동
cd c:\Users\Administrator\Desktop\project_1

# FastAPI 서버 실행
uvicorn app.main:app --reload
```

서버가 정상적으로 실행되면 다음과 같은 메시지가 표시됩니다:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**브라우저에서 확인:**
- API 문서: http://localhost:8000/docs
- API 정보: http://localhost:8000/

---

### Step 2: 테스트 스크립트 실행

**터미널 2 (테스트용):**

```powershell
# 프로젝트 디렉토리로 이동
cd c:\Users\Administrator\Desktop\project_1

# 테스트 스크립트 실행
python tests\test_run.py
```

---

## 📊 테스트 스크립트 기능

`tests/test_run.py`는 다음 기능을 수행합니다:

### 1. 서버 헬스 체크
- 서버가 실행 중인지 확인
- `/health` 엔드포인트 호출

### 2. 환경 변수 확인
- `OPENAI_API_KEY` 설정 여부 확인

### 3. PDF 파일 업로드 및 테스트
- 현재 디렉토리에서 PDF 파일 자동 탐색
- 없으면 사용자에게 경로 입력 요청
- `/extract` API 호출

### 4. 결과 출력
- 추출된 데이터 (제목, 헤더, 행)
- 메타데이터 (파일명, 페이지 정보)
- 검증 결과 (성공/실패, 오류 상세)

### 5. 결과 저장
- `test_result.json` 파일로 저장

---

## 🎯 예상 출력 예시

### 성공 케이스

```
============================================================
🚀 FinDistill API 통합 테스트
============================================================

[1/3] 서버 헬스 체크
✅ 서버가 정상적으로 실행 중입니다.

[2/3] 환경 변수 확인
✅ OPENAI_API_KEY 설정됨 (길이: 51)

[3/3] PDF 파일 테스트
✅ PDF 파일 발견: financial_report.pdf

============================================================
📄 PDF 파일 업로드 및 데이터 추출 테스트
============================================================

📁 파일: financial_report.pdf
📄 페이지: 0
💱 통화: KRW
📊 단위: 1
✓ 검증: True

⏳ API 요청 중...
⏱️  소요 시간: 3.45초

📡 응답 상태 코드: 200

✅ 데이터 추출 성공!

------------------------------------------------------------
📊 추출된 데이터
------------------------------------------------------------

제목: 2024년 분기별 매출
통화: KRW
단위: 1

헤더 (5개):
  ['구분', '1분기', '2분기', '3분기', '4분기']

데이터 (3행):
  행 0: ['매출액', 1234567.0, 2345678.0, 3456789.0, 4567890.0]
  행 1: ['영업이익', 234567.0, 345678.0, 456789.0, 567890.0]
  행 2: ['순이익', 123456.0, 234567.0, 345678.0, 456789.0]

메타데이터:
  파일명: financial_report.pdf
  페이지: 0 / 5

------------------------------------------------------------
🔍 검증 결과
------------------------------------------------------------

✅ 모든 검증을 통과했습니다!

------------------------------------------------------------
📋 상세 리포트
------------------------------------------------------------
✅ 모든 검증을 통과했습니다.

💾 결과가 저장되었습니다: test_result.json

============================================================
✅ 테스트 완료!
============================================================
```

### 검증 실패 케이스

```
------------------------------------------------------------
🔍 검증 결과
------------------------------------------------------------

❌ 검증 실패

오류 개수: 1개

[오류 1]
  행 번호: 0
  오류 유형: EQUATION_MISMATCH
  메시지: 대차대조표 균형 검증 실패: {자산} = {부채} + {자본}
  상세 정보:
    - 좌변 값: 1000000.0
    - 우변 값: 999999.0
    - 차이: 1.0
    - 허용 오차: 0.01
    - 행 데이터: ['2024', 1000000.0, 500000.0, 499999.0]
```

---

## 🔧 커스텀 테스트

테스트 스크립트를 직접 수정하여 다양한 시나리오를 테스트할 수 있습니다:

```python
# tests/test_run.py의 main() 함수에서

# 특정 페이지 테스트
result = test_extract_api(
    pdf_path="your_file.pdf",
    page_number=2,  # 3번째 페이지
    currency="USD",
    unit=1000,
    validate=True,
    tolerance=0.01
)

# 검증 없이 추출만
result = test_extract_api(
    pdf_path="your_file.pdf",
    validate=False
)

# 허용 오차 변경
result = test_extract_api(
    pdf_path="your_file.pdf",
    tolerance=1.0  # 1원까지 허용
)
```

---

## 🐛 문제 해결

### 1. "서버에 연결할 수 없습니다"
- 서버가 실행 중인지 확인
- 포트 8000이 사용 중인지 확인
- 방화벽 설정 확인

### 2. "OPENAI_API_KEY 환경변수가 설정되지 않았습니다"
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

### 3. "PDF 파일을 찾을 수 없습니다"
- PDF 파일 경로 확인
- 파일 권한 확인

### 4. "데이터 파싱 실패"
- PDF에 표가 포함되어 있는지 확인
- 이미지 품질 확인 (300 DPI 권장)
- OpenAI API 크레딧 확인

---

## 📚 추가 테스트 방법

### cURL로 테스트

```bash
curl -X POST "http://localhost:8000/extract" \
  -F "file=@financial_report.pdf" \
  -F "page_number=0" \
  -F "currency=KRW" \
  -F "unit=1" \
  -F "validate=true"
```

### Python 스크립트로 테스트

```python
import requests

url = "http://localhost:8000/extract"

with open("financial_report.pdf", "rb") as f:
    files = {"file": f}
    data = {
        "page_number": 0,
        "currency": "KRW",
        "unit": 1,
        "validate": True
    }
    
    response = requests.post(url, files=files, data=data)
    print(response.json())
```

### Swagger UI로 테스트

1. 브라우저에서 http://localhost:8000/docs 접속
2. `POST /extract` 엔드포인트 선택
3. "Try it out" 클릭
4. 파일 업로드 및 파라미터 입력
5. "Execute" 클릭

---

## ✅ 체크리스트

테스트 전 확인사항:

- [ ] Python 3.8 이상 설치
- [ ] 모든 의존성 설치 완료 (`pip install -r requirements.txt`)
- [ ] OpenAI API 키 설정
- [ ] 테스트용 PDF 파일 준비
- [ ] 서버 실행 (터미널 1)
- [ ] 테스트 스크립트 실행 (터미널 2)

---

## 📞 문의

문제가 발생하면 다음을 확인하세요:
1. 서버 로그 (터미널 1)
2. 테스트 스크립트 출력 (터미널 2)
3. `test_result.json` 파일
