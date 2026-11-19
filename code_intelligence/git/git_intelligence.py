import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
from mcp.policy import policy_engine


class GitIntelligence:
    """Git-aware repository intelligence analyzing commit history, blame, and change co-occurrence."""

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def get_commit_history(
        self,
        path: Optional[str] = None,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 100))
        cmd = ["git", "log", f"-n{limit}", "--pretty=format:%H%x09%an%x09%ad%x09%s", "--date=short"]
        if path:
            target = policy_engine.validate_workspace_path(str(self.workspace_root), path)
            rel = os.path.relpath(target, str(self.workspace_root))
            cmd.extend(["--", rel])

        try:
            proc = subprocess.run(cmd, cwd=str(self.workspace_root), capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return []
            commits = []
            for line in proc.stdout.splitlines():
                parts = line.split("\t")
                if len(parts) >= 4:
                    commits.append({
                        "commit_hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    })
            return commits
        except Exception:
            return []

    def get_file_blame(
        self,
        path: str,
        start_line: int = 1,
        end_line: int = 100,
    ) -> List[Dict[str, Any]]:
        target = policy_engine.validate_workspace_path(str(self.workspace_root), path)
        if not target.exists() or not target.is_file():
            return []

        rel = os.path.relpath(target, str(self.workspace_root))
        start_line = max(1, start_line)
        end_line = max(start_line, end_line)
        cmd = ["git", "blame", "-L", f"{start_line},{end_line}", "--porcelain", rel]

        try:
            proc = subprocess.run(cmd, cwd=str(self.workspace_root), capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return []

            blame_entries: List[Dict[str, Any]] = []
            current_entry: Dict[str, Any] = {}
            lines = proc.stdout.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i]
                parts = line.split()
                if len(parts) >= 3 and len(parts[0]) == 40:
                    current_entry = {
                        "commit_hash": parts[0],
                        "original_line": int(parts[1]),
                        "final_line": int(parts[2]),
                    }
                    i += 1
                    while i < len(lines) and not lines[i].startswith("\t"):
                        header = lines[i]
                        if header.startswith("author "):
                            current_entry["author"] = header[7:]
                        elif header.startswith("author-time "):
                            current_entry["timestamp"] = int(header[12:])
                        i += 1
                    if i < len(lines) and lines[i].startswith("\t"):
                        current_entry["code"] = lines[i][1:]
                        blame_entries.append(current_entry)
                i += 1

            return blame_entries
        except Exception:
            return []

    def get_change_co_occurrence(
        self,
        path: str,
        limit_commits: int = 50,
    ) -> List[Dict[str, Any]]:
        """Finds other files that frequently change in the same commits as target path."""
        target = policy_engine.validate_workspace_path(str(self.workspace_root), path)
        rel_target = os.path.relpath(target, str(self.workspace_root)).replace("\\", "/")

        cmd = ["git", "log", f"-n{limit_commits}", "--name-only", "--pretty=format:COMMIT:%H", "--", rel_target]
        try:
            proc = subprocess.run(cmd, cwd=str(self.workspace_root), capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return []

            # For each commit where rel_target was changed, fetch all files in that commit
            commit_hashes: List[str] = []
            for line in proc.stdout.splitlines():
                if line.startswith("COMMIT:"):
                    commit_hashes.append(line.replace("COMMIT:", "").strip())

            counter: Counter = Counter()
            for chash in commit_hashes[:25]:
                diff_cmd = ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", chash]
                diff_proc = subprocess.run(diff_cmd, cwd=str(self.workspace_root), capture_output=True, text=True, timeout=5)
                if diff_proc.returncode == 0:
                    for touched_file in diff_proc.stdout.splitlines():
                        touched_file = touched_file.strip().replace("\\", "/")
                        if touched_file and touched_file != rel_target:
                            counter[touched_file] += 1

            total_analyzed = len(commit_hashes)
            results = [
                {
                    "file": f,
                    "co_occurrence_count": count,
                    "confidence": round(count / max(1, total_analyzed), 2),
                    "relationship_type": "HISTORICAL_CO_CHANGE",
                    "note": f"Changed together with '{rel_target}' in {count} commits. Historical correlation only; does not prove structural dependency.",
                }
                for f, count in counter.most_common(10)
            ]
            return results
        except Exception:
            return []
