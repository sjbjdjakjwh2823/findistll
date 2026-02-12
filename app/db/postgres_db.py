from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
    from psycopg2.pool import SimpleConnectionPool
except Exception:
    psycopg2 = None
    RealDictCursor = None
    Json = None
    SimpleConnectionPool = None

from app.core.tenant_context import get_effective_tenant_id
from app.services.types import DecisionResult, DistillResult


class PostgresDB:
    def __init__(self, db_url: str) -> None:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for PostgresDB but is not installed.")
        self.db_url = db_url
        self._pool = None
        try:
            minconn = int(os.getenv("POSTGRES_POOL_MIN", "1"))
            maxconn = int(os.getenv("POSTGRES_POOL_MAX", "5"))
            if SimpleConnectionPool is not None:
                self._pool = SimpleConnectionPool(minconn, maxconn, dsn=self.db_url)
        except Exception:
            self._pool = None

    def _conn(self):
        if self._pool is not None:
            return self._pool.getconn()
        return psycopg2.connect(self.db_url)

    def _release(self, conn) -> None:
        if self._pool is not None:
            self._pool.putconn(conn)
            return
        try:
            conn.close()
        except Exception:
            pass

    def _tenant_id(self) -> str:
        return get_effective_tenant_id()

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            self._release(conn)

    def _fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        finally:
            self._release(conn)

    def _execute(self, sql: str, params: tuple = ()) -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                conn.commit()
        finally:
            self._release(conn)

    def create_case(self, case_data: Dict) -> str:
        case_id = case_data.get("case_id") or f"case_{uuid4().hex[:8]}"
        title = case_data.get("title", "Untitled")
        sql = """
            INSERT INTO cases (case_id, title, status, tenant_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (case_id) DO UPDATE SET title=EXCLUDED.title
        """
        self._execute(sql, (case_id, title, "created", self._tenant_id()))
        return case_id

    def ensure_case_exists(self, case_id: str, *, title: str = "Untitled") -> None:
        if not case_id:
            return
        sql = """
            INSERT INTO cases (case_id, title, status, tenant_id)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (case_id) DO NOTHING
        """
        self._execute(sql, (case_id, title, "created", self._tenant_id()))

    def add_document(self, case_id: str, document: Dict) -> str:
        doc_id = document.get("doc_id") or f"doc_{uuid4().hex[:8]}"
        payload = document
        sql = """
            INSERT INTO documents (doc_id, case_id, filename, mime_type, source, payload, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (doc_id) DO UPDATE SET payload=EXCLUDED.payload
        """
        self._execute(
            sql,
            (
                doc_id,
                case_id,
                document.get("filename"),
                document.get("mime_type"),
                document.get("source"),
                Json(payload),
                self._tenant_id(),
            ),
        )
        return doc_id

    def save_distill(self, case_id: str, distill: DistillResult) -> None:
        self.ensure_case_exists(case_id, title=(distill.metadata or {}).get("title") or "Untitled")
        payload = {
            "facts": distill.facts,
            "cot_markdown": distill.cot_markdown,
            "metadata": distill.metadata,
        }
        sql = """
            UPDATE cases
            SET distill=%s::jsonb, status=%s
            WHERE case_id=%s AND tenant_id=%s
        """
        self._execute(sql, (Json(payload), "distilled", case_id, self._tenant_id()))

    def save_decision(self, case_id: str, decision: DecisionResult) -> None:
        self.ensure_case_exists(case_id)
        payload = {
            "decision": decision.decision,
            "rationale": decision.rationale,
            "actions": decision.actions,
            "approvals": decision.approvals,
        }
        sql = """
            UPDATE cases
            SET decision=%s::jsonb, status=%s
            WHERE case_id=%s AND tenant_id=%s
        """
        self._execute(sql, (Json(payload), "decided", case_id, self._tenant_id()))

    def get_case(self, case_id: str) -> Dict:
        sql = "SELECT * FROM cases WHERE case_id=%s AND tenant_id=%s LIMIT 1"
        return self._fetchone(sql, (case_id, self._tenant_id())) or {}

    def list_cases(self) -> Dict:
        sql = "SELECT * FROM cases WHERE tenant_id=%s ORDER BY created_at DESC"
        return self._fetchall(sql, (self._tenant_id(),))

    def list_documents(self) -> Dict:
        sql = "SELECT * FROM documents WHERE tenant_id=%s ORDER BY created_at DESC"
        return self._fetchall(sql, (self._tenant_id(),))

    def save_rag_context(self, case_id: str, contexts: List[Dict[str, Any]]) -> None:
        if not contexts:
            return
        sql = """
            INSERT INTO spoke_c_rag_context
            (chunk_id, entity, period, source, text_content, keywords, metadata, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (chunk_id) DO NOTHING
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                for ctx in contexts:
                    cur.execute(
                        sql,
                        (
                            ctx.get("chunk_id"),
                            ctx.get("entity"),
                            ctx.get("period"),
                            ctx.get("source"),
                            ctx.get("text_content"),
                            ctx.get("keywords"),
                            Json(ctx.get("metadata") or {}),
                            self._tenant_id(),
                        ),
                    )
            conn.commit()

    def list_rag_context(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM spoke_c_rag_context
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def search_rag_context(
        self,
        entity: Optional[str] = None,
        period: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clauses = ["tenant_id=%s"]
        params: List[Any] = [self._tenant_id()]
        if entity:
            clauses.append("entity=%s")
            params.append(entity)
        if period:
            clauses.append("period=%s")
            params.append(period)
        if keyword:
            clauses.append("text_content ILIKE %s")
            params.append(f"%{keyword}%")
        sql = f"SELECT * FROM spoke_c_rag_context WHERE {' AND '.join(clauses)} LIMIT %s"
        params.append(limit)
        return self._fetchall(sql, tuple(params))

    def save_graph_triples(self, case_id: str, triples: List[Dict[str, Any]]) -> None:
        if not triples:
            return
        sql = """
            INSERT INTO spoke_d_graph (head_node, relation, tail_node, properties, tenant_id)
            VALUES (%s, %s, %s, %s::jsonb, %s)
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                for triple in triples:
                    cur.execute(
                        sql,
                        (
                            triple.get("head_node"),
                            triple.get("relation"),
                            triple.get("tail_node"),
                            Json(triple.get("properties") or {}),
                            self._tenant_id(),
                        ),
                    )
            conn.commit()

    def list_graph_triples(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM spoke_d_graph
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def search_graph_triples(
        self,
        head: Optional[str] = None,
        relation: Optional[str] = None,
        tail: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clauses = ["tenant_id=%s"]
        params: List[Any] = [self._tenant_id()]
        if head:
            clauses.append("head_node=%s")
            params.append(head)
        if relation:
            clauses.append("relation=%s")
            params.append(relation)
        if tail:
            clauses.append("tail_node=%s")
            params.append(tail)
        sql = f"SELECT * FROM spoke_d_graph WHERE {' AND '.join(clauses)} LIMIT %s"
        params.append(limit)
        return self._fetchall(sql, tuple(params))

    def save_training_set(self, case_id: str, record: Dict[str, Any]) -> None:
        sql = """
            INSERT INTO ai_training_sets (metadata, input_features, reasoning_chain, output_narrative, training_prompt, tenant_id)
            VALUES (%s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s)
        """
        self._execute(
            sql,
            (
                Json(record.get("metadata") or {}),
                Json(record.get("input_features") or {}),
                Json(record.get("reasoning_chain") or {}),
                record.get("output_narrative"),
                record.get("training_prompt"),
                self._tenant_id(),
            ),
        )

    def list_training_sets(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM ai_training_sets
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def search_training_sets(
        self,
        case_id: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        clauses = ["tenant_id=%s"]
        params: List[Any] = [self._tenant_id()]
        if case_id:
            clauses.append("metadata @> %s::jsonb")
            params.append(Json({"case_id": case_id}))
        if keyword:
            clauses.append("output_narrative ILIKE %s")
            params.append(f"%{keyword}%")
        sql = f"SELECT * FROM ai_training_sets WHERE {' AND '.join(clauses)} LIMIT %s"
        params.append(limit)
        return self._fetchall(sql, tuple(params))

    def save_case_embedding(self, record: Dict[str, Any]) -> None:
        sql = """
            INSERT INTO case_embeddings (case_id, content, embedding, metadata, tenant_id)
            VALUES (%s, %s, %s, %s::jsonb, %s)
        """
        self._execute(
            sql,
            (
                record.get("case_id"),
                record.get("content"),
                record.get("embedding"),
                Json(record.get("metadata") or {}),
                self._tenant_id(),
            ),
        )

    def search_case_embeddings(
        self,
        query_embedding: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["tenant_id=%s"]
        params: List[Any] = [self._tenant_id()]
        if filters:
            for key, value in filters.items():
                clauses.append(f"{key}=%s")
                params.append(value)
        sql = f"""
            SELECT * FROM case_embeddings
            WHERE {' AND '.join(clauses)}
            ORDER BY embedding <=> %s
            LIMIT %s
        """
        params.append(query_embedding)
        params.append(limit)
        return self._fetchall(sql, tuple(params))

    def list_case_embeddings(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM case_embeddings
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def save_evidence_feedback(self, record: Dict[str, Any]) -> None:
        sql = """
            INSERT INTO evidence_feedback (case_id, evidence_id, feedback, score, metadata, tenant_id)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
        """
        self._execute(
            sql,
            (
                record.get("case_id"),
                record.get("evidence_id"),
                record.get("feedback"),
                record.get("score"),
                Json(record.get("metadata") or {}),
                self._tenant_id(),
            ),
        )

    def get_feedback_summary(self, case_id: str) -> Dict[str, Any]:
        sql = """
            SELECT * FROM feedback_summary
            WHERE case_id=%s AND tenant_id=%s
            LIMIT 1
        """
        return self._fetchone(sql, (case_id, self._tenant_id())) or {}

    def append_audit_log(self, record: Dict[str, Any]) -> None:
        sql = """
            INSERT INTO audit_logs (event_type, payload, actor_id, tenant_id, timestamp)
            VALUES (%s, %s::jsonb, %s, %s, NOW())
        """
        self._execute(
            sql,
            (
                record.get("event_type") or record.get("action") or "event",
                Json(record),
                record.get("actor_id"),
                self._tenant_id(),
            ),
        )

    def list_audit_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM audit_logs
            WHERE tenant_id=%s
            ORDER BY timestamp DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def get_license_by_key(self, license_key: str, user_id: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT * FROM licenses
            WHERE license_key=%s AND (user_id=%s OR user_id IS NULL)
            LIMIT 1
        """
        return self._fetchone(sql, (license_key, user_id))

    def upsert_license_activation(self, license_id: str, device_fingerprint: str) -> None:
        sql = """
            INSERT INTO license_activations (license_id, device_fingerprint, tenant_id)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING
        """
        self._execute(sql, (license_id, device_fingerprint, self._tenant_id()))

    def record_license_check(self, license_id: str, device_fingerprint: str, result: str) -> None:
        sql = """
            INSERT INTO license_checks (license_id, device_fingerprint, result, tenant_id)
            VALUES (%s, %s, %s, %s)
        """
        self._execute(sql, (license_id, device_fingerprint, result, self._tenant_id()))

    def update_case_status(self, case_id: str, status: str, fields: Optional[Dict[str, Any]] = None) -> None:
        fields = fields or {}
        sql = """
            UPDATE cases
            SET status=%s, decision=COALESCE(%s::jsonb, decision), distill=COALESCE(%s::jsonb, distill)
            WHERE case_id=%s AND tenant_id=%s
        """
        self._execute(sql, (status, Json(fields.get("decision")) if fields.get("decision") else None,
                            Json(fields.get("distill")) if fields.get("distill") else None,
                            case_id, self._tenant_id()))

    # -------------------------------------------------------------------------
    # Spoke A/B downstream consumption (WS8)
    # -------------------------------------------------------------------------
    def get_or_create_active_dataset_version(self, name_hint: Optional[str] = None) -> Dict[str, Any]:
        sql = """
            SELECT * FROM dataset_versions
            WHERE status='active' AND tenant_id=%s
            ORDER BY created_at DESC LIMIT 1
        """
        row = self._fetchone(sql, (self._tenant_id(),))
        if row:
            return row
        name = name_hint or f"dataset_{uuid4().hex[:8]}"
        insert_sql = """
            INSERT INTO dataset_versions (name, status, tenant_id)
            VALUES (%s, 'active', %s)
            RETURNING *
        """
        return self._fetchone(insert_sql, (name, self._tenant_id())) or {}

    def seal_dataset_version(self, dataset_version_id: str) -> None:
        sql = """
            UPDATE dataset_versions
            SET status='sealed'
            WHERE id=%s AND tenant_id=%s
        """
        self._execute(sql, (dataset_version_id, self._tenant_id()))

    def list_dataset_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM dataset_versions
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def insert_spoke_a_sample(self, record: Dict[str, Any]) -> str:
        sql = """
            INSERT INTO spoke_a_samples (dataset_version_id, record, tenant_id)
            VALUES (%s, %s::jsonb, %s)
            RETURNING id
        """
        row = self._fetchone(sql, (record.get("dataset_version_id"), Json(record), self._tenant_id()))
        return str(row.get("id")) if row else ""

    def list_spoke_a_samples(self, dataset_version_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM spoke_a_samples
            WHERE dataset_version_id=%s AND tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (dataset_version_id, self._tenant_id(), limit))

    def insert_spoke_b_artifact(self, record: Dict[str, Any]) -> str:
        sql = """
            INSERT INTO spoke_b_artifacts (doc_id, kind, metadata, uri, tenant_id)
            VALUES (%s, %s, %s::jsonb, %s, %s)
            RETURNING id
        """
        row = self._fetchone(
            sql,
            (record.get("doc_id"), record.get("kind"), Json(record.get("metadata") or {}), record.get("uri"), self._tenant_id()),
        )
        return str(row.get("id")) if row else ""

    def get_spoke_b_artifact(self, doc_id: str, kind: str) -> Optional[Dict[str, Any]]:
        sql = """
            SELECT * FROM spoke_b_artifacts
            WHERE doc_id=%s AND kind=%s AND tenant_id=%s
            LIMIT 1
        """
        return self._fetchone(sql, (doc_id, kind, self._tenant_id()))

    # -------------------------------------------------------------------------
    # Console / Model Registry / Run Logs
    # -------------------------------------------------------------------------
    def list_model_registry(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM model_registry
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def upsert_model_registry(self, record: Dict[str, Any]) -> str:
        model_id = record.get("id") or str(uuid4())
        sql = """
            INSERT INTO model_registry (id, name, provider, base_url, model, purpose, is_default, metadata, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name,
                provider=EXCLUDED.provider,
                base_url=EXCLUDED.base_url,
                model=EXCLUDED.model,
                purpose=EXCLUDED.purpose,
                is_default=EXCLUDED.is_default,
                metadata=EXCLUDED.metadata
        """
        self._execute(
            sql,
            (
                model_id,
                record.get("name"),
                record.get("provider"),
                record.get("base_url"),
                record.get("model"),
                record.get("purpose"),
                record.get("is_default", False),
                Json(record.get("metadata") or {}),
                self._tenant_id(),
            ),
        )
        return model_id

    def insert_llm_run(self, record: Dict[str, Any]) -> str:
        run_id = record.get("id") or str(uuid4())
        sql = """
            INSERT INTO llm_runs
            (id, user_id, model_id, model_name, prompt, response, tokens, latency_ms, status, metadata, tenant_id)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s)
        """
        self._execute(
            sql,
            (
                run_id,
                record.get("user_id"),
                record.get("model_id"),
                record.get("model_name"),
                record.get("prompt"),
                Json(record.get("response") or {}),
                record.get("tokens"),
                record.get("latency_ms"),
                record.get("status"),
                Json(record.get("metadata") or {}),
                self._tenant_id(),
            ),
        )
        return run_id

    def list_llm_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM llm_runs
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))

    def insert_rag_run(self, record: Dict[str, Any]) -> str:
        run_id = record.get("id") or str(uuid4())
        sql = """
            INSERT INTO rag_runs
            (id, user_id, query, response, metrics, status, metadata, tenant_id)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s)
        """
        self._execute(
            sql,
            (
                run_id,
                record.get("user_id"),
                record.get("query"),
                Json(record.get("response") or {}),
                Json(record.get("metrics") or {}),
                record.get("status"),
                Json(record.get("metadata") or {}),
                self._tenant_id(),
            ),
        )
        return run_id

    def insert_rag_run_chunks(self, run_id: str, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            return
        sql = """
            INSERT INTO rag_run_chunks
            (run_id, chunk_id, similarity, metadata, tenant_id)
            VALUES (%s, %s, %s, %s::jsonb, %s)
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                for chunk in chunks:
                    cur.execute(
                        sql,
                        (
                            run_id,
                            chunk.get("chunk_id"),
                            chunk.get("similarity"),
                            Json(chunk.get("metadata") or {}),
                            self._tenant_id(),
                        ),
                    )
            conn.commit()

    def list_rag_runs(self, limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
            SELECT * FROM rag_runs
            WHERE tenant_id=%s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self._fetchall(sql, (self._tenant_id(), limit))
