"""Devaura LLM Data Contracts and Structured Schemas.

Defines validated data models for LLM usage, structured responses,
investigation proposals, repair planning, and patch synthesis.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LLMMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LIVE = "live"


class LLMUsage(BaseModel):
    """Token consumption, latency, and financial cost tracking."""
    model_config = ConfigDict(extra="ignore")

    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    request_id: Optional[str] = None
    token_status: str = "CONFIRMED"


class LLMResponse(BaseModel):
    """Raw and structured LLM output with execution telemetry."""
    model_config = ConfigDict(extra="ignore")

    content: str
    structured_data: Optional[Dict[str, Any]] = None
    usage: LLMUsage
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    finish_reason: Optional[str] = None


class LLMInvestigationCandidate(BaseModel):
    """Root-cause hypothesis proposed by an LLM."""
    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    statement: str
    affected_files: List[str] = Field(default_factory=list)
    affected_symbols: List[str] = Field(default_factory=list)
    supporting_evidence_ids: List[str] = Field(
        default_factory=list,
        description="IDs of concrete evidence items supporting this hypothesis"
    )
    contradicting_evidence_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: str = ""


class LLMInvestigationResult(BaseModel):
    """Strictly validated structured output from the LLM Investigator."""
    model_config = ConfigDict(extra="ignore")

    failure_summary: str
    observed_facts: List[str] = Field(default_factory=list)
    root_cause_candidates: List[LLMInvestigationCandidate] = Field(default_factory=list)
    recommended_next_evidence: List[str] = Field(default_factory=list)
    sufficiency: str = Field(
        default="SUFFICIENT",
        description="SUFFICIENT | PARTIALLY_SUFFICIENT | INSUFFICIENT"
    )


class LLMProposedChange(BaseModel):
    """Atomic change proposed by LLM repair planner."""
    model_config = ConfigDict(extra="ignore")

    file: str
    symbol: str
    location: str
    change_description: str
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Evidence IDs directly justifying this modification"
    )
    verification_tests: List[str] = Field(default_factory=list)


class LLMRepairPlanProposal(BaseModel):
    """Strictly validated structured output from the LLM Repair Planner."""
    model_config = ConfigDict(extra="ignore")

    objective: str
    root_cause_summary: str
    proposed_changes: List[LLMProposedChange] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LLMPatchProposal(BaseModel):
    """Unified diff proposed by LLM with justification."""
    model_config = ConfigDict(extra="ignore")

    unified_diff: str
    explanation: str
    assumptions: List[str] = Field(default_factory=list)
    cited_evidence_ids: List[str] = Field(default_factory=list)
