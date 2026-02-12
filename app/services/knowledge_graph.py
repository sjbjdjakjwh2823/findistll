from typing import Any, Dict, List


class KnowledgeGraphBuilder:
    """
    Build a lightweight knowledge graph from OpsGraph entities/cases.
    """

    def __init__(self, client) -> None:
        self.client = client

    def build(self) -> Dict[str, int]:
        entities = self.client.table("ops_entities").select("*").execute().data or []
        cases = self.client.table("ops_cases").select("*").execute().data or []
        ops_relationships = self.client.table("ops_relationships").select("*").execute().data or []

        kg_entities = []
        for entity in entities:
            kg_entities.append(
                {
                    "entity_type": entity.get("entity_type"),
                    "entity_id": entity.get("id"),
                    "properties": entity.get("properties", {}),
                }
            )

        for case in cases:
            kg_entities.append(
                {
                    "entity_type": "case",
                    "entity_id": case.get("id"),
                    "properties": {
                        "status": case.get("status"),
                        "priority": case.get("priority"),
                    },
                }
            )

        if kg_entities:
            self.client.table("kg_entities").upsert(kg_entities, on_conflict="entity_type,entity_id").execute()

        relationships = []
        entity_index = {e.get("id"): e for e in entities}

        # case -> entity link
        for case in cases:
            entity_id = case.get("entity_id")
            if not entity_id:
                continue
            relationships.append(
                {
                    "source_entity_type": "case",
                    "source_entity_id": case.get("id"),
                    "target_entity_type": entity_index.get(entity_id, {}).get("entity_type", "entity"),
                    "target_entity_id": entity_id,
                    "relationship_type": "belongs_to",
                    "weight": 1.0,
                }
            )

        # same industry relationships
        industry_map: Dict[str, List[str]] = {}
        for entity in entities:
            props = entity.get("properties") or {}
            industry = props.get("industry")
            if industry:
                industry_map.setdefault(industry, []).append(entity.get("id"))

        for industry, ids in industry_map.items():
            for i, source_id in enumerate(ids):
                for target_id in ids[i + 1 :]:
                    relationships.append(
                        {
                            "source_entity_type": entity_index.get(source_id, {}).get("entity_type", "entity"),
                            "source_entity_id": source_id,
                            "target_entity_type": entity_index.get(target_id, {}).get("entity_type", "entity"),
                            "target_entity_id": target_id,
                            "relationship_type": "same_industry",
                            "weight": 0.8,
                            "properties": {"industry": industry},
                        }
                    )

        if relationships:
            self.client.table("kg_relationships").upsert(
                relationships,
                on_conflict="source_entity_type,source_entity_id,target_entity_type,target_entity_id,relationship_type",
            ).execute()

        # ops_relationships -> kg_relationships (enterprise causal/supply-chain wiring)
        ops_rels_written = 0
        if ops_relationships:
            payload = []
            for rel in ops_relationships:
                src = rel.get("source_id")
                dst = rel.get("target_id")
                if not src or not dst:
                    continue
                src_type = (entity_index.get(src) or {}).get("entity_type", "entity")
                dst_type = (entity_index.get(dst) or {}).get("entity_type", "entity")
                payload.append(
                    {
                        "source_entity_type": src_type,
                        "source_entity_id": src,
                        "target_entity_type": dst_type,
                        "target_entity_id": dst,
                        "relationship_type": rel.get("relationship_type") or "related_to",
                        "weight": float(rel.get("confidence") or 0.5),
                        "properties": rel.get("properties") or {},
                    }
                )
            if payload:
                self.client.table("kg_relationships").upsert(
                    payload,
                    on_conflict="source_entity_type,source_entity_id,target_entity_type,target_entity_id,relationship_type",
                ).execute()
                ops_rels_written = len(payload)

        return {"entities": len(kg_entities), "relationships": len(relationships) + ops_rels_written}


class OntologyBuilder:
    """
    Lightweight ontology from OpsGraph entities + case fields.
    """

    def __init__(self, client) -> None:
        self.client = client

    def build(self) -> Dict[str, int]:
        entities = self.client.table("ops_entities").select("*").execute().data or []
        fields = {"status", "priority", "entity_type", "industry"}

        ontology_nodes = []
        for entity in entities:
            ontology_nodes.append(
                {
                    "node_type": "entity_type",
                    "name": entity.get("entity_type"),
                }
            )
            props = entity.get("properties") or {}
            industry = props.get("industry")
            if industry:
                ontology_nodes.append({"node_type": "industry", "name": industry})

        for field in fields:
            ontology_nodes.append({"node_type": "field", "name": field})

        if ontology_nodes:
            self.client.table("ontology_nodes").upsert(
                ontology_nodes,
                on_conflict="node_type,name",
            ).execute()

        return {"nodes": len(ontology_nodes)}
