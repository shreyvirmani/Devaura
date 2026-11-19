from typing import Any, Dict, List, Optional, Set
from code_intelligence.graph.repository_graph import RepositoryGraph
from code_intelligence.models import GraphEdge, GraphNode


class GraphQueryEngine:
    """High-level query engine running over RepositoryGraph."""

    def __init__(self, graph: RepositoryGraph) -> None:
        self.graph = graph

    def get_callers(self, symbol_name: str) -> List[GraphNode]:
        """Finds all symbols that call the specified symbol."""
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
        """Finds all symbols called by the specified symbol."""
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

    def get_blast_radius(self, node_id: str, max_depth: int = 3) -> Dict[str, Any]:
        """Calculates transitive dependents that could break if node_id is modified."""
        affected_files: Set[str] = set()
        affected_symbols: Set[str] = set()
        visited: Set[str] = {node_id}
        frontier: Set[str] = {node_id}

        depth = 0
        while frontier and depth < max_depth:
            next_frontier: Set[str] = set()
            for current in frontier:
                # Inbound edges indicate things that depend on, call, extend, or test current
                inbound = self.graph._reverse_adjacency.get(current, [])
                for edge in inbound:
                    src = edge.source_id
                    if src not in visited:
                        visited.add(src)
                        next_frontier.add(src)
                        node = self.graph.get_node(src)
                        if node:
                            if node.type == "file":
                                affected_files.add(node.label)
                            elif node.type == "symbol":
                                affected_symbols.add(node.metadata.get("qualified_name", node.label))
                                file_label = node.metadata.get("file")
                                if file_label:
                                    affected_files.add(file_label)
            frontier = next_frontier
            depth += 1

        return {
            "root_node": node_id,
            "max_depth": max_depth,
            "affected_files": sorted(list(affected_files)),
            "affected_symbols": sorted(list(affected_symbols)),
            "total_impacted": len(affected_files) + len(affected_symbols),
        }
