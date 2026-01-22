import os
import logging
import time
import concurrent.futures
import polars as pl
import pyarrow as pa
from hub.core import MasterFinancialHub
from spokes.engines import SpokeA, SpokeB, SpokeC, SpokeD

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("Orchestrator")

# Spoke Worker Function (Must be top-level for pickling)
def run_spoke_task(spoke_class, arrow_table, output_filename, output_dir):
    try:
        spoke = spoke_class()
        output_path = os.path.join(output_dir, output_filename)
        spoke.generate(arrow_table, output_path)
        return f"{spoke_class.__name__} Success"
    except Exception as e:
        return f"{spoke_class.__name__} Failed: {e}"

class Orchestrator:
    """
    FinDistill v19.5 Orchestrator: The Speed Engine
    """
    def __init__(self, data_dir="project_1/output"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        # Initialize ProcessPoolExecutor (Warm-up)
        # We use a persistent pool for the lifecycle of the orchestrator
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=4)

    def process_pipeline(self, raw_data_iter):
        logger.info("Orchestrator: Starting v19.5 Pipeline...")
        start_time = time.time()
        
        # Generator for 1M Chunks
        def chunk_generator(data, chunk_size=1000000):
            if isinstance(data, list):
                for i in range(0, len(data), chunk_size):
                    yield data[i:i + chunk_size]
            else:
                import itertools
                iterator = iter(data)
                while True:
                    chunk = list(itertools.islice(iterator, chunk_size))
                    if not chunk:
                        break
                    yield chunk

        chunk_idx = 0
        for chunk in chunk_generator(raw_data_iter):
            chunk_idx += 1
            logger.info(f"Processing Chunk {chunk_idx}...")
            
            arrow_table, audit_score = self._run_hub(chunk)
            
            if not arrow_table or arrow_table.num_rows == 0:
                continue

            logger.info(f"--- Chunk {chunk_idx} Quality Score: {audit_score:.2f}/100 ---")

            spoke_tasks = [
                (SpokeA, f"spoke_a_tuning_part{chunk_idx}.jsonl"),
                (SpokeB, f"spoke_b_quant_part{chunk_idx}.parquet"),
                (SpokeC, f"spoke_c_rag_part{chunk_idx}.json"),
                (SpokeD, f"spoke_d_graph_part{chunk_idx}.json")
            ]
            
            futures = []
            for spoke_cls, fname in spoke_tasks:
                f = self.executor.submit(
                    run_spoke_task, 
                    spoke_cls, 
                    arrow_table, 
                    fname, 
                    self.data_dir
                )
                futures.append(f)
                
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                logger.info(f"Chunk {chunk_idx} Result: {result}")
            
        elapsed = time.time() - start_time
        logger.info(f"Pipeline Completed in {elapsed:.4f} seconds.")

    def _run_hub(self, raw_data):
        hub = MasterFinancialHub()
        hub.ingest_data(raw_data)
        
        arrow_table = hub.get_arrow_table()
        audit_score = hub.get_audit_score()
        
        return arrow_table, audit_score
        
    def shutdown(self):
        self.executor.shutdown()

if __name__ == "__main__":
    # For standalone testing
    pass
