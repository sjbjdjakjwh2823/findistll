import math
import re
from typing import Dict, List

from app.services.spoke_c_rag import RAGResult


class RAGOptimizer:
    """
    Lightweight reranker + compressor for RAG results.

    Uses lexical overlap for rerank (fast, offline).
    """

    def rerank(self, query: str, results: List[RAGResult], top_k: int = 5) -> List[RAGResult]:
        query_terms = list(self._terms(query))
        if not query_terms:
            return results[:top_k]

        doc_terms = [self._terms(result.content) for result in results]
        idf = self._idf(query_terms, doc_terms)

        def score(result: RAGResult) -> float:
            terms = self._terms(result.content)
            bm25 = self._bm25_score(query_terms, terms, idf, avg_len=self._avg_len(doc_terms))
            return (bm25 * 0.7) + (result.similarity * 0.3)

        ranked = sorted(results, key=score, reverse=True)
        return ranked[:top_k]

    def compress(self, results: List[RAGResult], max_chars: int = 3000) -> List[RAGResult]:
        compressed = []
        used = 0
        for result in results:
            content = result.content.strip()
            if not content:
                continue
            remaining = max_chars - used
            if remaining <= 0:
                break
            if len(content) > remaining:
                content = content[: max(0, remaining - 3)] + "..."
            compressed.append(
                RAGResult(
                    chunk_id=result.chunk_id,
                    content=content,
                    similarity=result.similarity,
                    metadata=result.metadata,
                )
            )
            used += len(content)
        return compressed

    def _terms(self, text: str) -> set:
        tokens = re.split(r"[\\s,;:()]+", text.lower())
        return {t for t in tokens if len(t) > 2}

    def _idf(self, query_terms: List[str], doc_terms: List[set]) -> Dict[str, float]:
        doc_count = len(doc_terms) or 1
        idf = {}
        for term in query_terms:
            containing = sum(1 for terms in doc_terms if term in terms)
            idf[term] = math.log((doc_count - containing + 0.5) / (containing + 0.5) + 1)
        return idf

    def _avg_len(self, doc_terms: List[set]) -> float:
        if not doc_terms:
            return 1.0
        return sum(len(t) for t in doc_terms) / max(1, len(doc_terms))

    def _bm25_score(
        self,
        query_terms: List[str],
        doc_terms: set,
        idf: Dict[str, float],
        avg_len: float,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        score = 0.0
        doc_len = len(doc_terms) or 1
        for term in query_terms:
            if term not in doc_terms:
                continue
            tf = 1.0
            denom = tf + k1 * (1 - b + b * (doc_len / avg_len))
            score += idf.get(term, 0.0) * ((tf * (k1 + 1)) / max(denom, 1e-6))
        return score
