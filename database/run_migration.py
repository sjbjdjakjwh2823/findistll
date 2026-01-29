import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("project_1/.env")

DB_URL = os.getenv("SUPABASE_DB_URL")

sql_file_path = "project_1/database/01_asura_schema.sql"

def run_migration():
    if not DB_URL:
        print("Error: SUPABASE_DB_URL not found in .env")
        return

    try:
        print("Connecting to Supabase Database...")
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # Read SQL file
        with open(sql_file_path, 'r') as f:
            sql_content = f.read()

        # Execute
        print("Executing Schema Migration...")
        # Drop tables first to ensure clean state (optional but recommended for schema mismatch fix)
        # Note: CASCADE will remove dependent objects
        drop_sql = """
        DROP TABLE IF EXISTS public.market_data CASCADE;
        DROP TABLE IF EXISTS public.macro_data CASCADE;
        DROP TABLE IF EXISTS public.geo_events CASCADE;
        DROP TABLE IF EXISTS public.company_fundamentals CASCADE;
        DROP TABLE IF EXISTS public.huggingface_data CASCADE;
        """
        cur.execute(drop_sql)
        
        cur.execute(sql_content)
        conn.commit()
        
        print("Migration Successful! Tables recreated.")
        cur.close()
        conn.close()

    except Exception as e:
        print(f"Migration Failed: {e}")

if __name__ == "__main__":
    run_migration()