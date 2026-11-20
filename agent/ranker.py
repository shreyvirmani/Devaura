"""Evidence Ranking & Change Locality Scoring Layer.

Calculates deterministic change-locality scores and ranks collected evidence
prior to root-cause candidate synthesis.

Scoring Formula (Locality Score):
--------------------------------
LocalityScore(item) =
    w_sym  * touches_failing_symbol   (default 0.35)
  + w_file * touches_failing_file     (default 0.25)
  + w_rec  * recency_decay(commit)    (default 0.20)
  + w_dep  * on_dependency_path       (default 0.10)
  + w_test * matches_failing_test     (default 0.10)

Evidence Ranking Formula:
-------------------------
PriorityBase:
  DIRECT_STACK_FRAME          = 1.00
  DIRECT_FAILED_TEST          = 0.90
  RESOLVED_CALL_RELATIONSHIP  = 0.80
  RECENT_DIRECT_CODE_CHANGE   = 0.75
  IMPORT_RELATIONSHIP         = 0.65
  HEURISTIC_TEST_MATCH        = 0.50
  GIT_CO_CHANGE               = 0.35
  UNRESOLVED_CALL_RELATIONSHIP= 0.25
  GENERIC_LOG                 = 0.15

Relevance(evidence) = PriorityBase * (0.6 * confidence + 0.4 * locality_score)
"""

from typing import Any, Dict, List, Optional, Set
from agent.models import EvidenceSource, EvidenceType, NormalizedEvidence, ResolutionStatus


class EvidenceRankerConfig:
    """Configurable weights for change locality and evidence ranking."""

    def __init__(
        self,
        weight_symbol: float = 0.35,
        weight_file: float = 0.25,
        weight_recency: float = 0.20,
        weight_dependency: float = 0.10,
        weight_test: float = 0.10,
    ):
        self.weight_symbol = weight_symbol
        self.weight_file = weight_file
        self.weight_recency = weight_recency
        self.weight_dependency = weight_dependency
        self.weight_test = weight_test


class EvidenceRanker:
    """Ranks normalized evidence items deterministically."""

    # Priority base lookup by evidence type and characteristics
    PRIORITY_TIERS: Dict[str, float] = {
        "DIRECT_STACK_FRAME": 1.00,
        "DIRECT_FAILED_TEST": 0.90,
        "RESOLVED_CALL_RELATIONSHIP": 0.80,
        "RECENT_DIRECT_CODE_CHANGE": 0.75,
        "IMPORT_RELATIONSHIP": 0.65,
        "HEURISTIC_TEST_MATCH": 0.50,
        "GIT_CO_CHANGE": 0.35,
        "UNRESOLVED_CALL_RELATIONSHIP": 0.25,
        "GENERIC_LOG": 0.15,
    }

    def __init__(self, config: Optional[EvidenceRankerConfig] = None):
        self.config = config or EvidenceRankerConfig()

    def compute_locality_score(
        self,
        evidence: NormalizedEvidence,
        failing_file: Optional[str] = None,
        failing_symbol: Optional[str] = None,
        dependency_files: Optional[Set[str]] = None,
        failed_test_files: Optional[Set[str]] = None,
    ) -> float:
        """Compute the deterministic change-locality score for an evidence item."""
        dependency_files = dependency_files or set()
        failed_test_files = failed_test_files or set()

        score = 0.0

        # 1. Same Symbol check
        if failing_symbol and evidence.symbol_id and failing_symbol in evidence.symbol_id:
            score += self.config.weight_symbol

        # 2. Same File check
        if failing_file and evidence.repository_path:
            norm_failing = failing_file.replace("\\", "/").lstrip("/")
            norm_ev_path = evidence.repository_path.replace("\\", "/").lstrip("/")
            if norm_failing == norm_ev_path or norm_failing in norm_ev_path or norm_ev_path in norm_failing:
                score += self.config.weight_file

        # 3. Recency decay check (from metadata or commit_sha)
        commit_distance = evidence.metadata.get("commit_distance", 0)
        if evidence.commit_sha or evidence.source == EvidenceSource.GIT:
            recency_factor = 1.0 / (1.0 + float(commit_distance))
            score += self.config.weight_recency * recency_factor

        # 4. On Dependency path
        if evidence.repository_path:
            norm_path = evidence.repository_path.replace("\\", "/").lstrip("/")
            if any(norm_path in dep or dep in norm_path for dep in dependency_files):
                score += self.config.weight_dependency

        # 5. Same / Matching failing test
        if evidence.repository_path:
            norm_path = evidence.repository_path.replace("\\", "/").lstrip("/")
            if any(norm_path in tf or tf in norm_path for tf in failed_test_files):
                score += self.config.weight_test

        return min(1.0, round(score, 4))

    def get_priority_base(self, evidence: NormalizedEvidence) -> float:
        """Determine base priority tier based on evidence type and resolution status."""
        ev_type = evidence.type
        resolution = evidence.metadata.get("resolution_status", ResolutionStatus.RESOLVED.value)

        if ev_type == EvidenceType.STACK_FRAME:
            return self.PRIORITY_TIERS["DIRECT_STACK_FRAME"]
        elif ev_type == EvidenceType.TEST_FAILURE:
            return self.PRIORITY_TIERS["DIRECT_FAILED_TEST"]
        elif ev_type == EvidenceType.CALL_RELATIONSHIP:
            if resolution == ResolutionStatus.UNRESOLVED.value:
                return self.PRIORITY_TIERS["UNRESOLVED_CALL_RELATIONSHIP"]
            return self.PRIORITY_TIERS["RESOLVED_CALL_RELATIONSHIP"]
        elif ev_type in (EvidenceType.COMMIT, EvidenceType.CODE_CHANGE, EvidenceType.BLAME):
            return self.PRIORITY_TIERS["RECENT_DIRECT_CODE_CHANGE"]
        elif ev_type == EvidenceType.IMPORT_RELATIONSHIP:
            return self.PRIORITY_TIERS["IMPORT_RELATIONSHIP"]
        elif ev_type == EvidenceType.TEST_RELATIONSHIP:
            ev_evidence_str = str(evidence.metadata.get("evidence", "")).upper()
            if "HEURISTIC" in ev_evidence_str or "NAME_MATCH" in ev_evidence_str:
                return self.PRIORITY_TIERS["HEURISTIC_TEST_MATCH"]
            return self.PRIORITY_TIERS["RESOLVED_CALL_RELATIONSHIP"]
        elif evidence.metadata.get("is_co_occurrence", False):
            return self.PRIORITY_TIERS["GIT_CO_CHANGE"]
        else:
            return self.PRIORITY_TIERS["GENERIC_LOG"]

    def rank_evidence(
        self,
        evidence_list: List[NormalizedEvidence],
        failing_file: Optional[str] = None,
        failing_symbol: Optional[str] = None,
        dependency_files: Optional[Set[str]] = None,
        failed_test_files: Optional[Set[str]] = None,
    ) -> List[NormalizedEvidence]:
        """Rank and sort all evidence items by calculated relevance and confidence."""
        for item in evidence_list:
            locality = self.compute_locality_score(
                item,
                failing_file=failing_file,
                failing_symbol=failing_symbol,
                dependency_files=dependency_files,
                failed_test_files=failed_test_files,
            )
            item.metadata["locality_score"] = locality

            priority_base = self.get_priority_base(item)
            item.metadata["priority_base"] = priority_base

            # Relevance = PriorityBase * (0.6 * confidence + 0.4 * locality)
            raw_relevance = priority_base * (0.6 * item.confidence + 0.4 * locality)
            item.relevance = min(1.0, max(0.05, round(raw_relevance, 4)))

        # Deterministic sorting: relevance descending, then confidence descending, then evidence_id
        ranked = sorted(
            evidence_list,
            key=lambda e: (e.relevance, e.confidence, e.evidence_id),
            reverse=True,
        )
        return ranked
