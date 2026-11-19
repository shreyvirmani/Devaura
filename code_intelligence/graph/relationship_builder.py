import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from code_intelligence.graph.repository_graph import RepositoryGraph
from code_intelligence.models import GraphEdge, GraphNode, ParsedFile


class RelationshipBuilder:
    """Builds and resolves semantic relationships across parsed files and symbols."""

    def __init__(self, repository_id: str = "") -> None:
        self.repository_id = repository_id

    def build_graph(self, parsed_files: List[ParsedFile]) -> RepositoryGraph:
        graph = RepositoryGraph(repository_id=self.repository_id)

        # 1. Register File and Symbol Nodes
        file_map: Dict[str, ParsedFile] = {pf.path: pf for pf in parsed_files}
        symbol_map: Dict[str, str] = {}  # qualname / short_name -> node_id
        exact_symbol_map: Dict[str, str] = {}  # f"{pf.path}:{sym.qualified_name}" -> node_id

        for pf in parsed_files:
            file_node_id = f"file:{pf.path}"
            graph.add_node(
                GraphNode(
                    id=file_node_id,
                    type="file",
                    label=pf.path,
                    metadata={"language": pf.language, "lines": pf.line_count, "size": pf.size_bytes},
                )
            )

            for sym in pf.symbols:
                sym_node_id = f"symbol:{pf.path}:{sym.qualified_name}"
                graph.add_node(
                    GraphNode(
                        id=sym_node_id,
                        type="symbol",
                        label=sym.name,
                        metadata={
                            "file": pf.path,
                            "qualified_name": sym.qualified_name,
                            "kind": sym.kind.value,
                            "signature": sym.signature,
                            "start_line": sym.start_line,
                            "end_line": sym.end_line,
                        },
                    )
                )
                exact_symbol_map[f"{pf.path}:{sym.qualified_name}"] = sym_node_id
                symbol_map[sym.qualified_name] = sym_node_id
                if sym.name not in symbol_map:
                    symbol_map[sym.name] = sym_node_id

        # 2. Build Structural & Definitional Edges (CONTAINS, DEFINES)
        edge_seq = 0
        for pf in parsed_files:
            file_node_id = f"file:{pf.path}"
            for sym in pf.symbols:
                sym_node_id = f"symbol:{pf.path}:{sym.qualified_name}"
                if sym.parent_name:
                    # DEFINES edge from parent class to method/nested symbol
                    parent_id = exact_symbol_map.get(f"{pf.path}:{sym.parent_name}") or symbol_map.get(sym.parent_name)
                    if parent_id:
                        edge_seq += 1
                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{edge_seq}",
                                source_id=parent_id,
                                target_id=sym_node_id,
                                type="DEFINES",
                                confidence=1.0,
                                resolution_status="RESOLVED",
                            )
                        )
                else:
                    # CONTAINS edge from file to top-level symbol
                    edge_seq += 1
                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:{edge_seq}",
                            source_id=file_node_id,
                            target_id=sym_node_id,
                            type="CONTAINS",
                            confidence=1.0,
                            resolution_status="RESOLVED",
                        )
                    )

                # EXTENDS edges
                for base in sym.extends:
                    target_sym_id = symbol_map.get(base)
                    edge_seq += 1
                    if target_sym_id:
                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{edge_seq}",
                                source_id=sym_node_id,
                                target_id=target_sym_id,
                                type="EXTENDS",
                                confidence=1.0,
                                resolution_status="RESOLVED",
                            )
                        )
                    else:
                        ext_id = f"external:{base}"
                        if ext_id not in graph.nodes:
                            graph.add_node(GraphNode(id=ext_id, type="external", label=base))
                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{edge_seq}",
                                source_id=sym_node_id,
                                target_id=ext_id,
                                type="EXTENDS",
                                confidence=0.7,
                                resolution_status="PARTIAL",
                            )
                        )

                # CALLS edges
                for called_name in sym.calls:
                    target_id = None
                    # First check intra-class self.method or method in same file
                    clean_called = called_name.replace("self.", "")
                    local_key = f"{pf.path}:{clean_called}"
                    if local_key in exact_symbol_map:
                        target_id = exact_symbol_map[local_key]
                    elif clean_called in symbol_map:
                        target_id = symbol_map[clean_called]

                    if target_id:
                        edge_seq += 1
                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{edge_seq}",
                                source_id=sym_node_id,
                                target_id=target_id,
                                type="CALLS",
                                confidence=0.85,
                                resolution_status="RESOLVED",
                            )
                        )

            # 3. Build Import Edges (IMPORTS)
            for imp in pf.imports:
                target_file_id = self._resolve_import_to_file(imp.module, pf.path, file_map)
                edge_seq += 1
                if target_file_id:
                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:{edge_seq}",
                            source_id=file_node_id,
                            target_id=target_file_id,
                            type="IMPORTS",
                            confidence=1.0,
                            resolution_status="RESOLVED",
                            metadata={"symbol": imp.symbol_name, "module": imp.module},
                        )
                    )
                else:
                    ext_id = f"module:{imp.module}"
                    if ext_id not in graph.nodes:
                        graph.add_node(GraphNode(id=ext_id, type="module", label=imp.module))
                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:{edge_seq}",
                            source_id=file_node_id,
                            target_id=ext_id,
                            type="IMPORTS",
                            confidence=1.0 if imp.is_external else 0.6,
                            resolution_status="RESOLVED" if imp.is_external else "UNRESOLVED",
                            metadata={"symbol": imp.symbol_name, "module": imp.module, "external": imp.is_external},
                        )
                    )

        # 4. Build Test Edges (TESTS)
        self._build_test_edges(graph, parsed_files, edge_seq)

        return graph

    def _resolve_import_to_file(
        self,
        module: str,
        current_file: str,
        file_map: Dict[str, ParsedFile],
    ) -> Optional[str]:
        """Resolves module path to an existing repo file node ID."""
        # Convert dotted module to path (e.g., calculator.core -> calculator/core.py)
        rel_candidate = module.replace(".", "/") + ".py"
        if rel_candidate in file_map:
            return f"file:{rel_candidate}"

        # Relative import resolution
        curr_dir = str(Path(current_file).parent).replace("\\", "/")
        if curr_dir == ".":
            curr_dir = ""

        if module.startswith("."):
            clean_mod = module.lstrip(".").replace(".", "/")
            candidate = f"{curr_dir}/{clean_mod}.py" if curr_dir else f"{clean_mod}.py"
            candidate = candidate.lstrip("/")
            if candidate in file_map:
                return f"file:{candidate}"

        # Check for matching stem in file_map
        mod_stem = module.split(".")[-1]
        for f_path in file_map:
            if Path(f_path).stem == mod_stem:
                return f"file:{f_path}"

        return None

    def _build_test_edges(
        self,
        graph: RepositoryGraph,
        parsed_files: List[ParsedFile],
        start_seq: int,
    ) -> None:
        """Connects test files and test functions to their target sources."""
        seq = start_seq
        for pf in parsed_files:
            file_name = Path(pf.path).name
            if file_name.startswith("test_") or file_name.endswith("_test.py") or ".test." in file_name or ".spec." in file_name:
                test_file_id = f"file:{pf.path}"
                # Derive target source file stem
                target_stem = file_name.replace("test_", "").replace("_test.py", "").replace(".test.ts", "").replace(".test.js", "")
                if target_stem.endswith(".py"):
                    target_stem = target_stem[:-3]

                for other_pf in parsed_files:
                    if other_pf.path == pf.path:
                        continue
                    if Path(other_pf.path).stem == target_stem:
                        source_file_id = f"file:{other_pf.path}"
                        seq += 1
                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{seq}",
                                source_id=test_file_id,
                                target_id=source_file_id,
                                type="TESTS",
                                confidence=0.95,
                                resolution_status="RESOLVED",
                            )
                        )
