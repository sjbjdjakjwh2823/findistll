import duckdb
import logging
import os
import pandas as pd
import json

logger = logging.getLogger(__name__)

class DuckDBManager:
    def __init__(self, db_path="project_1/data/local_cache.duckdb"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = duckdb.connect(self.db_path)
        self._init_schema()

    def _init_schema(self):
        """
        Initialize tables for Market Data, News, and Logs.
        """
        # Market Data Table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS market_data (
                entity VARCHAR,
                period TIMESTAMP,
                concept VARCHAR,
                value DOUBLE,
                unit VARCHAR,
                source_tier VARCHAR,
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity, period, concept)
            )
        """)
        
        # News/Events Table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id VARCHAR PRIMARY KEY,
                headline VARCHAR,
                source VARCHAR,
                period TIMESTAMP,
                related_entities VARCHAR[],
                impact_score DOUBLE
            )
        """)
        
        # System Logs
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS log_id_seq;
            CREATE TABLE IF NOT EXISTS system_logs (
                log_id INTEGER PRIMARY KEY DEFAULT nextval('log_id_seq'),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                level VARCHAR,
                message VARCHAR,
                module VARCHAR
            )
        """)

    def upsert_market_data(self, data_list):
        """
        Bulk upsert market data.
        data_list: list of dicts {entity, period, concept, value, unit, source_tier}
        """
        if not data_list: return
        
        # Convert to DF for DuckDB
        df = pd.DataFrame(data_list)
        if 'period' in df.columns:
            # Use 'mixed' to handle ISO8601 with/without timezone
            df['period'] = pd.to_datetime(df['period'], format='mixed', errors='coerce', utc=True)
            
        # Handle Wide Format (OHLCV) -> Long Format (Concept/Value)
        wide_cols = ['open', 'high', 'low', 'close', 'volume']
        if any(c in df.columns for c in wide_cols):
             # Identify id_vars (everything that is NOT a metric)
             id_vars = [c for c in df.columns if c not in wide_cols and c != 'value' and c != 'concept']
             
             # Melt
             df_long = df.melt(id_vars=id_vars, value_vars=[c for c in wide_cols if c in df.columns], 
                               var_name='concept', value_name='value')
             
             # Standardize Concept Names (e.g. close -> MarketClose)
             concept_map = {
                 'close': 'MarketClose',
                 'open': 'MarketOpen',
                 'high': 'MarketHigh',
                 'low': 'MarketLow',
                 'volume': 'MarketVolume'
             }
             df_long['concept'] = df_long['concept'].map(lambda x: concept_map.get(x, x))
             df = df_long

        try:
            # Create temp table
            self.conn.register('temp_market_data', df)
            
            # Merge (Upsert)
            query = """
                INSERT INTO market_data (entity, period, concept, value, unit, source_tier)
                SELECT entity, period, concept, value, unit, source_tier FROM temp_market_data
                ON CONFLICT (entity, period, concept) DO UPDATE SET
                    value = EXCLUDED.value,
                    unit = EXCLUDED.unit,
                    source_tier = EXCLUDED.source_tier,
                    ingested_at = now()
            """
            self.conn.execute(query)
            logger.info(f"DuckDB: Upserted {len(df)} market records.")
        except Exception as e:
            logger.error(f"DuckDB Upsert Error: {e}")
            
    def log_event(self, level, message, module="System"):
        self.conn.execute("INSERT INTO system_logs (level, message, module) VALUES (?, ?, ?)", 
                          (level, message, module))

    def get_latest_data(self, entity, limit=100):
        return self.conn.execute(
            "SELECT * FROM market_data WHERE entity = ? ORDER BY period DESC LIMIT ?", 
            (entity, limit)
        ).fetchdf()

    def close(self):
        self.conn.close()
