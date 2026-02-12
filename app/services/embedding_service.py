from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

import requests
import numpy as np

from app.db.client import DBClient

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, db: DBClient, embedding_model: str = 'text-embedding-3-small') -> None:
        self.db = db
        self.provider = (os.getenv("EMBEDDING_PROVIDER") or "openai").strip().lower()
        self.embedding_model = os.getenv("EMBEDDING_MODEL") or embedding_model
        self.ollama_base_url = (os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
        self.embedding_dim = self._resolve_embedding_dim()
        self._openai_client = None
        self._st_model = None
        self._session = requests.Session()

    @property
    def openai_client(self):
        if self._openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            base_url = (os.getenv("OPENAI_BASE_URL") or "").strip() or None
            # OpenAI-compatible local endpoints may not require an API key.
            if not api_key and not base_url:
                return None
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(
                    api_key=api_key or "local-dev-key",
                    base_url=base_url,
                )
            except Exception:
                return None
        return self._openai_client

    def generate_embedding(self, text: str) -> List[float]:
        if self.provider in {"sentence_transformers", "st"}:
            return self._generate_embedding_sentence_transformers(text)
        if self.provider in {"ollama", "local"}:
            return self._generate_embedding_ollama(text)
        if not self.openai_client:
            return [0.0] * self.embedding_dim
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text[:8000],
            )
            return response.data[0].embedding
        except Exception as exc:
            logger.warning("OpenAI-compatible embedding failed: %s", exc)
            return [0.0] * self.embedding_dim

    def _generate_embedding_ollama(self, text: str) -> List[float]:
        try:
            resp = self._session.post(
                f"{self.ollama_base_url}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text[:8000],
                },
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            vec = payload.get("embedding") or []
            if isinstance(vec, list) and vec:
                return [float(v) for v in vec]
        except Exception as exc:
            logger.warning("Ollama embedding failed: %s", exc)
        return [0.0] * self.embedding_dim

    def _resolve_embedding_dim(self) -> int:
        env_dim = (os.getenv("EMBEDDING_DIM") or "").strip()
        if env_dim.isdigit():
            return max(8, int(env_dim))
        model_name = (self.embedding_model or "").lower()
        if "text-embedding-3" in model_name:
            return 1536
        if "bge" in model_name:
            return 384
        return 384

    @property
    def st_model(self):
        if self._st_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._st_model = SentenceTransformer(self.embedding_model)
            except Exception as exc:
                logger.warning("SentenceTransformer init failed: %s", exc)
                self._st_model = None
        return self._st_model

    def _generate_embedding_sentence_transformers(self, text: str) -> List[float]:
        model = self.st_model
        if model is None:
            return [0.0] * self.embedding_dim
        try:
            vec = model.encode(text[:8000], normalize_embeddings=True)
            if isinstance(vec, np.ndarray):
                return vec.astype(float).tolist()
            return [float(v) for v in list(vec)]
        except Exception as exc:
            logger.warning("SentenceTransformer embedding failed: %s", exc)
            return [0.0] * self.embedding_dim

    def embed_case_sections(
        self,
        case_id: str,
        sections: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        count = 0
        for section in sections:
            content = section.get('content') or ''
            if not content:
                continue
            record = {
                'case_id': case_id,
                'section_type': section.get('section_type') or section.get('chunk_type'),
                'chunk_type': section.get('chunk_type') or section.get('section_type'),
                'chunk_id': section.get('chunk_id'),
                'content': content,
                'embedding': self.generate_embedding(content),
                'company': section.get('company') or (metadata or {}).get('company'),
                'industry': section.get('industry') or (metadata or {}).get('industry'),
                'severity': section.get('severity') or (metadata or {}).get('severity'),
                'period': section.get('period') or (metadata or {}).get('period'),
                'approval_status': section.get('approval_status') or (metadata or {}).get('approval_status'),
                'approved_at': section.get('approved_at') or (metadata or {}).get('approved_at'),
                'approved_by': section.get('approved_by') or (metadata or {}).get('approved_by'),
                'metadata': {**(metadata or {}), **section.get('metadata', {})},
            }
            self.db.save_case_embedding(record)
            count += 1
        return count
