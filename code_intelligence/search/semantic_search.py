from typing import List, Optional
from code_intelligence.models import SearchMatch


class SemanticSearch:
    """Tier 4: Semantic vector search abstraction.
    
    Status: OPTIONAL / NOT ACTIVE (PLANNED).
    Gracefully returns empty results when no external embedding model or vector index is configured.
    """

    STATUS = "OPTIONAL / NOT ACTIVE (PLANNED)"

    def __init__(self, is_enabled: bool = False) -> None:
        self.is_enabled = is_enabled

    def get_status(self) -> str:
        return "ACTIVE" if self.is_enabled else self.STATUS

    def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[SearchMatch]:
        if not self.is_enabled:
            return []
        # Pluggable vector search placeholder for future phases
        return []
