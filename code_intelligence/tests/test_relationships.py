import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from code_intelligence.models import ParsedFile, ParsedSymbol


class TestRelationshipsEngine:
    """Discovers and maps test files and test symbols to target implementation sources with provenance."""
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
            stem = Path(pf.path).stem
            clean_stem = stem
            if clean_stem.startswith("test_"):
                clean_stem = clean_stem[5:]
            elif clean_stem.endswith("_test"):
                clean_stem = clean_stem[:-5]

            # Candidate evaluation per source file
            for other_path, other_pf in file_map.items():
                if other_path == test_file_path or self._is_test_file(other_path):
                    continue

                evidence_tags: List[str] = []
                other_stem = Path(other_path).stem

                # Check 1: Import evidence
                has_import = False
                for imp in pf.imports:
                    mod = imp.module
                    if (
                        mod == other_stem
                        or mod.endswith(f".{other_stem}")
                        or mod.replace(".", "/") in other_path
                        or other_stem in mod.split(".")
                    ):
                        has_import = True
                        break
                if has_import:
                    evidence_tags.append("IMPORT")

                # Check 2: Symbol matching & direct calls in test functions
                src_symbols = other_pf.symbols
                symbol_matches = self._match_test_symbols(pf.symbols, src_symbols)
                has_direct_call = False

                src_symbol_names = {s.name for s in src_symbols}
                for ts in pf.symbols:
                    for call in ts.calls:
                        c_name = call.name.split(".")[-1]
                        if c_name in src_symbol_names:
                            has_direct_call = True
                            break

                if has_direct_call:
                    evidence_tags.append("DIRECT_CALL")
                elif symbol_matches:
                    evidence_tags.append("SYMBOL_REFERENCE")

                # Check 3: Name / Path heuristics
                has_name_match = (other_stem == clean_stem or clean_stem.endswith(other_stem))
                if has_name_match:
                    evidence_tags.append("NAME_MATCH")

                # Compute calibrated confidence
                if not evidence_tags:
                    continue

                confidence = 0.50
                if "IMPORT" in evidence_tags and "DIRECT_CALL" in evidence_tags:
                    confidence = 0.98
                elif "IMPORT" in evidence_tags and "SYMBOL_REFERENCE" in evidence_tags:
                    confidence = 0.95
                elif "IMPORT" in evidence_tags:
                    confidence = 0.82
                elif "DIRECT_CALL" in evidence_tags or "SYMBOL_REFERENCE" in evidence_tags:
                    confidence = 0.75
                elif "NAME_MATCH" in evidence_tags:
                    confidence = 0.55

                evidence_str = " + ".join(evidence_tags)

                mappings.append({
                    "test_file": test_file_path,
                    "source_file": other_path,
                    "confidence": confidence,
                    "evidence": evidence_str,
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
