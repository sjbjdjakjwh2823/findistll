@echo off
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn api.index:app --reload --port 8000
pause
