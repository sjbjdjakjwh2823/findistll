# Worker 2 - DataForge/Findistill Quality (WS6/WS7/WS8)

## Mission
Harden evidence quality + numeric integrity:
- OCR policy fixed order: text layer detect -> OCR -> fallback parsers
- Numeric preservation checks (table cell <-> facts), scale mismatch detection
- Evidence completeness enforcement (document/page/snippet/method/confidence)

Source of truth:
- `PLANS/Preciso_Enterprise_NonDev_Central_RAG_LLM_Master_Plan_v1.md` (Phase 3)

## Worktree + Branch
- Worktree: `.worktrees/ws-data-quality`
- Branch: `ws/data-quality`

## Owned Files (You Can Edit)
- `app/services/unified_engine.py`
- `app/services/distill_engine.py`
- `vendor/findistill/**`
- `app/services/preciso_mathematics.py`
- `app/services/data_quality.py`
- `app/services/polars_processing.py`
- `tests/test_ixbrl*`, `tests/test_pdf*`, `tests/test_spreadsheet*`

## Do Not Touch (Conductor-Only Contracts)
- `app/services/types.py`
- `app/core/auth.py`
- `app/core/rbac.py`
- `app/models/schemas.py`
- `supabase_all_in_one_safe.sql`
- `supabase_migration_safe.sql`

## Non-Negotiables (Finance Extraction Rules)
- Use `Decimal` for financial calculations (no float for normalized_value).
- Keep `raw_value` vs `normalized_value` separate where possible.
- Every extracted fact must carry evidence:
  - document_id (or doc_id)
  - page/section reference (if available)
  - snippet (or token range)
  - extraction_method (ixbrl/html/pdf_ocr/etc)
  - confidence_score (0-1)
- Never silently return empty facts:
  - If iXBRL yields 0 facts: fallback to HTML table; if still 0: OCR/table recovery; if still low quality: mark `needs_review`.

## Execution Template (Fill This Before Coding)
- Goal:
- Home: `.worktrees/ws-data-quality`
- Files to edit (owned only):
- DB migration required: yes/no (if yes, propose to Conductor; do not edit shared SQL here)
- Tests add/update:
- Rollback plan: feature flag off, or revert commit(s)

## High-Risk Hotspot
`app/services/distill_engine.py` currently has "mock fallback" behavior.
Do not delete it in your branch without Conductor approval; instead, propose a safe replacement strategy (e.g., needs_review + explicit error payload).

## Tests
- Add/extend at least 1 regression test for:
  - OCR fallback order (text layer detection)
  - scale handling or numeric preservation

## Local Commands
- `pytest -q tests/test_pdf_text_selection.py`
- `pytest -q tests/test_ixbrl_parser_smoke.py`
- `pytest -q tests/test_ixbrl_scale_handling.py`

## Hand-off To Conductor (What To Write)
When you're ready to merge, provide:
- Evidence schema changes you want (proposal only if contract files are impacted)
- Before/after examples of extracted facts (1-2)
- Failure-mode behavior (0 facts, low confidence, needs_review)
