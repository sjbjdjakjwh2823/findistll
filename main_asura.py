from fastapi import FastAPI
import threading
import uvicorn
import os
import sys

# 프로젝트 루트 경로 추가 (모듈 import 문제 해결)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ingestors.asura_scheduler import job as asura_job
import schedule
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AsuraMain")

app = FastAPI()

# --- 백그라운드 스케줄러 스레드 ---
def run_scheduler():
    logger.info("Scheduler Thread Started")
    
    # 시작하자마자 한번 실행
    try:
        asura_job()
    except Exception as e:
        logger.error(f"Initial job failed: {e}")

    # 1시간마다 실행 설정
    schedule.every(60).minutes.do(asura_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- FastAPI 이벤트 ---
@app.on_event("startup")
async def startup_event():
    logger.info("Starting Asura Engine + Web Server...")
    # 스케줄러를 별도 스레드로 실행 (웹 서버 차단 방지)
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()

# --- Health Check (Hugging Face가 살아있는지 확인하는 용도) ---
@app.get("/")
def read_root():
    return {"status": "Asura Engine is Running", "timestamp": time.time()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
