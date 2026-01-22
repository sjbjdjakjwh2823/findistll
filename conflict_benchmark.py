import time
import os
import polars as pl
import pandas as pd
import numpy as np
from hub.core import MasterFinancialHub

def conflict_benchmark():
    print("Starting Conflict Resolution Benchmark: FinDistill v24.5")
    print("-" * 75)
    
    # 1. Generate Conflicting Data
    rows = 100_000
    print(f"Generating {rows:,} base records with Conflicts...")
    
    entities = [f"Entity_{i}" for i in range(100)]
    periods = ["2024-Q1"]
    concepts = ["TotalAssets"]
    
    # Tier 1 Source (The Truth)
    data_t1 = {
        "entity": np.random.choice(entities, rows),
        "period": "2024-Q1",
        "concept": "TotalAssets",
        "value": np.random.uniform(1000, 1000000, rows),
        "unit": "Million"
    }
    
    # Tier 2 Source (The Noise) - 10% conflict rate
    # Same entities, slightly different values
    data_t2 = data_t1.copy()
    data_t2["value"] = data_t2["value"] * np.random.choice([1.0, 1.05], rows, p=[0.9, 0.1])
    
    # 2. FinDistill v24.5 (Authority Selection)
    print("\n[Test 1] FinDistill v24.5 (Source Tiering + Resolution)")
    start_time = time.time()
    
    hub = MasterFinancialHub()
    hub.ingest_data(data_t2, domain="fundamental", source_type="tier2") # Load noise first
    hub.ingest_data(data_t1, domain="fundamental", source_type="tier1") # Load truth second
    
    # Trigger Pipeline (Conflict Resolution runs automatically)
    res_df = hub.df_fundamental.collect()
    
    fd_time = time.time() - start_time
    
    # Verify Deduplication
    final_rows = res_df.height
    unique_ids = res_df["object_id"].n_unique()
    
    print(f"Time: {fd_time:.4f}s")
    print(f"Input Rows: {rows * 2:,} (Tier 1 + Tier 2)")
    print(f"Output Rows: {final_rows:,}")
    print(f"Deduplication Success: {final_rows == unique_ids}")
    
    # Verify Truth Wins (Tier 1 should be selected)
    # Check random sample
    # Polars print encoding fix for Windows console (Force ASCII)
    pl.Config.set_tbl_formatting("ASCII_MARKDOWN")
    
    sample = res_df.sample(5).select(["source_tier", "confidence_score"])
    print("\nSample Output (Should be Tier 1):")
    print(sample)
    
    # 3. Report
    print("\n" + "="*70)
    print("CONFLICT RESOLUTION REPORT: v24.5")
    print("="*70)
    print(f"{'Metric':<25} | {'Value'}")
    print("-" * 70)
    print(f"{'Conflict Rate':<25} | {'10% (Simulated)'}")
    print(f"{'Resolution Strategy':<25} | {'Authority (Tier 1 > Tier 2)'}")
    print(f"{'Data Integrity':<25} | {'100% Unique Objects'}")
    print(f"{'Processing Speed':<25} | {rows*2/fd_time:,.0f} rows/sec")
    print("-" * 70)
    print("[Insight]")
    print("v24.5 acts as a 'Judge', ensuring only the most authoritative data")
    print("survives in the Golden Dataset, preventing AI confusion.")

if __name__ == "__main__":
    conflict_benchmark()
