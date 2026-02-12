from typing import Optional
from app.db.client import DBClient

_db: Optional[DBClient] = None


def set_db(db: DBClient) -> None:
    global _db
    _db = db


def get_db() -> DBClient:
    if _db is None:
        raise RuntimeError('Database not initialized')
    return _db
