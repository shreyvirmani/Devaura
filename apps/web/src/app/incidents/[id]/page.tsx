"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  GitBranch,
  GitPullRequest,
  RefreshCw,
  Search,
  ShieldCheck,
  Wrench,
  XCircle,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface IncidentDetailData {
  id: string;
  workspace_id: string;
  repository_id: string;
  repository_full_name?: string;
  source: string;
  external_event_id?: string;
  external_run_id?: string;
  external_check_id?: string;
  type: string;
  status: string;
  failure_classification?: string;
  title: string;
  summary: string;
  failure_signature?: string;
  commit_sha?: string;
  branch?: string;
  workflow_name?: string;
  workflow_run_url?: string;
  correlation_id: string;
  detected_at: string;
  started_at?: string;
  resolved_at?: string;
  eligibility?: {
    eligible: boolean;
    reason: string;
  } | null;
  jobs: Array<{
    id: string;
    job_type: string;
    status: string;
    attempt_count: number;
    max_attempts: number;
    worker_id?: string;
    last_error?: string;
    failure_classification?: string;
    started_at?: string;
    completed_at?: string;
  }>;
  investigation?: {
    id: string;
    status: string;
    evidence_sufficiency: string;
    root_cause?: string;
    confidence?: number;
    evidence_items: Array<{
      id: string;
      source: string;
      type: string;
      content: string;
      repository_path?: string;
      line_start?: number;
      confidence: number;
    }>;
    root_cause_candidates: Array<{
      id: string;
      title: string;
      description: string;
      confidence: number;
      affected_files: string[];
    }>;
    investigation_steps: Array<{
      id: string;
      step_number: number;
      action: string;
      observation: string;
    }>;
  } | null;
  repair?: {
    id: string;
    status: string;
    base_revision: string;
    target_branch: string;
    current_attempt: number;
    max_attempts: number;
    plan?: {
      objective: string;
      root_cause: string;
      proposed_changes: Array<Record<string, any>>;
      tests_to_run: string[];
      confidence: number;
    } | null;
    patch?: {
      patch_hash: string;
      unified_diff: string;
      modified_files: string[];
      explanation: string;
    } | null;
    risk?: {
      risk_level: string;
      blast_radius_score: number;
      protected_paths_touched: boolean;
      secrets_detected: boolean;
      findings: string[];
    } | null;
  } | null;
  verification?: {
    id: string;
    attempt_number: number;
    overall_result: string;
    checks: Array<{
      id: string;
      check_type: string;
      command: string;
      exit_code: number;
      status: string;
      duration_ms: number;
    }>;
  } | null;
  approval?: {
    status: string;
    approved_by: string;
    patch_hash: string;
    rejection_reason?: string;
    created_at: string;
  } | null;
  pull_request?: {
    id: string;
    provider_pr_id: string;
    pr_number?: number;
    url: string;
    repair_branch?: string;
    base_branch?: string;
    commit_sha?: string;
    status: string;
  } | null;
  timeline: Array<{
    id: string;
    action: string;
    resource_type: string;
    outcome: string;
    details: Record<string, any>;
    created_at: string;
  }>;
}

const PIPELINE_STAGES = [
  "Incident received",
  "Investigation",
  "Root cause identified",
  "Repair proposed",
  "Patch generated",
  "Sandbox verification",
  "Human approval",
  "PR created",
];

function getCompletedStageIndex(data: IncidentDetailData): number {
  if (data.pull_request || data.status === "PR_CREATED") return 7;
  if (data.approval?.status === "APPROVED" || data.status === "APPROVED" || data.status === "PR_PREPARATION") return 6;
  if (data.verification?.overall_result === "PASSED" || data.status === "AWAITING_APPROVAL" || data.status === "VERIFIED") return 5;
  if (data.repair?.patch || data.status === "PATCH_APPLIED" || data.status === "VERIFICATION_QUEUED" || data.status === "VERIFYING") return 4;
  if (data.repair?.plan || data.status === "REPAIR_PENDING" || data.status === "REPAIR_PLANNING") return 3;
  if (data.investigation?.status === "COMPLETED") return 2;
  if (data.investigation || data.status === "INVESTIGATING") return 1;
  return 0;
}

export default function IncidentDetailPage() {
  const params = useParams();
  const incidentId =
    typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : "";

  const { currentWorkspace } = useAuth();
  const [data, setData] = useState<IncidentDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const API_BASE = "http://localhost:8000/api/v1";

  const getHeaders = () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("devaura_token") : null;
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchDetail = async () => {
    if (!currentWorkspace?.id || !incidentId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/incidents/${incidentId}`,
        { headers: getHeaders() }
      );
      if (res.ok) {
        setData(await res.json());
      } else {
        setError("Incident not found or access denied in this workspace.");
      }
    } catch {
      setError("Backend API unavailable or offline. Live telemetry cannot be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [currentWorkspace?.id, incidentId]);

  const handleAction = async (action: "retry" | "cancel") => {
    if (!currentWorkspace?.id || !incidentId) return;
    setSubmitting(true);
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/incidents/${incidentId}/${action}`,
        { method: "POST", headers: getHeaders() }
      );
      if (res.ok) {
        await fetchDetail();
      }
    } catch {
      setError(`Failed to ${action} incident.`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!currentWorkspace?.id || !incidentId || !data?.repair?.patch) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/incidents/${incidentId}/approve`,
        {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({
            patch_hash: data.repair.patch.patch_hash,
            base_revision: data.repair.base_revision,
          }),
        }
      );
      if (res.ok) {
        await fetchDetail();
      } else {
        const err = await res.json().catch(() => ({}));
        setError(err.detail?.error?.message || err.detail || "Approval failed.");
      }
    } catch {
      setError("Network error submitting human approval.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!currentWorkspace?.id || !incidentId) return;
    setSubmitting(true);
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/incidents/${incidentId}/reject`,
        {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({ reason: "Rejected by reviewer from Incident UI." }),
        }
      );
      if (res.ok) {
        await fetchDetail();
      }
    } catch {
      setError("Network error rejecting repair.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto py-16 text-center space-y-3">
        <RefreshCw className="w-6 h-6 animate-spin text-blue-400 mx-auto" />
        <p className="text-xs text-gray-400 font-mono">Loading incident lifecycle telemetry...</p>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-4">
        <Link href="/incidents" className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Incidents
        </Link>
        <div className="p-6 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const stageIdx = getCompletedStageIndex(data);

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Navigation & Actions */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <Link href="/incidents" className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Incidents
        </Link>
        <div className="flex items-center gap-2">
          {data.workflow_run_url && (
            <a
              href={data.workflow_run_url}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#191D21] border border-[#2A3036] text-xs text-gray-300 hover:text-white"
            >
              <ExternalLink className="w-3.5 h-3.5" /> View Workflow on GitHub
            </a>
          )}
          <button
            onClick={() => handleAction("retry")}
            disabled={submitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-medium"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Re-run Investigation
          </button>
          <button
            onClick={() => handleAction("cancel")}
            disabled={submitting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-xs font-medium"
          >
            <XCircle className="w-3.5 h-3.5" /> Cancel
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* 8-Stage Lifecycle Pipeline */}
      <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-5 space-y-3">
        <div className="flex items-center justify-between text-xs">
          <span className="font-mono uppercase text-gray-400">Live Repair Execution Pipeline</span>
          <span className="font-mono text-emerald-400 text-[11px]">LIVE TELEMETRY</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {PIPELINE_STAGES.map((label, idx) => {
            const done = idx <= stageIdx;
            return (
              <div
                key={label}
                className={`p-2.5 rounded-lg border text-[11px] font-mono flex flex-col justify-between gap-1.5 ${
                  done
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : "bg-[#191D21] border-[#2A3036] text-gray-500"
                }`}
              >
                <span className="text-[10px] opacity-70">0{idx + 1}</span>
                <span className="leading-tight font-medium">{label}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 1. Failure Summary & GitHub Metadata */}
      <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                {data.status}
              </span>
              {data.failure_classification && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  {data.failure_classification}
                </span>
              )}
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#191D21] text-gray-300 border border-[#2A3036]">
                {data.type}
              </span>
              <span className="text-xs font-mono text-gray-400">
                Correlation: {data.correlation_id}
              </span>
            </div>
            <h1 className="text-xl font-bold text-white">{data.title}</h1>
            <p className="text-xs text-gray-300 leading-relaxed">{data.summary}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 border-t border-[#2A3036] text-xs">
          <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
            <span className="text-gray-500 block text-[11px]">Repository</span>
            <span className="font-mono text-white">{data.repository_full_name || data.repository_id}</span>
          </div>
          <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
            <span className="text-gray-500 block text-[11px]">GitHub Source / Workflow</span>
            <span className="font-mono text-gray-200">{data.workflow_name || data.source}</span>
          </div>
          <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
            <span className="text-gray-500 block text-[11px]">Branch / Commit</span>
            <span className="font-mono text-gray-200 flex items-center gap-1">
              <GitBranch className="w-3 h-3 text-purple-400" />
              {data.branch || "N/A"} {data.commit_sha ? `@ ${data.commit_sha.slice(0, 7)}` : ""}
            </span>
          </div>
          <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
            <span className="text-gray-500 block text-[11px]">Detected At</span>
            <span className="font-mono text-gray-200">{new Date(data.detected_at).toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Human Approval Gate Banner */}
      {data.status === "AWAITING_APPROVAL" && data.repair?.patch && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-amber-300 font-semibold text-sm">
                <ShieldCheck className="w-4 h-4" /> Human Approval Required Before PR Creation
              </div>
              <p className="text-xs text-gray-300">
                Sandbox verification passed. Review the patch diff, affected files, risk score, and verification checks below.
                Approval is cryptographically bound to patch hash{" "}
                <span className="font-mono text-white">{data.repair.patch.patch_hash.slice(0, 12)}</span> and base revision{" "}
                <span className="font-mono text-white">{data.repair.base_revision}</span>.
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                onClick={handleReject}
                disabled={submitting}
                className="px-4 py-2 rounded-lg bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 text-red-300 text-xs font-semibold"
              >
                Reject Repair
              </button>
              <button
                onClick={handleApprove}
                disabled={submitting}
                className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold flex items-center gap-1.5"
              >
                <CheckCircle2 className="w-4 h-4" /> Approve &amp; Create PR
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Investigation, Repair, Verification & PR States */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1.5">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5 text-blue-400" /> Investigation &amp; Eligibility
          </div>
          <div className="text-sm font-mono font-semibold text-white">
            {data.investigation ? data.investigation.status : "Awaiting Worker"}
          </div>
          <p className="text-[11px] text-gray-400">
            {data.eligibility
              ? `${data.eligibility.eligible ? "Eligible" : "Not Eligible"}: ${data.eligibility.reason}`
              : "Eligibility not yet evaluated"}
          </p>
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1.5">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Wrench className="w-3.5 h-3.5 text-amber-400" /> Repair &amp; Verification
          </div>
          <div className="text-sm font-mono font-semibold text-white">
            {data.verification
              ? `Verification: ${data.verification.overall_result}`
              : data.repair
              ? data.repair.status
              : "Not Started"}
          </div>
          <p className="text-[11px] text-gray-400">
            {data.repair?.risk
              ? `Risk: ${data.repair.risk.risk_level} (blast radius ${data.repair.risk.blast_radius_score})`
              : "Human approval required before any PR or merge."}
          </p>
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1.5">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <GitPullRequest className="w-3.5 h-3.5 text-emerald-400" /> Pull Request
          </div>
          {data.pull_request ? (
            <a
              href={data.pull_request.url}
              target="_blank"
              rel="noreferrer"
              className="text-sm font-mono text-blue-400 hover:underline flex items-center gap-1"
            >
              PR #{data.pull_request.provider_pr_id} ({data.pull_request.status})
              <ExternalLink className="w-3 h-3" />
            </a>
          ) : (
            <div className="text-sm font-mono text-gray-400">No PR created</div>
          )}
        </div>
      </div>

      {/* 3. Repair Plan, Patch Diff & Sandbox Verification */}
      {data.repair && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white">Proposed Repair &amp; Sandbox Verification</h2>
            <span className="font-mono text-[11px] text-gray-400">
              Attempt {data.repair.current_attempt}/{data.repair.max_attempts} &bull; Base: {data.repair.base_revision}
            </span>
          </div>

          {data.repair.plan && (
            <div className="p-3.5 rounded-lg bg-[#191D21] border border-[#2A3036] text-xs space-y-1">
              <span className="font-semibold text-white block">Repair Objective</span>
              <p className="text-gray-300">{data.repair.plan.objective}</p>
            </div>
          )}

          {data.repair.patch && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-gray-400">
                <span>Modified Files: {data.repair.patch.modified_files.join(", ")}</span>
                <span>SHA-256: {data.repair.patch.patch_hash.slice(0, 16)}...</span>
              </div>
              <pre className="p-4 rounded-lg bg-[#0C0E10] border border-[#2A3036] text-[11px] font-mono text-emerald-300 overflow-x-auto max-h-80">
                {data.repair.patch.unified_diff}
              </pre>
            </div>
          )}

          {data.verification && (
            <div className="space-y-2">
              <h3 className="text-xs font-mono uppercase text-gray-400">
                Sandbox Verification Checks ({data.verification.overall_result})
              </h3>
              <div className="space-y-1.5">
                {data.verification.checks.map((chk) => (
                  <div
                    key={chk.id}
                    className="p-2.5 rounded bg-[#191D21] border border-[#2A3036] text-xs font-mono flex items-center justify-between"
                  >
                    <span className="text-gray-200">
                      [{chk.check_type}] {chk.command}
                    </span>
                    <span className={chk.status === "PASSED" ? "text-emerald-400" : "text-red-400"}>
                      {chk.status} (exit {chk.exit_code}, {Math.round(chk.duration_ms)}ms)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 4. Investigation Findings & Evidence */}
      {data.investigation && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-4">
          <h2 className="text-sm font-semibold text-white">Investigation Findings &amp; Evidence</h2>
          {data.investigation.root_cause && (
            <div className="p-3.5 rounded-lg bg-[#191D21] border border-[#2A3036] text-xs text-gray-200">
              <span className="font-semibold text-white block mb-1">Diagnosis Summary</span>
              {data.investigation.root_cause}
            </div>
          )}

          {data.investigation.evidence_items.length > 0 ? (
            <div className="space-y-2">
              <h3 className="text-xs font-mono uppercase text-gray-400">
                Collected Evidence ({data.investigation.evidence_items.length})
              </h3>
              {data.investigation.evidence_items.map((ev) => (
                <div key={ev.id} className="p-3 rounded bg-[#191D21] border border-[#2A3036] text-xs space-y-1">
                  <div className="flex items-center justify-between font-mono text-[11px] text-gray-400">
                    <span>{ev.source} &bull; {ev.type}</span>
                    <span>{ev.repository_path || "workspace"}</span>
                  </div>
                  <p className="text-gray-200 font-mono text-[11px] whitespace-pre-wrap">{ev.content}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400">No evidence items persisted yet.</p>
          )}
        </div>
      )}

      {/* 5. Durable Jobs & Event Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-3">
          <h2 className="text-sm font-semibold text-white">Durable Job Executions</h2>
          {data.jobs.length === 0 ? (
            <p className="text-xs text-gray-400">No jobs scheduled.</p>
          ) : (
            <div className="space-y-2">
              {data.jobs.map((job) => (
                <div key={job.id} className="p-3 rounded bg-[#191D21] border border-[#2A3036] text-xs space-y-1">
                  <div className="flex items-center justify-between font-mono">
                    <span className="text-white font-semibold">{job.job_type}</span>
                    <span className="text-blue-400">{job.status}</span>
                  </div>
                  <div className="text-[11px] text-gray-400 font-mono">
                    Attempts: {job.attempt_count}/{job.max_attempts} &bull; Worker: {job.worker_id || "unassigned"}
                  </div>
                  {job.last_error && (
                    <div className="text-[11px] text-red-400 font-mono mt-1">{job.last_error}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-3">
          <h2 className="text-sm font-semibold text-white">Audit &amp; Event Timeline</h2>
          {data.timeline.length === 0 ? (
            <p className="text-xs text-gray-400">No timeline events recorded yet.</p>
          ) : (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {data.timeline.map((ev) => (
                <div key={ev.id} className="p-2.5 rounded bg-[#191D21] border border-[#2A3036] text-xs flex items-center justify-between">
                  <div>
                    <span className="font-mono text-white block">{ev.action}</span>
                    <span className="text-[11px] text-gray-500 font-mono">
                      {new Date(ev.created_at).toLocaleString()}
                    </span>
                  </div>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[#121518] text-gray-300 border border-[#2A3036]">
                    {ev.outcome}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
