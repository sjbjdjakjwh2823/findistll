import os
import time
import logging
import schedule
import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from datetime import datetime
from datasets import load_dataset
import requests
from dotenv import load_dotenv
import sys
import os

# 스포크 폴더 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from spokes.active_engines import SpokeA, SpokeB, SpokeC, SpokeD

# Load environment variables from .env file
load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AsuraEngine")

# Initialize Spokes
spoke_a = SpokeA()
spoke_b = SpokeB()
spoke_c = SpokeC()
spoke_d = SpokeD()

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("!!! CRITICAL: Supabase URL or KEY is missing. Data cannot be saved. !!!")
    supabase = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info(f"Connected to Supabase: {SUPABASE_URL}")
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        supabase = None

# --- Asura Connectors ---

class MarketConnector:
    """yfinance: Stocks, Gold, Commodities"""
    def __init__(self, tickers=None):
        # Use ETFs for Commodities to avoid delisted Futures issues
        # GLD (Gold), USO (Oil), SLV (Silver)
        self.tickers = tickers or ['AAPL', 'GOOGL', 'MSFT', 'GLD', 'USO', 'SLV']

    def fetch_and_store(self):
        logger.info("Fetching Market Data (yfinance)...")
        if not supabase: return
        
        try:
            # Fetch 1d data for the last day
            data = yf.download(self.tickers, period="1d", interval="1h", group_by='ticker', progress=False)
            
            for ticker in self.tickers:
                try:
                    df = data[ticker] if len(self.tickers) > 1 else data
                    if df.empty: continue
                    
                    row = df.iloc[-1]
                    
                    # Determine Asset Class
                    if ticker in ['GLD', 'USO', 'SLV']:
                        asset_class = 'COMMODITY'
                    elif ticker in ['BTC-USD', 'ETH-USD']:
                        asset_class = 'CRYPTO'
                    else:
                        asset_class = 'EQUITY'

                    record = {
                        "ticker": ticker,
                        "asset_class": asset_class,
                        "interval": "1h",
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": int(row['Volume']),
                        "timestamp": row.name.isoformat()
                    }
                    
                    # Try to insert. If it fails due to schema, log it but don't crash
                    supabase.table("market_data").upsert(record).execute()
                    
                    # --- Trigger Spokes (Real-time Analysis) ---
                    # Pass list of 1 record for simplicity in this loop
                    data_batch = [record]
                    spoke_a.process_and_store(data_batch, supabase)
                    spoke_b.process_and_store(data_batch, supabase)
                    spoke_c.process_and_store(data_batch, supabase)
                    spoke_d.process_and_store(data_batch, supabase)
                    
                except Exception as e:
                    # Log simple error message
                    logger.error(f"Error processing {ticker}: {str(e)}")
            logger.info("Market Data Stored.")
        except Exception as e:
            logger.error(f"Market Fetch Error: {e}")

class HuggingFaceConnector:
    """
    Fetches data from Hugging Face Datasets.
    Using 'zeroshot/twitter-financial-news-sentiment' as it is compatible with modern datasets library (Parquet/Arrow).
    """
    def __init__(self):
        self.dataset_name = "zeroshot/twitter-financial-news-sentiment"
        self.subset = None # No subset needed for this one

    def fetch_and_store(self):
        logger.info(f"Fetching Hugging Face Data ({self.dataset_name})...")
        if not supabase: return

        try:
            # Load dataset (modern compatible)
            ds = load_dataset(self.dataset_name, split="train", streaming=True)
            
            count = 0
            for item in ds:
                if count >= 5: break
                
                # Item structure: {'text': ..., 'label': ...}
                record = {
                    "dataset_name": self.dataset_name,
                    "subset": "default",
                    "data_content": item, 
                    "sentiment_label": str(item.get('label')),
                    "fetched_at": datetime.now().isoformat()
                }
                supabase.table("huggingface_data").insert(record).execute()
                
                # --- Trigger Spokes for HF Data ---
                hf_batch = [record]
                spoke_a.process_and_store(hf_batch, supabase) # Strategy analysis on news
                spoke_c.process_and_store(hf_batch, supabase) # RAG context
                
                count += 1
                
            logger.info("Hugging Face Data Stored.")
        except Exception as e:
            logger.error(f"HF Fetch Error: {e}")


# --- Orchestrator ---

def job():
    logger.info("--- Starting Asura 24h Cycle ---")
    
    market = MarketConnector()
    hf = HuggingFaceConnector()

    market.fetch_and_store()
    time.sleep(2)
    hf.fetch_and_store()
    
    logger.info("--- Cycle Complete ---")

if __name__ == "__main__":
    logger.info("Starting Asura Engine Scheduler (24h Continuous Fetch)")
    
    # Run once immediately
    job()
    
    # Schedule every 60 minutes
    schedule.every(60).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
