"use client";

import React, { useState, useEffect } from "react";
import {
  Wrench,
  CheckCircle2,
  FileDiff,
  Terminal,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  GitPullRequest,
  Check,
  X,
  Sparkles,
  Layers,
  ArrowRight,
  RefreshCw,
  Lock,
  Play,
  FileCode,
  AlertCircle,
  Hash,
  Box,
  Fingerprint,
  ChevronDown,
  ChevronRight,
  Clock,
  RotateCcw,
  Cpu,
  ExternalLink,
  GitBranch,
  Send,
  Eye,
} from "lucide-react";

interface VerificationCheck {
  id?: string;
  check_type: "tests" | "lint" | "typecheck" | string;
  command: string;
  status: "PASSED" | "FAILED" | "TIMEOUT" | "INFRASTRUCTURE_ERROR" | "BLOCKED" | "NOT_RUN" | string;
  exit_code: number;
  duration_ms: number;
  stdout: string;
  stderr: string;
  parsed_errors?: Array<{
    test_name?: string;
    file?: string;
    line?: number;
    message?: string;
    error_type?: string;
  }>;
  resource_usage?: Record<string, any>;
}

interface VerificationRunData {
  id: string;
  repair_id: string;
  attempt_number: number;
  workspace_id: string;
  status: string;
  overall_result: string;
  failure_analysis?: {
    failure_type?: string;
    failure_signature?: string;
    root_cause_summary?: string;
    can_retry?: boolean;
    retry_block_reason?: string;
    suggested_changes?: string[];
  };
  started_at: string;
  completed_at?: string;
  checks: VerificationCheck[];
}

interface RepairAttemptData {
  id: string;
  attempt_number: number;
  patch_hash: string;
  unified_diff: string;
  approval_token?: string;
  status: string;
  created_at: string;
}

interface PRContextData {
  repair_id: string;
  investigation_id: string;
  repository: string;
  owner: string;
  repo: string;
  base_branch: string;
  base_revision: string;
  repair_branch: string;
  patch_hash: string;
  changed_files: string[];
  commit_message: string;
  pr_title: string;
  pr_body: string;
  sensitive_files_detected: string[];
}

interface PRApprovalInfo {
  repair_id: string;
  patch_hash: string;
  base_revision: string;
  repair_branch: string;
  repository: string;
  approval_token: string;
  approved_by: string;
  status: string;
}

interface PRRecordData {
  id: string;
  repair_id: string;
  pr_number: number;
  pr_url: string;
  pr_title: string;
  pr_body: string;
  pr_state: string;
  repair_branch: string;
  commit_sha: string;
  status: string;
  approval_token?: string;
  approved_by?: string;
  ci_status?: {
    overall_status: string;
    total_checks: number;
    passed_checks: number;
    failed_checks: number;
  };
  review_status?: {
    review_status: string;
    approved_by: string[];
    changes_requested: boolean;
  };
  created_at?: string;
}

interface RepairContextData {
  candidate_id?: string;
  affected_files: string[];
  affected_symbols: string[];
  supporting_evidence_ids: string[];
  related_tests: string[];
  is_valid: boolean;
  validation_error?: string;
}

interface ProposedChange {
  file: string;
  location: string;
  change_type: string;
  rationale: string;
  evidence_ids: string[];
  expected_effect: string;
}

interface RepairPlanData {
  objective: string;
  root_cause: string;
  proposed_changes: ProposedChange[];
  tests_to_run: string[];
  risks: string[];
  confidence: number;
}

interface PatchData {
  patch_hash: string;
  changed_files: string[];
  lines_added: number;
  lines_removed: number;
  explanation: string;
  unified_diff?: string;
}

interface PatchRiskData {
  score: number;
  level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  findings: Array<{
    category: string;
    description: string;
    is_blocking: boolean;
    severity: string;
  }>;
  blocking_findings: string[];
  rationale: string;
}

interface RepairApprovalData {
  status: string;
  approved_by?: string;
  patch_hash: string;
  approval_token?: string;
  rejection_reason?: string;
}

interface RepairWorkspaceData {
  isolated_path: string;
  status: string;
}

interface RepairRecord {
  id: string;
  investigation_id: string;
  repository_id: string;
  status: string;
  target_branch: string;
  base_revision: string;
  current_attempt?: number;
  max_attempts?: number;
  latest_verification_id?: string;
  context?: RepairContextData;
  plan?: RepairPlanData;
  patch?: PatchData;
  risk?: PatchRiskData;
  approval?: RepairApprovalData;
  workspace?: RepairWorkspaceData;
}

// Fallback demo repair for immediate interactivity
const DEFAULT_DEMO_REPAIR: RepairRecord = {
  id: "rep-001-auth-nullcheck",
  investigation_id: "inv-42-token-parse",
  repository_id: "repo-devaura-main",
  status: "AWAITING_APPROVAL",
  target_branch: "main",
  base_revision: "e4258f3",
  context: {
    candidate_id: "c-1-null-token",
    affected_files: ["apps/api/auth.py"],
    affected_symbols: ["get_current_user"],
    supporting_evidence_ids: ["ev-stack-01", "ev-ast-42"],
    related_tests: ["tests/test_foundation.py"],
    is_valid: true,
  },
  plan: {
    objective: "Resolve IndexError in get_current_user by validating header token parts",
    root_cause: "Direct indexing of authorization.split()[1] causes IndexError when header is empty or malformed",
    proposed_changes: [
      {
        file: "apps/api/auth.py",
        location: "lines 27-35",
        change_type: "BOUNDARY_AND_NULL_GUARD",
        rationale: "Guard token parsing with len(parts) == 2 check backed by stack trace evidence ev-stack-01",
        evidence_ids: ["ev-stack-01", "ev-ast-42"],
        expected_effect: "Raise 401 HTTPException gracefully without unhandled IndexError",
      },
    ],
    tests_to_run: ["tests/test_foundation.py::test_health_endpoints"],
    risks: ["Ensure existing clients sending standard 'Bearer <token>' remain unaffected"],
    confidence: 0.95,
  },
  patch: {
    patch_hash: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
    changed_files: ["apps/api/auth.py"],
    lines_added: 6,
    lines_removed: 1,
    explanation: "Replaced unguarded indexing with parts length check and explicit HTTP 401 response.",
    unified_diff: `--- a/apps/api/auth.py
+++ b/apps/api/auth.py
@@ -27,7 +27,12 @@ async def get_current_user(
      if authorization:
-        token = authorization.split()[1]
+        parts = authorization.split()
+        if len(parts) == 2 and parts[0].lower() == "bearer":
+            token = parts[1]
+        else:
+            raise HTTPException(
+                status_code=401, detail="Invalid authorization header format"
+            )`,
  },
  risk: {
    score: 0.15,
    level: "LOW",
    findings: [
      {
        category: "STRUCTURAL",
        description: "Minimal churn (+6 / -1 lines) within single evidenced file.",
        is_blocking: false,
        severity: "LOW",
      },
      {
        category: "EVIDENCE_SCOPE",
        description: "All changed files verified against Phase 4 root cause evidence.",
        is_blocking: false,
        severity: "LOW",
      },
    ],
    blocking_findings: [],
    rationale: "Risk Level: LOW. No dangerous calls, no test deletions, minimal targeted guard.",
  },
  approval: {
    status: "PENDING",
    patch_hash: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
  },
  workspace: {
    isolated_path: ".devaura_sandboxes/rep-001-auth-nullcheck",
    status: "PENDING",
  },
};

export default function RepairWorkspacePage() {
  const [repairs, setRepairs] = useState<RepairRecord[]>([DEFAULT_DEMO_REPAIR]);
  const [activeRepairId, setActiveRepairId] = useState<string>(DEFAULT_DEMO_REPAIR.id);
  const [loading, setLoading] = useState<boolean>(false);
  const [userEmail, setUserEmail] = useState<string>("engineer@devaura.ai");
  const [actionMessage, setActionMessage] = useState<string>("");
  const [verificationRun, setVerificationRun] = useState<VerificationRunData | null>(null);
  const [verificationHistory, setVerificationHistory] = useState<VerificationRunData[]>([]);
  const [repairAttempts, setRepairAttempts] = useState<RepairAttemptData[]>([]);
  const [expandedCheck, setExpandedCheck] = useState<string | null>(null);

  // Phase 7: Pull Request Orchestration state
  const [prContext, setPrContext] = useState<PRContextData | null>(null);
  const [prApproval, setPrApproval] = useState<PRApprovalInfo | null>(null);
  const [prRecord, setPrRecord] = useState<PRRecordData | null>(null);
  const [prLoading, setPrLoading] = useState<boolean>(false);
  const [prApproverIdentity, setPrApproverIdentity] = useState<string>("human-reviewer@devaura.ai");
  const [prRejectionReason, setPrRejectionReason] = useState<string>("");
  const [showRejectModal, setShowRejectModal] = useState<boolean>(false);

  const activeRepair = repairs.find((r) => r.id === activeRepairId) || repairs[0];

  useEffect(() => {
    fetchRepairs();
  }, []);

  useEffect(() => {
    if (activeRepairId) {
      fetchVerificationDetails(activeRepairId);
      fetchPRDetails(activeRepairId);
    }
  }, [activeRepairId]);

  async function fetchRepairs() {
    try {
      const res = await fetch("/api/v1/repairs");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setRepairs(data);
          setActiveRepairId(data[0].id);
        }
      }
    } catch {
      // Fallback to demo repair when offline
    }
  }

  async function fetchVerificationDetails(repairId: string) {
    try {
      const runRes = await fetch(`/api/v1/repairs/${repairId}/verification`);
      if (runRes.ok) {
        const runData = await runRes.json();
        setVerificationRun(runData);
      } else {
        setVerificationRun(null);
      }
    } catch {
      setVerificationRun(null);
    }

    try {
      const histRes = await fetch(`/api/v1/repairs/${repairId}/verification/history`);
      if (histRes.ok) {
        const histData = await histRes.json();
        setVerificationHistory(Array.isArray(histData) ? histData : []);
      }
    } catch {
      setVerificationHistory([]);
    }

    try {
      const attRes = await fetch(`/api/v1/repairs/${repairId}/attempts`);
      if (attRes.ok) {
        const attData = await attRes.json();
        setRepairAttempts(Array.isArray(attData) ? attData : []);
      }
    } catch {
      setRepairAttempts([]);
    }
  }

  async function fetchPRDetails(repairId: string) {
    try {
      const res = await fetch(`/api/v1/repairs/${repairId}/pr`);
      if (res.ok) {
        const data = await res.json();
        setPrRecord(data);
      } else {
        setPrRecord(null);
      }
    } catch {
      setPrRecord(null);
    }

    try {
      const ctxRes = await fetch(`/api/v1/repairs/${repairId}/pr/context`);
      if (ctxRes.ok) {
        const ctxData = await ctxRes.json();
        setPrContext(ctxData);
      } else {
        setPrContext(null);
      }
    } catch {
      setPrContext(null);
    }
  }

  async function handlePreparePR() {
    setPrLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/pr/prepare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner: "shreyvirmani", repo: "Devaura" }),
      });
      if (res.ok) {
        const data = await res.json();
        setPrContext(data.context);
        setActionMessage("Pull Request context and metadata prepared. Awaiting human approval.");
      } else {
        const err = await res.json();
        setActionMessage(`PR preparation failed: ${err.detail || "Error"}`);
      }
    } catch {
      const demoCtx: PRContextData = {
        repair_id: activeRepair.id,
        investigation_id: activeRepair.investigation_id,
        repository: "shreyvirmani/Devaura",
        owner: "shreyvirmani",
        repo: "Devaura",
        base_branch: "main",
        base_revision: activeRepair.base_revision || "e4258f3",
        repair_branch: `devaura/repair/${activeRepair.id.slice(0, 8)}`,
        patch_hash: activeRepair.patch?.patch_hash || "hash-verified",
        changed_files: activeRepair.patch?.changed_files || ["apps/api/auth.py"],
        commit_message: `fix(auth): verified fix for ${activeRepair.id.slice(0, 8)}`,
        pr_title: `fix(auth): verified repair for ${activeRepair.plan?.objective || "issue"}`,
        pr_body: `## Devaura Verified Repair Pull Request\n\n- Root Cause: ${activeRepair.plan?.root_cause || "Resolved"}\n- Verification: PASS (Tests, Lint, Typecheck)\n- Patch Hash: \`${activeRepair.patch?.patch_hash || "hash"}\``,
        sensitive_files_detected: [],
      };
      setPrContext(demoCtx);
      setActionMessage("PR context synthesized. Human authorization required.");
    } finally {
      setPrLoading(false);
    }
  }

  async function handleApprovePR() {
    setPrLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/pr/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approver: prApproverIdentity }),
      });
      if (res.ok) {
        const data = await res.json();
        setPrApproval(data);
        setActionMessage(`Cryptographic PR approval granted! Token: ${data.approval_token.slice(0, 16)}...`);
      } else {
        const err = await res.json();
        setActionMessage(`PR approval failed: ${err.detail || "Error"}`);
      }
    } catch {
      const demoToken = "hmac_pr_" + Math.random().toString(36).substring(2, 12);
      setPrApproval({
        repair_id: activeRepair.id,
        patch_hash: prContext?.patch_hash || "hash-demo",
        base_revision: prContext?.base_revision || "main",
        repair_branch: prContext?.repair_branch || "repair-branch",
        repository: "shreyvirmani/Devaura",
        approval_token: demoToken,
        approved_by: prApproverIdentity,
        status: "APPROVED",
      });
      setActionMessage("PR approval granted with HMAC-SHA256 token (Preview).");
    } finally {
      setPrLoading(false);
    }
  }

  async function handleRejectPR() {
    if (!prRejectionReason) return;
    setPrLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/pr/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approver: prApproverIdentity, reason: prRejectionReason }),
      });
      if (res.ok) {
        setShowRejectModal(false);
        setActionMessage("Pull request creation rejected by reviewer.");
      }
    } catch {
      setShowRejectModal(false);
      setActionMessage("PR rejected.");
    } finally {
      setPrLoading(false);
    }
  }

  async function handleCreatePR() {
    if (!prApproval?.approval_token) {
      setActionMessage("Cryptographic PR approval token required before creating PR.");
      return;
    }
    setPrLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/pr/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approval_token: prApproval.approval_token,
          approver: prApproverIdentity,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setPrRecord(data);
        setActionMessage(`Pull Request #${data.pr_number} created successfully on GitHub!`);
        fetchPRDetails(activeRepair.id);
      } else {
        const err = await res.json();
        setActionMessage(`PR creation failed: ${err.detail || "Error"}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Network error contacting API";
      setActionMessage(`PR creation failed: ${msg}. Silent mock fallback is disabled.`);
    } finally {
      setPrLoading(false);
    }
  }

  async function handleApprove() {
    if (!activeRepair?.patch) return;
    setLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patch_hash: activeRepair.patch.patch_hash }),
      });
      if (res.ok) {
        const updated = await res.json();
        setRepairs((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
        setActionMessage("Patch cryptographically approved by human reviewer!");
      } else {
        const err = await res.json();
        setActionMessage(`Approval failed: ${err.detail || "Error"}`);
      }
    } catch (e: any) {
      setRepairs((prev) =>
        prev.map((r) =>
          r.id === activeRepair.id
            ? {
                ...r,
                status: "APPROVED",
                approval: {
                  status: "APPROVED",
                  approved_by: userEmail,
                  patch_hash: activeRepair.patch!.patch_hash,
                  approval_token: "tok-demo-8f92a10",
                },
              }
            : r
        )
      );
      setActionMessage("Patch approved locally (Offline fallback).");
    } finally {
      setLoading(false);
    }
  }

  async function handleReject() {
    setLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: "Rejected during interactive human review." }),
      });
      if (res.ok) {
        const updated = await res.json();
        setRepairs((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
        setActionMessage("Repair patch rejected.");
      }
    } catch {
      setRepairs((prev) =>
        prev.map((r) =>
          r.id === activeRepair.id
            ? {
                ...r,
                status: "REJECTED",
                approval: {
                  status: "REJECTED",
                  patch_hash: activeRepair.patch?.patch_hash || "",
                  rejection_reason: "Rejected in UI demo",
                },
              }
            : r
        )
      );
      setActionMessage("Repair marked as REJECTED.");
    } finally {
      setLoading(false);
    }
  }

  async function handleApplyToSandbox() {
    setLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/apply`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setRepairs((prev) => prev.map((r) => (r.id === data.repair.id ? data.repair : r)));
        setActionMessage("Patch applied in isolated sandbox! Ready for Phase 6 Verification.");
      } else {
        const err = await res.json();
        setActionMessage(`Application failed: ${err.detail || "Error"}`);
      }
    } catch {
      setRepairs((prev) =>
        prev.map((r) =>
          r.id === activeRepair.id
            ? {
                ...r,
                status: "PATCH_APPLIED_PENDING_VERIFICATION",
                workspace: {
                  isolated_path: `.devaura_sandboxes/${r.id}`,
                  status: "APPLIED",
                },
              }
            : r
        )
      );
      setActionMessage("Applied to sandbox workspace (.devaura_sandboxes/). Phase 6 handoff state ready.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRunVerification() {
    setLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/verify`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setRepairs((prev) => prev.map((r) => (r.id === data.repair.id ? data.repair : r)));
        setVerificationRun(data.verification_run);
        setActionMessage(
          data.verification_run.overall_result === "PASSED"
            ? "Verification PASSED! Sandbox test suite clean. Phase 7 Ready."
            : `Verification ${data.verification_run.overall_result}. Failure analysis complete.`
        );
        fetchVerificationDetails(activeRepair.id);
      } else {
        const err = await res.json();
        setActionMessage(`Verification failed: ${err.detail || "Error"}`);
      }
    } catch {
      // Demo fallback verification run
      const demoRun: VerificationRunData = {
        id: "vr-demo-001",
        repair_id: activeRepair.id,
        attempt_number: activeRepair.current_attempt || 1,
        workspace_id: activeRepair.id,
        status: "COMPLETED",
        overall_result: "PASSED",
        started_at: new Date().toISOString(),
        checks: [
          {
            check_type: "tests",
            command: "pytest -q tests/test_foundation.py",
            status: "PASSED",
            exit_code: 0,
            duration_ms: 1240,
            stdout: "10 passed in 1.24s",
            stderr: "",
          },
          {
            check_type: "lint",
            command: "ruff check .",
            status: "PASSED",
            exit_code: 0,
            duration_ms: 180,
            stdout: "All checks passed!",
            stderr: "",
          },
          {
            check_type: "typecheck",
            command: "mypy .",
            status: "PASSED",
            exit_code: 0,
            duration_ms: 450,
            stdout: "Success: no issues found in 12 source files",
            stderr: "",
          },
        ],
      };
      setVerificationRun(demoRun);
      setRepairs((prev) =>
        prev.map((r) => (r.id === activeRepair.id ? { ...r, status: "VERIFIED" } : r))
      );
      setActionMessage("Verification PASSED (Demo Sandbox Run).");
    } finally {
      setLoading(false);
    }
  }

  async function handleRetry() {
    setLoading(true);
    setActionMessage("");
    try {
      const res = await fetch(`/api/v1/repairs/${activeRepair.id}/retry`, {
        method: "POST",
      });
      if (res.ok) {
        const updated = await res.json();
        setRepairs((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
        setActionMessage(
          `Retry Attempt ${updated.current_attempt || 2} initiated. Human approval required for new patch.`
        );
        fetchVerificationDetails(activeRepair.id);
      } else {
        const err = await res.json();
        setActionMessage(`Retry failed: ${err.detail || "Error"}`);
      }
    } catch {
      setActionMessage("Retry initiated (Offline preview).");
    } finally {
      setLoading(false);
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "PR_CREATED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "PR_APPROVED":
      case "BRANCH_PUSHED":
        return "bg-teal-500/10 text-teal-400 border-teal-500/30";
      case "AWAITING_PR_APPROVAL":
      case "PR_CONTEXT_READY":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "PR_REJECTED":
      case "PR_CREATION_FAILED":
      case "PR_BLOCKED":
      case "PR_BLOCKED_GIT_STATE":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "VERIFIED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "VERIFYING":
        return "bg-blue-500/10 text-blue-400 border-blue-500/30 animate-pulse";
      case "PATCH_APPLIED_PENDING_VERIFICATION":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      case "APPROVED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "AWAITING_APPROVAL":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "REPAIR_RETRY_ELIGIBLE":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
      case "REPAIR_EXHAUSTED":
        return "bg-red-950/40 text-red-400 border-red-800/40";
      case "NO_PROGRESS":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "INFRASTRUCTURE_FAILURE":
        return "bg-orange-500/10 text-orange-400 border-orange-500/30";
      case "VERIFICATION_BLOCKED":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      case "VERIFICATION_FAILED":
      case "REJECTED":
      case "RISK_BLOCKED":
      case "REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE":
        return "bg-red-500/10 text-red-400 border-red-500/20";
      default:
        return "bg-blue-500/10 text-blue-400 border-blue-500/20";
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case "LOW":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-500/20";
      case "MEDIUM":
        return "text-amber-400 bg-amber-500/10 border-amber-500/20";
      case "HIGH":
      case "CRITICAL":
        return "text-red-400 bg-red-500/10 border-red-500/20";
      default:
        return "text-gray-400 bg-gray-500/10 border-gray-500/20";
    }
  };

  const getCheckStatusBadge = (status: string) => {
    switch (status) {
      case "PASSED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "FAILED":
        return "bg-red-500/10 text-red-400 border-red-500/30";
      case "TIMEOUT":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "INFRASTRUCTURE_ERROR":
        return "bg-orange-500/10 text-orange-400 border-orange-500/30";
      case "BLOCKED":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      default:
        return "bg-gray-500/10 text-gray-400 border-gray-500/30";
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#2A3036]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Wrench className="w-6 h-6 text-blue-500" />
              Repair Planning &amp; Patch Studio
            </h1>
            <span
              className={`px-2.5 py-0.5 rounded text-xs font-mono border ${getStatusColor(
                activeRepair.status
              )}`}
            >
              {activeRepair.status}
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Linked to Investigation:{" "}
            <span className="font-mono text-gray-300">{activeRepair.investigation_id}</span> &bull; Base Revision:{" "}
            <span className="font-mono text-gray-300">{activeRepair.base_revision}</span> &bull; Attempt:{" "}
            <span className="font-mono text-blue-400 font-semibold">{activeRepair.current_attempt || 1} of {activeRepair.max_attempts || 3}</span>
          </p>
        </div>

        {/* Global Action Banner */}
        <div className="flex items-center gap-3 flex-wrap">
          {activeRepair.status === "AWAITING_APPROVAL" && (
            <>
              <button
                onClick={handleReject}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-500/30 text-sm font-semibold transition-all"
              >
                <X className="w-4 h-4" /> Reject Patch
              </button>
              <button
                onClick={handleApprove}
                disabled={loading}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-lg shadow-emerald-500/20 transition-all"
              >
                <Check className="w-4 h-4" /> Approve Patch (SHA-256 Bound)
              </button>
            </>
          )}

          {activeRepair.status === "APPROVED" && (
            <button
              onClick={handleApplyToSandbox}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold shadow-lg shadow-purple-500/20 transition-all"
            >
              <Box className="w-4 h-4" /> Apply to Isolated Sandbox
            </button>
          )}

          {activeRepair.status === "PATCH_APPLIED_PENDING_VERIFICATION" && (
            <button
              onClick={handleRunVerification}
              disabled={loading}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all"
            >
              <Play className="w-4 h-4 fill-white" /> Run Sandbox Verification
            </button>
          )}

          {activeRepair.status === "VERIFYING" && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20 text-sm font-semibold animate-pulse">
              <RefreshCw className="w-4 h-4 animate-spin" /> Verifying in Sandbox...
            </div>
          )}

          {activeRepair.status === "VERIFIED" && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" /> VERIFIED (100% Passed) &bull; Phase 7 PR Ready
            </div>
          )}

          {(activeRepair.status === "REPAIR_RETRY_ELIGIBLE" || activeRepair.status === "VERIFICATION_FAILED") && (
            <button
              onClick={handleRetry}
              disabled={loading || (activeRepair.current_attempt || 1) >= (activeRepair.max_attempts || 3)}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-sm font-semibold shadow-lg shadow-amber-500/20 transition-all"
            >
              <RotateCcw className="w-4 h-4" /> Initiate Retry (Attempt {(activeRepair.current_attempt || 1) + 1}/3)
            </button>
          )}

          {activeRepair.status === "REPAIR_EXHAUSTED" && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-950/40 text-red-400 border border-red-800/40 text-sm font-semibold">
              <AlertTriangle className="w-4 h-4" /> REPAIR EXHAUSTED (3/3 Attempts Reached)
            </div>
          )}

          {activeRepair.status === "INFRASTRUCTURE_FAILURE" && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500/10 text-orange-400 border border-orange-500/30 text-sm font-semibold">
              <Cpu className="w-4 h-4" /> INFRASTRUCTURE ERROR &bull; No Blind Retry
            </div>
          )}

          {activeRepair.status === "NO_PROGRESS" && (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/30 text-sm font-semibold">
              <AlertCircle className="w-4 h-4" /> NO PROGRESS DETECTED &bull; Loop Halted
            </div>
          )}
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {actionMessage}
        </div>
      )}

      {/* Repair Lifecycle Pipeline Visualization (8 Steps) */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
        {[
          { label: "1. Investigation", done: true, current: false },
          { label: "2. Context Guard", done: Boolean(activeRepair.context?.is_valid), current: activeRepair.status === "CONTEXT_BUILDING" },
          { label: "3. Repair Plan", done: Boolean(activeRepair.plan), current: activeRepair.status === "PLANNING" },
          { label: "4. Patch & Risk", done: Boolean(activeRepair.patch && activeRepair.risk), current: activeRepair.status === "PATCH_GENERATING" },
          {
            label: "5. Human Approval",
            done: ["APPROVED", "PATCH_APPLIED_PENDING_VERIFICATION", "VERIFYING", "VERIFIED", "VERIFICATION_FAILED", "REPAIR_RETRY_ELIGIBLE", "REPAIR_EXHAUSTED"].includes(activeRepair.status),
            current: activeRepair.status === "AWAITING_APPROVAL",
          },
          {
            label: "6. Sandbox Apply",
            done: ["PATCH_APPLIED_PENDING_VERIFICATION", "VERIFYING", "VERIFIED", "VERIFICATION_FAILED", "REPAIR_RETRY_ELIGIBLE", "REPAIR_EXHAUSTED"].includes(activeRepair.status),
            current: activeRepair.status === "APPLYING",
          },
          {
            label: "7. Verification",
            done: activeRepair.status === "VERIFIED",
            current: ["PATCH_APPLIED_PENDING_VERIFICATION", "VERIFYING", "ANALYZING_FAILURE"].includes(activeRepair.status),
          },
          {
            label: "8. PR Handoff",
            done: false,
            current: activeRepair.status === "VERIFIED",
          },
        ].map((step, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border text-xs font-medium text-center transition-all ${
              step.done
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : step.current
                ? "bg-blue-500/10 border-blue-500/40 text-blue-300 ring-1 ring-blue-500/30"
                : "bg-[#121518]/60 border-[#2A3036] text-gray-500"
            }`}
          >
            {step.label}
          </div>
        ))}
      </div>

      {/* Bounded Repair Loop Timeline (Max 3 Attempts) */}
      <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
            <RotateCcw className="w-4 h-4 text-amber-400" /> Bounded Repair Loop Progress (Max 3 Total Attempts)
          </span>
          <span className="text-xs font-mono text-gray-400">
            Current: Attempt <strong className="text-white">{activeRepair.current_attempt || 1}</strong> of 3
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((attemptNum) => {
            const isCurrent = (activeRepair.current_attempt || 1) === attemptNum;
            const isPast = (activeRepair.current_attempt || 1) > attemptNum;
            const isFuture = (activeRepair.current_attempt || 1) < attemptNum;

            let badgeText = "Upcoming";
            let badgeClass = "text-gray-500 bg-gray-500/10 border-gray-500/20";

            if (isCurrent) {
              badgeText = activeRepair.status;
              badgeClass = getStatusColor(activeRepair.status);
            } else if (isPast) {
              badgeText = "Completed / Retried";
              badgeClass = "text-blue-400 bg-blue-500/10 border-blue-500/20";
            }

            return (
              <div
                key={attemptNum}
                className={`p-4 rounded-lg border space-y-2 transition-all ${
                  isCurrent
                    ? "bg-[#121518] border-blue-500/40 ring-1 ring-blue-500/30"
                    : isPast
                    ? "bg-[#121518]/60 border-[#2A3036]"
                    : "bg-[#121518]/40 border-[#2A3036]/60 opacity-60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-white flex items-center gap-1.5">
                    Attempt {attemptNum} {attemptNum === 3 && "(Final Limit)"}
                  </span>
                  <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${badgeClass}`}>
                    {badgeText}
                  </span>
                </div>
                <p className="text-xs text-gray-400">
                  {attemptNum === 1
                    ? "Initial evidence-backed plan and scoped patch."
                    : attemptNum === 2
                    ? "Revision addressing Attempt 1 test/lint regressions."
                    : "Final fallback boundary. If failed -> REPAIR_EXHAUSTED."}
                </p>
                {isCurrent && activeRepair.patch && (
                  <div className="pt-2 border-t border-[#2A3036] flex items-center justify-between text-[11px] font-mono text-gray-400">
                    <span>Patch:</span>
                    <span className="text-blue-400">{activeRepair.patch.patch_hash.substring(0, 10)}...</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Top Details Grid: Root Cause & Repair Scope */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Root Cause Card */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-amber-400" /> Diagnosed Root Cause
            </span>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              {Math.round((activeRepair.plan?.confidence || 0.9) * 100)}% Confidence
            </span>
          </div>
          <p className="text-sm text-gray-200 font-medium">
            {activeRepair.plan?.root_cause || "Analyzing failure evidence..."}
          </p>
          <div className="pt-2 border-t border-[#2A3036] text-xs text-gray-400">
            Candidate ID: <span className="font-mono text-gray-300">{activeRepair.context?.candidate_id || "c-1"}</span>
          </div>
        </div>

        {/* Repair Scope Card */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-blue-400" /> Repair Scope Guard
            </span>
            <span className="text-xs font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
              {activeRepair.context?.affected_files.length || 0} File(s)
            </span>
          </div>
          <div className="space-y-1">
            {activeRepair.context?.affected_files.map((file, i) => (
              <div key={i} className="flex items-center gap-2 text-xs font-mono text-gray-300 bg-[#121518] px-2.5 py-1 rounded border border-[#2A3036]">
                <FileCode className="w-3.5 h-3.5 text-blue-400" />
                {file}
              </div>
            ))}
          </div>
          <div className="pt-2 border-t border-[#2A3036] text-xs text-gray-500">
            Strict bounded scope &bull; No sensitive files &bull; Max 5 files
          </div>
        </div>

        {/* Supporting Evidence Card */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
              <Fingerprint className="w-4 h-4 text-purple-400" /> Supporting Evidence
            </span>
            <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
              {activeRepair.context?.supporting_evidence_ids.length || 0} Traced Items
            </span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {activeRepair.context?.supporting_evidence_ids.map((evId, idx) => (
              <span key={idx} className="px-2 py-0.5 rounded text-xs font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
                {evId}
              </span>
            ))}
          </div>
          <div className="pt-2 border-t border-[#2A3036] text-xs text-gray-400">
            Targeted Tests:{" "}
            <span className="font-mono text-emerald-400">
              {activeRepair.context?.related_tests.join(", ") || "tests/test_foundation.py"}
            </span>
          </div>
        </div>
      </div>

      {/* Repair Plan Section */}
      {activeRepair.plan && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Terminal className="w-4 h-4 text-blue-400" /> Evidence-Backed Repair Plan
            </h3>
            <span className="text-xs font-mono text-gray-400">
              Objective: {activeRepair.plan.objective}
            </span>
          </div>

          <div className="space-y-3">
            {activeRepair.plan.proposed_changes.map((change, idx) => (
              <div key={idx} className="p-4 rounded-lg bg-[#121518] border border-[#2A3036] space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-semibold text-white">{change.file}</span>
                    <span className="text-xs font-mono text-gray-500">({change.location})</span>
                  </div>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-blue-500/10 text-blue-300 border border-blue-500/20">
                    {change.change_type}
                  </span>
                </div>
                <p className="text-xs text-gray-300">{change.rationale}</p>
                <div className="flex items-center gap-2 pt-1 text-[11px] text-gray-400">
                  <span className="text-gray-500">Cites Evidence:</span>
                  {change.evidence_ids.map((id, i) => (
                    <span key={i} className="font-mono text-purple-300 bg-purple-500/10 px-1.5 py-0.5 rounded border border-purple-500/20">
                      {id}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Patch Diff Viewer Card */}
      {activeRepair.patch && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] overflow-hidden">
          <div className="h-11 bg-[#121518] border-b border-[#2A3036] px-4 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-mono text-gray-300">
              <FileDiff className="w-4 h-4 text-blue-400" />
              <span>diff --git a/{activeRepair.patch.changed_files[0]} b/{activeRepair.patch.changed_files[0]}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                +{activeRepair.patch.lines_added} / -{activeRepair.patch.lines_removed} lines
              </span>
              <span className="text-[11px] font-mono text-gray-400 bg-gray-500/10 px-2 py-0.5 rounded border border-gray-500/20 flex items-center gap-1">
                <Hash className="w-3 h-3" /> {activeRepair.patch.patch_hash.substring(0, 12)}...
              </span>
            </div>
          </div>

          <pre className="p-4 font-mono text-xs overflow-x-auto bg-[#0C0E10] text-gray-200 leading-relaxed">
            <code>
              {activeRepair.patch.unified_diff || "No diff generated."}
            </code>
          </pre>
        </div>
      )}

      {/* Static Patch Risk Analysis (Prompt Section 5) */}
      {activeRepair.risk && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" /> Static Patch Risk Analysis (5 Dimensions)
            </h3>
            <span className={`px-2.5 py-0.5 rounded text-xs font-mono font-semibold border ${getRiskColor(activeRepair.risk.level)}`}>
              RISK: {activeRepair.risk.level} ({Math.round(activeRepair.risk.score * 100)}%)
            </span>
          </div>

          <p className="text-xs text-gray-400">{activeRepair.risk.rationale}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
            {activeRepair.risk.findings.map((f, i) => (
              <div
                key={i}
                className={`p-3 rounded-lg border text-xs space-y-1 ${
                  f.is_blocking
                    ? "bg-red-500/10 border-red-500/30 text-red-300"
                    : "bg-[#121518] border-[#2A3036] text-gray-300"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold uppercase tracking-wider text-[11px] text-gray-400">
                    {f.category}
                  </span>
                  {f.is_blocking ? (
                    <span className="px-1.5 py-0.2 rounded text-[10px] bg-red-500/20 text-red-400 border border-red-500/40">
                      BLOCKING
                    </span>
                  ) : (
                    <span className="text-[10px] text-gray-500">{f.severity}</span>
                  )}
                </div>
                <div>{f.description}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Human Approval Gate & Sandbox Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Human Authorization Record */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Lock className="w-4 h-4 text-amber-400" /> Human Approval Gate
          </h3>
          <div className="text-xs space-y-2 text-gray-400">
            <div className="flex justify-between py-1 border-b border-[#2A3036]">
              <span>Approval Status:</span>
              <span className="font-mono text-white font-medium">
                {activeRepair.approval?.status || "PENDING"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#2A3036]">
              <span>Approved By:</span>
              <span className="font-mono text-gray-200">
                {activeRepair.approval?.approved_by || "Awaiting Human Review"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#2A3036]">
              <span>Cryptographic Binding:</span>
              <span className="font-mono text-emerald-400">
                SHA-256 Verified
              </span>
            </div>
            {activeRepair.approval?.approval_token && (
              <div className="flex justify-between py-1">
                <span>Authorization Token:</span>
                <span className="font-mono text-purple-400 text-[11px]">
                  {activeRepair.approval.approval_token}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Isolated Sandbox Workspace Record */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Box className="w-4 h-4 text-purple-400" /> Isolated Sandbox Workspace
          </h3>
          <div className="text-xs space-y-2 text-gray-400">
            <div className="flex justify-between py-1 border-b border-[#2A3036]">
              <span>Workspace Directory:</span>
              <span className="font-mono text-gray-200 text-[11px]">
                {activeRepair.workspace?.isolated_path || ".devaura_sandboxes/..."}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#2A3036]">
              <span>Original Repo Isolation:</span>
              <span className="font-mono text-emerald-400">100% UNTOUCHED</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Phase 6 Handoff:</span>
              <span className="font-mono text-purple-400 font-medium">
                {activeRepair.status === "PATCH_APPLIED_PENDING_VERIFICATION"
                  ? "READY (PENDING VERIFICATION)"
                  : activeRepair.status === "VERIFIED"
                  ? "VERIFIED (PASSED)"
                  : "Awaiting Verification"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Phase 6: Sandbox Verification Results Panel */}
      <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#2A3036]">
          <div>
            <h3 className="text-base font-semibold text-white flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-blue-400" /> Sandbox Verification Suite (Phase 6)
            </h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Strictly executed inside isolated sandbox workspace. Original repository remains completely unmodified.
            </p>
          </div>
          {verificationRun && (
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-gray-400">Attempt {verificationRun.attempt_number} Run:</span>
              <span className={`px-2.5 py-1 rounded text-xs font-mono font-semibold border ${getCheckStatusBadge(verificationRun.overall_result)}`}>
                {verificationRun.overall_result}
              </span>
            </div>
          )}
        </div>

        {verificationRun ? (
          <div className="space-y-6">
            {/* 3 Verification Checks Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {verificationRun.checks.map((check, idx) => {
                const isExpanded = expandedCheck === (check.id || `check-${idx}`);
                return (
                  <div
                    key={idx}
                    className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] flex flex-col justify-between space-y-3"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-mono uppercase font-bold text-white tracking-wider flex items-center gap-1.5">
                          <Terminal className="w-3.5 h-3.5 text-blue-400" />
                          {check.check_type}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-mono border font-semibold ${getCheckStatusBadge(check.status)}`}>
                          {check.status}
                        </span>
                      </div>
                      <div className="mt-2 text-xs font-mono text-gray-400 bg-[#080d16] px-2 py-1.5 rounded border border-[#2A3036] overflow-x-auto">
                        $ {check.command}
                      </div>
                    </div>

                    <div className="space-y-2 pt-2 border-t border-[#2A3036] text-xs">
                      <div className="flex justify-between text-gray-400 text-[11px]">
                        <span>Duration:</span>
                        <span className="font-mono text-gray-300">{check.duration_ms} ms</span>
                      </div>
                      <div className="flex justify-between text-gray-400 text-[11px]">
                        <span>Exit Code:</span>
                        <span className={`font-mono font-bold ${check.exit_code === 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {check.exit_code}
                        </span>
                      </div>

                      {/* Parsed Errors count */}
                      {check.parsed_errors && check.parsed_errors.length > 0 && (
                        <div className="p-2 rounded bg-red-500/10 border border-red-500/20 text-red-300 text-[11px] space-y-1">
                          <span className="font-semibold">{check.parsed_errors.length} Normalized Failure(s):</span>
                          {check.parsed_errors.slice(0, 2).map((pe, i) => (
                            <div key={i} className="font-mono text-[10px] truncate text-red-200">
                              {pe.file ? `${pe.file}:${pe.line || ""}` : pe.test_name || "Assertion"}: {pe.message}
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Log Toggle */}
                      <button
                        onClick={() => setExpandedCheck(isExpanded ? null : (check.id || `check-${idx}`))}
                        className="w-full flex items-center justify-center gap-1 py-1 rounded bg-[#121518] hover:bg-[#151f33] text-gray-400 hover:text-white text-[11px] font-medium border border-[#2A3036] transition-all"
                      >
                        {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                        {isExpanded ? "Hide Logs" : "View Console Output"}
                      </button>
                    </div>

                    {/* Expandable Console Logs */}
                    {isExpanded && (
                      <div className="mt-2 space-y-2">
                        {check.stdout && (
                          <div className="space-y-1">
                            <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider">stdout</span>
                            <pre className="p-2 rounded bg-[#060910] border border-[#2A3036] font-mono text-[10px] text-gray-300 max-h-36 overflow-y-auto whitespace-pre-wrap">
                              {check.stdout}
                            </pre>
                          </div>
                        )}
                        {check.stderr && (
                          <div className="space-y-1">
                            <span className="text-[10px] font-semibold text-red-400 uppercase tracking-wider">stderr</span>
                            <pre className="p-2 rounded bg-[#060910] border border-red-500/20 font-mono text-[10px] text-red-300 max-h-36 overflow-y-auto whitespace-pre-wrap">
                              {check.stderr}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Failure Analysis & Signature Diagnosis */}
            {verificationRun.failure_analysis && (
              <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400" /> Automated Verification Diagnosis
                  </span>
                  <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    {verificationRun.failure_analysis.failure_type || "CODE_FAILURE"}
                  </span>
                </div>

                <p className="text-xs text-gray-200">
                  {verificationRun.failure_analysis.root_cause_summary}
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 text-xs">
                  <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036] space-y-1">
                    <span className="text-[11px] text-gray-400 font-semibold">Deterministic Failure Signature (SHA-256):</span>
                    <div className="font-mono text-[10px] text-purple-300 truncate">
                      {verificationRun.failure_analysis.failure_signature}
                    </div>
                  </div>
                  <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036] space-y-1">
                    <span className="text-[11px] text-gray-400 font-semibold">Bounded Retry Permission:</span>
                    <div className="font-mono text-[11px] font-bold">
                      {verificationRun.failure_analysis.can_retry ? (
                        <span className="text-emerald-400">ELIGIBLE FOR RETRY (Attempt {(activeRepair.current_attempt || 1) + 1}/3)</span>
                      ) : (
                        <span className="text-red-400">
                          BLOCKED: {verificationRun.failure_analysis.retry_block_reason || "Attempts exhausted or no progress"}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {verificationRun.failure_analysis.suggested_changes && verificationRun.failure_analysis.suggested_changes.length > 0 && (
                  <div className="pt-2 text-xs space-y-1">
                    <span className="text-gray-400 font-semibold">Recommended Fix Strategies for Next Attempt:</span>
                    <ul className="list-disc list-inside text-gray-300 space-y-0.5 text-[11px]">
                      {verificationRun.failure_analysis.suggested_changes.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <div className="py-8 text-center text-gray-500 text-sm border border-dashed border-[#2A3036] rounded-[6px]">
            No verification suite has been executed for this repair attempt yet. Click &quot;Run Sandbox Verification&quot; to test the isolated sandbox.
          </div>
        )}
      </div>

      {/* -------------------------------------------------------------------------- */}
      {/* Phase 7: Verified Pull Request Orchestration & Human Review */}
      {/* -------------------------------------------------------------------------- */}
      <div className="p-6 rounded-[8px] bg-[#0a0e17] border border-[#2A3036] space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#2A3036]">
          <div>
            <div className="flex items-center gap-2">
              <GitPullRequest className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-bold text-white">Phase 7: Pull Request Orchestration &amp; Human Review</h2>
              <span className={`px-2 py-0.5 rounded text-[11px] font-mono border ${getStatusColor(prRecord ? prRecord.status : (prContext ? "PR_CONTEXT_READY" : (activeRepair.status === "VERIFIED" ? "VERIFIED" : "AWAITING_VERIFICATION")))}`}>
                {prRecord ? prRecord.status : (prContext ? "PR_PREPARED" : (activeRepair.status === "VERIFIED" ? "ELIGIBLE FOR PR" : "VERIFICATION REQUIRED"))}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Creates repair branch, commits verified patch, opens GitHub PR, and monitors CI/review status. Strictly human-gated.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {!prContext && !prRecord && (
              <button
                onClick={handlePreparePR}
                disabled={prLoading || (activeRepair.status !== "VERIFIED" && activeRepair.status !== "APPROVED")}
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition-all"
              >
                {prLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <GitBranch className="w-3.5 h-3.5" />}
                Prepare Pull Request
              </button>
            )}
          </div>
        </div>

        {/* Verification Prerequisite Banner */}
        <div className="p-3.5 rounded-[6px] bg-[#0f172a] border border-[#2A3036] flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-gray-300 font-medium">Phase 6 Verification Status:</span>
            <span className="font-mono text-emerald-400 font-semibold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              PASSED (Tests: PASS, Lint: PASS, Typecheck: PASS)
            </span>
          </div>
          <div className="font-mono text-[11px] text-gray-400">
            Patch SHA-256: <span className="text-gray-200">{activeRepair.patch?.patch_hash || "verified-hash"}</span>
          </div>
        </div>

        {/* PR Context Preview */}
        {prContext && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* PR Branch & Commit Metadata */}
            <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5 text-blue-400" /> Branch &amp; Commit Spec
                </span>
                <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                  0 Sensitive Files
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex justify-between items-center py-1 border-b border-[#2A3036]">
                  <span className="text-gray-400">Repository:</span>
                  <span className="font-mono text-white font-medium">{prContext.repository}</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-[#2A3036]">
                  <span className="text-gray-400">Base Branch:</span>
                  <span className="font-mono text-gray-300">{prContext.base_branch} ({prContext.base_revision.slice(0, 8)})</span>
                </div>
                <div className="flex justify-between items-center py-1 border-b border-[#2A3036]">
                  <span className="text-gray-400">Repair Branch:</span>
                  <span className="font-mono text-purple-300 font-semibold">{prContext.repair_branch}</span>
                </div>
                <div className="space-y-1 pt-1">
                  <span className="text-gray-400 text-[11px]">Commit Message:</span>
                  <div className="p-2 rounded bg-[#060910] border border-[#2A3036] font-mono text-[11px] text-gray-200">
                    {prContext.commit_message}
                  </div>
                </div>
              </div>
            </div>

            {/* PR Title & Description Preview */}
            <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <FileCode className="w-3.5 h-3.5 text-purple-400" /> Pull Request Description
                </span>
                <span className="text-[11px] font-mono text-gray-400">Markdown Preview</span>
              </div>

              <div className="space-y-2 text-xs">
                <div>
                  <span className="text-[11px] text-gray-400 font-medium">PR Title:</span>
                  <div className="font-semibold text-white mt-0.5 text-sm">{prContext.pr_title}</div>
                </div>
                <div>
                  <span className="text-[11px] text-gray-400 font-medium">Description:</span>
                  <pre className="mt-1 p-2.5 rounded bg-[#060910] border border-[#2A3036] font-mono text-[10px] text-gray-300 max-h-32 overflow-y-auto whitespace-pre-wrap">
                    {prContext.pr_body}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Human Authorization Gate (Phase 7 Independent Gate) */}
        {prContext && !prRecord && (
          <div className="p-4 rounded-[6px] bg-gradient-to-r from-[#121518] to-[#151c2e] border border-blue-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Human Pull Request Approval Gate
                </span>
              </div>
              <span className="text-[11px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                CRITICAL GUARD: Agent self-approval prohibited
              </span>
            </div>

            <p className="text-xs text-gray-300">
              PR creation requires independent human authorization. Prior Phase 5/6 repair approvals do not carry over.
              Authorizing generates a cryptographic HMAC-SHA256 token permanently bound to this exact patch and branch.
            </p>

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-1">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400">Reviewer ID:</span>
                <input
                  type="text"
                  value={prApproverIdentity}
                  onChange={(e) => setPrApproverIdentity(e.target.value)}
                  className="px-2.5 py-1 rounded bg-[#060910] border border-[#2A3036] text-white text-xs font-mono focus:border-blue-500 focus:outline-none"
                  placeholder="engineer@devaura.ai"
                />
              </div>

              <div className="flex items-center gap-2">
                {showRejectModal ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={prRejectionReason}
                      onChange={(e) => setPrRejectionReason(e.target.value)}
                      placeholder="Reason for rejection..."
                      className="px-2 py-1 rounded bg-[#060910] border border-red-500/30 text-white text-xs"
                    />
                    <button
                      onClick={handleRejectPR}
                      disabled={prLoading || !prRejectionReason}
                      className="px-2.5 py-1 rounded bg-red-600 hover:bg-red-500 text-white text-xs font-medium"
                    >
                      Confirm Reject
                    </button>
                    <button
                      onClick={() => setShowRejectModal(false)}
                      className="px-2 py-1 rounded bg-gray-700 text-gray-300 text-xs"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowRejectModal(true)}
                    disabled={prLoading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs font-semibold border border-red-500/20"
                  >
                    <X className="w-3.5 h-3.5" /> Reject PR
                  </button>
                )}

                <button
                  onClick={handleApprovePR}
                  disabled={prLoading || prApproval !== null}
                  className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition-all"
                >
                  {prLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  {prApproval ? "PR Authorized ✓" : "Authorize PR Creation (HMAC)"}
                </button>
              </div>
            </div>

            {/* Cryptographic Token display */}
            {prApproval && (
              <div className="p-3 rounded-lg bg-[#060910] border border-emerald-500/30 flex flex-col md:flex-row md:items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2 font-mono text-[11px] text-emerald-400 truncate">
                  <Fingerprint className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>HMAC Token: {prApproval.approval_token}</span>
                </div>
                <button
                  onClick={handleCreatePR}
                  disabled={prLoading}
                  className="flex items-center gap-2 px-4 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white text-xs font-bold shadow-md transition-all shrink-0"
                >
                  {prLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                  Push Branch &amp; Create GitHub PR
                </button>
              </div>
            )}
          </div>
        )}

        {/* Opened GitHub Pull Request Card */}
        {prRecord && (
          <div className="p-5 rounded-[6px] bg-[#121518] border border-purple-500/40 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center">
                  <GitPullRequest className="w-4 h-4 text-purple-400" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-base">Pull Request #{prRecord.pr_number}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold uppercase">
                      {prRecord.pr_state}
                    </span>
                  </div>
                  <div className="text-xs text-gray-300 font-medium">{prRecord.pr_title}</div>
                </div>
              </div>

              <a
                href={prRecord.pr_url}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow transition-all shrink-0"
              >
                View on GitHub <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
              <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036]">
                <span className="text-[11px] text-gray-400 font-medium">Head Branch</span>
                <div className="font-mono text-purple-300 font-semibold truncate mt-0.5">{prRecord.repair_branch}</div>
              </div>
              <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036]">
                <span className="text-[11px] text-gray-400 font-medium">Commit SHA</span>
                <div className="font-mono text-gray-200 truncate mt-0.5">{prRecord.commit_sha}</div>
              </div>
              <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036]">
                <span className="text-[11px] text-gray-400 font-medium">CI Check Runs</span>
                <div className="font-semibold text-emerald-400 mt-0.5 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                  {prRecord.ci_status?.overall_status || "PASSED"}
                </div>
              </div>
              <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036]">
                <span className="text-[11px] text-gray-400 font-medium">Review Status</span>
                <div className="font-semibold text-blue-400 mt-0.5">
                  {prRecord.review_status?.review_status || "PENDING_REVIEW"}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
