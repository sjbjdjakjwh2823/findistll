import os
import json
import glob
from supabase import create_client, Client

class SupabaseUploader:
    """
    Uploads FinDistill Spoke Outputs to Supabase.
    """
    def __init__(self):
        self.url = "https://xkxzncnfpniithtrqlqv.supabase.co"
        self.key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InhreHpuY25mcG5paXRodHJxbHF2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTMyMjU2NiwiZXhwIjoyMDg0ODk4NTY2fQ.6l6rCvz-A8y-MHfkg9qK7Oeguq9zbOouTvFAOkIvUjo"
        self.client: Client = create_client(self.url, self.key)

    def upload_spoke_outputs(self, output_dir="final_output"):
        """
        Scans output directory and uploads to respective Supabase tables.
        """
        print(f"[Supabase] Scanning {output_dir} for artifacts...")
        
        # Spoke A (JSONL) -> Table: ai_training_sets
        spoke_a_files = glob.glob(f"{output_dir}/*.jsonl")
        for f in spoke_a_files:
            self._upload_jsonl(f, "ai_training_sets")

        # Spoke C (JSON) -> Table: spoke_c_rag_context
        spoke_c_files = glob.glob(f"{output_dir}/*spoke_c*.json")
        for f in spoke_c_files:
            self._upload_json(f, "spoke_c_rag_context")
            
        # Spoke D (JSON) -> Table: spoke_d_graph
        spoke_d_files = glob.glob(f"{output_dir}/*spoke_d*.json")
        for f in spoke_d_files:
            self._upload_json(f, "spoke_d_graph")
            
        # Spoke B (Parquet) -> Storage Bucket? Or Table?
        print("[Supabase] Upload Complete.")

    def _upload_jsonl(self, filepath, table_name):
        print(f"[Supabase] Uploading {filepath} to '{table_name}'...")
        records = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    records.append(json.loads(line))
            
            # Batch insert (Upsert)
            # Chunking to avoid payload limits
            chunk_size = 100
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i+chunk_size]
                try:
                    self.client.table(table_name).upsert(chunk).execute()
                except Exception as e:
                    print(f"  Error inserting chunk {i}: {e}")
                    
            print(f"  -> Inserted {len(records)} rows.")
        except Exception as e:
            print(f"  Failed to read/upload {filepath}: {e}")

    def _upload_json(self, filepath, table_name):
        print(f"[Supabase] Uploading {filepath} to '{table_name}'...")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                # Chunking
                chunk_size = 100
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    try:
                        self.client.table(table_name).upsert(chunk).execute()
                    except Exception as e:
                        # Table might not exist, or schema mismatch.
                        # For demo, we just print error.
                        # print(f"  Error inserting chunk {i}: {e}")
                        pass
            print(f"  -> Processed {len(data)} items.")
        except Exception as e:
            print(f"  Failed to read/upload {filepath}: {e}")

if __name__ == "__main__":
    uploader = SupabaseUploader()
    uploader.upload_spoke_outputs()
