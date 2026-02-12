from typing import Any, Dict, List

from app.db.registry import get_db


class CustomFieldService:
    def list_company_fields(self, company_id: str) -> List[Dict[str, Any]]:
        db = get_db()
        if hasattr(db, 'client'):
            try:
                res = db.client.table('company_schemas').select('*').eq('company_id', company_id).execute()
                return res.data or []
            except Exception:
                return []
        return []
