@echo off
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn backend.app.main:app --reload --port 8000
pause
