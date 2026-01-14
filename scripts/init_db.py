"""
FinDistill Database Initialization Script
"""

import asyncio
import os
import sys
import ssl
from urllib.parse import urlparse, unquote

# Fix Windows asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()


def parse_database_url(url: str) -> dict:
    """Parse database URL into components."""
    url = url.replace('postgresql+asyncpg://', 'postgresql://')
    parsed = urlparse(url)
    
    return {
        'user': unquote(parsed.username or ''),
        'password': unquote(parsed.password or ''),
        'host': parsed.hostname or 'localhost',
        'port': parsed.port or 5432,
        'database': parsed.path.lstrip('/'),
    }


async def init_db():
    """Initialize database with pgvector extension and tables."""
    import asyncpg
    
    database_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    
    if not database_url:
        print("[ERROR] Database URL not found!")
        sys.exit(1)
    
    db_config = parse_database_url(database_url)
    
    print(f"[INFO] Host: {db_config['host']}")
    print(f"[INFO] Port: {db_config['port']}")
    print(f"[INFO] User: {db_config['user']}")
    print(f"[INFO] Database: {db_config['database']}")
    
    # Create SSL context - required for Supabase
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        print("[INFO] Connecting...")
        
        # Try connection with DSN string format (more compatible)
        dsn = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
        
        conn = await asyncpg.connect(dsn=dsn, ssl=ssl_context)
        
        print("[OK] Connected!")
        
        # Create pgvector extension
        print("[INFO] Creating pgvector extension...")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("   [OK] pgvector ready")
        
        # Create tables
        print("[INFO] Creating tables...")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR UNIQUE NOT NULL,
                hashed_password VARCHAR NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("   [OK] users")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR NOT NULL,
                file_path VARCHAR NOT NULL,
                upload_date TIMESTAMPTZ DEFAULT NOW(),
                user_id INTEGER REFERENCES users(id)
            )
        """)
        print("   [OK] documents")
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS extracted_results (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES documents(id),
                data JSONB NOT NULL,
                embedding vector(768)
            )
        """)
        print("   [OK] extracted_results")
        
        # Verify
        tables = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        print(f"[INFO] Tables: {', '.join([r['table_name'] for r in tables])}")
        
        await conn.close()
        print("\n[SUCCESS] Database initialization complete!")
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 50)
    print("FinDistill Database Initialization")
    print("=" * 50)
    asyncio.run(init_db())
