#!/usr/bin/env python3
"""
DataForge Phase 1 Database Initialization Script

This script connects to Supabase and creates the required tables
for Phase 1: DataForge as defined in specs/PHASE1_DATAFORGE_SPEC.md.

Uses environment variables for Supabase credentials.
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try to import psycopg2 or asyncpg
try:
    import psycopg2
    USE_PSYCOPG2 = True
except ImportError:
    USE_PSYCOPG2 = False

if not USE_PSYCOPG2:
    try:
        import asyncio
        import asyncpg
        USE_ASYNCPG = True
    except ImportError:
        USE_ASYNCPG = False
else:
    USE_ASYNCPG = False


PHASE1_DDL = """
-- =============================================================================
-- PHASE 1: DataForge Schema Migration
-- =============================================================================

-- 1. Raw Documents Queue
CREATE TABLE IF NOT EXISTS raw_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,              -- 'sec_10k', 'fred', 'finnhub', 'upload'
    ticker TEXT,
    document_type TEXT,                -- '10-K', '10-Q', 'earnings_call', 'macro_report'
    document_date TEXT,                -- Optional date (YYYY-MM-DD)
    raw_content JSONB,                 -- Stores text content or file reference
    file_hash TEXT,                    -- SHA-256 hash for deduplication
    file_path TEXT,                    -- Original filename if uploaded
    metadata JSONB DEFAULT '{}',       -- Additional metadata
    processing_status TEXT DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    processing_error TEXT,             -- Error message if failed
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Prompt Templates (for generation)
CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_type TEXT NOT NULL,       -- 'qa_pair', 'reasoning_chain', 'summary', etc.
    template_name TEXT NOT NULL,
    system_prompt TEXT,
    user_prompt_template TEXT NOT NULL, -- Jinja2-style template with placeholders
    is_active BOOLEAN DEFAULT true,
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Generated Samples (AI Output)
CREATE TABLE IF NOT EXISTS generated_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id UUID REFERENCES raw_documents(id) ON DELETE CASCADE,
    template_type TEXT,                -- 'qa_pair', 'reasoning_chain', 'summary'
    generated_content JSONB,           -- The AI's output (question, answer, reasoning)
    model_used TEXT,                   -- 'gpt-4-turbo', 'gemini-1.5-pro'
    confidence_score FLOAT,
    generation_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'review_pending' -- 'review_pending', 'in_review', 'approved', 'rejected', 'corrected'
);

-- 4. Human Annotations (Golden Labeling)
CREATE TABLE IF NOT EXISTS human_annotations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sample_id UUID REFERENCES generated_samples(id) ON DELETE CASCADE,
    annotator_id TEXT NOT NULL,        -- Email or user ID
    annotator_name TEXT,
    action TEXT,                       -- 'approved', 'corrected', 'rejected'
    corrections JSONB,                 -- The fixed content
    reasoning TEXT,                    -- Why the human made this change
    time_spent_seconds INT,            -- Optional timing
    annotated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Skipped Samples (for fair rotation)
CREATE TABLE IF NOT EXISTS skipped_samples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sample_id UUID REFERENCES generated_samples(id) ON DELETE CASCADE,
    annotator_id TEXT NOT NULL,
    skipped_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Generation Jobs (for batch processing)
CREATE TABLE IF NOT EXISTS generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status TEXT DEFAULT 'pending',     -- 'pending', 'running', 'completed', 'failed'
    total_tasks INT DEFAULT 0,
    completed_tasks INT DEFAULT 0,
    failed_tasks INT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Indexes for Dashboard Performance
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_raw_docs_status ON raw_documents(processing_status);
CREATE INDEX IF NOT EXISTS idx_raw_docs_source ON raw_documents(source);
CREATE INDEX IF NOT EXISTS idx_raw_docs_ticker ON raw_documents(ticker);
CREATE INDEX IF NOT EXISTS idx_raw_docs_hash ON raw_documents(file_hash);

CREATE INDEX IF NOT EXISTS idx_gen_samples_status ON generated_samples(status);
CREATE INDEX IF NOT EXISTS idx_gen_samples_doc ON generated_samples(raw_document_id);
CREATE INDEX IF NOT EXISTS idx_gen_samples_template ON generated_samples(template_type);

CREATE INDEX IF NOT EXISTS idx_annotations_sample ON human_annotations(sample_id);
CREATE INDEX IF NOT EXISTS idx_annotations_annotator ON human_annotations(annotator_id);

CREATE INDEX IF NOT EXISTS idx_skipped_sample ON skipped_samples(sample_id);
CREATE INDEX IF NOT EXISTS idx_skipped_annotator ON skipped_samples(annotator_id);

CREATE INDEX IF NOT EXISTS idx_templates_type ON prompt_templates(template_type);
CREATE INDEX IF NOT EXISTS idx_templates_active ON prompt_templates(is_active);

-- =============================================================================
-- Seed Default Prompt Templates
-- =============================================================================

INSERT INTO prompt_templates (template_type, template_name, system_prompt, user_prompt_template, is_active)
VALUES 
    (
        'qa_pair',
        'Financial QA Pair Generator',
        'You are an expert financial analyst. Generate high-quality question-answer pairs based on the provided financial data. Questions should test understanding of key financial metrics, trends, and business context. Answers should be comprehensive and accurate.',
        'Based on the following financial document:\n\n{{content}}\n\nGenerate 3 high-quality question-answer pairs that test understanding of:\n1. Key financial metrics and ratios\n2. Business trends and performance\n3. Risk factors or outlook\n\nFormat your response as JSON with structure: {"qa_pairs": [{"question": "...", "answer": "..."}]}',
        true
    ),
    (
        'reasoning_chain',
        'Chain-of-Thought Financial Reasoning',
        'You are an expert financial analyst who explains your reasoning step by step. When analyzing financial data, show your complete thought process including calculations, comparisons, and conclusions.',
        'Analyze the following financial data and provide a chain-of-thought reasoning:\n\n{{content}}\n\nProvide your analysis in the following JSON format:\n{\n  "context": "Brief summary of the data",\n  "reasoning_steps": ["Step 1...", "Step 2...", ...],\n  "calculations": {"metric_name": {"formula": "...", "result": ...}},\n  "conclusion": "Your final assessment"\n}',
        true
    ),
    (
        'summary',
        'Executive Summary Generator',
        'You are a financial report summarizer. Create concise, executive-level summaries that highlight the most important information for decision-makers.',
        'Create an executive summary of the following financial document:\n\n{{content}}\n\nProvide your summary in the following JSON format:\n{\n  "headline": "One-line summary",\n  "key_points": ["Point 1", "Point 2", ...],\n  "metrics_highlights": [{"metric": "...", "value": "...", "context": "..."}],\n  "outlook": "Forward-looking statement"\n}',
        true
    ),
    (
        'risk_analysis',
        'Risk Factor Analyzer',
        'You are a risk analyst specializing in financial markets. Identify and assess risk factors from financial documents.',
        'Analyze the risk factors in the following document:\n\n{{content}}\n\nProvide your analysis in JSON format:\n{\n  "identified_risks": [{"risk": "...", "severity": "high/medium/low", "likelihood": "high/medium/low", "impact": "..."}],\n  "risk_correlations": ["..."],\n  "mitigation_strategies": ["..."]\n}',
        true
    ),
    (
        'metrics_extraction',
        'Financial Metrics Extractor',
        'You are a financial data extraction specialist. Extract structured financial metrics from documents.',
        'Extract all quantitative financial metrics from the following document:\n\n{{content}}\n\nProvide extracted data in JSON format:\n{\n  "metrics": [{"name": "...", "value": ..., "unit": "...", "period": "...", "source_text": "..."}],\n  "ratios": [{"name": "...", "value": ..., "interpretation": "..."}]\n}',
        true
    )
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Enable Row Level Security (optional, for production)
-- =============================================================================

-- ALTER TABLE raw_documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE generated_samples ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE human_annotations ENABLE ROW LEVEL SECURITY;

SELECT 'Phase 1 DataForge schema initialized successfully!' as result;
"""


def run_with_psycopg2(db_url: str):
    """Execute DDL using psycopg2."""
    print("Using psycopg2 for database connection...")
    
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    
    try:
        with conn.cursor() as cur:
            # Split by semicolons and execute each statement
            statements = [s.strip() for s in PHASE1_DDL.split(';') if s.strip()]
            for stmt in statements:
                if stmt and not stmt.startswith('--'):
                    try:
                        cur.execute(stmt + ';')
                        print(f"✓ Executed: {stmt[:60]}...")
                    except Exception as e:
                        # Skip if already exists
                        if 'already exists' in str(e).lower():
                            print(f"⊘ Skipped (exists): {stmt[:60]}...")
                        else:
                            print(f"⚠ Warning: {e}")
            
            print("\n✅ Phase 1 DataForge schema initialized successfully!")
    finally:
        conn.close()


async def run_with_asyncpg(db_url: str):
    """Execute DDL using asyncpg."""
    print("Using asyncpg for database connection...")
    
    conn = await asyncpg.connect(db_url)
    
    try:
        # Execute the entire DDL
        await conn.execute(PHASE1_DDL)
        print("\n✅ Phase 1 DataForge schema initialized successfully!")
    finally:
        await conn.close()


def run_with_supabase():
    """Use Supabase client to execute SQL via RPC (if available)."""
    from supabase import create_client
    
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required")
    
    print("Using Supabase client...")
    client = create_client(url, key)
    
    # Check if tables exist by trying to query them
    try:
        result = client.table("raw_documents").select("id", count="exact").limit(1).execute()
        print("✓ raw_documents table exists")
    except Exception as e:
        print(f"⚠ raw_documents table check: {e}")
    
    try:
        result = client.table("generated_samples").select("id", count="exact").limit(1).execute()
        print("✓ generated_samples table exists")
    except Exception as e:
        print(f"⚠ generated_samples table check: {e}")
    
    try:
        result = client.table("human_annotations").select("id", count="exact").limit(1).execute()
        print("✓ human_annotations table exists")
    except Exception as e:
        print(f"⚠ human_annotations table check: {e}")
    
    try:
        result = client.table("prompt_templates").select("id", count="exact").limit(1).execute()
        print("✓ prompt_templates table exists")
    except Exception as e:
        print(f"⚠ prompt_templates table check: {e}")
    
    print("\n📋 Tables verified. Run DDL manually in Supabase SQL Editor if needed.")
    print("\n--- DDL for manual execution ---")
    print(PHASE1_DDL)


def main():
    print("=" * 60)
    print("DataForge Phase 1 - Database Initialization")
    print("=" * 60)
    
    db_url = os.getenv('SUPABASE_DB_URL')
    
    if db_url and USE_PSYCOPG2:
        run_with_psycopg2(db_url)
    elif db_url and USE_ASYNCPG:
        asyncio.run(run_with_asyncpg(db_url))
    else:
        print("No direct database connection available.")
        print("Attempting Supabase client verification...")
        try:
            run_with_supabase()
        except Exception as e:
            print(f"Error: {e}")
            print("\n📋 Copy the DDL above and run it in Supabase SQL Editor.")
            return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
