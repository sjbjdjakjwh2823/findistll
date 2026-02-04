# Phase 5.0 Alpha - Global Interconnectedness Mapping

Purpose: define a data schema that models cross-market interconnectedness across the US, Europe (ECB), and Asia (BoJ, PBoC), and specify graph-metadata for global risk transfer visualization.

## 1) Core Entities (Relational or Document)

### 1.1 Market
- market_id (string, PK)
- region (enum: US, EU, JP, CN)
- name (string)
- central_bank_id (string, FK)
- base_currency (string, ISO 4217)
- trading_hours (string, tz-aware)
- liquidity_tier (int, 1-5)

### 1.2 CentralBank
- central_bank_id (string, PK)
- name (string)
- policy_rate (float)
- balance_sheet_usd (float)
- policy_regime (string)
- last_decision_date (date)

### 1.3 Instrument
- instrument_id (string, PK)
- market_id (string, FK)
- asset_class (enum: EQ, FI, FX, CMDTY, CRYPTO)
- ticker (string)
- currency (string, ISO 4217)
- issuer_country (string, ISO 3166-1 alpha-2)
- maturity_date (date, nullable)
- duration (float, nullable)

### 1.4 MacroFactor
- factor_id (string, PK)
- name (string)
- factor_type (enum: policy, growth, inflation, liquidity, geopolitics, fx_vol)
- unit (string)
- update_frequency (enum: daily, weekly, monthly, ad_hoc)

### 1.5 CountryRisk
- country_code (string, ISO 3166-1 alpha-2, PK)
- geopolitical_risk_index (float)
- fx_volatility_index (float)
- sovereign_spread_bps (float)
- capital_flow_pressure (float)
- last_updated (date)

### 1.6 Exposure
- exposure_id (string, PK)
- source_entity_type (enum: market, instrument, macro_factor, country)
- source_entity_id (string)
- target_entity_type (enum: market, instrument, macro_factor, country)
- target_entity_id (string)
- exposure_channel (enum: rates, fx, credit, liquidity, supply_chain, geopolitics)
- strength (float, 0-1)
- lag_days (int)
- confidence (float, 0-1)
- evidence_ref (string, nullable)

### 1.7 ShockEvent
- shock_id (string, PK)
- event_type (enum: policy, geopolitical, liquidity, credit, fx)
- origin_market_id (string, FK)
- origin_country (string, ISO 3166-1 alpha-2)
- timestamp_utc (datetime)
- magnitude (float)
- description (string)

### 1.8 TransmissionTrace
- trace_id (string, PK)
- shock_id (string, FK)
- path_order (int)
- from_entity_type (enum)
- from_entity_id (string)
- to_entity_type (enum)
- to_entity_id (string)
- propagation_delay_hours (int)
- incremental_impact (float)
- cumulative_impact (float)

## 2) Minimal Graph-Native View (Denormalized)

### 2.1 Node
- node_id (string)
- node_type (enum: market, instrument, macro_factor, country, central_bank)
- label (string)
- region (enum: US, EU, JP, CN, GLOBAL)
- weight (float)  # e.g., market cap, volume, risk importance
- attributes (json)

### 2.2 Edge
- edge_id (string)
- source (node_id)
- target (node_id)
- edge_type (enum: exposure, policy_link, fx_link, credit_link, liquidity_link)
- direction (enum: directed, undirected)
- weight (float)
- lag_days (int)
- confidence (float)
- attributes (json)

## 3) Data Provenance

### 3.1 Source
- source_id (string, PK)
- provider (string)
- dataset_name (string)
- update_frequency (enum)
- coverage (string)
- license (string)

### 3.2 Lineage
- lineage_id (string, PK)
- entity_type (enum: node, edge, factor)
- entity_id (string)
- source_id (string, FK)
- last_ingested_at (datetime)
- transformation_notes (string)

## 4) Graph Engine Metadata for Risk Transfer Visualization

### 4.1 GraphMeta
- graph_id (string, PK)
- graph_version (string)
- snapshot_time_utc (datetime)
- window_start_utc (datetime)
- window_end_utc (datetime)
- scenario_id (string, nullable)
- primary_focus (enum: contagion, liquidity, policy, fx, geopolitics)
- default_layout (enum: force, geo, hierarchy)
- region_focus (enum: global, us, eu, jp, cn)

### 4.2 LayerMeta
- layer_id (string, PK)
- graph_id (string, FK)
- layer_type (enum: nodes, edges, heatmap, annotations)
- filter_rule (json)
- visual_encoding (json)  # color, size, opacity, texture
- z_index (int)

### 4.3 NodeStyleMeta
- style_id (string, PK)
- graph_id (string, FK)
- node_type (enum)
- color (string)
- size_range (tuple)
- label_rule (json)
- animation_rule (json)

### 4.4 EdgeStyleMeta
- style_id (string, PK)
- graph_id (string, FK)
- edge_type (enum)
- color (string)
- width_range (tuple)
- dashed (bool)
- animation_rule (json)

### 4.5 PathMeta (Risk Transfer)
- path_id (string, PK)
- graph_id (string, FK)
- shock_id (string, FK)
- path_sequence (array[node_id])
- path_score (float)
- total_delay_hours (int)
- total_impact (float)
- rationale (string)

### 4.6 AnnotationMeta
- annotation_id (string, PK)
- graph_id (string, FK)
- anchor_node_id (string)
- text (string)
- severity (enum: low, medium, high)
- created_at (datetime)

## 5) Suggested Indexes
- Exposure: (source_entity_type, source_entity_id), (target_entity_type, target_entity_id)
- TransmissionTrace: (shock_id, path_order)
- CountryRisk: (country_code, last_updated)
- Node: (node_type, region)
- Edge: (edge_type, weight)

## 6) Example Payloads

### 6.1 Node
{
  "node_id": "market_us_equities",
  "node_type": "market",
  "label": "US Equities",
  "region": "US",
  "weight": 0.92,
  "attributes": {
    "market_id": "US_EQ",
    "base_currency": "USD"
  }
}

### 6.2 Edge
{
  "edge_id": "edge_us_eu_fx",
  "source": "market_us_equities",
  "target": "market_eu_equities",
  "edge_type": "fx_link",
  "direction": "directed",
  "weight": 0.68,
  "lag_days": 2,
  "confidence": 0.74,
  "attributes": {
    "exposure_channel": "fx",
    "evidence_ref": "model_v0.5"
  }
}

### 6.3 GraphMeta
{
  "graph_id": "global_contagion_2026w05",
  "graph_version": "v0.5-alpha",
  "snapshot_time_utc": "2026-02-04T03:00:00Z",
  "window_start_utc": "2026-01-01T00:00:00Z",
  "window_end_utc": "2026-02-04T00:00:00Z",
  "primary_focus": "contagion",
  "default_layout": "force",
  "region_focus": "global"
}
