import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from code_intelligence.models import ParsedFile, ParsedSymbol


class TestRelationshipsEngine:
    """Discovers and maps test files and test symbols to target implementation sources."""
    __test__ = False

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def discover_test_mappings(self, parsed_files: List[ParsedFile]) -> List[Dict[str, Any]]:
        mappings: List[Dict[str, Any]] = []
        file_map: Dict[str, ParsedFile] = {pf.path: pf for pf in parsed_files}

        for pf in parsed_files:
            if not self._is_test_file(pf.path):
                continue

            test_file_path = pf.path
            source_candidates: List[str] = []

            # 1. Match by file naming convention
            stem = Path(pf.path).stem
            # strip "test_" or "_test"
            clean_stem = stem
            if clean_stem.startswith("test_"):
                clean_stem = clean_stem[5:]
            elif clean_stem.endswith("_test"):
                clean_stem = clean_stem[:-5]

            for other_path, other_pf in file_map.items():
                if other_path == test_file_path or self._is_test_file(other_path):
                    continue
                other_stem = Path(other_path).stem
                if other_stem == clean_stem or clean_stem.endswith(other_stem):
                    source_candidates.append(other_path)

            # 2. Match by imports within test file
            for imp in pf.imports:
                for other_path, other_pf in file_map.items():
                    if other_path == test_file_path or self._is_test_file(other_path):
                        continue
                    other_stem = Path(other_path).stem
                    if imp.module.endswith(other_stem) or imp.module.split(".")[-1] == other_stem:
                        if other_path not in source_candidates:
                            source_candidates.append(other_path)

            for src in source_candidates:
                # Find symbol-level mappings
                src_pf = file_map.get(src)
                src_symbols = src_pf.symbols if src_pf else []
                symbol_matches = self._match_test_symbols(pf.symbols, src_symbols)

                mappings.append({
                    "test_file": test_file_path,
                    "source_file": src,
                    "confidence": 0.95 if symbol_matches else 0.8,
                    "symbol_mappings": symbol_matches,
                })

        return mappings

    def _is_test_file(self, path: str) -> bool:
        norm = path.replace("\\", "/").lower()
        name = Path(norm).name
        return (
            name.startswith("test_")
            or name.endswith("_test.py")
            or ".test." in name
            or ".spec." in name
            or "/tests/" in norm
            or "/__tests__/" in norm
        )

    def _match_test_symbols(
        self,
        test_symbols: List[ParsedSymbol],
        source_symbols: List[ParsedSymbol],
    ) -> List[Dict[str, str]]:
        matched: List[Dict[str, str]] = []
        for ts in test_symbols:
            t_name = ts.name.lower()
            if not t_name.startswith("test_") and not t_name.startswith("test"):
                continue
            clean_test = t_name.replace("test_", "").replace("test", "")
            for ss in source_symbols:
                s_name = ss.name.lower()
                if s_name == clean_test or s_name in clean_test:
                    matched.append({
                        "test_symbol": ts.name,
                        "source_symbol": ss.name,
                        "source_qualified_name": ss.qualified_name,
                    })
                    break
        return matched
