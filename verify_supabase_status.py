import os
from supabase import create_client, Client
from dotenv import load_dotenv
import logging

# Load env
load_dotenv("project_1/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SupabaseVerifier")

def verify():
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Missing credentials in .env")
        return

    try:
        logger.info(f"Connecting to {SUPABASE_URL}...")
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 1. Check Tables Existence & Row Counts
        tables = [
            "market_data", 
            "huggingface_data", 
            "spoke_a_strategy", 
            "spoke_b_quant_meta", 
            "spoke_c_rag_context", 
            "spoke_d_graph"
        ]
        
        for table in tables:
            try:
                # Count rows
                res = supabase.table(table).select("*", count="exact").limit(1).execute()
                count = res.count
                logger.info(f"✅ Table '{table}' exists. Rows: {count}")
                
                # Check for 'asset_class' specifically in market_data
                if table == "market_data":
                    if res.data:
                        if 'asset_class' in res.data[0]:
                             logger.info("   -> Column 'asset_class' found.")
                        else:
                             logger.warning("   -> ⚠️ Column 'asset_class' MISSING in returned data (might be null or not selected).")
                    else:
                        logger.info("   -> Table is empty, cannot verify columns by reading.")

            except Exception as e:
                logger.error(f"❌ Table '{table}' check failed: {e}")
                if "404" in str(e) or "relation" in str(e) and "does not exist" in str(e):
                     logger.error("   -> Table might not exist in Supabase.")

        # 2. Test Write (Market Data)
        logger.info("\nTesting Write to 'market_data'...")
        dummy = {
            "ticker": "TEST_WRITE",
            "asset_class": "TEST", 
            "interval": "1m",
            "timestamp": "2026-01-01T00:00:00"
        }
        try:
            res = supabase.table("market_data").insert(dummy).execute()
            logger.info("✅ Write Successful!")
            
            # Clean up
            supabase.table("market_data").delete().eq("ticker", "TEST_WRITE").execute()
            logger.info("✅ Clean up Successful!")
        except Exception as e:
            logger.error(f"❌ Write Failed: {e}")
            if "asset_class" in str(e):
                logger.error("!!! ISSUE FOUND: The 'asset_class' column is definitely missing.")

    except Exception as e:
        logger.error(f"Connection failed: {e}")

if __name__ == "__main__":
    verify()