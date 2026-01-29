import time
import os
import shutil
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hub.core import MasterFinancialHub
from spokes.engines import SpokeA, SpokeB, SpokeC, SpokeD
from deployment.huggingface_connector import HuggingFaceConnector
from deployment.supabase_uploader import SupabaseUploader

def run_auto_pipeline():
    print("Starting FinDistill v29.0 Auto-Pipeline (HF -> Hub -> Supabase)")
    print("=" * 80)
    
    # 1. Initialize Components
    hub = MasterFinancialHub()
    hf = HuggingFaceConnector()
    uploader = SupabaseUploader()
    
    # 2. Ingest from Hugging Face
    # This downloads 'sdkfsklf/preciso' (or valid dataset) and feeds to Hub
    print("\n[Step 1] Fetching Data from Hugging Face...")
    try:
        hf.feed_to_hub(hub, limit=5000) # Limit for demo speed
    except Exception as e:
        print(f"HF Ingest Failed (Expected if dataset private/missing): {e}")
        print(">> Switching to Fallback Simulation Data...")
        # Fallback Data
        data_sim = [{"entity": f"Sim_{i}", "period": "2024-01-01", "concept": "Price", "value": 100 + i, "unit": "USD"} for i in range(100)]
        hub.ingest_data(data_sim, domain="market", source_type="tier3")

    # 3. Run Engine (Transform)
    print("\n[Step 2] Running FinDistill Engine...")
    hub.run()
    
    # 4. Generate Outputs
    print("\n[Step 3] Generating Spoke Artifacts...")
    out_dir = "final_output"
    os.makedirs(out_dir, exist_ok=True)
    
    arrow_table = hub.get_arrow_table()
    
    # Generate all spokes
    SpokeA().generate(arrow_table, f"{out_dir}/spoke_a.jsonl")
    SpokeB().generate(arrow_table, f"{out_dir}/spoke_b.parquet")
    SpokeC().generate(arrow_table, f"{out_dir}/spoke_c.json")
    SpokeD().generate(arrow_table, f"{out_dir}/spoke_d.json")
    
    # 5. Upload to Supabase
    print("\n[Step 4] Uploading to Supabase...")
    uploader.upload_spoke_outputs(out_dir)
    
    print("\n" + "="*80)
    print("PIPELINE COMPLETE")
    print("Data flowed from Cloud (HF) -> Engine (Local) -> Cloud (Supabase)")

if __name__ == "__main__":
    run_auto_pipeline()
