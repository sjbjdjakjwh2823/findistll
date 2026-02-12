from typing import Any, Dict, List, Optional

from app.core.tenant_context import get_effective_tenant_id
from app.services.embedding_service import EmbeddingService

class CaseEmbeddingSearch:
    def __init__(self, supabase_client: Any, embedding_model: str = 'text-embedding-3-small') -> None:
        self.supabase = supabase_client
        self.embedding_model = embedding_model
        self._embedder = EmbeddingService(db=None, embedding_model=embedding_model)  # type: ignore[arg-type]

    def _embed(self, text: str) -> List[float]:
        return self._embedder.generate_embedding(text)

    def search(
        self,
        query_text: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not self.supabase:
            return []
        query_embedding = self._embed(query_text)
        merged_filters = filters.copy() if filters else {}
        merged_filters.setdefault("tenant_id", get_effective_tenant_id())
        payload = {
            'query_embedding': query_embedding,
            'match_count': limit,
            'filters': merged_filters,
        }
        res = self.supabase.rpc('match_case_embeddings', payload).execute()
        return res.data or []

    @staticmethod
    def format_context(results: List[Dict[str, Any]], max_chars: int = 3000) -> str:
        if not results:
            return ''
        parts = ['[Similar Approved Cases]']
        char_count = len(parts[0])
        for i, row in enumerate(results, 1):
            entry = f"\n\n[{i}] (similarity: {row.get('similarity', 0):.2f})\n{row.get('content', '')}"
            if char_count + len(entry) > max_chars:
                break
            parts.append(entry)
            char_count += len(entry)
        return ''.join(parts)
