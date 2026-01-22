import csv
from main import Orchestrator

def verify_pipeline():
    data_file = "large_financial_data.csv"
    if not os.path.exists(data_file):
        print("Dataset not found. Run generate_dataset.py first.")
        return

    print("Starting Pipeline Verification with Streaming...")
    
    # Use a generator to read CSV row by row (Simulate Stream)
    def csv_reader(fname):
        with open(fname, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert value to float immediately for Polars? 
                # Polars infer_schema might handle strings, but safe to convert if we passed list of dicts.
                # But here we pass dicts with strings. Polars handles it.
                row['value'] = float(row['value'])
                yield row

    orchestrator = Orchestrator()
    try:
        orchestrator.process_pipeline(csv_reader(data_file))
    finally:
        orchestrator.shutdown()

    print("Verification Complete. Check logs and output folder.")

import os
if __name__ == "__main__":
    verify_pipeline()
