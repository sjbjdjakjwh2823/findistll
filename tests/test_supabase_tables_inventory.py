from pathlib import Path


def test_supabase_tables_inventory_is_present():
    """
    Keep a single "one place" inventory file up to date for the project.
    """
    repo = Path(__file__).resolve().parents[1]
    p = repo / "docs" / "SUPABASE_TABLES_INVENTORY.md"
    assert p.exists()
    txt = p.read_text(encoding="utf-8")
    # sanity: inventory must include core tables
    assert "`raw_documents`" in txt
    assert "`generated_samples`" in txt
    assert "`partner_accounts`" in txt
    assert "`integration_secrets`" in txt

