# FinDistill - 빠른 시작 가이드

## 🚀 5분 안에 시작하기

### 1단계: 의존성 설치 (1분)

```powershell
cd c:\Users\Administrator\Desktop\project_1
pip install -r requirements.txt
```

### 2단계: OpenAI API 키 설정 (30초)

```powershell
$env:OPENAI_API_KEY="your-openai-api-key-here"
```

### 3단계: 서버 실행 (30초)

**터미널 1을 열고:**

```powershell
cd c:\Users\Administrator\Desktop\project_1
uvicorn app.main:app --reload
```

✅ 서버가 실행되면 다음 메시지가 표시됩니다:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 4단계: 테스트 실행 (3분)

**터미널 2를 새로 열고:**

```powershell
cd c:\Users\Administrator\Desktop\project_1
python tests\test_run.py
```

테스트 스크립트가 자동으로:
1. 서버 헬스 체크 ✅
2. 환경 변수 확인 ✅
3. PDF 파일 찾기 (없으면 경로 입력 요청)
4. API 호출 및 결과 출력 📊

---

## 📋 전체 실행 순서 요약

### 터미널 1 (서버)
```powershell
# 1. 프로젝트 디렉토리로 이동
cd c:\Users\Administrator\Desktop\project_1

# 2. 환경 변수 설정
$env:OPENAI_API_KEY="your-api-key"

# 3. 서버 실행
uvicorn app.main:app --reload
```

### 터미널 2 (테스트)
```powershell
# 1. 프로젝트 디렉토리로 이동
cd c:\Users\Administrator\Desktop\project_1

# 2. 테스트 실행
python tests\test_run.py
```

---

## 🎯 브라우저에서 확인

서버 실행 후 브라우저에서 접속:

- **API 문서 (Swagger)**: http://localhost:8000/docs
- **API 정보**: http://localhost:8000/
- **헬스 체크**: http://localhost:8000/health

---

## 📁 필요한 파일

테스트를 위해 **금융 표가 포함된 PDF 파일**을 준비하세요.

예시:
- 대차대조표 (자산, 부채, 자본 포함)
- 손익계산서 (매출, 원가, 이익 포함)
- 분기별 재무제표

PDF 파일을 프로젝트 디렉토리에 넣으면 자동으로 감지됩니다.

---

## ✅ 성공 확인

테스트가 성공하면 다음과 같이 표시됩니다:

```
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
  ...

------------------------------------------------------------
🔍 검증 결과
------------------------------------------------------------

✅ 모든 검증을 통과했습니다!
```

결과는 `test_result.json` 파일에 저장됩니다.

---

## 🐛 문제 해결

### "서버에 연결할 수 없습니다"
→ 터미널 1에서 서버가 실행 중인지 확인

### "OPENAI_API_KEY 환경변수가 설정되지 않았습니다"
→ `$env:OPENAI_API_KEY="your-key"` 실행

### "PDF 파일을 찾을 수 없습니다"
→ PDF 파일을 프로젝트 디렉토리에 넣거나 경로 입력

---

## 📚 더 자세한 정보

- 전체 문서: [README.md](README.md)
- 테스트 가이드: [TESTING.md](TESTING.md)
- API 문서: http://localhost:8000/docs (서버 실행 후)

---

## 🎉 다음 단계

1. ✅ 서버 실행 확인
2. ✅ 테스트 스크립트 실행
3. 📊 실제 PDF 파일로 테스트
4. 🔧 필요에 따라 커스터마이징
5. 🚀 프로덕션 배포

Happy coding! 🎊
