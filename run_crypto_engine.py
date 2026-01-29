import os
import logging
import time
import concurrent.futures
import pandas as pd
from hub.core import MasterFinancialHub
from spokes.engines import SpokeA, SpokeB, SpokeC, SpokeD
from ingestors.market import CryptoIngestor, MacroIngestor, NewsIngestor
from ingestors.history import HistoricalIngestor
from database.manager import DuckDBManager
from database.supabase_manager import SupabaseManager
from api.services.telegram_alert import TelegramAlerter

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CryptoEngine")

def run_spoke_task(spoke_class, arrow_table, output_path):
    try:
        spoke = spoke_class()
        spoke.generate(arrow_table, output_path)
        return f"{spoke_class.__name__} Success"
    except Exception as e:
        logger.error(f"{spoke_class.__name__} Failed: {e}")
        TelegramAlerter().send_alert_sync(f"Spoke Failure: {spoke_class.__name__} - {e}")
        return f"{spoke_class.__name__} Failed"

def run_history_mode():
    logger.info("Starting HISTORY MODE (2000-Present)...")
    db = DuckDBManager()
    supabase = SupabaseManager()
    ingestor = HistoricalIngestor()
    
    # Fetch all history
    history_data = ingestor.fetch_full_history(start_date="2000-01-01")
    
    if not history_data:
        logger.error("No historical data fetched.")
        return

    logger.info(f"Collected {len(history_data)} historical records.")
    
    # Batch Processing for Supabase (avoid timeout)
    batch_size = 2000
    for i in range(0, len(history_data), batch_size):
        batch = history_data[i:i+batch_size]
        logger.info(f"Upserting batch {i//batch_size + 1}/{len(history_data)//batch_size + 1}...")
        db.upsert_market_data(batch)
        supabase.upsert_market_data(batch)
        time.sleep(0.5) # Rate limit protection
        
    logger.info("History Ingestion Complete.")

def main():
    # Check if we should run History Mode (Environment Variable or Flag)
    # For now, we run realtime by default, but let's add a trigger
    # In a real app, use CLI args. Here we default to Realtime unless specified.
    
    if os.getenv("RUN_HISTORY_MODE", "False") == "True":
        run_history_mode()
        return

    alerter = TelegramAlerter()
    logger.info("Starting FinDistill v28.0 Crypto Engine (Realtime)...")
    
    try:
        # 0. Initialize DB
        db = DuckDBManager()
        supabase = SupabaseManager()
        
        # 1. Ingest Data
        crypto_ingestor = CryptoIngestor()
        macro_ingestor = MacroIngestor()
        news_ingestor = NewsIngestor()
        
        raw_data = []
        
        # Fetch Crypto
        assets = ['BTC', 'ETH', 'SOL', 'XRP']
        for asset in assets:
            logger.info(f"Fetching data for {asset}...")
            data = crypto_ingestor.fetch_ohlcv(asset, limit=100)
            
            if asset == 'USDT' or asset == 'USDC': 
                 peg = crypto_ingestor.check_stablecoin_peg(f"{asset}/USDT")
                 
            news_map = news_ingestor.fetch_news()
            if asset in news_map:
                for d in data:
                    d['meta'] = news_map[asset]
                    
            raw_data.extend(data)
            
        # Fetch Macro
        logger.info("Fetching Macro data...")
        macro_data = macro_ingestor.fetch_data()
        raw_data.extend(macro_data)
        
        if not raw_data:
            logger.error("No data collected. Exiting.")
            alerter.send_alert_sync("Pipeline Error: No data collected from any source.")
            return

        # 1.5 Persist Raw Data
        logger.info("Persisting raw data to DuckDB...")
        db.upsert_market_data(raw_data)
        
        logger.info("Persisting raw data to Supabase...")
        supabase.upsert_market_data(raw_data)
        
        # 2. Hub Processing
        logger.info(f"Ingesting {len(raw_data)} records into MasterFinancialHub...")
        hub = MasterFinancialHub()
        hub.ingest_data(raw_data, domain="market", source_type="tier1")
        hub.run() 
        
    # 3. Output Generation (Spokes)
    arrow_table = hub.get_arrow_table()
    logger.info(f"Hub Pipeline Complete. Arrow Table Rows: {arrow_table.num_rows}")
    
    output_dir = "final_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Define Spokes
    spoke_a_path = os.path.join(output_dir, "crypto_cot_strategy.jsonl")
    spokes = [
        (SpokeA, spoke_a_path),
        (SpokeB, "crypto_quant_data.parquet"),
        (SpokeC, "crypto_news_context.json"),
        (SpokeD, "crypto_macro_graph.json")
    ]
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        futures = []
        for cls, fname in spokes:
            # Fix path for others
            if fname != spoke_a_path:
                path = os.path.join(output_dir, fname)
            else:
                path = fname
                
            futures.append(executor.submit(run_spoke_task, cls, arrow_table, path))
            
        for future in concurrent.futures.as_completed(futures):
            logger.info(future.result())
            
    # Post-Spoke: Upload Spoke A (CoT) to Supabase
    if os.path.exists(spoke_a_path):
        import json
        logger.info("Uploading Spoke A (AI Training Data) to Supabase...")
        cot_data = []
        with open(spoke_a_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    cot_data.append(json.loads(line))
        
        # Upsert to 'ai_training_sets'
        supabase.upsert_ai_training_data(cot_data)
            
    db.close()
    logger.info("Engine Cycle Complete.")
        
    except Exception as e:
        logger.critical(f"Critical Pipeline Failure: {e}")
        alerter.send_alert_sync(f"CRITICAL: Engine Crash - {e}")
        raise e

if __name__ == "__main__":
    main()
