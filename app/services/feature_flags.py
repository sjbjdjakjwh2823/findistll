from __future__ import annotations

import os
from typing import Dict


_OVERRIDES: Dict[str, bool] = {}

_FLAG_ENV = {
    "auto_scale_enabled": "AUTO_SCALE_ENABLED",
    "auto_train_on_approval": "AUTO_TRAIN_ON_APPROVAL",
    "rag_cache_enabled": "RAG_CACHE_ENABLED",
    "rag_rerank_enabled": "RAG_RERANK_ENABLED",
    "rag_compress_enabled": "RAG_COMPRESS_ENABLED",
    "rag_async_enabled": "RAG_ASYNC_ENABLED",
    "finrobot_enabled": "FINROBOT_ENABLED",
    "rate_limit_enabled": "RATE_LIMIT_ENABLED",
    "license_check_enabled": "LICENSE_CHECK_ENABLED",
    "lakehouse_enabled": "LAKEHOUSE_ENABLED",
    "egress_sensitive_block": "EGRESS_SENSITIVE_BLOCK",
    "egress_approval_required": "EGRESS_APPROVAL_REQUIRED",
    "pdf_text_layer_probe_first": "PDF_TEXT_LAYER_PROBE_FIRST",
}

_FLAG_META = {
    "auto_scale_enabled": "Enable latency-based auto scaling for RAG features",
    "auto_train_on_approval": "Auto train immediately after approval gate passes",
    "rag_cache_enabled": "Enable Redis-backed RAG cache",
    "rag_rerank_enabled": "Enable RAG re-ranker",
    "rag_compress_enabled": "Enable RAG compression",
    "rag_async_enabled": "Enable async RAG mode (queue/worker) for heavy queries",
    "finrobot_enabled": "Enable FinRobot multi-agent pipeline",
    "rate_limit_enabled": "Enable API rate limiting",
    "license_check_enabled": "Enable license checks middleware",
    "lakehouse_enabled": "Enable Lakehouse services (Delta/Spark/MLflow/UC)",
    "egress_sensitive_block": "Block external egress when sensitive content detected",
    "egress_approval_required": "Require approval before external egress",
    "pdf_text_layer_probe_first": "Prefer PDF text-layer when sufficient before doing OCR",
}


def _env_flag(name: str) -> bool:
    env_name = _FLAG_ENV.get(name, name.upper())
    return os.getenv(env_name, "0") == "1"


def get_flag(name: str, default: bool | None = None) -> bool:
    if name in _OVERRIDES:
        return _OVERRIDES[name]
    if name in _FLAG_ENV:
        return _env_flag(name)
    return default if default is not None else False


def set_flag(name: str, value: bool) -> None:
    _OVERRIDES[name] = bool(value)


def list_flags() -> Dict[str, Dict[str, object]]:
    out: Dict[str, Dict[str, object]] = {}
    for key in _FLAG_ENV.keys():
        source = "override" if key in _OVERRIDES else "env"
        out[key] = {
            "enabled": get_flag(key),
            "source": source,
            "description": _FLAG_META.get(key, ""),
        }
    return out
