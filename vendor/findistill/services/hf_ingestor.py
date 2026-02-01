import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List
from dotenv import load_dotenv
from huggingface_hub import list_repo_files, hf_hub_download
from datasets import load_dataset
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Import FileIngestionService
try:
    from .ingestion import ingestion_service
except ImportError:
    ingestion_service = None

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hf_ingestor")

class HuggingFaceIngestor:
    def __init__(self):
        load_dotenv()
        self.hf_token = os.getenv("HF_TOKEN")
        # Define multiple datasets/topics
        self.datasets = [
             "sdkfsklf/preciso", # Base dataset
             "finbert/financial_phrasebank", # Financial News
             "zeroshot/twitter-financial-news-sentiment", # Market Sentiment
             # Add other relevant financial datasets found on HF
        ]
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not all([self.hf_token, self.supabase_url, self.supabase_key]):
            logger.warning("Missing configuration for Hugging Face or Supabase. Ingestion disabled.")
            self.enabled = False
        else:
            self.enabled = True
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
            self.scheduler = AsyncIOScheduler()
            
            # Using ingestion_service global instance
            self.ingestion = ingestion_service
            
    def start_polling(self, interval_seconds: int = 60):
        """Start the real-time polling scheduler."""
        if not self.enabled:
            logger.warning("HF Ingestor is disabled due to missing config.")
            return

        logger.info(f"Starting HF Ingestor with {interval_seconds}s interval.")
        self.scheduler.add_job(self._poll_dataset, 'interval', seconds=interval_seconds)
        self.scheduler.start()

    async def _poll_dataset(self):
        """Task to check for new data and ingest it."""
        logger.info("Polling Hugging Face datasets...")
        
        for dataset_name in self.datasets:
            try:
                logger.info(f"Checking dataset: {dataset_name}")
                # logic to fetch data
                # Since we don't know the exact structure, we'll try to load the dataset
                # and fetch the latest rows. In a real real-time scenario, we'd track a cursor.
                
                # For demonstration, we'll fetch the first 10 rows (or latest if sorted)
                # transform them, and upsert them.
                # 'sentences' is specific to financial_phrasebank, 'text' is common.
                # We need to handle config names for some datasets (e.g. phrasebank needs 'sentences_50agree')
                if "financial_phrasebank" in dataset_name:
                     dataset = load_dataset(dataset_name, "sentences_50agree", split="train", streaming=True, token=self.hf_token)
                else:
                     dataset = load_dataset(dataset_name, split="train", streaming=True, token=self.hf_token)
                
                # Take first 3 items per dataset to avoid rate limits
                items = list(dataset.take(3))
                
                logger.info(f"Fetched {len(items)} items from {dataset_name}.")
                
                # Process sequentially to allow async calls
                processed_data = []
                for item in items:
                    # Inject dataset name for tracking
                    item['_dataset_source'] = dataset_name
                    processed = await self._transform(item)
                    processed_data.append(processed)
                    
                await self._save_to_supabase(processed_data)
                
            except Exception as e:
                logger.error(f"Error during HF polling for {dataset_name}: {e}")

    async def _transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw HF data into Supabase schema.
        Uses project_1's FileIngestionService for deep analysis if text is present.
        """
        dataset_name = data.pop('_dataset_source', self.datasets[0])
        
        transformed = {
            "raw_data": data,
            "ingested_at": datetime.utcnow().isoformat(),
            "source": "huggingface",
            "dataset": dataset_name
        }
        
        # Extract text content based on dataset structure
        text_content = ""
        if "sentence" in data: # financial_phrasebank
            text_content = data["sentence"]
        elif "text" in data: # generic
            text_content = data["text"]
            
        # Deep Transformation: Use ingestion_service (XBRLSemanticEngine/Gemini Pipeline)
        if text_content and self.ingestion:
            try:
                if len(text_content) > 50: # Only process meaningful content
                    # ingestion_service.process_file expects bytes
                    content_bytes = text_content.encode('utf-8')
                    
                    # Virtual filename for logging/metadata
                    virtual_filename = f"hf_ingest_{datetime.utcnow().timestamp()}.txt"
                    
                    # Call the Engine
                    logger.info(f"Routing HF data to Ingestion Engine: {virtual_filename}")
                    engine_result = await self.ingestion.process_file(
                        content_bytes, 
                        virtual_filename, 
                        "text/plain"
                    )
                    
                    # Add Engine results to transformed data
                    transformed["engine_result"] = engine_result
                    transformed["content_summary"] = engine_result.get("summary", "No summary generated")
                    transformed["structured_facts"] = engine_result.get("facts", [])
                else:
                    transformed["content_summary"] = text_content
            except Exception as e:
                logger.error(f"Engine transformation failed: {e}")
                transformed["content_summary"] = text_content[:100] + "... (Engine Failed)"
        elif text_content:
             transformed["content_summary"] = text_content[:100] + "..."
        
        return transformed

    async def _save_to_supabase(self, data: List[Dict[str, Any]]):
        """Save batch data to Supabase."""
        if not data:
            return

        try:
            # We assume a table 'ingested_data' exists. 
            # If not, we might fail unless we create it or map to 'documents'.
            # For this task, I'll assume we use a generic 'ingested_data' table
            # OR map to the existing 'documents' table if suitable (but documents table seems file-centric).
            
            # Let's try to insert into 'ingested_data'.
            # Note: You might need to create this table in Supabase if it doesn't exist.
            
            # For safety in this environment, I will log the intended insert
            # and try to insert.
            response = self.supabase.table("ingested_data").upsert(data).execute()
            logger.info(f"Successfully saved {len(data)} rows to Supabase.")
            
        except Exception as e:
            logger.error(f"Failed to save to Supabase: {e}")
            # Fallback: Log that table might be missing
            if "relation" in str(e) and "does not exist" in str(e):
                 logger.error("Table 'ingested_data' does not exist in Supabase. Please create it.")

hf_ingestor = HuggingFaceIngestor()
