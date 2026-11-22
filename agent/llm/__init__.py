"""Devaura LLM-Backed Maintenance & Repair Engine."""

from agent.llm.generator import LLMPatchGenerator
from agent.llm.investigator import LLMInvestigator
from agent.llm.models import (
    LLMInvestigationCandidate,
    LLMInvestigationResult,
    LLMMode,
    LLMPatchProposal,
    LLMProposedChange,
    LLMRepairPlanProposal,
    LLMResponse,
    LLMUsage,
)
from agent.llm.planner import LLMRepairPlanner
from agent.llm.prompts import (
    INVESTIGATION_SYSTEM_PROMPT,
    PATCH_GENERATOR_SYSTEM_PROMPT,
    REPAIR_PLANNER_SYSTEM_PROMPT,
    SecretRedactor,
    build_investigation_prompt,
    build_patch_prompt,
    build_repair_plan_prompt,
)
from agent.llm.provider import (
    DeterministicMockLLMProvider,
    GeminiProvider,
    LLMConfigurationError,
    LLMExecutionError,
    LLMProvider,
    OpenAIProvider,
    ProviderFactory,
)
from agent.llm.tools import (
    LLMToolGovernance,
    LifecyclePhase,
    PhaseToolPermissionError,
    RepairLifecyclePhase,
    ToolCallRecord,
)

__all__ = [
    "LLMInvestigator",
    "LLMRepairPlanner",
    "LLMPatchGenerator",
    "LLMProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "DeterministicMockLLMProvider",
    "ProviderFactory",
    "LLMConfigurationError",
    "LLMExecutionError",
    "LLMToolGovernance",
    "LifecyclePhase",
    "RepairLifecyclePhase",
    "PhaseToolPermissionError",
    "ToolCallRecord",
    "SecretRedactor",
    "LLMMode",
    "LLMUsage",
    "LLMResponse",
    "LLMInvestigationCandidate",
    "LLMInvestigationResult",
    "LLMProposedChange",
    "LLMRepairPlanProposal",
    "LLMPatchProposal",
    "INVESTIGATION_SYSTEM_PROMPT",
    "REPAIR_PLANNER_SYSTEM_PROMPT",
    "PATCH_GENERATOR_SYSTEM_PROMPT",
    "build_investigation_prompt",
    "build_repair_plan_prompt",
    "build_patch_prompt",
]
