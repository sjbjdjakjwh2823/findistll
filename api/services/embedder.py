"""
FinDistill Embedding Service

Generates vector embeddings using Gemini API for:
- Document similarity search
- RAG retrieval
- Semantic clustering
"""

from google import genai
from typing import List, Optional
import os


class EmbeddingService:
    """Generates and manages vector embeddings for documents."""
    
    # Gemini embedding dimension
    EMBEDDING_DIM = 768
    
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = "text-embedding-004" # Updated to newer model for V2
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text using Gemini.
        
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
        
        # New SDK call
        response = self.client.models.embed_content(
            model=self.model,
            contents=text,
            config={"task_type": "RETRIEVAL_DOCUMENT"}
        )
        
        return response.embeddings[0].values
    
    async def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.
        Uses different task type for better retrieval.
        """
        if not query or len(query.strip()) == 0:
            return [0.0] * self.EMBEDDING_DIM
        
        response = self.client.models.embed_content(
            model=self.model,
            contents=query,
            config={"task_type": "RETRIEVAL_QUERY"}
        )
        
        return response.embeddings[0].values
    
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
