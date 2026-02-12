#!/usr/bin/env python3
"""
Phase 2: AI Brain - Database Initialization Script
Creates vector embeddings and causal graph tables in Supabase.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client


def get_supabase_client():
    """Create Supabase client from environment or hardcoded fallback."""
    url = os.getenv("SUPABASE_URL", "https://nnuixqxmalttautcqckt.supabase.co")
    key = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        "REDACTED_SUPABASE_SERVICE_ROLE_KEY"
    )
    return create_client(url, key)


# SQL statements for Phase 2 tables
PHASE2_SQL = """
-- ============================================
-- PHASE 2: AI Brain Tables
-- ============================================

-- 1. Enable vector extension (if not already)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Knowledge Base for RAG (Spoke C)
CREATE TABLE IF NOT EXISTS embeddings_finance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1536),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for vector similarity search
CREATE INDEX IF NOT EXISTS embeddings_finance_embedding_idx 
    ON embeddings_finance 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Text search index
CREATE INDEX IF NOT EXISTS embeddings_finance_content_idx 
    ON embeddings_finance 
    USING gin (to_tsvector('english', content));

-- 3. Causal Graph Nodes (Spoke D)
CREATE TABLE IF NOT EXISTS causal_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    category TEXT CHECK (category IN ('macro', 'company', 'metric', 'sector', 'event')),
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for category lookups
CREATE INDEX IF NOT EXISTS causal_nodes_category_idx ON causal_nodes(category);
CREATE INDEX IF NOT EXISTS causal_nodes_name_idx ON causal_nodes(name);

-- 4. Causal Graph Edges (Spoke D)
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

-- Indexes for graph traversal
CREATE INDEX IF NOT EXISTS causal_edges_source_idx ON causal_edges(source_id);
CREATE INDEX IF NOT EXISTS causal_edges_target_idx ON causal_edges(target_id);
CREATE INDEX IF NOT EXISTS causal_edges_relation_idx ON causal_edges(relation);

-- 5. AI Brain Traces (for traceability)
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

-- 6. RPC function for vector similarity search
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

-- 7. Seed some initial causal nodes (common macro factors)
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

-- 8. Seed initial causal edges (known economic relationships)
INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT 
    s.id, t.id, 'negative_correlation', -0.7, 30, 0.85
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'Fed_Funds_Rate' AND t.name = 'Tech_Sector_Valuation'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT 
    s.id, t.id, 'positive_correlation', 0.6, 0, 0.8
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'Inflation_CPI' AND t.name = 'Fed_Funds_Rate'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT 
    s.id, t.id, 'negative_correlation', -0.8, 90, 0.75
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'Fed_Funds_Rate' AND t.name = 'GDP_Growth'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT 
    s.id, t.id, 'positive_correlation', 0.7, 0, 0.9
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'VIX_Index' AND t.name = 'Bond_Yields_10Y'
ON CONFLICT DO NOTHING;

INSERT INTO causal_edges (source_id, target_id, relation, weight, lag_days, confidence)
SELECT 
    s.id, t.id, 'negative_correlation', -0.5, 7, 0.7
FROM causal_nodes s, causal_nodes t
WHERE s.name = 'USD_Index' AND t.name = 'Oil_Price_WTI'
ON CONFLICT DO NOTHING;
"""


def run_sql_via_rpc(client, sql: str):
    """
    Execute SQL via Supabase.
    Since Supabase doesn't allow direct SQL execution via the client,
    we need to use the REST API or run this in the Supabase SQL Editor.
    """
    print("=" * 60)
    print("PHASE 2: AI Brain Database Setup")
    print("=" * 60)
    print()
    print("Please run the following SQL in Supabase SQL Editor:")
    print("Go to: https://supabase.com/dashboard → Your Project → SQL Editor")
    print()
    print("-" * 60)
    print(sql)
    print("-" * 60)
    
    # Save SQL to file for easy access
    sql_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "supabase_phase2.sql")
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"\n✅ SQL saved to: {sql_file}")
    print()
    
    # Test connection
    try:
        result = client.table("causal_nodes").select("count", count="exact").execute()
        print(f"✅ Connection test passed. causal_nodes rows: {result.count or 0}")
    except Exception as e:
        if "does not exist" in str(e):
            print("⚠️  Tables don't exist yet. Please run the SQL above first.")
        else:
            print(f"⚠️  Connection test: {e}")
    
    return True


def verify_tables(client):
    """Verify that Phase 2 tables exist."""
    tables = ["embeddings_finance", "causal_nodes", "causal_edges", "ai_brain_traces"]
    results = {}
    
    print("\n📊 Verifying Phase 2 tables:")
    for table in tables:
        try:
            result = client.table(table).select("count", count="exact").execute()
            results[table] = {"exists": True, "count": result.count or 0}
            print(f"  ✅ {table}: {results[table]['count']} rows")
        except Exception as e:
            results[table] = {"exists": False, "error": str(e)}
            print(f"  ❌ {table}: Not found")
    
    return results


def main():
    print("🧠 Phase 2: AI Brain - Database Initialization")
    print()
    
    client = get_supabase_client()
    
    # Output SQL for manual execution
    run_sql_via_rpc(client, PHASE2_SQL)
    
    # Try to verify
    print("\n" + "=" * 60)
    verify_tables(client)
    
    print("\n✅ Phase 2 DB initialization script complete!")
    print("   If tables show ❌, please run the SQL in Supabase SQL Editor.")


if __name__ == "__main__":
    main()
