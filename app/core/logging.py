from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(service_name: str = "preciso") -> None:
    """
    Default: log to stdout for container environments.
    Optional: also log to a rotating file when LOG_TO_FILE=1.
    """
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers when imported multiple times.
    if getattr(root, "_preciso_configured", False):
        return

    fmt = os.getenv("LOG_FORMAT") or "%(asctime)s %(levelname)s %(name)s %(message)s"
    formatter = logging.Formatter(fmt)

    sh = logging.StreamHandler()
    sh.setLevel(level)
    sh.setFormatter(formatter)
    root.addHandler(sh)

    if os.getenv("LOG_TO_FILE", "0") == "1":
        path = os.getenv("LOG_FILE_PATH") or f"/var/log/preciso/{service_name}.log"
        max_bytes = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
        backups = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fh = RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            root.addHandler(fh)
        except Exception:
            # Never block process startup due to file logging.
            root.warning("failed to initialize file logging", exc_info=True)

    setattr(root, "_preciso_configured", True)
