"""
Spoke C: RAG Engine for Evidence-Based Retrieval
Phase 2: AI Brain - Retrieval Augmented Generation
"""

import os
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass, field
import hashlib
import json
import time
import re
from collections import OrderedDict

from app.services.embedding_service import EmbeddingService
from app.services.feature_flags import get_flag

logger = logging.getLogger(__name__)


@dataclass
class RAGResult:
    """Result from RAG retrieval."""
    chunk_id: str
    content: str
    similarity: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGContext:
    """Aggregated RAG context for decision-making."""
    results: List[RAGResult] = field(default_factory=list)
    query: str = ""
    total_tokens: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)


class RAGEngine:
    """
    Retrieval-Augmented Generation Engine for financial documents.
    
    Implements hybrid search:
    - Vector similarity (semantic)
    - Keyword matching (lexical)
    """
    
    def __init__(
        self,
        supabase_client: Any = None,
        db_client: Any = None,
        openai_api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-3-small",
    ):
        """
        Initialize RAG Engine.
        
        Args:
            supabase_client: Supabase client instance
            openai_api_key: OpenAI API key for embeddings
            embedding_model: Model to use for embeddings
        """
        self.supabase = supabase_client
        self.db = db_client
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.embedding_model = embedding_model
        self._openai_client = None
        self._embedding_service = EmbeddingService(db=None, embedding_model=embedding_model)  # type: ignore[arg-type]
        self._embedding_cache: OrderedDict[str, List[float]] = OrderedDict()
        self._redis_client = None
        self._redis_ready = False
        try:
            self._embedding_cache_size = max(16, int(os.getenv("RAG_EMBED_CACHE_SIZE", "256")))
        except ValueError:
            self._embedding_cache_size = 256
        self._token_re = re.compile(r"[a-z0-9_\\-]{3,}")
        
    @property
    def openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None and self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key)
            except ImportError:
                logger.warning("OpenAI not installed. Install with: pip install openai")
        return self._openai_client
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text using OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        key = (text or "").strip()
        if not key:
            return [0.0] * 384
        if key in self._embedding_cache:
            vec = self._embedding_cache.pop(key)
            self._embedding_cache[key] = vec
            return vec
        try:
            vec = self._embedding_service.generate_embedding(key)
            self._embedding_cache[key] = vec
            if len(self._embedding_cache) > self._embedding_cache_size:
                self._embedding_cache.popitem(last=False)
            return vec
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return [0.0] * 384
    
    def chunk_document(
        self,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Semantic chunking for financial documents.
        
        Args:
            text: Document text to chunk
            chunk_size: Target size per chunk
            overlap: Overlap between chunks
            metadata: Metadata to attach to chunks
            
        Returns:
            List of chunk dictionaries
        """
        if not text:
            return []
        
        try:
            chunk_size = int(os.getenv("RAG_CHUNK_SIZE", str(chunk_size)))
        except ValueError:
            chunk_size = 1000
        try:
            overlap = int(os.getenv("RAG_CHUNK_OVERLAP", str(overlap)))
        except ValueError:
            overlap = 200
        chunk_size = max(300, min(chunk_size, 4000))
        overlap = max(0, min(overlap, max(0, chunk_size - 50)))

        chunks = []
        start = 0
        chunk_idx = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for sep in ['. ', '.\n', '? ', '! ']:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > chunk_size // 2:
                        end = start + last_sep + len(sep)
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_id = hashlib.md5(f"{chunk_text[:100]}_{chunk_idx}".encode()).hexdigest()[:16]
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": chunk_text,
                    "metadata": {
                        **(metadata or {}),
                        "chunk_index": chunk_idx,
                        "char_start": start,
                        "char_end": end,
                    }
                })
                chunk_idx += 1
            
            start = end - overlap if end < len(text) else end
        
        return chunks
    
    def ingest_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Ingest a document into the vector store.
        
        Args:
            text: Document text
            metadata: Document metadata
            
        Returns:
            Number of chunks ingested
        """
        if not self.supabase:
            logger.error("Supabase client not configured")
            return 0
        
        chunks = self.chunk_document(text, metadata=metadata)
        ingested = 0
        if not chunks:
            return 0

        try:
            batch_size = max(10, int(os.getenv("RAG_INGEST_BATCH", "50")))
        except ValueError:
            batch_size = 50

        payloads: List[Dict[str, Any]] = []
        tenant_id = None
        if metadata:
            tenant_id = metadata.get("tenant_id") or metadata.get("tenant")
        if not tenant_id:
            tenant_id = os.getenv("DEFAULT_TENANT_ID", "public")
        for chunk in chunks:
            try:
                embedding = self.get_embedding(chunk["content"])
                payloads.append({
                    "chunk_id": chunk["metadata"].get("chunk_id") or chunk["chunk_id"],
                    "content": chunk["content"],
                    "embedding": embedding,
                    "metadata": chunk["metadata"],
                    "tenant_id": tenant_id,
                })
                if len(payloads) >= batch_size:
                    self.supabase.table("case_embeddings").upsert(payloads).execute()
                    ingested += len(payloads)
                    payloads = []
            except Exception as e:
                logger.error(f"Failed to prepare chunk: {e}")

        if payloads:
            try:
                self.supabase.table("case_embeddings").upsert(payloads).execute()
                ingested += len(payloads)
            except Exception as e:
                logger.error(f"Failed to ingest batch: {e}")
        
        logger.info(f"Ingested {ingested}/{len(chunks)} chunks")
        return ingested
    
    def retrieve(
        self,
        query: str,
        k: int = 5,
        threshold: float = 0.7,
        keyword_filter: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> RAGContext:
        """
        Hybrid retrieval: vector similarity + keyword matching.
        
        Args:
            query: Search query
            k: Number of results to return
            threshold: Minimum similarity threshold
            keyword_filter: Optional keyword to filter by
            metadata_filter: Optional metadata filters
            
        Returns:
            RAGContext with retrieved results
        """
        start = time.time()
        cache_enabled = get_flag("rag_cache_enabled")
        cache_ttl = int(os.getenv("RAG_CACHE_TTL_S", "900"))
        cache_prefix = os.getenv("RAG_CACHE_PREFIX", "rag")
        cache_key = None
        if cache_enabled:
            tenant_hint = None
            if metadata_filter:
                tenant_hint = metadata_filter.get("tenant_id") or metadata_filter.get("tenant")
            if not tenant_hint:
                tenant_hint = os.getenv("DEFAULT_TENANT_ID", "public")
            cache_payload = {
                "query": query,
                "k": k,
                "threshold": threshold,
                "keyword_filter": keyword_filter,
                "metadata_filter": metadata_filter or {},
                "tenant_id": tenant_hint,
            }
            cache_key = hashlib.sha256(
                json.dumps(cache_payload, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            try:
                if self._redis_client is None and not self._redis_ready:
                    import redis  # type: ignore
                    redis_url = os.getenv("REDIS_URL", "")
                    if redis_url:
                        self._redis_client = redis.Redis.from_url(redis_url)
                    self._redis_ready = True
                client = self._redis_client
                if client is not None:
                    cache_read_start = time.time()
                    cached = client.get(f"{cache_prefix}:{cache_key}")
                    cache_read_ms = int((time.time() - cache_read_start) * 1000)
                    if cached:
                        payload = json.loads(cached.decode("utf-8"))
                        results = [
                            RAGResult(
                                chunk_id=r.get("chunk_id", ""),
                                content=r.get("content", ""),
                                similarity=float(r.get("similarity", 0)),
                                metadata=r.get("metadata", {}) or {},
                            )
                            for r in payload.get("results", [])
                        ]
                        metrics = payload.get("metrics", {})
                        metrics["cache_hit"] = True
                        metrics["cache_read_ms"] = cache_read_ms
                        latency_ms = int((time.time() - start) * 1000)
                        metrics["latency_ms"] = latency_ms
                        try:
                            from app.services.metrics_logger import MetricsLogger
                            MetricsLogger().log("rag.cache_hit", 1, {"k": k})
                            MetricsLogger().log("rag.cache_read_ms", cache_read_ms, {"k": k})
                            MetricsLogger().log("rag.latency_ms", latency_ms, {"k": k})
                        except Exception as exc:
                            logger.warning("swallowed exception", exc_info=exc)
                        return RAGContext(
                            results=results,
                            query=query,
                            total_tokens=int(metrics.get("total_tokens", 0)),
                            metrics=metrics,
                        )
            except Exception as exc:
                logger.warning("RAG cache read failed", exc_info=exc)
        results = []
        
        # Vector search
        vector_results, vector_perf = self._vector_search(query, k, threshold, metadata_filter)
        results.extend(vector_results)
        
        # Keyword search (if keyword provided or as fallback)
        if keyword_filter or not vector_results:
            keyword_results = self._keyword_search(
                keyword_filter or query,
                k,
                metadata_filter,
            )
            # Merge results, avoiding duplicates
            seen_ids = {r.chunk_id for r in results}
            for kr in keyword_results:
                if kr.chunk_id not in seen_ids:
                    results.append(kr)
                    seen_ids.add(kr.chunk_id)
        else:
            keyword_results = []
        
        def _metrics_for(items: List[RAGResult]) -> Dict[str, Any]:
            hit_rate = len(items) / max(1, k)
            avg_similarity = sum(r.similarity for r in items) / max(1, len(items))
            return {
                "hit_rate": round(hit_rate, 4),
                "avg_similarity": round(avg_similarity, 4),
                "count": len(items),
            }

        vector_metrics = _metrics_for(vector_results)
        keyword_metrics = _metrics_for(keyword_results)
        hybrid_metrics = _metrics_for(results)

        # Hybrid selection (vector vs keyword vs hybrid)
        mode = os.getenv("RAG_HYBRID_MODE", "hybrid")
        selected_mode = mode
        if mode == "vector":
            results = vector_results
        elif mode == "keyword":
            results = keyword_results
        elif mode == "auto":
            scored = [
                ("vector", vector_results, vector_metrics),
                ("keyword", keyword_results, keyword_metrics),
                ("hybrid", results, hybrid_metrics),
            ]
            scored.sort(key=lambda x: (x[2]["avg_similarity"], x[2]["hit_rate"]), reverse=True)
            selected_mode, results, _ = scored[0]
        else:
            results = results

        # Apply minimum similarity filter (quality gate)
        try:
            min_similarity = float(os.getenv("RAG_MIN_SIM", str(max(0.0, min(1.0, threshold)))))
        except ValueError:
            min_similarity = max(0.0, min(1.0, threshold))
        filtered = [r for r in results if r.similarity >= min_similarity]
        if filtered:
            results = filtered

        # Sort by similarity and limit
        results.sort(key=lambda x: x.similarity, reverse=True)
        results = results[:k]

        if get_flag("rag_rerank_enabled"):
            try:
                from app.services.rag_optimizer import RAGOptimizer
                optimizer = RAGOptimizer()
                results = optimizer.rerank(query, results, top_k=k)
            except Exception as exc:
                logger.warning(f"RAG rerank failed: {exc}")
        
        # Estimate tokens once (avoid double compute below)
        total_tokens = sum(len(r.content.split()) * 1.3 for r in results)
        
        context_build_start = time.time()
        latency_ms = int((time.time() - start) * 1000)
        final_metrics = _metrics_for(results)
        final_metrics.update(
            {
                "latency_ms": latency_ms,
                "mode": selected_mode,
                "vector_metrics": vector_metrics,
                "keyword_metrics": keyword_metrics,
                "hybrid_metrics": hybrid_metrics,
                "cache_hit": False,
                "embedding_ms": int(vector_perf.get("embedding_ms", 0)),
                "vector_query_ms": int(vector_perf.get("vector_query_ms", 0)),
            }
        )
        final_metrics["context_build_ms"] = int((time.time() - context_build_start) * 1000)
        try:
            from app.services.metrics_logger import MetricsLogger
            MetricsLogger().log("rag.latency_ms", latency_ms, {"k": k})
            MetricsLogger().log("rag.results_count", len(results), {"k": k})
            MetricsLogger().log("rag.vector_count", len(vector_results), {"k": k})
            MetricsLogger().log("rag.keyword_count", len(keyword_results), {"k": k})
            MetricsLogger().log("rag.hit_rate", final_metrics["hit_rate"], {"k": k, "mode": selected_mode})
            MetricsLogger().log("rag.avg_similarity", final_metrics["avg_similarity"], {"k": k, "mode": selected_mode})
            MetricsLogger().log("rag.embedding_ms", final_metrics["embedding_ms"], {"k": k})
            MetricsLogger().log("rag.vector_query_ms", final_metrics["vector_query_ms"], {"k": k})
            MetricsLogger().log("rag.context_build_ms", final_metrics["context_build_ms"], {"k": k})
            MetricsLogger().log("rag.cache_hit", 0, {"k": k})
        except Exception as exc:
            logger.warning("swallowed exception", exc_info=exc)

        if cache_enabled and cache_key:
            try:
                if self._redis_client is None and not self._redis_ready:
                    import redis  # type: ignore
                    redis_url = os.getenv("REDIS_URL", "")
                    if redis_url:
                        self._redis_client = redis.Redis.from_url(redis_url)
                    self._redis_ready = True
                client = self._redis_client
                if client is not None:
                    payload = {
                        "results": [
                            {
                                "chunk_id": r.chunk_id,
                                "content": r.content,
                                "similarity": r.similarity,
                                "metadata": r.metadata,
                            }
                            for r in results
                        ],
                        "metrics": {**final_metrics, "total_tokens": int(total_tokens)},
                    }
                    cache_write_start = time.time()
                    client.setex(f"{cache_prefix}:{cache_key}", cache_ttl, json.dumps(payload))
                    cache_write_ms = int((time.time() - cache_write_start) * 1000)
                    try:
                        from app.services.metrics_logger import MetricsLogger
                        MetricsLogger().log("rag.cache_write_ms", cache_write_ms, {"k": k})
                    except Exception as exc:
                        logger.warning("swallowed exception", exc_info=exc)
            except Exception as exc:
                logger.warning("RAG cache write failed", exc_info=exc)

        return RAGContext(
            results=results,
            query=query,
            total_tokens=int(total_tokens),
            metrics=final_metrics,
        )
    
    def _vector_search(
        self,
        query: str,
        k: int,
        threshold: float,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[RAGResult], Dict[str, int]]:
        """Perform vector similarity search."""
        if not self.supabase:
            return [], {"embedding_ms": 0, "vector_query_ms": 0}

        try:
            embed_start = time.time()
            query_embedding = self.get_embedding(query)
            embedding_ms = int((time.time() - embed_start) * 1000)
            if not query_embedding or all(v == 0.0 for v in query_embedding):
                return [], {"embedding_ms": embedding_ms, "vector_query_ms": 0}

            # Use RPC function for hybrid case search
            vector_query_start = time.time()
            filters = {}
            tenant_id = os.getenv("DEFAULT_TENANT_ID", "public")
            if metadata_filter:
                tenant_id = metadata_filter.get("tenant_id") or metadata_filter.get("tenant") or tenant_id
            filters["tenant_id"] = tenant_id
            if metadata_filter:
                if metadata_filter.get("period"):
                    filters["period"] = str(metadata_filter.get("period"))
                if metadata_filter.get("entity"):
                    filters["entity"] = str(metadata_filter.get("entity"))
                if metadata_filter.get("owner_user_id"):
                    # Used by upgraded hybrid_case_search; safe even if older RPC ignores it.
                    filters["owner_user_id"] = str(metadata_filter.get("owner_user_id"))
                if metadata_filter.get("doc_ids") and isinstance(metadata_filter.get("doc_ids"), list):
                    filters["doc_ids"] = metadata_filter.get("doc_ids")
            response = self.supabase.rpc(
                "hybrid_case_search",
                {
                    "query_embedding": query_embedding,
                    "query_text": query,
                    "filters": filters,
                    "match_count": k,
                }
            ).execute()
            vector_query_ms = int((time.time() - vector_query_start) * 1000)

            results = []
            for row in (response.data or []):
                results.append(RAGResult(
                    chunk_id=str(row.get("chunk_id", "")),
                    content=row.get("content", ""),
                    similarity=float(row.get("similarity", 0)),
                    metadata=row.get("metadata", {}),
                ))
            return results, {"embedding_ms": embedding_ms, "vector_query_ms": vector_query_ms}

        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return [], {"embedding_ms": 0, "vector_query_ms": 0}
    
    def _keyword_search(
        self,
        keyword: str,
        k: int,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[RAGResult]:
        """Perform keyword text search."""
        try:
            min_keyword_sim = float(os.getenv("RAG_MIN_KEYWORD_SIM", "0.35"))
        except ValueError:
            min_keyword_sim = 0.35
        if not self.supabase:
            # In-memory/local fallback for MVP environments without Supabase.
            raw_docs = getattr(self.db, "raw_documents", {}) if self.db is not None else {}
            if not isinstance(raw_docs, dict):
                return []
            query_tokens = set(self._token_re.findall((keyword or "").lower()))
            matches: List[RAGResult] = []
            for doc_id, row in raw_docs.items():
                if not isinstance(row, dict):
                    continue
                raw_content = row.get("raw_content")
                if isinstance(raw_content, dict):
                    text = raw_content.get("text")
                    if not text:
                        text = json.dumps(raw_content, ensure_ascii=False)
                else:
                    text = str(raw_content or "")
                hay = (text or "").lower()
                if not hay:
                    continue
                if query_tokens:
                    doc_tokens = set(self._token_re.findall(hay))
                    overlap = len(query_tokens & doc_tokens)
                    if overlap == 0:
                        continue
                    similarity = min(0.85, 0.2 + (overlap / max(1, len(query_tokens))) * 0.6)
                else:
                    similarity = 0.35
                if similarity >= min_keyword_sim:
                    matches.append(
                        RAGResult(
                            chunk_id=str(doc_id),
                            content=text[:4000],
                            similarity=similarity,
                            metadata=row.get("metadata", {}) or {},
                        )
                    )
                if len(matches) >= k:
                    break
            return matches
        
        try:
            results: List[RAGResult] = []
            tenant_id = os.getenv("DEFAULT_TENANT_ID", "public")
            if metadata_filter:
                tenant_id = metadata_filter.get("tenant_id") or metadata_filter.get("tenant") or tenant_id

            # 1) case_embeddings (vector store)
            try:
                query = self.supabase.table("case_embeddings").select("chunk_id,content,metadata")
                query = query.ilike("content", f"%{keyword}%")
                query = query.eq("tenant_id", tenant_id)
                if metadata_filter:
                    for key, value in metadata_filter.items():
                        # doc_ids is a request-scoped allow-list, not an embedding metadata field.
                        # Filtering is enforced after retrieval by the API layer.
                        if key in {"doc_ids"}:
                            continue
                        query = query.contains("metadata", {key: value})
                response = query.limit(k).execute()
                for row in (response.data or []):
                    similarity = 0.5
                    if similarity >= min_keyword_sim:
                        results.append(
                            RAGResult(
                                chunk_id=str(row.get("chunk_id", "")),
                                content=row.get("content", ""),
                                similarity=similarity,
                                metadata=row.get("metadata", {}),
                            )
                        )
            except Exception:
                # Missing table or restricted env; skip with trace.
                logger.info("embeddings_finance keyword search unavailable", exc_info=True)

            # 2) canonical evidence store: spoke_c_rag_context
            # This keeps RAG usable even when embeddings are not populated.
            if not results:
                try:
                    response = (
                        self.supabase.table("spoke_c_rag_context")
                        .select("chunk_id,text_content,metadata")
                        .ilike("text_content", f"%{keyword}%")
                        .eq("tenant_id", tenant_id)
                        .order("created_at", desc=True)
                        .limit(k)
                        .execute()
                    )
                    for row in (response.data or []):
                        similarity = 0.45
                        if similarity >= min_keyword_sim:
                            results.append(
                                RAGResult(
                                    chunk_id=str(row.get("chunk_id", "")),
                                    content=row.get("text_content", ""),
                                    similarity=similarity,
                                    metadata=row.get("metadata", {}) or {},
                                )
                            )
                except Exception as exc:
                    logger.warning("swallowed exception", exc_info=exc)

            # 3) raw document fallback for early MVP environments where
            # spoke_c_rag_context is not yet populated.
            if not results:
                try:
                    response = (
                        self.supabase.table("raw_documents")
                        .select("id,raw_content,metadata")
                        .eq("tenant_id", tenant_id)
                        .order("ingested_at", desc=True)
                        .limit(max(50, k * 10))
                        .execute()
                    )
                    query_tokens = set(self._token_re.findall((keyword or "").lower()))
                    for row in (response.data or []):
                        raw_content = row.get("raw_content")
                        if isinstance(raw_content, dict):
                            text = raw_content.get("text") or json.dumps(raw_content, ensure_ascii=False)
                        else:
                            text = str(raw_content or "")
                        hay = text.lower()
                        if query_tokens:
                            doc_tokens = set(self._token_re.findall(hay))
                            overlap = len(query_tokens & doc_tokens)
                            if overlap == 0:
                                continue
                            similarity = min(0.9, 0.25 + (overlap / max(1, len(query_tokens))) * 0.65)
                        else:
                            similarity = 0.35
                        if not hay:
                            continue
                        if similarity >= min_keyword_sim:
                            results.append(
                                RAGResult(
                                    chunk_id=str(row.get("id", "")),
                                    content=text[:4000],
                                    similarity=similarity,
                                    metadata=row.get("metadata", {}) or {},
                                )
                            )
                        if len(results) >= k:
                            break
                except Exception as exc:
                    logger.warning("raw_documents keyword fallback failed", exc_info=exc)

            return results
            
        except Exception as e:
            logger.warning(f"Keyword search failed: {e}")
            return []
    
    def format_context(self, context: RAGContext, max_chars: int = 4000) -> str:
        """
        Format RAG context for LLM prompt injection.
        
        Args:
            context: RAGContext from retrieval
            max_chars: Maximum characters to include
            
        Returns:
            Formatted string for prompt injection
        """
        if not context.results:
            return "[No relevant context found]"
        
        results = context.results
        if get_flag("rag_compress_enabled"):
            try:
                from app.services.rag_optimizer import RAGOptimizer
                optimizer = RAGOptimizer()
                results = optimizer.compress(results, max_chars=max_chars)
            except Exception as exc:
                logger.warning(f"RAG compression failed: {exc}")

        parts = ["[Retrieved Evidence]"]
        char_count = len(parts[0])
        
        for i, result in enumerate(results, 1):
            entry = f"\n\n[{i}] (similarity: {result.similarity:.2f})\n{result.content}"
            
            if char_count + len(entry) > max_chars:
                remaining = max_chars - char_count - 20
                if remaining > 100:
                    entry = entry[:remaining] + "..."
                else:
                    break
            
            parts.append(entry)
            char_count += len(entry)
        
        return "".join(parts)


# =============================================================================
# Compatibility Layer (tests + legacy API)
# =============================================================================
#
# Some parts of the repo (notably tests) expect a "RAGService/TextChunker" API and
# evaluation utilities. The production RAGEngine above is Supabase-backed and
# returns RAGContext/RAGResult. The following lightweight types keep the old
# interface usable without changing the core engine.


@dataclass
class Document:
    id: str
    content: str
    source: str = "unknown"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    document: Document
    score: float
    rank: int


class TextChunker:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        self.chunk_size = int(chunk_size)
        self.chunk_overlap = int(chunk_overlap)

    def chunk(self, text: str, source: str = "unknown") -> List[Document]:
        if not text:
            return []
        size = max(1, self.chunk_size)
        overlap = max(0, min(self.chunk_overlap, size - 1))
        step = max(1, size - overlap)

        docs: List[Document] = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(len(text), start + size)
            content = text[start:end]
            docs.append(
                Document(
                    id=f"chunk_{idx+1}",
                    content=content,
                    source=source,
                    metadata={
                        "chunk_index": idx,
                        "char_start": start,
                        "char_end": end,
                        "char_count": len(content),
                    },
                )
            )
            idx += 1
            if end >= len(text):
                break
            start = start + step
        return docs


class RAGService:
    """
    Minimal in-memory RAG façade expected by older code/tests.
    This does not persist; it's only meant for chunking + lightweight retrieval hooks.
    """

    def __init__(self, chunker: Optional[TextChunker] = None) -> None:
        self.chunker = chunker or TextChunker()


class RetrievalEvaluator:
    def __init__(self, rag_engine: Any) -> None:
        self.rag_engine = rag_engine

    @staticmethod
    def _calculate_precision_at_k(retrieved: Sequence[str], ground_truth: Sequence[str], k: int) -> float:
        if k <= 0:
            return 0.0
        topk = list(retrieved)[:k]
        if not topk:
            return 0.0
        gt = set(ground_truth)
        hits = sum(1 for x in topk if x in gt)
        return hits / len(topk)

    @staticmethod
    def _calculate_recall_at_k(retrieved: Sequence[str], ground_truth: Sequence[str], k: int) -> float:
        gt = set(ground_truth)
        if not gt:
            # By convention: if there are no relevant docs, recall is perfect.
            return 1.0
        topk = list(retrieved)[: max(0, k)]
        hits = sum(1 for x in topk if x in gt)
        return hits / len(gt)

    @staticmethod
    def _calculate_mrr(retrieved: Sequence[str], ground_truth: Sequence[str]) -> float:
        gt = set(ground_truth)
        for i, doc_id in enumerate(retrieved, start=1):
            if doc_id in gt:
                return 1.0 / i
        return 0.0

    async def evaluate_query(self, query: str, ground_truth: List[str], top_k: int = 10) -> Dict[str, Any]:
        results: List[RetrievalResult] = await self.rag_engine.retrieve(query, top_k=top_k)
        retrieved_ids = [r.document.id for r in results]
        precision = self._calculate_precision_at_k(retrieved_ids, ground_truth, top_k)
        recall = self._calculate_recall_at_k(retrieved_ids, ground_truth, top_k)
        mrr = self._calculate_mrr(retrieved_ids, ground_truth)
        return {
            "query": query,
            "retrieved_doc_ids": retrieved_ids,
            "precision_at_k": precision,
            "recall_at_k": recall,
            "mrr": mrr,
            "retrieved_count": len(retrieved_ids),
        }

    async def evaluate_retrieval_suite(
        self, test_suite: List[Tuple[str, List[str]]], top_k: int = 10
    ) -> Dict[str, Any]:
        individual = []
        for query, gt in test_suite:
            individual.append(await self.evaluate_query(query, gt, top_k=top_k))

        if not individual:
            return {"overall_metrics": {}, "individual_results": []}

        avg_p = sum(r["precision_at_k"] for r in individual) / len(individual)
        avg_r = sum(r["recall_at_k"] for r in individual) / len(individual)
        avg_m = sum(r["mrr"] for r in individual) / len(individual)
        return {
            "overall_metrics": {
                "average_precision_at_k": avg_p,
                "average_recall_at_k": avg_r,
                "average_mrr": avg_m,
            },
            "individual_results": individual,
        }
