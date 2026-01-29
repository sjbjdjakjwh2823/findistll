import os
import logging
import time
import pandas as pd
from datetime import datetime, timedelta
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestors.history import HistoricalIngestor
from ingestors.geopolitical import GeopoliticalIngestor
from database.supabase_manager import SupabaseManager
from database.manager import DuckDBManager

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("backfill.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BackfillEngine")

def transform_to_cot(market_data, geo_events):
    """
    Spoke A Logic: Transform raw data into Chain-of-Thought training samples.
    """
    cot_samples = []
    
    # Simple correlation matching by date
    # Convert list of dicts to DF for joining
    if not market_data or not geo_events:
        return []
        
    df_m = pd.DataFrame(market_data)
    df_g = pd.DataFrame(geo_events)
    
    if 'period' not in df_m.columns or 'period' not in df_g.columns:
        return []

    # Ensure date format YYYY-MM-DD
    df_m['date'] = pd.to_datetime(df_m['period']).dt.strftime('%Y-%m-%d')
    df_g['date'] = pd.to_datetime(df_g['period']).dt.strftime('%Y-%m-%d')
    
    # Iterate events and find market context
    for _, event in df_g.iterrows():
        evt_date = pd.to_datetime(event['date'])
        headline = event['headline']
        
        # Find market data window (Event Date -> Event Date + 5 Days)
        # We want to see the REACTION, so we look forward.
        # But for 'Context', we might want t-1.
        # Let's simple look for the nearest trading day ON or AFTER the event.
        
        # Filter market data to be >= evt_date
        # df_m['period'] is the source of truth, converted to datetime objects for comparison
        market_dates = pd.to_datetime(df_m['date'])
        
        # Find closest date after event
        future_data = df_m[market_dates >= evt_date]
        
        if future_data.empty:
            continue
            
        # Get the first available date (closest reaction)
        target_date = future_data.iloc[0]['date']
        
        # Check if it's within reasonable range (e.g. 7 days)
        delta = (pd.to_datetime(target_date) - evt_date).days
        if delta > 7:
            continue
            
        context_data = df_m[df_m['date'] == target_date]
        
        # Create CoT
        # Example: Gold price reaction
        gold_data = context_data[context_data['entity'] == 'Gold']
        sp500_data = context_data[context_data['entity'] == '^GSPC']
        
        market_context = ""
        if not gold_data.empty:
            market_context += f"Gold Price: {gold_data.iloc[0]['value']}. "
        if not sp500_data.empty:
            market_context += f"S&P 500: {sp500_data.iloc[0]['value']}. "
            
        if not market_context:
            continue
            
        instruction = "Analyze the market reaction to the following geopolitical event."
        input_text = f"Event: {headline} ({evt_date})\nMarket Context: {market_context}"
        output_text = f"Step 1: The event '{headline}' occurred.\nStep 2: Market data shows {market_context}\nStep 3: This suggests a correlation between the event and market volatility."
        
        cot_samples.append({
            "instruction": instruction,
            "input": input_text,
            "output": output_text
        })
        
    return cot_samples

def main():
    logger.info("Starting Historical Backfill Engine (2000-2026)...")
    
    db = DuckDBManager()
    supabase = SupabaseManager()
    hist_ingestor = HistoricalIngestor()
    geo_ingestor = GeopoliticalIngestor()
    
    start_year = 2000
    end_year = datetime.now().year
    
    for year in range(start_year, end_year + 1):
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        logger.info(f"Processing Year: {year} ({start_date} ~ {end_date})")
        
        try:
            # 1. Fetch Market Data
            market_data = hist_ingestor.fetch_full_history(start_date=start_date, end_date=end_date)
            logger.info(f"Fetched {len(market_data)} market records.")
            
            # 2. Fetch Geopolitical Data
            geo_data = geo_ingestor.fetch_events(start_date=start_date, end_date=end_date)
            logger.info(f"Fetched {len(geo_data)} geopolitical events.")
            
            # 3. Generate CoT (AI Training Data)
            ai_data = transform_to_cot(market_data, geo_data)
            logger.info(f"Generated {len(ai_data)} CoT training samples.")
            
            # 4. Upsert to Supabase
            if market_data:
                supabase.upsert_market_data(market_data)
            
            if geo_data:
                supabase.upsert_geopolitical_events(geo_data)
                
            if ai_data:
                supabase.upsert_ai_training_data(ai_data)
                
            # 5. Local Cache
            db.upsert_market_data(market_data)
            
            logger.info(f"Year {year} Completed. Sleeping to respect rate limits...")
            time.sleep(2) 
            
        except Exception as e:
            logger.error(f"Error processing year {year}: {e}")
            # Checkpoint logic could be added here (retry or skip)
            continue

    logger.info("Backfill Complete.")

if __name__ == "__main__":
    main()
