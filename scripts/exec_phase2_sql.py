#!/usr/bin/env python3
"""Execute Phase 2 SQL directly via psycopg2."""

import os
import sys

# SQL to execute
SQL = """
-- Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Knowledge Base for RAG (Spoke C)
CREATE TABLE IF NOT EXISTS embeddings_finance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Causal Graph Nodes (Spoke D)
CREATE TABLE IF NOT EXISTS causal_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    category TEXT CHECK (category IN ('macro', 'company', 'metric', 'sector', 'event')),
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS causal_nodes_category_idx ON causal_nodes(category);
CREATE INDEX IF NOT EXISTS causal_nodes_name_idx ON causal_nodes(name);

-- Causal Graph Edges (Spoke D)
CREATE TABLE IF NOT EXISTS causal_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES causal_nodes(id) ON DELETE CASCADE,
    target_id UUID REFERENCES causal_nodes(id) ON DELETE CASCADE,
    relation TEXT DEFAULT 'causes',
    weight FLOAT DEFAULT 1.0,
    lag_days INTEGER DEFAULT 0,
    confidence FLOAT DEFAULT 0.5,
    evidence JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source_id, target_id, relation)
);

CREATE INDEX IF NOT EXISTS causal_edges_source_idx ON causal_edges(source_id);
CREATE INDEX IF NOT EXISTS causal_edges_target_idx ON causal_edges(target_id);
CREATE INDEX IF NOT EXISTS causal_edges_relation_idx ON causal_edges(relation);

-- AI Brain Traces
CREATE TABLE IF NOT EXISTS ai_brain_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT,
    query TEXT,
    rag_results JSONB DEFAULT '[]',
    causal_results JSONB DEFAULT '[]',
    final_decision JSONB DEFAULT '{}',
    latency_ms INTEGER,
    model_used TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_brain_traces_case_idx ON ai_brain_traces(case_id);
CREATE INDEX IF NOT EXISTS ai_brain_traces_created_idx ON ai_brain_traces(created_at DESC);

-- RPC function for vector similarity search
CREATE OR REPLACE FUNCTION match_embeddings(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        embeddings_finance.id,
        embeddings_finance.content,
        embeddings_finance.metadata,
        1 - (embeddings_finance.embedding <=> query_embedding) AS similarity
    FROM embeddings_finance
    WHERE 1 - (embeddings_finance.embedding <=> query_embedding) > match_threshold
    ORDER BY embeddings_finance.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""

SEED_NODES = """
INSERT INTO causal_nodes (name, category, properties) VALUES
    ('Fed_Funds_Rate', 'macro', '{"description": "Federal Reserve interest rate target"}'),
    ('Inflation_CPI', 'macro', '{"description": "Consumer Price Index inflation rate"}'),
    ('GDP_Growth', 'macro', '{"description": "Real GDP growth rate"}'),
    ('Unemployment_Rate', 'macro', '{"description": "U.S. unemployment rate"}'),
    ('SP500_Index', 'metric', '{"description": "S&P 500 stock market index"}'),
    ('Tech_Sector_Valuation', 'sector', '{"description": "Technology sector valuation multiple"}'),
    ('Bond_Yields_10Y', 'macro', '{"description": "10-year Treasury yield"}'),
    ('USD_Index', 'macro', '{"description": "U.S. Dollar strength index"}'),
    ('Oil_Price_WTI', 'macro', '{"description": "WTI crude oil price"}'),
    ('VIX_Index', 'metric', '{"description": "CBOE Volatility Index"}')
ON CONFLICT (name) DO NOTHING;
"""

SEED_EDGES = """
INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT s.id, t.id, 'negative_correlation', -0.7, 30, 0.85
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'Fed_Funds_Rate' AND t.name = 'Tech_Sector_Valuation'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT s.id, t.id, 'positive_correlation', 0.6, 0, 0.8
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'Inflation_CPI' AND t.name = 'Fed_Funds_Rate'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT s.id, t.id, 'negative_correlation', -0.8, 90, 0.75
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'Fed_Funds_Rate' AND t.name = 'GDP_Growth'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT s.id, t.id, 'positive_correlation', 0.7, 0, 0.9
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'VIX_Index' AND t.name = 'Bond_Yields_10Y'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT s.id, t.id, 'negative_correlation', -0.5, 7, 0.7
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'USD_Index' AND t.name = 'Oil_Price_WTI'
ON CONFLICT DO NOTHING;
"""

def main():
    try:
        import psycopg2
    except ImportError:
        print("Installing psycopg2-binary...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
        import psycopg2
    
    db_url = os.getenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:dltkdals2747@db.nnuixqxmalttautcqckt.supabase.co:5432/postgres"
    )
    
    print("🧠 Phase 2: Executing SQL directly via psycopg2...")
    print(f"   Database: {db_url.split('@')[1] if '@' in db_url else 'configured'}")
    
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("\n📦 Creating tables and functions...")
        cur.execute(SQL)
        print("   ✅ Tables created")
        
        print("\n🌱 Seeding causal nodes...")
        cur.execute(SEED_NODES)
        print("   ✅ Nodes seeded")
        
        print("\n🔗 Seeding causal edges...")
        cur.execute(SEED_EDGES)
        print("   ✅ Edges seeded")
        
        # Verify
        print("\n📊 Verification:")
        for table in ["embeddings_finance", "causal_nodes", "causal_edges", "ai_brain_traces"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"   ✅ {table}: {count} rows")
        
        cur.close()
        conn.close()
        
        print("\n✅ Phase 2 DB setup complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
