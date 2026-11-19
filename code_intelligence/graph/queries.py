from typing import Any, Dict, List, Optional, Set
from code_intelligence.graph.repository_graph import RepositoryGraph
from code_intelligence.models import GraphEdge, GraphNode


class GraphQueryEngine:
    """High-level query engine running over RepositoryGraph with bounded traversals and provenance."""

    def __init__(self, graph: RepositoryGraph) -> None:
        self.graph = graph

    def get_callers(self, symbol_name: str) -> List[GraphNode]:
        """Finds all symbols that call the specified symbol.
        
        Semantics: A CALLS B -> Caller of B is A.
        """
        matching_targets = [
            n for n in self.graph.nodes.values()
            if n.type == "symbol" and (n.label == symbol_name or n.metadata.get("qualified_name") == symbol_name)
        ]
        caller_nodes: List[GraphNode] = []
        for target in matching_targets:
            inbound = self.graph.get_inbound_edges(target.id, edge_type="CALLS")
            for edge in inbound:
                caller = self.graph.get_node(edge.source_id)
                if caller and caller not in caller_nodes:
                    caller_nodes.append(caller)
        return caller_nodes

    def get_callees(self, symbol_name: str) -> List[GraphNode]:
        """Finds all symbols called by the specified symbol.
        
        Semantics: A CALLS B -> Callee of A is B.
        """
        matching_sources = [
            n for n in self.graph.nodes.values()
            if n.type == "symbol" and (n.label == symbol_name or n.metadata.get("qualified_name") == symbol_name)
        ]
        callee_nodes: List[GraphNode] = []
        for src in matching_sources:
            outbound = self.graph.get_outbound_edges(src.id, edge_type="CALLS")
            for edge in outbound:
                callee = self.graph.get_node(edge.target_id)
                if callee and callee not in callee_nodes:
                    callee_nodes.append(callee)
        return callee_nodes

    def get_file_dependencies(self, file_path: str) -> List[str]:
        """Finds all internal files or external modules directly imported by file_path."""
        file_id = f"file:{file_path}"
        edges = self.graph.get_outbound_edges(file_id, edge_type="IMPORTS")
        return [e.target_id.replace("file:", "").replace("module:", "") for e in edges]

    def get_file_dependents(self, file_path: str) -> List[str]:
        """Finds all files that import file_path."""
        file_id = f"file:{file_path}"
        edges = self.graph.get_inbound_edges(file_id, edge_type="IMPORTS")
        return [e.source_id.replace("file:", "") for e in edges]

    def get_blast_radius(
        self,
        node_id: str,
        max_depth: int = 3,
        max_nodes: int = 100,
    ) -> Dict[str, Any]:
        """Calculates bounded blast radius of files, callers, and tests affected if node_id is modified."""
        max_depth = max(1, min(max_depth, 10))
        max_nodes = max(10, min(max_nodes, 500))

        # Normalize prefix if needed
        target_node = self.graph.get_node(node_id)
        if not target_node:
            for n in self.graph.nodes.values():
                if n.label == node_id or n.metadata.get("qualified_name") == node_id or n.metadata.get("file") == node_id:
                    target_node = n
                    node_id = n.id
                    break

        impacted_items: List[Dict[str, Any]] = []
        affected_files: Set[str] = set()
        affected_symbols: Set[str] = set()
        direct_callers: List[str] = []
        direct_callees: List[str] = []
        tests: List[str] = []

        # 1. Direct callees (outbound CALLS)
        for e in self.graph.get_outbound_edges(node_id, edge_type="CALLS"):
            callee_node = self.graph.get_node(e.target_id)
            if callee_node:
                direct_callees.append(callee_node.label)
                impacted_items.append({
                    "node": callee_node.label,
                    "type": callee_node.type,
                    "distance": 1,
                    "reason": f"CALLED_BY: {e.evidence or 'direct call'}",
                    "confidence": e.confidence,
                })

        # 2. Inbound traversal (dependents, callers, subclasses, tests)
        visited: Set[str] = {node_id}
        frontier: Set[str] = {node_id}
        depth = 0

        while frontier and depth < max_depth and len(visited) < max_nodes:
            depth += 1
            next_frontier: Set[str] = set()

            for curr in frontier:
                inbound_edges = self.graph._reverse_adjacency.get(curr, [])
                for edge in inbound_edges:
                    src = edge.source_id
                    if src not in visited and len(visited) < max_nodes:
                        visited.add(src)
                        next_frontier.add(src)
                        src_node = self.graph.get_node(src)
                        if src_node:
                            # Record reasons
                            reason_str = f"{edge.type}: {edge.evidence or 'graph dependency'}"
                            impacted_items.append({
                                "node": src_node.label,
                                "type": src_node.type,
                                "distance": depth,
                                "reason": reason_str,
                                "confidence": edge.confidence,
                            })

                            if edge.type == "CALLS" and depth == 1:
                                direct_callers.append(src_node.label)
                            if edge.type == "TESTS" or src_node.label.startswith("test_") or "test" in src_node.metadata.get("file", ""):
                                tests.append(src_node.metadata.get("file", src_node.label))

                            if src_node.type == "file":
                                affected_files.add(src_node.label)
                            elif src_node.type == "symbol":
                                affected_symbols.add(src_node.metadata.get("qualified_name", src_node.label))
                                f_lbl = src_node.metadata.get("file")
                                if f_lbl:
                                    affected_files.add(f_lbl)

            frontier = next_frontier

        return {
            "root_node": node_id,
            "max_depth": max_depth,
            "total_impacted": len(impacted_items),
            "direct_callers": sorted(list(set(direct_callers))),
            "direct_callees": sorted(list(set(direct_callees))),
            "tests": sorted(list(set(tests))),
            "affected_files": sorted(list(affected_files)),
            "affected_symbols": sorted(list(affected_symbols)),
            "impacted": impacted_items[:max_nodes],
        }
