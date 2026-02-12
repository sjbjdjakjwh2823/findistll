# Supabase Tables Inventory (Source of Truth: supabase_bootstrap_preciso.sql)

이 문서는 `supabase_bootstrap_preciso.sql`에서 생성되는 테이블을 섹션(작업대/워크스트림)별로 자동 추출한 인벤토리입니다.

## How To Update
- 새로운 작업대에서 테이블을 추가하면 반드시 `supabase_bootstrap_preciso.sql`에 섹션(`-- >>> BEGIN ...`)으로 포함시키고
- `python3 scripts/supabase_table_inventory.py`를 실행해 이 문서를 갱신합니다.

## Sections
- `supabase_ai_evolution.sql`: 12 tables
- `supabase_integration_secrets.sql`: 1 tables
- `supabase_partner_registry.sql`: 2 tables
- `supabase_phase1.sql`: 13 tables
- `supabase_phase2.sql`: 4 tables
- `supabase_phase3.sql`: 8 tables
- `supabase_rbac.sql`: 3 tables
- `supabase_retrieval_trust_plan.sql`: 5 tables
- `supabase_schema.sql`: 2 tables
- `supabase_spokes.sql`: 5 tables
- `supabase_ws8_spoke_ab.sql`: 3 tables

## supabase_ai_evolution.sql
- `app_versions` (bootstrap line 1164)
- `audit_logs` (bootstrap line 1093)
- `case_embeddings` (bootstrap line 927)
- `company_schemas` (bootstrap line 1066)
- `eval_runs` (bootstrap line 981)
- `evidence_feedback` (bootstrap line 953)
- `gold_standard_cases` (bootstrap line 1077)
- `license_activations` (bootstrap line 1141)
- `license_checks` (bootstrap line 1151)
- `licenses` (bootstrap line 1128)
- `perf_metrics` (bootstrap line 990)
- `selfcheck_samples` (bootstrap line 967)

## supabase_integration_secrets.sql
- `integration_secrets` (bootstrap line 901)

## supabase_partner_registry.sql
- `partner_accounts` (bootstrap line 867)
- `partner_api_keys` (bootstrap line 877)

## supabase_phase1.sql
- `annotator_stats` (bootstrap line 289)
- `data_quality_scores` (bootstrap line 168)
- `dataforge_metrics` (bootstrap line 267)
- `dataset_samples` (bootstrap line 207)
- `generated_samples` (bootstrap line 74)
- `golden_datasets` (bootstrap line 185)
- `human_annotations` (bootstrap line 102)
- `labeling_function_profiles` (bootstrap line 157)
- `labeling_function_results` (bootstrap line 126)
- `prompt_templates` (bootstrap line 224)
- `qa_validations` (bootstrap line 248)
- `raw_documents` (bootstrap line 47)
- `snorkel_aggregated_facts` (bootstrap line 143)

## supabase_phase2.sql
- `ai_brain_traces` (bootstrap line 590)
- `causal_edges` (bootstrap line 571)
- `causal_nodes` (bootstrap line 558)
- `embeddings_finance` (bootstrap line 537)

## supabase_phase3.sql
- `kg_entities` (bootstrap line 766)
- `kg_relationships` (bootstrap line 775)
- `ontology_nodes` (bootstrap line 794)
- `ops_audit_logs` (bootstrap line 736)
- `ops_case_state_history` (bootstrap line 751)
- `ops_cases` (bootstrap line 719)
- `ops_entities` (bootstrap line 692)
- `ops_relationships` (bootstrap line 705)

## supabase_rbac.sql
- `permissions` (bootstrap line 1212)
- `rbac_users` (bootstrap line 1189)
- `role_assignments` (bootstrap line 1200)

## supabase_retrieval_trust_plan.sql
- `audit_events` (bootstrap line 1544)
- `golden_samples` (bootstrap line 1585)
- `lf_metrics` (bootstrap line 1575)
- `lf_runs` (bootstrap line 1556)
- `lf_votes` (bootstrap line 1565)

## supabase_schema.sql
- `cases` (bootstrap line 8)
- `documents` (bootstrap line 18)

## supabase_spokes.sql
- `ai_training_sets` (bootstrap line 850)
- `spoke_a_strategy` (bootstrap line 808)
- `spoke_b_quant_meta` (bootstrap line 820)
- `spoke_c_rag_context` (bootstrap line 830)
- `spoke_d_graph` (bootstrap line 841)

## supabase_ws8_spoke_ab.sql
- `dataset_versions` (bootstrap line 1779)
- `spoke_a_samples` (bootstrap line 1793)
- `spoke_b_artifacts` (bootstrap line 1811)
