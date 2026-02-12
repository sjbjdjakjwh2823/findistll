import os
import io
import json
import logging
from typing import Optional, List

import httpx
from datetime import datetime, timezone
from contextlib import contextmanager

logger = logging.getLogger(__name__)


VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"


def _get_api_key() -> Optional[str]:
    key = os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key
    # Best-effort: load local .env secrets in monorepo runs (scripts/tests).
    try:
        from app.core.secret_loader import load_secrets_from_file

        load_secrets_from_file()
        return os.getenv("GOOGLE_VISION_API_KEY") or os.getenv("GOOGLE_API_KEY")
    except Exception:
        return None


def _usage_store_path() -> str:
    return os.getenv(
        "VISION_USAGE_STORE",
        "/Users/leesangmin/.openclaw/workspace/preciso/artifacts/vision_usage.json",
    )


def _vision_daily_limit() -> int:
    try:
        return int(os.getenv("VISION_DAILY_LIMIT", "30") or "30")
    except Exception:
        return 30


def _get_today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _redis_url() -> Optional[str]:
    return os.getenv("REDIS_URL")


def _can_consume_vision_call_redis() -> Optional[bool]:
    """
    If REDIS_URL is set, use Redis counter with expiry.
    Returns True/False if redis used, or None if not configured/failed.
    """
    url = _redis_url()
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(url)
        day = _get_today_key()
        key = f"vision_usage:{day}"
        limit = _vision_daily_limit()
        if limit <= 0:
            return False
        count = client.incr(key)
        if count == 1:
            client.expire(key, 60 * 60 * 48)
        if count > limit:
            return False
        return True
    except Exception:
        return None


@contextmanager
def _locked_usage_file(path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path, "a+", encoding="utf-8")
    try:
        try:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except Exception:
            # Best-effort lock on non-Unix platforms.
            logger.info("vision usage file lock not available; proceeding without lock")
        f.seek(0)
        yield f
    finally:
        try:
            f.flush()
        except Exception:
            logger.warning("vision usage file flush failed", exc_info=True)
        try:
            import fcntl

            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            logger.info("vision usage file unlock skipped")
        f.close()


def _can_consume_vision_call() -> bool:
    redis_result = _can_consume_vision_call_redis()
    if redis_result is not None:
        return redis_result
    limit = _vision_daily_limit()
    if limit <= 0:
        return False
    path = _usage_store_path()
    day = _get_today_key()
    with _locked_usage_file(path) as f:
        try:
            raw = f.read().strip()
            usage = json.loads(raw) if raw else {}
        except Exception:
            usage = {}
        count = int(usage.get(day, 0))
        if count >= limit:
            return False
        usage[day] = count + 1
        f.seek(0)
        f.truncate()
        json.dump(usage, f, ensure_ascii=False, indent=2)
    return True


def _extract_text_from_response(payload: dict) -> str:
    try:
        responses = payload.get("responses") or []
        if not responses:
            return ""
        first = responses[0] or {}
        # Prefer full document text when available.
        full = (((first.get("fullTextAnnotation") or {}) or {}).get("text")) or ""
        if full:
            return full
        # Fallback: join text annotations.
        ann = first.get("textAnnotations") or []
        if ann and isinstance(ann, list):
            # The first item is usually the full text.
            if isinstance(ann[0], dict) and ann[0].get("description"):
                return str(ann[0].get("description"))
            return "\n".join([str(a.get("description", "")) for a in ann if isinstance(a, dict)])
    except Exception:
        return ""
    return ""


async def ocr_image_bytes(image_bytes: bytes, *, api_key: Optional[str] = None) -> str:
    """
    OCR a single image using Google Vision API (API key auth).

    Note:
    - This uses the REST API with an API key (not service account JSON).
    - Returns best-effort extracted text; empty string on failure.
    """
    key = api_key or _get_api_key()
    if not key:
        return ""
    if not _can_consume_vision_call():
        logger.warning("Vision OCR daily limit reached. Skipping Vision call.")
        return ""

    import base64

    req = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("ascii")},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }

    try:
        timeout_s = float(os.getenv("GOOGLE_VISION_TIMEOUT_S", "25") or "25")
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            r = await client.post(VISION_ENDPOINT, params={"key": key}, json=req)
            if r.status_code != 200:
                logger.warning("Google Vision OCR failed (%s): %s", r.status_code, r.text[:2000])
                return ""
            return _extract_text_from_response(r.json())
    except Exception as exc:
        logger.warning("Google Vision OCR exception: %s", exc)
        return ""


async def ocr_pil_images(images: List["Image.Image"], *, api_key: Optional[str] = None, max_pages: int = 6) -> str:
    """
    OCR a list of PIL Images. Caps pages to control latency/cost.
    """
    key = api_key or _get_api_key()
    if not key:
        return ""
    if not images:
        return ""
    try:
        from PIL import Image  # noqa: F401
    except Exception:
        return ""

    merged: List[str] = []
    for img in images[: max_pages]:
        try:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            text = await ocr_image_bytes(buf.getvalue(), api_key=key)
            if text:
                merged.append(text)
        except Exception:
            continue
    return "\n\n".join(merged).strip()
