@echo off
echo [INFO] Backend Server Starting...

:: 1. 기존 8000번 포트 점유 프로세스 강제 종료 (포트 충돌 방지)
echo [INFO] Checking for processes on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo [WARN] Killing process %%a occupying port 8000...
    taskkill /F /PID %%a >nul 2>&1
)

:: 2. Python 경로 설정 (현재 디렉토리를 PYTHONPATH에 추가)
set PYTHONPATH=%PYTHONPATH%;%cd%

:: 3. 서버 실행 (api.app:app으로 변경됨, 절대 경로 사용)
:: --reload 옵션은 코드 수정 시 자동 재시작을 지원합니다.
echo [INFO] Running Uvicorn...
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Server failed to start.
    pause
    exit /b %ERRORLEVEL%
)
