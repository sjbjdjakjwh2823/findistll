-- Asura Engine Schema Update: Spoke A, B, C, D Tables

-- Spoke A: AI Tuning / Strategy (Instruction Data)
CREATE TABLE IF NOT EXISTS public.spoke_a_strategy (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    entity TEXT NOT NULL,
    period TEXT,
    instruction TEXT,
    input_context TEXT,
    output_strategy TEXT, -- The "Strategy: Hold..." part
    analysis_trace TEXT,  -- The "Step 1, Step 2..." CoT part
    confidence TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spoke B: Quant Engine (Parquet Metadata)
-- Note: Actual Parquet files are typically stored in Storage Buckets.
-- Here we store metadata about the processed quant datasets.
CREATE TABLE IF NOT EXISTS public.spoke_b_quant_meta (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    dataset_name TEXT,
    partition_year TEXT,
    partition_month TEXT,
    record_count INTEGER,
    storage_path TEXT, -- Link to where the parquet file is (if using storage)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spoke C: RAG Context (Vector Ready)
CREATE TABLE IF NOT EXISTS public.spoke_c_rag_context (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    chunk_id TEXT UNIQUE, -- e.g. BTC_2024-01-01_Close
    entity TEXT,
    period TEXT,
    source TEXT,
    text_content TEXT, -- "On 2024..., BTC recorded..."
    keywords TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spoke D: Knowledge Graph (Triples)
CREATE TABLE IF NOT EXISTS public.spoke_d_graph (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    head_node TEXT NOT NULL,
    relation TEXT NOT NULL,
    tail_node TEXT NOT NULL,
    properties JSONB, -- {"strength": "High", "lag": "2-Days"}
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.spoke_a_strategy ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spoke_b_quant_meta ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spoke_c_rag_context ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spoke_d_graph ENABLE ROW LEVEL SECURITY;
