import asyncio
import logging
import os
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from contextlib import asynccontextmanager
from database.manager import DuckDBManager
from api.services.hf_integration import HFManager
from run_crypto_engine import main as run_pipeline

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FinDistill_Server")

# Global State
db_manager = None
hf_manager = None

# Scheduler Loop
async def scheduler_loop():
    """
    Runs the pipeline every hour.
    """
    logger.info("Scheduler started. Pipeline will run every 60 minutes.")
    while True:
        try:
            logger.info("Scheduler: Triggering Pipeline...")
            # Run the synchronous pipeline in a thread pool to avoid blocking async loop
            await asyncio.to_thread(run_pipeline)
            
            # Post-Pipeline: Sync to DuckDB or HF if not handled inside pipeline
            # (Assuming pipeline handles file generation, we might push here)
            if hf_manager:
                await asyncio.to_thread(hf_manager.push_dataset, "final_output")
                
            logger.info("Scheduler: Pipeline Cycle Finished. Sleeping for 1 hour.")
        except Exception as e:
            logger.error(f"Scheduler Error: {e}")
            
        await asyncio.sleep(3600) # 1 Hour

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global db_manager, hf_manager
    logger.info("Server Startup...")
    db_manager = DuckDBManager()
    hf_manager = HFManager()
    
    # Start Scheduler in background
    asyncio.create_task(scheduler_loop())
    
    yield
    
    # Shutdown
    logger.info("Server Shutdown...")
    if db_manager:
        db_manager.close()

app = FastAPI(title="FinDistill v28.0 Factory", lifespan=lifespan)

@app.get("/")
def read_root():
    return {"status": "running", "system": "FinDistill v28.0", "memory_mode": "16GB_Optimized"}

@app.get("/health")
def health_check():
    return {"status": "ok", "db": "connected" if db_manager else "error"}

@app.post("/trigger")
async def trigger_pipeline_manually(background_tasks: BackgroundTasks):
    """
    Manually trigger the ETL pipeline
    """
    background_tasks.add_task(run_pipeline)
    return {"message": "Pipeline triggered in background"}

@app.get("/logs")
def get_logs():
    # Simple log reader (in production, use DB)
    if db_manager:
        try:
            return db_manager.conn.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 50").fetchdf().to_dict(orient="records")
        except:
            return []
    return []

if __name__ == "__main__":
    # Port 7860 is required by HuggingFace Spaces
    uvicorn.run(app, host="0.0.0.0", port=7860)
