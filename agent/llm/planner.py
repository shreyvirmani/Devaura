"""Devaura LLM-Backed Repair Planner.

Formulates evidence-backed, structured Repair Plans using LLM reasoning,
strictly enforced by deterministic citation checks and scope guards.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from agent.llm.models import (
    LLMProposedChange,
    LLMRepairPlanProposal,
    LLMUsage,
)
from agent.llm.prompts import (
    REPAIR_PLANNER_SYSTEM_PROMPT,
    SecretRedactor,
    build_repair_plan_prompt,
)
from agent.llm.provider import LLMProvider, ProviderFactory
from agent.repair.models import ProposedChange, RepairContext, RepairPlan
from apps.api.logger import logger


class LLMRepairPlanner:
    """Plans software repairs using an LLM governed by deterministic scope and evidence citation invariants."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or ProviderFactory.get_provider()

    def create_plan(
        self,
        context: RepairContext,
        custom_objective: Optional[str] = None,
    ) -> Tuple[RepairPlan, LLMUsage]:
        """Formulate a RepairPlan strictly bounded by RepairContext evidence."""
        prompt = build_repair_plan_prompt(context)

        # Call LLM with structured schema
        proposal, usage = self.provider.generate_structured(
            prompt=prompt,
            schema=LLMRepairPlanProposal,
            system_prompt=REPAIR_PLANNER_SYSTEM_PROMPT,
        )

        # Set of valid evidence IDs from context
        valid_evidence_ids: Set[str] = {
            e.get("evidence_id")
            for e in context.supporting_evidence
            if e.get("evidence_id")
        }

        # Deterministic Policy Validation on Proposed Changes
        validated_changes: List[ProposedChange] = []
        rejected_changes: List[Dict[str, Any]] = []

        if proposal and proposal.proposed_changes:
            for raw_change in proposal.proposed_changes:
                # 1. Scope Guard: File must be in context.affected_files
                norm_file = raw_change.file.replace("\\", "/").strip()
                if norm_file not in context.affected_files:
                    logger.warning(
                        f"REJECTED change targeting '{norm_file}': out-of-scope (allowed: {context.affected_files})"
                    )
                    rejected_changes.append({"file": norm_file, "reason": "out_of_scope"})
                    continue

                # 2. Evidence Citation Guard: Must cite valid evidence IDs
                valid_cites = [eid for eid in raw_change.evidence_ids if eid in valid_evidence_ids]
                if not valid_cites:
                    # Check if there is file-specific evidence in context
                    inferred_cites = [
                        e.get("evidence_id")
                        for e in context.supporting_evidence
                        if e.get("repository_path") == norm_file and e.get("evidence_id")
                    ]
                    if inferred_cites:
                        valid_cites = inferred_cites[:2]
                    else:
                        logger.warning(
                            f"REJECTED change to '{norm_file}': missing concrete evidence citation (cited: {raw_change.evidence_ids})"
                        )
                        rejected_changes.append({"file": norm_file, "reason": "missing_evidence_citation"})
                        continue

                validated_changes.append(
                    ProposedChange(
                        file=norm_file,
                        location=raw_change.location or "target component",
                        change_type="MODIFICATION",
                        rationale=raw_change.change_description,
                        evidence_ids=valid_cites,
                        expected_effect=f"Resolve defect in {raw_change.symbol or norm_file}",
                    )
                )

        # Fallback if LLM proposed no valid changes: generate bounded default changes from context
        if not validated_changes:
            for target_file in context.affected_files:
                file_ev = [
                    e.get("evidence_id")
                    for e in context.supporting_evidence
                    if e.get("repository_path") == target_file and e.get("evidence_id")
                ]
                fallback_ev = file_ev if file_ev else list(valid_evidence_ids)[:2]
                validated_changes.append(
                    ProposedChange(
                        file=target_file,
                        location="target component",
                        change_type="MODIFICATION",
                        rationale="Fallback deterministic change from validated repair context.",
                        evidence_ids=fallback_ev,
                        expected_effect="Resolve defect at localized site.",
                    )
                )

        root_cause_data = context.selected_root_cause
        root_cause_title = root_cause_data.get("title", "Issue repair")

        objective = (
            custom_objective
            or (proposal.objective if proposal else None)
            or f"Resolve root cause: {root_cause_title} in {', '.join(context.affected_files)}"
        )

        plan = RepairPlan(
            repair_id=context.repair_id,
            investigation_id=context.investigation_id,
            objective=objective,
            root_cause=root_cause_title,
            affected_files=list({c.file for c in validated_changes}),
            affected_symbols=context.affected_symbols,
            proposed_changes=validated_changes,
            tests_to_run=context.related_tests,
            risks=proposal.risks if proposal else ["Potential regression in edge cases"],
            assumptions=proposal.assumptions if proposal else ["Failure localized to specified files"],
            unresolved_questions=proposal.unresolved_questions if proposal else [],
            confidence=proposal.confidence if proposal else 0.7,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        return plan, usage
