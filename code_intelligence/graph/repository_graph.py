from collections import defaultdict, deque
from typing import Dict, List, Optional, Set
from code_intelligence.models import GraphEdge, GraphNode, RepositoryGraphData


class RepositoryGraph:
    """In-memory Directed Acyclic/Cyclic Multigraph representing code dependencies and symbols."""

    def __init__(self, repository_id: str = "") -> None:
        self.repository_id = repository_id
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self._adjacency: Dict[str, List[GraphEdge]] = defaultdict(list)
        self._reverse_adjacency: Dict[str, List[GraphEdge]] = defaultdict(list)

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        self.edges.append(edge)
        self._adjacency[edge.source_id].append(edge)
        self._reverse_adjacency[edge.target_id].append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        return self.nodes.get(node_id)

    def get_outbound_edges(self, source_id: str, edge_type: Optional[str] = None) -> List[GraphEdge]:
        edges = self._adjacency.get(source_id, [])
        if edge_type:
            return [e for e in edges if e.type == edge_type]
        return edges

    def get_inbound_edges(self, target_id: str, edge_type: Optional[str] = None) -> List[GraphEdge]:
        edges = self._reverse_adjacency.get(target_id, [])
        if edge_type:
            return [e for e in edges if e.type == edge_type]
        return edges

    def get_dependencies(self, node_id: str) -> List[str]:
        """Returns direct dependencies (targets of outbound IMPORTS, EXTENDS, CALLS edges)."""
        valid_types = {"IMPORTS", "EXTENDS", "CALLS"}
        return [e.target_id for e in self._adjacency.get(node_id, []) if e.type in valid_types]

    def get_dependents(self, node_id: str) -> List[str]:
        """Returns direct dependents (sources of inbound IMPORTS, EXTENDS, CALLS edges)."""
        valid_types = {"IMPORTS", "EXTENDS", "CALLS"}
        return [e.source_id for e in self._reverse_adjacency.get(node_id, []) if e.type in valid_types]

    def find_path(self, start_id: str, target_id: str, max_depth: int = 5) -> Optional[List[str]]:
        """Finds shortest path between two nodes using Breadth-First Search (BFS)."""
        if start_id not in self.nodes or target_id not in self.nodes:
            return None
        if start_id == target_id:
            return [start_id]

        queue = deque([(start_id, [start_id])])
        visited: Set[str] = {start_id}

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth:
                continue

            for edge in self._adjacency.get(current, []):
                neighbor = edge.target_id
                if neighbor == target_id:
                    return path + [neighbor]
                if neighbor not in visited and neighbor in self.nodes:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def to_graph_data(self) -> RepositoryGraphData:
        """Serializes to API-ready RepositoryGraphData schema."""
        stats = {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "files": sum(1 for n in self.nodes.values() if n.type == "file"),
            "symbols": sum(1 for n in self.nodes.values() if n.type == "symbol"),
            "imports": sum(1 for e in self.edges if e.type == "IMPORTS"),
            "calls": sum(1 for e in self.edges if e.type == "CALLS"),
            "extends": sum(1 for e in self.edges if e.type == "EXTENDS"),
            "tests": sum(1 for e in self.edges if e.type == "TESTS"),
        }
        return RepositoryGraphData(
            repository_id=self.repository_id,
            nodes=list(self.nodes.values()),
            edges=self.edges,
            stats=stats,
        )
