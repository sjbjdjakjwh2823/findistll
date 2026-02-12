from __future__ import annotations

from typing import Any, Dict, List, Optional


def find_three_hop_paths_from_triples(
    *,
    start_node: str,
    triples: List[Dict[str, Any]],
    max_hops: int = 3,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Local (DB-agnostic) 3-hop reasoning over Spoke D triples.

    Supabase mode uses `kg_relationships` (OpsGraph). On-prem deployments often rely
    on `spoke_d_graph`, so we provide a deterministic BFS over those edges.
    """
    if not start_node:
        return []

    adj: Dict[str, List[Dict[str, Any]]] = {}
    for t in triples or []:
        src = t.get("head_node")
        dst = t.get("tail_node")
        if not src or not dst:
            continue
        adj.setdefault(str(src), []).append(
            {
                "to": str(dst),
                "relation": t.get("relation") or "related_to",
                "properties": t.get("properties") or {},
            }
        )

    paths: List[Dict[str, Any]] = []
    queue: List[Dict[str, Any]] = [{"node": start_node, "path": []}]
    seen = set()

    while queue and len(paths) < limit:
        cur = queue.pop(0)
        node = cur["node"]
        path = cur["path"]
        if len(path) >= max_hops:
            continue
        for edge in adj.get(node, []):
            nxt = edge["to"]
            step = {"from": node, "to": nxt, "relation": edge["relation"], "properties": edge["properties"]}
            new_path = path + [step]
            key = (start_node, nxt, len(new_path), tuple((p["from"], p["relation"], p["to"]) for p in new_path))
            if key in seen:
                continue
            seen.add(key)
            paths.append({"start": start_node, "end": nxt, "hops": len(new_path), "steps": new_path})
            queue.append({"node": nxt, "path": new_path})

    return paths


def format_three_hop_paths(paths: List[Dict[str, Any]], *, max_items: int = 5) -> str:
    if not paths:
        return ""
    lines = ["[Graph 3-Hop Paths (local)]"]
    for idx, p in enumerate(paths[:max_items], 1):
        steps = p.get("steps") or []
        chain = " -> ".join([str(s.get("to")) for s in steps if s.get("to")])
        lines.append(f"{idx}. {p.get('start')} -> {chain} (hops={p.get('hops')})")
    return "\n".join(lines)

