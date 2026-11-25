"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Clock,
  ExternalLink,
  GitBranch,
  GitCommit,
  GitPullRequest,
  RefreshCw,
  Search,
  ShieldCheck,
  Terminal,
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
  } | null;
  pull_request?: {
    id: string;
    provider_pr_id: string;
    url: string;
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

export default function IncidentDetailPage() {
  const params = useParams();
  const incidentId =
    typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : "";

  const { currentWorkspace } = useAuth();
  const [data, setData] = useState<IncidentDetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      setError("Failed to connect to Devaura API backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [currentWorkspace?.id, incidentId]);

  const handleAction = async (action: "retry" | "cancel") => {
    if (!currentWorkspace?.id || !incidentId) return;
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

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-4">
        <Link href="/incidents" className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-white">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Incidents
        </Link>
        <div className="p-6 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error || "Incident details unavailable."}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Navigation & Actions */}
      <div className="flex items-center justify-between">
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
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Re-run Investigation
          </button>
          <button
            onClick={() => handleAction("cancel")}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-xs font-medium"
          >
            <XCircle className="w-3.5 h-3.5" /> Cancel
          </button>
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

      {/* 2. Investigation, Repair, Verification & PR States */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1.5">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5 text-blue-400" /> Investigation State
          </div>
          <div className="text-sm font-mono font-semibold text-white">
            {data.investigation ? data.investigation.status : "Awaiting Worker"}
          </div>
          <p className="text-[11px] text-gray-400">
            {data.investigation
              ? `Sufficiency: ${data.investigation.evidence_sufficiency}`
              : "Queued for asynchronous investigation"}
          </p>
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1.5">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Wrench className="w-3.5 h-3.5 text-amber-400" /> Repair & Verification
          </div>
          <div className="text-sm font-mono font-semibold text-white">
            {data.repair ? data.repair.status : "Not Started"}
          </div>
          <p className="text-[11px] text-gray-400">
            Human approval required before any PR or merge.
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

      {/* 3. Investigation Evidence & Root Cause */}
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

      {/* 4. Durable Jobs & Event Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-3">
          <h2 className="text-sm font-semibold text-white">Durable Job Executions</h2>
          {data.jobs.length === 0 ? (
            <p className="text-xs text-gray-400">No jobs scheduled (e.g. blocked by workspace quota).</p>
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
