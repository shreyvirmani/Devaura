"""
Devaura Multi-Tier Ablation Study Runner (Phase 10).

Delegates to AblationFramework to run the multi-tier causal ablation matrix:
A (Raw LLM) -> B (Code Intel) -> C (Planning) -> D (Validation) -> E (Sandbox) -> F (Full Loop).
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.ablation.framework import AblationFramework


class AblationRunner:
    """Orchestrates comparative ablation experiments on real reproducible defects."""

    def __init__(self, results_dir: Optional[Path] = None):
        self.framework = AblationFramework(results_dir=results_dir)

    def run_all(
        self,
        target_bug_ids: List[str] = ["HIST-012", "HIST-013", "HIST-017"],
        tiers: List[str] = ["A", "B", "C", "D", "E", "F"],
    ) -> Dict[str, Any]:
        """Execute the multi-tier causal ablation matrix across representative defects."""
        return self.framework.run_matrix(target_bug_ids=target_bug_ids, tiers=tiers)


def main():
    runner = AblationRunner()
    runner.run_all()


if __name__ == "__main__":
    main()
