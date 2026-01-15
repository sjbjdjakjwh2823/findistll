"""
FinDistill Embedding Service

Generates vector embeddings using Gemini API via HTTP for:
- Document similarity search
- RAG retrieval
- Semantic clustering
"""

import httpx
from typing import List
import os

# Gemini API configuration
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class EmbeddingService:
    """Generates and manages vector embeddings for documents via HTTP."""
    
    # Gemini embedding dimension
    EMBEDDING_DIM = 768
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = "text-embedding-004"
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using Gemini via HTTP.
        
        Args:
            text: Text to embed
            
        Returns:
            768-dimensional embedding vector
        """
        if not text or len(text.strip()) == 0:
            return [0.0] * self.EMBEDDING_DIM
        
        # Truncate if too long (Gemini has token limits)
        max_chars = 10000
        if len(text) > max_chars:
            text = text[:max_chars]
        
        return await self._call_embed_api(text, "RETRIEVAL_DOCUMENT")
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.
        Uses different task type for better retrieval.
        """
        if not query or len(query.strip()) == 0:
            return [0.0] * self.EMBEDDING_DIM
        
        return await self._call_embed_api(query, "RETRIEVAL_QUERY")
    
    async def _call_embed_api(self, text: str, task_type: str) -> List[float]:
        """Call Gemini embedding API via HTTP."""
        url = f"{GEMINI_API_BASE}/models/{self.model}:embedContent?key={self.api_key}"
        
        payload = {
            "model": f"models/{self.model}",
            "content": {
                "parts": [{"text": text}]
            },
            "taskType": task_type
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        
        embedding = data.get("embedding", {}).get("values", [])
        if not embedding:
            return [0.0] * self.EMBEDDING_DIM
        
        return embedding
    
    def create_document_text(self, data: dict) -> str:
        """
        Create a text representation of document for embedding.
        Combines title, summary, and key information.
        """
        parts = []
        
        # Title
        if "title" in data:
            parts.append(f"제목: {data['title']}")
        
        # Summary
        if "summary" in data:
            parts.append(f"요약: {data['summary']}")
        
        # Key metrics
        if "key_metrics" in data:
            metrics_text = ", ".join([
                f"{k}: {v}" for k, v in data["key_metrics"].items()
            ])
            parts.append(f"주요 지표: {metrics_text}")
        
        # Table names and headers
        if "tables" in data:
            for table in data["tables"]:
                table_name = table.get("name", "")
                headers = table.get("headers", [])
                parts.append(f"테이블 '{table_name}': {', '.join(str(h) for h in headers)}")
        
        return "\n".join(parts)


# Singleton instance  
embedder = EmbeddingService()
