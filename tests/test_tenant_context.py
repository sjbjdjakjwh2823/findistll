from app.core.tenant_context import (
    clear_tenant_id,
    get_effective_tenant_id,
    set_tenant_id,
)
from app.db.client import InMemoryDB


def test_default_tenant_is_public():
    clear_tenant_id()
    assert get_effective_tenant_id() == "public"


def test_inmemorydb_isolation_by_tenant():
    db = InMemoryDB()
    try:
        set_tenant_id("tenant_alpha")
        case_a = db.create_case({"title": "Alpha Case"})

        set_tenant_id("tenant_beta")
        case_b = db.create_case({"title": "Beta Case"})

        set_tenant_id("tenant_alpha")
        cases_alpha = db.list_cases()
        assert len(cases_alpha) == 1
        assert cases_alpha[0]["case_id"] == case_a

        set_tenant_id("tenant_beta")
        cases_beta = db.list_cases()
        assert len(cases_beta) == 1
        assert cases_beta[0]["case_id"] == case_b
    finally:
        clear_tenant_id()
