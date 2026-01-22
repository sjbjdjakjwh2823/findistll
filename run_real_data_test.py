import os
import shutil
import glob
from main import Orchestrator
from ingestors import Ingestor

def run_real_world_test():
    # 1. Define Source Directory (Desktop) and patterns
    desktop_path = r"C:\Users\Administrator\Desktop"
    output_dir = r"C:\Users\Administrator\Desktop\FinDistill_Output"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"Scanning {desktop_path} for real data...")
    
    # Specific files found in 'ls'
    target_files = [
        r"C:\Users\Administrator\Desktop\tsla-20250422-gen.pdf", # PDF
        r"C:\Users\Administrator\Desktop\aapl-20250927_htm.xml", # XML/HTML?
        # XLSX: Need to find one. The grep showed 'GE_2023.xlsx' in Artifacts, but let's check deep search.
        # Actually grep output showed 'GE_2023.xlsx' only as part of 'converted_GE_2023.xlsx.json' filename?
        # Let's check 'Desktop/CES_Converted_Artifacts' for ANY original file.
        # If not, we will use the JSONs as 'pre-ingested' data.
    ]
    
    # Let's also look for any .xlsx or .html recursively
    # We use glob for a broader search
    extensions = ["**/*.pdf", "**/*.xlsx", "**/*.html", "**/*.xml", "**/*.xbrl"]
    found_files = []
    for ext in extensions:
        # Recursive glob requires python 3.10+ and glob.glob(root, recursive=True)
        # Limit depth to avoid scanning whole C drive if we mess up path
        found_files.extend(glob.glob(os.path.join(desktop_path, ext), recursive=True))
        
    # Filter out system files or likely irrelevant ones
    # Filter for known financial tickers or keywords
    keywords = ["2023", "2024", "2025", "report", "financial", "tsla", "aapl", "samsung", "entity", "ces"]
    valid_files = [
        f for f in found_files 
        if any(k in os.path.basename(f).lower() for k in keywords) 
        and "converted_" not in os.path.basename(f) # Skip the json artifacts for now, prefer raw
        and "lnk" not in f
    ]
    
    # Dedup
    valid_files = list(set(valid_files))
    
    print(f"Found {len(valid_files)} potential financial documents.")
    
    all_facts = []
    processed_files = []

    for fpath in valid_files:
        if os.path.getsize(fpath) > 10 * 1024 * 1024: # Skip > 10MB to avoid timeout
            continue
            
        print(f"Processing: {os.path.basename(fpath)}")
        facts = Ingestor.ingest_file(fpath)
        if facts:
            print(f"  -> Extracted {len(facts)} facts.")
            all_facts.extend(facts)
            processed_files.append(os.path.basename(fpath))
        else:
            print("  -> No usable data found.")
            
    if not all_facts:
        print("No data extracted from any file. Exiting.")
        return

    print(f"Total extracted facts: {len(all_facts)}")
    
    # Run Orchestrator
    orchestrator = Orchestrator()
    try:
        orchestrator.process_pipeline(all_facts)
    finally:
        orchestrator.shutdown()
        
    # Move Outputs to Desktop
    print("Moving artifacts to Desktop/FinDistill_Output...")
    project_output = r"project_1/output"
    if os.path.exists(project_output):
        for f in os.listdir(project_output):
            src = os.path.join(project_output, f)
            dst = os.path.join(output_dir, f)
            # Handle directories (partitioned parquet)
            if os.path.isdir(src):
                if os.path.exists(dst): shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
                
    # Create Briefing Text
    import pandas as pd
    briefing = f"""
    FinDistill v19.5 Execution Report
    ---------------------------------
    Date: {pd.Timestamp.now()}
    Files Processed: {len(processed_files)}
    
    List of Processed Files:
    {chr(10).join(processed_files)}
    
    Total Data Points: {len(all_facts)}
    
    Outputs Generated:
    - AI Tuning Data (JSONL): Optimized for CoT training.
    - Quant Data (Parquet): Partitioned by Year/Month.
    - RAG Vectors (JSON): Context-aware chunks.
    - Risk Graph (JSON): Entity-Metric-Value triples.
    
    Status: Completed Successfully.
    """
    
    with open(os.path.join(output_dir, "Briefing_Report.txt"), "w", encoding="utf-8") as f:
        f.write(briefing)
        
    print("Process Complete.")

if __name__ == "__main__":
    run_real_world_test()
