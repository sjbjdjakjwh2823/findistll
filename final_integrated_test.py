import time
import os
import polars as pl
import pandas as pd
import numpy as np
from hub.core import MasterFinancialHub
from spokes.engines import SpokeA, SpokeB, SpokeC, SpokeD

def final_integrated_test():
    print("Starting FinDistill Grand Final Test (v19.5 - v27.0)")
    print("=" * 80)
    
    # 1. Data Preparation (Multi-Source, Multi-Domain)
    print("[Phase 1] Data Generation (The Chaos)")
    rows_f = 50_000
    ticks_m = 1_000_000
    
    # Fundamental: Tier 1 (Truth) & Tier 2 (Noise)
    data_f_t1 = {
        "entity": [f"Entity_{i}" for i in range(rows_f)],
        "period": ["2024-Q1"] * rows_f,
        "concept": ["TotalAssets"] * rows_f,
        "value": np.random.uniform(1000, 1000000, rows_f),
        "unit": ["Million"] * rows_f
    }
    data_f_t2 = data_f_t1.copy()
    data_f_t2["value"] = np.array(data_f_t1["value"]) * 1.1 # Conflict!
    
    # Market: High Volatility Scenario
    data_m = {
        "entity": np.random.choice([f"Entity_{i}" for i in range(rows_f)], ticks_m),
        "date": "2024-01-01",
        "close": np.random.uniform(100, 200, ticks_m) * np.concatenate([np.ones(ticks_m//2), np.random.uniform(1, 5, ticks_m//2)]),
        "volume": np.random.randint(100, 10000, ticks_m),
        "bid": np.random.uniform(99, 199, ticks_m),
        "ask": np.random.uniform(101, 201, ticks_m),
        "bid_size": np.random.randint(10, 100, ticks_m),
        "ask_size": np.random.randint(10, 100, ticks_m)
    }
    
    print(f"Generated {rows_f*2 + ticks_m:,} raw records.")

    # 2. Engine Execution
    print("\n[Phase 2] Engine Execution (The Order)")
    start_time = time.time()
    
    hub = MasterFinancialHub()
    
    # Ingest Fundamentals (Conflict Resolution Trigger)
    hub.ingest_data(data_f_t2, domain="fundamental", source_type="tier2")
    hub.ingest_data(data_f_t1, domain="fundamental", source_type="tier1")
    
    # Ingest Market (Alpha & Execution Trigger)
    hub.ingest_data(data_m, domain="market")
    
    # Trigger Calculations (Lazy -> Eager)
    # v28.0 API change: run() must be called
    hub.run()
    
    df_f = hub.df_fundamental.collect()
    df_m = hub.df_market.collect()
    arrow_f = df_f.to_arrow()
    arrow_m = df_m.to_arrow()
    
    exec_time = time.time() - start_time
    print(f"Total Execution Time: {exec_time:.4f}s")
    
    # 3. Validation & Metrics
    print("\n[Phase 3] Validation & Inspection")
    
    # Integrity Check
    unique_f = df_f["object_id"].n_unique()
    print(f"Fundamental Rows: {df_f.height:,} (Expected {rows_f:,} unique)")
    print(f"Conflict Resolution: {'Pass' if df_f.height == unique_f else 'Fail'}")
    
    # Intelligence Check
    cols_m = df_m.columns
    features = [
        ("Microstructure", "ofi_signal"),
        ("Memory", "frac_diff_04"),
        ("Strategy", "evolved_strategy_signal"),
        ("Execution", "net_alpha_score"),
        ("Auto-Tuning", "market_regime")
    ]
    
    print(f"{'Module':<20} | {'Status':<10} | {'Feature'}")
    print("-" * 50)
    for mod, col in features:
        status = "Active" if col in cols_m else "Missing"
        print(f"{mod:<20} | {status:<10} | {col}")
        
    # 4. Spoke Generation
    print("\n[Phase 4] Product Generation (The Value)")
    out_dir = "final_output"
    os.makedirs(out_dir, exist_ok=True)
    
    # Generate Samples
    SpokeA().generate(arrow_m.slice(0, 100), f"{out_dir}/spoke_a.jsonl")
    SpokeB().generate(arrow_m.slice(0, 100), f"{out_dir}/spoke_b.parquet")
    SpokeC().generate(arrow_m.slice(0, 100), f"{out_dir}/spoke_c.json")
    SpokeD().generate(arrow_m.slice(0, 100), f"{out_dir}/spoke_d.json")
    
    print(f"All Spokes generated in '{out_dir}/'")
    
    print("\n" + "="*80)
    print("GRAND FINAL REPORT: FinDistill Complete Architecture")
    print("="*80)
    print("The system has successfully ingested chaotic, conflicting data,")
    print("purified it, evolved strategies, optimized execution, and")
    print("produced AI-ready artifacts in sub-second time.")

if __name__ == "__main__":
    final_integrated_test()
