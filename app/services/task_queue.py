import json
import os
from typing import Any, Dict, Optional
import time

try:
    import redis
except Exception:  # pragma: no cover - optional dependency
    redis = None


class TaskQueue:
    def __init__(self, queue_name: Optional[str] = None) -> None:
        self.queue_name = queue_name or os.getenv("DATAFORGE_QUEUE", "dataforge:extract")
        self.embed_queue = os.getenv("DATAFORGE_EMBED_QUEUE", "dataforge:embed")
        self.rag_queue = os.getenv("DATAFORGE_RAG_QUEUE", "dataforge:rag")
        self.dead_letter_queue = os.getenv("DATAFORGE_DLQ", "dataforge:dead_letter")
        self.redis_url = os.getenv("REDIS_URL")
        self.client = None
        if self.redis_url and redis:
            self.client = redis.from_url(self.redis_url)
        # Queue mode:
        # - "streams": Redis Streams + consumer group + ack (stronger against dup/loss)
        # - "list": legacy RPUSH/BLPOP
        self.mode = (os.getenv("DATAFORGE_QUEUE_MODE") or "streams").strip().lower()
        if self.mode not in {"streams", "list"}:
            self.mode = "streams"
        self.group = os.getenv("DATAFORGE_CONSUMER_GROUP", "dataforge-workers")
        self.consumer = os.getenv("DATAFORGE_CONSUMER_ID") or os.getenv("HOSTNAME", "worker")
        self.block_ms = int(os.getenv("DATAFORGE_STREAM_BLOCK_MS", "5000") or "5000")
        self.claim_idle_ms = int(os.getenv("DATAFORGE_STREAM_CLAIM_IDLE_MS", "300000") or "300000")
        self.stream_maxlen = int(os.getenv("DATAFORGE_STREAM_MAXLEN", "20000") or "20000")

    def enabled(self) -> bool:
        return self.client is not None

    def _ensure_group(self, stream: str) -> None:
        if not self.client or self.mode != "streams":
            return
        try:
            # MKSTREAM ensures the stream exists.
            self.client.xgroup_create(name=stream, groupname=self.group, id="0", mkstream=True)
        except Exception as exc:
            if "WRONGTYPE" in str(exc):
                # Back-compat: existing deployments may have a legacy LIST at this key.
                # Fall back to list mode to avoid breaking ingestion/worker.
                self.mode = "list"
                return
            # BUSYGROUP is fine.
            if "BUSYGROUP" not in str(exc):
                raise

    def _xadd(self, stream: str, payload: Dict[str, Any]) -> None:
        if not self.client:
            raise RuntimeError("Redis not configured for TaskQueue")
        self._ensure_group(stream)
        if self.mode != "streams":
            # Fell back due to WRONGTYPE
            self.client.rpush(stream, json.dumps(payload))
            return
        msg = {"payload": json.dumps(payload)}
        try:
            self.client.xadd(stream, msg, maxlen=self.stream_maxlen, approximate=True)
        except TypeError:
            # Older redis-py doesn't support approximate kw arg in some versions.
            self.client.xadd(stream, msg)
        except Exception as exc:
            if "WRONGTYPE" in str(exc):
                self.mode = "list"
                self.client.rpush(stream, json.dumps(payload))
                return
            raise

    def enqueue_extract(self, doc_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.client:
            raise RuntimeError("Redis not configured for TaskQueue")
        payload = {"doc_id": doc_id}
        if isinstance(extra, dict) and extra:
            payload.update(extra)
        if self.mode == "streams":
            self._xadd(self.queue_name, payload)
            return
        self.client.rpush(self.queue_name, json.dumps(payload))

    def enqueue_embed(self, doc_id: str, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.client:
            raise RuntimeError("Redis not configured for TaskQueue")
        payload = {"doc_id": doc_id}
        if isinstance(extra, dict) and extra:
            payload.update(extra)
        if self.mode == "streams":
            self._xadd(self.embed_queue, payload)
            return
        self.client.rpush(self.embed_queue, json.dumps(payload))

    def enqueue_dead_letter(self, doc_id: str, reason: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> None:
        if not self.client:
            raise RuntimeError("Redis not configured for TaskQueue")
        payload = {"doc_id": doc_id, "reason": reason}
        if isinstance(extra, dict) and extra:
            payload.update(extra)
        if self.mode == "streams":
            self._xadd(self.dead_letter_queue, payload)
            return
        self.client.rpush(self.dead_letter_queue, json.dumps(payload))

    def enqueue_rag_query(self, *, job_id: str, tenant_id: str, user_id: str, role: str, query: str, top_k: int, threshold: float, metadata_filter: Optional[Dict[str, Any]] = None) -> None:
        if not self.client:
            raise RuntimeError("Redis not configured for TaskQueue")
        payload: Dict[str, Any] = {
            "task_type": "rag_query",
            "job_id": job_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "query": query,
            "top_k": int(top_k),
            "threshold": float(threshold),
            "metadata_filter": metadata_filter or {},
        }
        if self.mode == "streams":
            self._xadd(self.rag_queue, payload)
            return
        self.client.rpush(self.rag_queue, json.dumps(payload))

    def dequeue_from(self, stream: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        if self.mode == "streams":
            self._ensure_group(stream)
            if self.mode != "streams":
                # WRONGTYPE fallback
                result = self.client.blpop(stream, timeout=timeout)
                if not result:
                    return None
                _, payload = result
                return json.loads(payload)
            task = self._try_claim_stale(stream)
            if task:
                return task
            resp = self.client.xreadgroup(
                groupname=self.group,
                consumername=self.consumer,
                streams={stream: ">"},
                count=1,
                block=self.block_ms,
            )
            if not resp:
                return None
            stream_name, entries = resp[0]
            msg_id, fields = entries[0]
            raw = fields.get(b"payload") if isinstance(fields, dict) else None
            if raw is None:
                return None
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                payload = {}
            payload["_msg_id"] = msg_id.decode("utf-8") if isinstance(msg_id, (bytes, bytearray)) else str(msg_id)
            payload["_stream"] = stream_name.decode("utf-8") if isinstance(stream_name, (bytes, bytearray)) else str(stream_name)
            payload["_queue_mode"] = "streams"
            payload["_dequeued_at_ms"] = int(time.time() * 1000)
            return payload

        result = self.client.blpop(stream, timeout=timeout)
        if not result:
            return None
        _, payload = result
        return json.loads(payload)

    def dequeue(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        return self.dequeue_from(self.queue_name, timeout=timeout)

    def dequeue_rag(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        return self.dequeue_from(self.rag_queue, timeout=timeout)

    def ack(self, task: Dict[str, Any]) -> None:
        if not self.client or self.mode != "streams":
            return
        msg_id = task.get("_msg_id")
        stream = task.get("_stream") or self.queue_name
        if not msg_id:
            return
        try:
            self.client.xack(stream, self.group, msg_id)
        except Exception:
            # Ack failure should not crash workers; will be reclaimed/claimed later.
            return

    def _try_claim_stale(self, stream: str) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None
        # Prefer XAUTOCLAIM (Redis >= 6.2) if available.
        try:
            if hasattr(self.client, "xautoclaim"):
                next_id, claimed = self.client.xautoclaim(stream, self.group, self.consumer, min_idle_time=self.claim_idle_ms, start_id="0-0", count=1)
                if claimed:
                    msg_id, fields = claimed[0]
                    raw = fields.get(b"payload") if isinstance(fields, dict) else None
                    if raw is None:
                        return None
                    try:
                        payload = json.loads(raw.decode("utf-8"))
                    except Exception:
                        payload = {}
                    payload["_msg_id"] = msg_id.decode("utf-8") if isinstance(msg_id, (bytes, bytearray)) else str(msg_id)
                    payload["_stream"] = stream
                    payload["_queue_mode"] = "streams"
                    return payload
        except Exception:
            pass
        return None

    def length(self) -> int:
        if not self.client:
            return 0
        if self.mode == "streams":
            try:
                return int(self.client.xlen(self.queue_name))
            except Exception:
                return 0
        return int(self.client.llen(self.queue_name))

    def dlq_length(self) -> int:
        if not self.client:
            return 0
        if self.mode == "streams":
            try:
                return int(self.client.xlen(self.dead_letter_queue))
            except Exception:
                return 0
        return int(self.client.llen(self.dead_letter_queue))
