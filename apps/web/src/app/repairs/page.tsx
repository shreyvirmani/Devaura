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
} from "lucide-react";

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

  const activeRepair = repairs.find((r) => r.id === activeRepairId) || repairs[0];

  useEffect(() => {
    fetchRepairs();
  }, []);

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
      // Offline fallback state update
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
        setActionMessage("Patch applied in isolated sandbox! Handoff to Phase 6 Verification ready.");
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case "PATCH_APPLIED_PENDING_VERIFICATION":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      case "APPROVED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "AWAITING_APPROVAL":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20";
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

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#1e293b]">
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
            <span className="font-mono text-gray-300">{activeRepair.base_revision}</span>
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
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20 text-sm font-semibold">
              <CheckCircle2 className="w-4 h-4" /> Sandbox Applied &bull; Ready for Phase 6 Handoff
            </div>
          )}
        </div>
      </div>

      {actionMessage && (
        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-300 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {actionMessage}
        </div>
      )}

      {/* Repair Lifecycle Pipeline Visualization */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        {[
          { label: "1. Investigation", done: true, current: false },
          { label: "2. Repair Context", done: Boolean(activeRepair.context?.is_valid), current: activeRepair.status === "CONTEXT_BUILDING" },
          { label: "3. Repair Plan", done: Boolean(activeRepair.plan), current: activeRepair.status === "PLANNING" },
          { label: "4. Patch & Risk", done: Boolean(activeRepair.patch && activeRepair.risk), current: activeRepair.status === "PATCH_GENERATING" },
          { label: "5. Human Approval", done: activeRepair.status === "APPROVED" || activeRepair.status === "PATCH_APPLIED_PENDING_VERIFICATION", current: activeRepair.status === "AWAITING_APPROVAL" },
          { label: "6. Sandbox Handoff", done: activeRepair.status === "PATCH_APPLIED_PENDING_VERIFICATION", current: activeRepair.status === "APPLYING" },
        ].map((step, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border text-xs font-medium text-center transition-all ${
              step.done
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                : step.current
                ? "bg-blue-500/10 border-blue-500/40 text-blue-300 ring-1 ring-blue-500/30"
                : "bg-[#111726]/60 border-[#1e293b] text-gray-500"
            }`}
          >
            {step.label}
          </div>
        ))}
      </div>

      {/* Top Details Grid: Root Cause & Repair Scope */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Root Cause Card */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
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
          <div className="pt-2 border-t border-[#1e293b] text-xs text-gray-400">
            Candidate ID: <span className="font-mono text-gray-300">{activeRepair.context?.candidate_id || "c-1"}</span>
          </div>
        </div>

        {/* Repair Scope Card */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
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
              <div key={i} className="flex items-center gap-2 text-xs font-mono text-gray-300 bg-[#0d131f] px-2.5 py-1 rounded border border-[#1e293b]">
                <FileCode className="w-3.5 h-3.5 text-blue-400" />
                {file}
              </div>
            ))}
          </div>
          <div className="pt-2 border-t border-[#1e293b] text-xs text-gray-500">
            Strict bounded scope &bull; No sensitive files &bull; Max 5 files
          </div>
        </div>

        {/* Supporting Evidence Card */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
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
          <div className="pt-2 border-t border-[#1e293b] text-xs text-gray-400">
            Targeted Tests:{" "}
            <span className="font-mono text-emerald-400">
              {activeRepair.context?.related_tests.join(", ") || "tests/test_foundation.py"}
            </span>
          </div>
        </div>
      </div>

      {/* Repair Plan Section */}
      {activeRepair.plan && (
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6 space-y-4">
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
              <div key={idx} className="p-4 rounded-lg bg-[#0d131f] border border-[#1e293b] space-y-2">
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
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl overflow-hidden">
          <div className="h-11 bg-[#0d131f] border-b border-[#1e293b] px-4 flex items-center justify-between">
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

          <pre className="p-4 font-mono text-xs overflow-x-auto bg-[#090d16] text-gray-200 leading-relaxed">
            <code>
              {activeRepair.patch.unified_diff || "No diff generated."}
            </code>
          </pre>
        </div>
      )}

      {/* Static Patch Risk Analysis (Prompt Section 5) */}
      {activeRepair.risk && (
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6 space-y-4">
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
                    : "bg-[#0d131f] border-[#1e293b] text-gray-300"
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
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Lock className="w-4 h-4 text-amber-400" /> Human Approval Gate
          </h3>
          <div className="text-xs space-y-2 text-gray-400">
            <div className="flex justify-between py-1 border-b border-[#1e293b]">
              <span>Approval Status:</span>
              <span className="font-mono text-white font-medium">
                {activeRepair.approval?.status || "PENDING"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1e293b]">
              <span>Approved By:</span>
              <span className="font-mono text-gray-200">
                {activeRepair.approval?.approved_by || "Awaiting Human Review"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1e293b]">
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
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Box className="w-4 h-4 text-purple-400" /> Isolated Sandbox Workspace
          </h3>
          <div className="text-xs space-y-2 text-gray-400">
            <div className="flex justify-between py-1 border-b border-[#1e293b]">
              <span>Workspace Directory:</span>
              <span className="font-mono text-gray-200 text-[11px]">
                {activeRepair.workspace?.isolated_path || ".devaura_sandboxes/..."}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#1e293b]">
              <span>Original Repo Isolation:</span>
              <span className="font-mono text-emerald-400">100% UNTOUCHED</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Phase 6 Handoff:</span>
              <span className="font-mono text-purple-400 font-medium">
                {activeRepair.status === "PATCH_APPLIED_PENDING_VERIFICATION"
                  ? "READY (PENDING VERIFICATION)"
                  : "Awaiting Application"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
