"""Repair Planner.

Formulates evidence-backed, structured Repair Plans from validated Repair Contexts.
Ensures every proposed modification cites concrete evidence IDs and adheres to
scope boundaries.
"""

from typing import List, Optional
from agent.repair.models import ProposedChange, RepairContext, RepairPlan


class RepairPlanner:
    """Generates structured, traceable repair plans."""

    def __init__(self):
        pass

    def create_plan(
        self,
        context: RepairContext,
        custom_objective: Optional[str] = None,
    ) -> RepairPlan:
        """Formulate a RepairPlan strictly bounded by RepairContext evidence."""
        root_cause_data = context.selected_root_cause
        root_cause_desc = root_cause_data.get("description", "Unknown root cause")
        root_cause_title = root_cause_data.get("title", "Issue repair")

        objective = (
            custom_objective
            or f"Resolve root cause: {root_cause_title} in {', '.join(context.affected_files)}"
        )

        # Collect evidence IDs from supporting evidence
        available_evidence_ids = [
            e.get("evidence_id")
            for e in context.supporting_evidence
            if e.get("evidence_id")
        ]

        proposed_changes: List[ProposedChange] = []

        for target_file in context.affected_files:
            # Find evidence items specific to this file
            file_ev_ids = [
                e.get("evidence_id")
                for e in context.supporting_evidence
                if e.get("repository_path") == target_file and e.get("evidence_id")
            ]
            if not file_ev_ids:
                file_ev_ids = available_evidence_ids[:3]

            # Determine affected lines / symbols for location
            file_lines = context.affected_lines.get(target_file, [])
            loc = (
                f"lines {min(file_lines)}-{max(file_lines)}"
                if file_lines
                else "target function / component"
            )

            # Heuristic change type categorization based on failure details
            fail_type = context.failure.get("failure_type", "")
            err_msg = context.failure.get("error_message", "").lower()

            if "none" in err_msg or "null" in err_msg or "attributeerror" in err_msg:
                change_type = "NULL_OR_NONE_GUARD"
            elif "zerodivision" in err_msg or "division by zero" in err_msg:
                change_type = "DEFENSIVE_GUARD"
            elif "keyerror" in err_msg or "indexerror" in err_msg:
                change_type = "BOUNDARY_OR_KEY_CHECK"
            elif "typeerror" in err_msg:
                change_type = "TYPE_GUARD"
            else:
                change_type = "DEFENSIVE_LOGIC_FIX"

            change = ProposedChange(
                file=target_file,
                location=loc,
                change_type=change_type,
                rationale=f"Fix {root_cause_title} by applying {change_type.lower().replace('_', ' ')} based on evidence {file_ev_ids}.",
                evidence_ids=file_ev_ids,
                expected_effect=f"Prevent failure condition in {target_file} without breaking existing caller interfaces.",
            )
            proposed_changes.append(change)

        # Determine risks
        risks = [
            "Potential behavioral changes for unexpected downstream callers",
            "Ensure edge case inputs still conform to expected type contracts",
        ]
        if len(context.affected_files) > 1:
            risks.append("Coordinated changes across multiple files may affect call-graph sequencing")

        # Determine assumptions
        assumptions = [
            "Existing test suite adequately covers adjacent regression paths",
            "Target repository syntax and style standards apply to generated diff",
            "No breaking changes introduced to public API boundaries",
        ]

        # Calculate confidence based on evidence volume and candidate confidence
        candidate_conf = float(root_cause_data.get("confidence", 0.7))
        evidence_factor = min(1.0, len(context.supporting_evidence) / 3.0)
        overall_confidence = round(0.5 * candidate_conf + 0.5 * evidence_factor, 2)

        return RepairPlan(
            repair_id=context.repair_id,
            investigation_id=context.investigation_id,
            objective=objective,
            root_cause=root_cause_desc,
            affected_files=context.affected_files,
            affected_symbols=context.affected_symbols,
            proposed_changes=proposed_changes,
            tests_to_run=context.related_tests,
            risks=risks,
            assumptions=assumptions,
            unresolved_questions=[],
            confidence=overall_confidence,
        )
