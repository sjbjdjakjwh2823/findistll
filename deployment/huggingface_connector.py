import os
import shutil
import time
from huggingface_hub import snapshot_download
from datasets import load_dataset
from hub.core import MasterFinancialHub

class HuggingFaceConnector:
    """
    Connects to Hugging Face Datasets (sdkfsklf/preciso).
    Downloads new data and feeds it into FinDistill Hub.
    """
    def __init__(self, dataset_name="sdkfsklf/preciso", local_dir="data/hf_cache"):
        self.dataset_name = dataset_name
        self.local_dir = local_dir
        self.token = os.getenv("HF_TOKEN")
        if not self.token:
            print("[Warning] HF_TOKEN env var not found. Using public access.")
        os.makedirs(self.local_dir, exist_ok=True)

    def fetch_latest(self):
        """
        Download dataset or load from cache.
        Returns list of file paths.
        """
        print(f"[HF] Checking for updates on {self.dataset_name}...")
        try:
            # For demo, we use 'load_dataset' which handles caching
            # But FinDistill needs raw files usually. 
            # We will use snapshot_download to get raw files if structured, 
            # OR use load_dataset and convert to Arrow/Dicts for Hub.
            
            # Using load_dataset to get iterator
            ds = load_dataset(self.dataset_name, token=self.token, streaming=True)
            
            # We assume the dataset has 'train' split
            # And structure: {entity, period, concept, value, unit}
            # Or market data structure.
            
            print(f"[HF] Connection Successful. Streaming data...")
            return ds['train']
            
        except Exception as e:
            print(f"[HF] Error fetching data: {e}")
            return None

    def feed_to_hub(self, hub_instance, limit=1000):
        """
        Feeds HF data to Hub.
        Detects domain (Fundamental vs Market) based on columns.
        """
        ds = self.fetch_latest()
        if not ds: return
        
        batch = []
        count = 0
        
        print(f"[HF] Ingesting first {limit} rows...")
        for row in ds:
            batch.append(row)
            count += 1
            if count >= limit:
                break
                
        if not batch:
            print("[HF] Dataset is empty.")
            return

        # Determine Domain
        sample = batch[0]
        domain = "fundamental"
        if "close" in sample or "price" in sample:
            domain = "market"
            
        print(f"[HF] Detected Domain: {domain}")
        
        # Ingest to Hub
        hub_instance.ingest_data(batch, domain=domain, source_type="tier3") # HF is Tier 3 (External)
        print(f"[HF] Successfully ingested {len(batch)} records.")

if __name__ == "__main__":
    # Test Run
    hub = MasterFinancialHub()
    connector = HuggingFaceConnector()
    connector.feed_to_hub(hub)
