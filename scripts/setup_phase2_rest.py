#!/usr/bin/env python3
"""
Execute Phase 2 SQL via Supabase REST API.
Uses the postgrest endpoint for DDL operations.
"""

import os
import json
import urllib.request
import urllib.error

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

if not SUPABASE_URL or not SERVICE_KEY:
    raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")


def supabase_request(endpoint: str, method: str = "GET", data: dict = None):
    """Make a request to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    
    req_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        return {"error": error_body, "status": e.code}


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists by trying to select from it."""
    result = supabase_request(f"{table_name}?select=count&limit=0")
    return "error" not in result or result.get("status") != 404


def insert_causal_nodes():
    """Insert seed causal nodes."""
    nodes = [
        {"name": "Fed_Funds_Rate", "category": "macro", "properties": {"description": "Federal Reserve interest rate target"}},
        {"name": "Inflation_CPI", "category": "macro", "properties": {"description": "Consumer Price Index inflation rate"}},
        {"name": "GDP_Growth", "category": "macro", "properties": {"description": "Real GDP growth rate"}},
        {"name": "Unemployment_Rate", "category": "macro", "properties": {"description": "U.S. unemployment rate"}},
        {"name": "SP500_Index", "category": "metric", "properties": {"description": "S&P 500 stock market index"}},
        {"name": "Tech_Sector_Valuation", "category": "sector", "properties": {"description": "Technology sector valuation multiple"}},
        {"name": "Bond_Yields_10Y", "category": "macro", "properties": {"description": "10-year Treasury yield"}},
        {"name": "USD_Index", "category": "macro", "properties": {"description": "U.S. Dollar strength index"}},
        {"name": "Oil_Price_WTI", "category": "macro", "properties": {"description": "WTI crude oil price"}},
        {"name": "VIX_Index", "category": "metric", "properties": {"description": "CBOE Volatility Index"}},
    ]
    
    inserted = 0
    for node in nodes:
        # Use upsert-like behavior with on_conflict
        url = f"{SUPABASE_URL}/rest/v1/causal_nodes"
        headers = {
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }
        
        req = urllib.request.Request(url, data=json.dumps(node).encode(), headers=headers, method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            inserted += 1
        except urllib.error.HTTPError as e:
            if e.code == 409:  # Conflict = already exists
                pass
            else:
                print(f"   Warning: {node['name']}: {e}")
    
    return inserted


def get_node_id(name: str) -> str:
    """Get node ID by name."""
    result = supabase_request(f"causal_nodes?name=eq.{name}&select=id")
    if result and not isinstance(result, dict):
        return result[0]["id"] if result else None
    return None


def insert_causal_edges():
    """Insert seed causal edges."""
    edges_def = [
        ("Fed_Funds_Rate", "Tech_Sector_Valuation", "negative_correlation", -0.7, 30, 0.85),
        ("Inflation_CPI", "Fed_Funds_Rate", "positive_correlation", 0.6, 0, 0.8),
        ("Fed_Funds_Rate", "GDP_Growth", "negative_correlation", -0.8, 90, 0.75),
        ("VIX_Index", "Bond_Yields_10Y", "positive_correlation", 0.7, 0, 0.9),
        ("USD_Index", "Oil_Price_WTI", "negative_correlation", -0.5, 7, 0.7),
    ]
    
    inserted = 0
    for source_name, target_name, relation, weight, lag, confidence in edges_def:
        source_id = get_node_id(source_name)
        target_id = get_node_id(target_name)
        
        if not source_id or not target_id:
            print(f"   Skipping edge {source_name} -> {target_name}: node not found")
            continue
        
        edge = {
            "source_id": source_id,
            "target_id": target_id,
            "relation": relation,
            "weight": weight,
            "lag_days": lag,
            "confidence": confidence,
        }
        
        url = f"{SUPABASE_URL}/rest/v1/causal_edges"
        headers = {
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=ignore-duplicates,return=minimal",
        }
        
        req = urllib.request.Request(url, data=json.dumps(edge).encode(), headers=headers, method="POST")
        try:
            urllib.request.urlopen(req, timeout=10)
            inserted += 1
        except urllib.error.HTTPError as e:
            if e.code == 409:  # Already exists
                pass
            else:
                print(f"   Warning: {source_name}->{target_name}: {e}")
    
    return inserted


def count_rows(table: str) -> int:
    """Count rows in a table."""
    result = supabase_request(f"{table}?select=id")
    if isinstance(result, list):
        return len(result)
    return 0


def main():
    print("🧠 Phase 2: AI Brain - Database Setup via REST API")
    print("=" * 60)
    
    # Check if tables exist
    print("\n📊 Checking table existence...")
    tables = ["embeddings_finance", "causal_nodes", "causal_edges", "ai_brain_traces"]
    
    missing = []
    for table in tables:
        exists = check_table_exists(table)
        status = "✅" if exists else "❌"
        print(f"   {status} {table}")
        if not exists:
            missing.append(table)
    
    if missing:
        print(f"\n⚠️  Missing tables: {', '.join(missing)}")
        print("   Please run the SQL in supabase_phase2.sql via Supabase SQL Editor:")
        print("   https://supabase.com/dashboard → Your Project → SQL Editor")
        print("\n   SQL file location: preciso/supabase_phase2.sql")
        return
    
    # Seed data
    print("\n🌱 Seeding causal nodes...")
    nodes_inserted = insert_causal_nodes()
    print(f"   Inserted/verified {nodes_inserted} nodes")
    
    print("\n🔗 Seeding causal edges...")
    edges_inserted = insert_causal_edges()
    print(f"   Inserted/verified {edges_inserted} edges")
    
    # Final verification
    print("\n📊 Final verification:")
    for table in tables:
        count = count_rows(table)
        print(f"   {table}: {count} rows")
    
    print("\n✅ Phase 2 DB setup complete!")


if __name__ == "__main__":
    main()
