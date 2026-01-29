-- Asura Engine Schema (Granular & Detailed)

-- 1. Market Data (YFinance: Stocks, Commodities, Crypto)
CREATE TABLE IF NOT EXISTS public.market_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    asset_class TEXT NOT NULL, -- 'EQUITY', 'COMMODITY', 'CRYPTO'
    interval TEXT NOT NULL, -- '1m', '1h', '1d'
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    adj_close NUMERIC,
    currency TEXT DEFAULT 'USD',
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, interval, timestamp)
);

-- 2. Macro Data (FRED: Rates, Economic Indicators)
CREATE TABLE IF NOT EXISTS public.macro_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    series_id TEXT NOT NULL, -- e.g., 'FEDFUNDS', 'GDP'
    category TEXT, -- 'INTEREST_RATE', 'INFLATION', 'EMPLOYMENT'
    value NUMERIC,
    unit TEXT,
    period_date DATE NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(series_id, period_date)
);

-- 3. Geo-Political Data (GDELT)
CREATE TABLE IF NOT EXISTS public.geo_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_code TEXT,
    actor1_name TEXT,
    actor2_name TEXT,
    goldstein_scale NUMERIC, -- Impact Rating (-10 to +10)
    num_mentions INTEGER,
    num_sources INTEGER,
    avg_tone NUMERIC,
    source_url TEXT,
    event_date TIMESTAMPTZ NOT NULL,
    region TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Fundamental Data (Alpha Vantage)
CREATE TABLE IF NOT EXISTS public.company_fundamentals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ticker TEXT NOT NULL,
    report_type TEXT NOT NULL, -- 'BALANCE_SHEET', 'INCOME_STATEMENT', 'CASH_FLOW'
    fiscal_date_ending DATE NOT NULL,
    total_revenue NUMERIC,
    net_income NUMERIC,
    eps NUMERIC,
    total_assets NUMERIC,
    total_liabilities NUMERIC,
    operating_cashflow NUMERIC,
    raw_data JSONB, -- Store full response for granularity
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, report_type, fiscal_date_ending)
);

-- 5. Hugging Face Data (NLP/Sentiment/Datasets)
CREATE TABLE IF NOT EXISTS public.huggingface_data (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    dataset_name TEXT NOT NULL, -- e.g., 'financial_phrasebank'
    subset TEXT,
    data_content JSONB NOT NULL, -- The actual row content
    sentiment_score NUMERIC, -- If applicable
    sentiment_label TEXT,    -- If applicable
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.market_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.macro_data ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.geo_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_fundamentals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.huggingface_data ENABLE ROW LEVEL SECURITY;
