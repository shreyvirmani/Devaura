import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from code_intelligence.graph.repository_graph import RepositoryGraph
from code_intelligence.models import (
    GraphEdge,
    GraphNode,
    ParsedCall,
    ParsedFile,
    ParsedImport,
    ParsedSymbol,
    ResolutionStatusEnum,
)
from code_intelligence.tests.test_relationships import TestRelationshipsEngine


class RelationshipBuilder:
    """Builds and resolves semantic relationships across parsed files and symbols with strict provenance."""

    def __init__(self, repository_id: str = "") -> None:
        self.repository_id = repository_id

    def build_graph(self, parsed_files: List[ParsedFile]) -> RepositoryGraph:
        graph = RepositoryGraph(repository_id=self.repository_id)

        # 1. Register File and Symbol Nodes
        file_map: Dict[str, ParsedFile] = {pf.path: pf for pf in parsed_files}
        exact_symbol_map: Dict[str, str] = {}  # f"{pf.path}:{sym.qualified_name}" -> node_id
        file_symbols: Dict[str, Dict[str, ParsedSymbol]] = {}  # file_path -> {name/qualname: sym}

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

            file_symbols[pf.path] = {}
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
                exact_symbol_map[f"{pf.path}:{sym.name}"] = sym_node_id
                file_symbols[pf.path][sym.qualified_name] = sym
                file_symbols[pf.path][sym.name] = sym

        edge_seq = 0

        # 2. Build Structural & Definitional Edges (CONTAINS, DEFINES)
        for pf in parsed_files:
            file_node_id = f"file:{pf.path}"
            for sym in pf.symbols:
                sym_node_id = f"symbol:{pf.path}:{sym.qualified_name}"
                if sym.parent_name:
                    parent_id = exact_symbol_map.get(f"{pf.path}:{sym.parent_name}")
                    if parent_id:
                        edge_seq += 1
                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{edge_seq}",
                                source_id=parent_id,
                                target_id=sym_node_id,
                                type="DEFINES",
                                confidence=1.0,
                                resolution_status=ResolutionStatusEnum.RESOLVED.value,
                                evidence=f"Class '{sym.parent_name}' defines member '{sym.name}'",
                                source_location={"file": pf.path, "line": sym.start_line},
                            )
                        )
                else:
                    edge_seq += 1
                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:{edge_seq}",
                            source_id=file_node_id,
                            target_id=sym_node_id,
                            type="CONTAINS",
                            confidence=1.0,
                            resolution_status=ResolutionStatusEnum.RESOLVED.value,
                            evidence=f"File contains top-level declaration '{sym.name}'",
                            source_location={"file": pf.path, "line": sym.start_line},
                        )
                    )

                # EXTENDS edges (Class inheritance)
                for base in sym.extends:
                    edge_seq += 1
                    target_id, res_status, conf, ev = self._resolve_base_class(base, pf, file_map, exact_symbol_map)
                    if not target_id.startswith("external:") and target_id not in graph.nodes:
                        ext_id = f"external:{base}"
                        if ext_id not in graph.nodes:
                            graph.add_node(GraphNode(id=ext_id, type="external", label=base))
                        target_id = ext_id

                    graph.add_edge(
                        GraphEdge(
                            id=f"edge:{edge_seq}",
                            source_id=sym_node_id,
                            target_id=target_id,
                            type="EXTENDS",
                            confidence=conf,
                            resolution_status=res_status,
                            evidence=ev,
                            source_location={"file": pf.path, "line": sym.start_line},
                        )
                    )

                # CALLS edges
                for call_item in sym.calls:
                    call_name = call_item.name if isinstance(call_item, ParsedCall) else str(call_item)
                    call_line = call_item.line_number if isinstance(call_item, ParsedCall) else sym.start_line

                    target_id, res_status, conf, ev = self._resolve_call(
                        call_name=call_name,
                        caller_sym=sym,
                        caller_file=pf,
                        file_map=file_map,
                        file_symbols=file_symbols,
                        exact_symbol_map=exact_symbol_map,
                    )

                    if target_id:
                        edge_seq += 1
                        if target_id not in graph.nodes and (target_id.startswith("external:") or target_id.startswith("unresolved:")):
                            graph.add_node(GraphNode(id=target_id, type=target_id.split(":")[0], label=call_name))

                        graph.add_edge(
                            GraphEdge(
                                id=f"edge:{edge_seq}",
                                source_id=sym_node_id,
                                target_id=target_id,
                                type="CALLS",
                                confidence=conf,
                                resolution_status=res_status,
                                evidence=ev,
                                source_location={"file": pf.path, "line": call_line},
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
                            resolution_status=ResolutionStatusEnum.RESOLVED.value,
                            evidence=f"Internal import '{imp.module}'" + (f" as '{imp.alias}'" if imp.alias else ""),
                            source_location={"file": pf.path, "line": imp.line_number},
                            metadata={"symbol": imp.symbol_name, "module": imp.module, "alias": imp.alias},
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
                            confidence=1.0 if imp.is_external else 0.5,
                            resolution_status=ResolutionStatusEnum.RESOLVED.value if imp.is_external else ResolutionStatusEnum.UNRESOLVED.value,
                            evidence=f"External import '{imp.module}'" if imp.is_external else f"Unresolved import '{imp.module}'",
                            source_location={"file": pf.path, "line": imp.line_number},
                            metadata={"symbol": imp.symbol_name, "module": imp.module, "external": imp.is_external, "alias": imp.alias},
                        )
                    )

        # 4. Build Test Edges (TESTS)
        test_engine = TestRelationshipsEngine()
        mappings = test_engine.discover_test_mappings(parsed_files)
        for m in mappings:
            test_file_id = f"file:{m['test_file']}"
            source_file_id = f"file:{m['source_file']}"
            edge_seq += 1
            graph.add_edge(
                GraphEdge(
                    id=f"edge:{edge_seq}",
                    source_id=test_file_id,
                    target_id=source_file_id,
                    type="TESTS",
                    confidence=m["confidence"],
                    resolution_status=ResolutionStatusEnum.RESOLVED.value if m["confidence"] >= 0.8 else ResolutionStatusEnum.PARTIALLY_RESOLVED.value,
                    evidence=m.get("evidence", "Test relationship"),
                    source_location={"file": m["test_file"], "line": 1},
                    metadata={"symbol_mappings": m.get("symbol_mappings", [])},
                )
            )

        return graph

    def _resolve_base_class(
        self,
        base_name: str,
        current_file: ParsedFile,
        file_map: Dict[str, ParsedFile],
        exact_symbol_map: Dict[str, str],
    ) -> Tuple[str, str, float, str]:
        """Resolves base class for inheritance without cross-module false positives."""
        # 1. Local symbol in same file
        local_key = f"{current_file.path}:{base_name}"
        if local_key in exact_symbol_map:
            return exact_symbol_map[local_key], ResolutionStatusEnum.RESOLVED.value, 1.0, f"Inherits local class '{base_name}'"

        # 2. Check if imported in current file
        for imp in current_file.imports:
            if imp.alias == base_name or imp.symbol_name == base_name:
                orig_name = imp.symbol_name or base_name
                target_file_id = self._resolve_import_to_file(imp.module, current_file.path, file_map)
                if target_file_id:
                    target_path = target_file_id.replace("file:", "")
                    target_sym_key = f"{target_path}:{orig_name}"
                    if target_sym_key in exact_symbol_map:
                        return (
                            exact_symbol_map[target_sym_key],
                            ResolutionStatusEnum.RESOLVED.value,
                            1.0,
                            f"Inherits imported class '{orig_name}' from '{imp.module}'",
                        )

        # 3. Known stdlib / external bases
        if base_name in {"Exception", "BaseModel", "object", "ABC", "TestCase", "BaseService"}:
            return f"external:{base_name}", ResolutionStatusEnum.RESOLVED.value, 0.9, f"Inherits standard/external class '{base_name}'"

        # 4. Unresolved
        return f"external:{base_name}", ResolutionStatusEnum.PARTIALLY_RESOLVED.value, 0.6, f"Inherits external/unresolved base class '{base_name}'"

    def _resolve_call(
        self,
        call_name: str,
        caller_sym: ParsedSymbol,
        caller_file: ParsedFile,
        file_map: Dict[str, ParsedFile],
        file_symbols: Dict[str, Dict[str, ParsedSymbol]],
        exact_symbol_map: Dict[str, str],
    ) -> Tuple[Optional[str], str, float, str]:
        """Strict lexical & import-scoped call resolution to eliminate false-positive cross-module matches."""
        clean_call = call_name.replace("self.", "")

        # 1. Intra-class method call
        if caller_sym.parent_name:
            method_key = f"{caller_file.path}:{caller_sym.parent_name}.{clean_call}"
            if method_key in exact_symbol_map:
                return (
                    exact_symbol_map[method_key],
                    ResolutionStatusEnum.RESOLVED.value,
                    0.98,
                    f"Direct intra-class method call to '{caller_sym.parent_name}.{clean_call}'",
                )

            # Check inherited class methods
            for base in caller_sym.extends:
                # Find base class symbol
                base_target_id, _, _, _ = self._resolve_base_class(base, caller_file, file_map, exact_symbol_map)
                if base_target_id and base_target_id.startswith("symbol:"):
                    parts = base_target_id.split(":")
                    b_file = parts[1]
                    b_qual = parts[2]
                    b_method_key = f"{b_file}:{b_qual}.{clean_call}"
                    if b_method_key in exact_symbol_map:
                        return (
                            exact_symbol_map[b_method_key],
                            ResolutionStatusEnum.RESOLVED.value,
                            0.95,
                            f"Inherited method call '{clean_call}' from base class '{base}'",
                        )

        # 2. Intra-file function/class call
        intra_key = f"{caller_file.path}:{clean_call}"
        if intra_key in exact_symbol_map:
            return (
                exact_symbol_map[intra_key],
                ResolutionStatusEnum.RESOLVED.value,
                0.95,
                f"Intra-file direct call to '{clean_call}'",
            )

        # 3. Check explicit imports in caller_file (direct or aliased)
        for imp in caller_file.imports:
            # Case 3a: Aliased import: `from app.database import get_user as fetch_db_user`
            if imp.alias and imp.alias == clean_call:
                target_file_id = self._resolve_import_to_file(imp.module, caller_file.path, file_map)
                if target_file_id:
                    target_path = target_file_id.replace("file:", "")
                    orig_sym = imp.symbol_name or clean_call
                    target_key = f"{target_path}:{orig_sym}"
                    if target_key in exact_symbol_map:
                        return (
                            exact_symbol_map[target_key],
                            ResolutionStatusEnum.RESOLVED.value,
                            0.95,
                            f"Imported function call via alias '{imp.alias}' -> '{orig_sym}' in '{imp.module}'",
                        )
                elif imp.is_external:
                    return (
                        f"module:{imp.module}",
                        ResolutionStatusEnum.RESOLVED.value,
                        0.90,
                        f"External call via alias '{imp.alias}' to '{imp.module}'",
                    )

            # Case 3b: Direct symbol import: `from app.database import get_user`
            if imp.symbol_name and imp.symbol_name == clean_call:
                target_file_id = self._resolve_import_to_file(imp.module, caller_file.path, file_map)
                if target_file_id:
                    target_path = target_file_id.replace("file:", "")
                    target_key = f"{target_path}:{clean_call}"
                    if target_key in exact_symbol_map:
                        return (
                            exact_symbol_map[target_key],
                            ResolutionStatusEnum.RESOLVED.value,
                            0.95,
                            f"Imported function call '{clean_call}' from '{imp.module}'",
                        )
                elif imp.is_external:
                    return (
                        f"module:{imp.module}",
                        ResolutionStatusEnum.RESOLVED.value,
                        0.90,
                        f"External library call to '{imp.module}.{clean_call}'",
                    )

            # Case 3c: Module-qualified call: `import app.database; app.database.get_user()` or `database.get_user()`
            if "." in clean_call:
                mod_prefix = clean_call.split(".")[0]
                func_name = clean_call.split(".")[-1]
                if imp.module.endswith(mod_prefix) or imp.alias == mod_prefix or imp.module == mod_prefix:
                    target_file_id = self._resolve_import_to_file(imp.module, caller_file.path, file_map)
                    if target_file_id:
                        target_path = target_file_id.replace("file:", "")
                        target_key = f"{target_path}:{func_name}"
                        if target_key in exact_symbol_map:
                            return (
                                exact_symbol_map[target_key],
                                ResolutionStatusEnum.RESOLVED.value,
                                0.95,
                                f"Module-qualified call '{clean_call}' via '{imp.module}'",
                            )
                    elif imp.is_external:
                        return (
                            f"module:{imp.module}",
                            ResolutionStatusEnum.RESOLVED.value,
                            0.90,
                            f"External library call to '{imp.module}.{func_name}'",
                        )

        # 4. Standard library or external calls without explicit local imports
        parts = clean_call.split(".")
        if len(parts) > 1 and parts[0] in {"math", "os", "sys", "json", "re", "hashlib", "time", "subprocess", "axios", "console"}:
            return (
                f"module:{parts[0]}",
                ResolutionStatusEnum.RESOLVED.value,
                0.90,
                f"Standard library / runtime call '{clean_call}'",
            )

        # 5. UNRESOLVED call: NOT defined in file, NOT imported, NOT a base class method!
        # Do NOT link to arbitrary files that define same-named function!
        return (
            f"unresolved:{clean_call}",
            ResolutionStatusEnum.UNRESOLVED.value,
            0.25,
            f"Unresolved call: symbol '{clean_call}' is neither defined nor imported in '{caller_file.path}'",
        )

    def _resolve_import_to_file(
        self,
        module: str,
        current_file: str,
        file_map: Dict[str, ParsedFile],
    ) -> Optional[str]:
        """Resolves module path to an existing repo file node ID."""
        # 1. Direct path check: `app.database` -> `app/database.py`
        rel_candidate = module.replace(".", "/") + ".py"
        if rel_candidate in file_map:
            return f"file:{rel_candidate}"

        # 2. Relative import resolution: `from .models import User`
        curr_dir = str(Path(current_file).parent).replace("\\", "/")
        if curr_dir == ".":
            curr_dir = ""

        if module.startswith("."):
            clean_mod = module.lstrip(".").replace(".", "/")
            candidate = f"{curr_dir}/{clean_mod}.py" if curr_dir else f"{clean_mod}.py"
            candidate = candidate.lstrip("/")
            if candidate in file_map:
                return f"file:{candidate}"

        # 3. Traversal matching: e.g. `app.database` where files are `tests/fixtures/validation_repo/app/database.py`
        normalized_mod = module.replace(".", "/")
        for f_path in file_map:
            norm_f = f_path.replace("\\", "/")
            if norm_f.endswith(f"{normalized_mod}.py") or norm_f.endswith(f"{normalized_mod}.js") or norm_f.endswith(f"{normalized_mod}.ts"):
                return f"file:{f_path}"

        # 4. JS relative import resolution (e.g. `./config.js`, `./api.js`)
        if module.startswith("./") or module.startswith("../"):
            norm_mod = module.lstrip("./").lstrip("../")
            for f_path in file_map:
                if f_path.endswith(norm_mod) or f_path.endswith(f"{norm_mod}.js") or f_path.endswith(f"{norm_mod}.ts"):
                    return f"file:{f_path}"

        return None
