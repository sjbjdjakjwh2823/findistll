"""
Spoke D: Causal Engine for Economic Reasoning
Phase 2: AI Brain - Causal Graph Analysis
"""

import os
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)

# Optional imports for advanced features
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.info("NetworkX not available. Using built-in graph implementation.")

try:
    import polars as pl
    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False


@dataclass
class CausalNode:
    """A node in the causal graph."""
    id: str
    name: str
    category: str  # 'macro', 'company', 'metric', 'sector', 'event'
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalEdge:
    """An edge in the causal graph."""
    source_id: str
    target_id: str
    relation: str
    weight: float
    lag_days: int
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CounterfactualResult:
    """Result of a counterfactual analysis."""
    scenario: str
    initial_node: str
    change_percent: float
    impacts: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class CausalTrace:
    """Trace of causal reasoning for transparency."""
    nodes_involved: List[str] = field(default_factory=list)
    edges_traversed: List[Dict[str, Any]] = field(default_factory=list)
    reasoning_steps: List[str] = field(default_factory=list)


class CausalEngine:
    """
    Causal reasoning engine for economic/financial analysis.
    
    Builds DAGs from correlation data and supports:
    - Graph construction
    - Counterfactual simulations
    - Path analysis
    """
    
    def __init__(self, supabase_client: Any = None):
        """
        Initialize Causal Engine.
        
        Args:
            supabase_client: Supabase client for persistence
        """
        self.supabase = supabase_client
        self.nodes: Dict[str, CausalNode] = {}
        self.edges: List[CausalEdge] = []
        self._graph = None
        
        # Load graph from DB if available
        if supabase_client:
            self._load_from_db()
    
    def _load_from_db(self) -> None:
        """Load causal graph from Supabase."""
        if not self.supabase:
            return
        
        try:
            # Load nodes
            nodes_resp = self.supabase.table("causal_nodes").select("*").execute()
            for row in (nodes_resp.data or []):
                node = CausalNode(
                    id=str(row["id"]),
                    name=row["name"],
                    category=row.get("category", "metric"),
                    properties=row.get("properties", {}),
                )
                self.nodes[node.id] = node
            
            # Load edges
            edges_resp = self.supabase.table("causal_edges").select("*").execute()
            for row in (edges_resp.data or []):
                edge = CausalEdge(
                    source_id=str(row["source_id"]),
                    target_id=str(row["target_id"]),
                    relation=row.get("relation", "causes"),
                    weight=float(row.get("weight", 1.0)),
                    lag_days=int(row.get("lag_days", 0)),
                    confidence=float(row.get("confidence", 0.5)),
                    evidence=row.get("evidence", {}),
                )
                self.edges.append(edge)
            
            logger.info(f"Loaded causal graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
            
        except Exception as e:
            logger.warning(f"Failed to load causal graph from DB: {e}")
    
    def build_graph(
        self,
        data: Optional[Any] = None,
        correlation_threshold: float = 0.3,
    ) -> None:
        """
        Build/update causal graph from correlation data.
        
        Args:
            data: Polars DataFrame with correlation matrix or raw data
            correlation_threshold: Minimum correlation to create an edge
        """
        if HAS_NETWORKX:
            self._graph = nx.DiGraph()
            
            # Add nodes
            for node in self.nodes.values():
                self._graph.add_node(
                    node.id,
                    name=node.name,
                    category=node.category,
                    **node.properties,
                )
            
            # Add edges
            for edge in self.edges:
                if abs(edge.weight) >= correlation_threshold:
                    self._graph.add_edge(
                        edge.source_id,
                        edge.target_id,
                        relation=edge.relation,
                        weight=edge.weight,
                        lag_days=edge.lag_days,
                        confidence=edge.confidence,
                    )
        
        # If Polars data provided, compute correlations
        if data is not None and HAS_POLARS and isinstance(data, pl.DataFrame):
            self._build_from_polars(data, correlation_threshold)
        
        logger.info(f"Built causal graph: {len(self.nodes)} nodes")
    
    def _build_from_polars(
        self,
        df: Any,  # pl.DataFrame
        threshold: float,
    ) -> None:
        """Build graph edges from Polars correlation analysis."""
        try:
            numeric_cols = [c for c in df.columns if df[c].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]
            
            if len(numeric_cols) < 2:
                logger.warning("Not enough numeric columns for correlation")
                return
            
            # Compute correlation matrix
            corr_matrix = df.select(numeric_cols).corr()
            
            for i, col1 in enumerate(numeric_cols):
                for j, col2 in enumerate(numeric_cols):
                    if i >= j:
                        continue
                    
                    corr = corr_matrix[i, j]
                    if abs(corr) >= threshold:
                        # Create nodes if they don't exist
                        if col1 not in [n.name for n in self.nodes.values()]:
                            self.add_node(col1, "metric")
                        if col2 not in [n.name for n in self.nodes.values()]:
                            self.add_node(col2, "metric")
                        
                        # Add edge
                        source = next(n.id for n in self.nodes.values() if n.name == col1)
                        target = next(n.id for n in self.nodes.values() if n.name == col2)
                        
                        relation = "positive_correlation" if corr > 0 else "negative_correlation"
                        self.add_edge(source, target, relation, corr, 0, abs(corr))
            
        except Exception as e:
            logger.error(f"Failed to build from Polars: {e}")
    
    def add_node(
        self,
        name: str,
        category: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a node to the graph."""
        import uuid
        node_id = str(uuid.uuid4())
        
        node = CausalNode(
            id=node_id,
            name=name,
            category=category,
            properties=properties or {},
        )
        self.nodes[node_id] = node
        
        # Persist to DB
        if self.supabase:
            try:
                self.supabase.table("causal_nodes").insert({
                    "id": node_id,
                    "name": name,
                    "category": category,
                    "properties": properties or {},
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to persist node: {e}")
        
        return node_id
    
    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        weight: float,
        lag_days: int = 0,
        confidence: float = 0.5,
    ) -> None:
        """Add an edge to the graph."""
        edge = CausalEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            weight=weight,
            lag_days=lag_days,
            confidence=confidence,
        )
        self.edges.append(edge)
        
        if HAS_NETWORKX and self._graph:
            self._graph.add_edge(
                source_id, target_id,
                relation=relation,
                weight=weight,
                lag_days=lag_days,
                confidence=confidence,
            )
        
        # Persist to DB
        if self.supabase:
            try:
                self.supabase.table("causal_edges").upsert({
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation": relation,
                    "weight": weight,
                    "lag_days": lag_days,
                    "confidence": confidence,
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to persist edge: {e}")
    
    def counterfactual(
        self,
        node_name: str,
        change_percent: float,
        max_depth: int = 3,
    ) -> CounterfactualResult:
        """
        Perform counterfactual analysis: "What if X changes by Y%?"
        
        Args:
            node_name: Name of the node to perturb
            change_percent: Percentage change (e.g., 0.25 for 25% increase)
            max_depth: Maximum depth of propagation
            
        Returns:
            CounterfactualResult with propagated impacts
        """
        # Find the node
        source_node = None
        for node in self.nodes.values():
            if node.name == node_name:
                source_node = node
                break
        
        if not source_node:
            return CounterfactualResult(
                scenario=f"Node '{node_name}' not found",
                initial_node=node_name,
                change_percent=change_percent,
                reasoning=f"Cannot analyze: node '{node_name}' does not exist in the causal graph.",
            )
        
        # BFS to propagate effects
        impacts = []
        visited: Set[str] = set()
        queue: List[Tuple[str, float, int, List[str]]] = [(source_node.id, change_percent, 0, [])]
        reasoning_steps = [
            f"Initial perturbation: {node_name} changes by {change_percent*100:+.1f}%"
        ]
        
        while queue:
            current_id, current_change, depth, path = queue.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            visited.add(current_id)
            
            current_node = self.nodes.get(current_id)
            if not current_node:
                continue
            
            # Record impact (skip the initial node)
            if depth > 0:
                impacts.append({
                    "node": current_node.name,
                    "category": current_node.category,
                    "impact_percent": current_change * 100,
                    "depth": depth,
                    "path": path,
                    "lag_days": sum(
                        e.lag_days for e in self.edges 
                        if e.source_id in path or e.target_id == current_id
                    ),
                })
                reasoning_steps.append(
                    f"  → {current_node.name}: {current_change*100:+.1f}% (depth {depth})"
                )
            
            # Find outgoing edges
            for edge in self.edges:
                if edge.source_id == current_id and edge.target_id not in visited:
                    # Calculate propagated effect
                    propagated = current_change * edge.weight * edge.confidence
                    
                    if abs(propagated) > 0.01:  # Only propagate significant effects
                        queue.append((
                            edge.target_id,
                            propagated,
                            depth + 1,
                            path + [current_id],
                        ))
        
        # Sort impacts by magnitude
        impacts.sort(key=lambda x: abs(x["impact_percent"]), reverse=True)
        
        return CounterfactualResult(
            scenario=f"What if {node_name} changes by {change_percent*100:+.1f}%?",
            initial_node=node_name,
            change_percent=change_percent,
            impacts=impacts,
            reasoning="\n".join(reasoning_steps),
        )
    
    def find_paths(
        self,
        source_name: str,
        target_name: str,
        max_length: int = 5,
    ) -> List[List[str]]:
        """Find all paths between two nodes."""
        source_id = target_id = None
        
        for node in self.nodes.values():
            if node.name == source_name:
                source_id = node.id
            if node.name == target_name:
                target_id = node.id
        
        if not source_id or not target_id:
            return []
        
        if HAS_NETWORKX and self._graph:
            try:
                paths = list(nx.all_simple_paths(
                    self._graph, source_id, target_id, cutoff=max_length
                ))
                # Convert IDs to names
                named_paths = []
                for path in paths:
                    named_path = [self.nodes[nid].name for nid in path if nid in self.nodes]
                    named_paths.append(named_path)
                return named_paths
            except nx.NetworkXError:
                return []
        
        # Fallback: simple BFS
        paths = []
        queue: List[List[str]] = [[source_id]]
        
        while queue:
            path = queue.pop(0)
            if len(path) > max_length:
                continue
            
            current = path[-1]
            
            if current == target_id:
                named_path = [self.nodes[nid].name for nid in path if nid in self.nodes]
                paths.append(named_path)
                continue
            
            for edge in self.edges:
                if edge.source_id == current and edge.target_id not in path:
                    queue.append(path + [edge.target_id])
        
        return paths
    
    def get_upstream_factors(self, node_name: str) -> List[Dict[str, Any]]:
        """Get factors that causally influence a given node."""
        target_id = None
        for node in self.nodes.values():
            if node.name == node_name:
                target_id = node.id
                break
        
        if not target_id:
            return []
        
        factors = []
        for edge in self.edges:
            if edge.target_id == target_id:
                source_node = self.nodes.get(edge.source_id)
                if source_node:
                    factors.append({
                        "name": source_node.name,
                        "category": source_node.category,
                        "relation": edge.relation,
                        "weight": edge.weight,
                        "lag_days": edge.lag_days,
                        "confidence": edge.confidence,
                    })
        
        return sorted(factors, key=lambda x: abs(x["weight"]), reverse=True)
    
    def format_context(self, result: CounterfactualResult, max_chars: int = 2000) -> str:
        """Format counterfactual result for LLM prompt injection."""
        parts = [
            f"[Causal Analysis: {result.scenario}]",
            "",
            result.reasoning,
            "",
            "Key Impacts:",
        ]
        
        for impact in result.impacts[:10]:
            direction = "↑" if impact["impact_percent"] > 0 else "↓"
            parts.append(
                f"  • {impact['node']}: {impact['impact_percent']:+.1f}% {direction} "
                f"(lag: {impact.get('lag_days', 0)} days)"
            )
        
        text = "\n".join(parts)
        if len(text) > max_chars:
            text = text[:max_chars-3] + "..."
        
        return text
    
    def get_trace(self) -> CausalTrace:
        """Get a trace of the graph structure for debugging."""
        return CausalTrace(
            nodes_involved=[n.name for n in self.nodes.values()],
            edges_traversed=[
                {
                    "source": self.nodes.get(e.source_id, CausalNode("", "?", "?")).name,
                    "target": self.nodes.get(e.target_id, CausalNode("", "?", "?")).name,
                    "relation": e.relation,
                    "weight": e.weight,
                }
                for e in self.edges
            ],
            reasoning_steps=["Graph loaded from database" if self.supabase else "Empty graph"],
        )
