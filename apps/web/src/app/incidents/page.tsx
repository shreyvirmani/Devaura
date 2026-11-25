"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  GitBranch,
  GitCommit,
  Radio,
  RefreshCw,
  Search,
  ShieldAlert,
  ArrowRight,
  Layers,
  ExternalLink,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface IncidentSummary {
  id: string;
  workspace_id: string;
  repository_id: string;
  repository_full_name?: string;
  investigation_id?: string;
  investigation_status?: string;
  source: string;
  external_run_id?: string;
  external_check_id?: string;
  type: string;
  status: string;
  title: string;
  summary: string;
  commit_sha?: string;
  branch?: string;
  workflow_name?: string;
  workflow_run_url?: string;
  correlation_id: string;
  detected_at: string;
  latest_job?: {
    id: string;
    status: string;
    attempt_count: number;
    max_attempts: number;
  };
}

const EVALUATION_INCIDENTS = [
  {
    id: "HIST-001",
    repository: "pallets/flask",
    type: "TEST_FAILURE",
    title: "Config.from_file silent silent=True regression",
    status: "INVESTIGATED",
    source: "benchmark_dataset_v1",
    branch: "main",
    commit: "a1b2c3d",
    investigation_state: "COMPLETED (3/3)",
  },
  {
    id: "HIST-004",
    repository: "expressjs/express",
    type: "CI_FAILURE",
    title: "Router param middleware path decoding edge case",
    status: "INVESTIGATED",
    source: "benchmark_dataset_v1",
    branch: "master",
    commit: "e4f5a6b",
    investigation_state: "COMPLETED (3/3)",
  },
];

export default function IncidentsPage() {
  const { currentWorkspace, isLiveMode, toggleDataMode } = useAuth();
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const API_BASE = "http://localhost:8000/api/v1";

  const getHeaders = () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("devaura_token") : null;
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchIncidents = async () => {
    if (!currentWorkspace?.id || !isLiveMode) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/workspaces/${currentWorkspace.id}/incidents`, {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setIncidents(data);
      } else {
        setError("Failed to load workspace incidents.");
      }
    } catch {
      setError("Unable to reach Devaura API backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isLiveMode && currentWorkspace?.id) {
      fetchIncidents();
    }
  }, [currentWorkspace?.id, isLiveMode]);

  const getStatusBadge = (status: string) => {
    const base = "px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border";
    switch (status) {
      case "INVESTIGATED":
      case "RESOLVED":
        return <span className={`${base} bg-emerald-500/10 text-emerald-400 border-emerald-500/20`}>{status}</span>;
      case "INVESTIGATING":
      case "QUEUED":
        return <span className={`${base} bg-blue-500/10 text-blue-400 border-blue-500/20`}>{status}</span>;
      case "FAILED":
      case "BLOCKED_QUOTA":
        return <span className={`${base} bg-red-500/10 text-red-400 border-red-500/20`}>{status}</span>;
      default:
        return <span className={`${base} bg-gray-500/10 text-gray-300 border-gray-500/20`}>{status}</span>;
    }
  };

  const filteredIncidents = incidents.filter(
    (inc) => statusFilter === "ALL" || inc.status === statusFilter
  );

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#2A3036]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Incidents</h1>
            <button
              onClick={toggleDataMode}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium border transition-colors ${
                isLiveMode
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
                  : "bg-blue-500/10 text-blue-400 border-blue-500/30 hover:bg-blue-500/20"
              }`}
            >
              <Radio className="w-3.5 h-3.5 animate-pulse" />
              {isLiveMode ? "LIVE TELEMETRY (WORKSPACE)" : "EVALUATION DATA (BENCHMARK)"}
            </button>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            {isLiveMode
              ? `Real CI/CD failure incidents ingested into workspace "${currentWorkspace?.name || "Default"}" and processed by durable investigation workers.`
              : "Static historical benchmark defect cases (evaluation mode). Switch to LIVE TELEMETRY for workspace incidents."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isLiveMode && (
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-[#191D21] border border-[#2A3036] rounded-lg px-3 py-1.5 text-xs text-gray-200 focus:outline-none focus:border-blue-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="QUEUED">QUEUED</option>
              <option value="INVESTIGATING">INVESTIGATING</option>
              <option value="INVESTIGATED">INVESTIGATED</option>
              <option value="FAILED">FAILED</option>
              <option value="BLOCKED_QUOTA">BLOCKED_QUOTA</option>
            </select>
          )}
          <button
            onClick={() => isLiveMode && fetchIncidents()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#191D21] hover:bg-[#1a2337] border border-[#2A3036] text-xs font-medium text-gray-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {isLiveMode ? (
        filteredIncidents.length === 0 ? (
          <div className="p-10 rounded-xl bg-[#121518] border border-[#2A3036] text-center space-y-4 max-w-2xl mx-auto my-8">
            <div className="w-12 h-12 rounded-xl bg-[#191D21] border border-[#2A3036] flex items-center justify-center mx-auto text-gray-400">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div className="space-y-1.5">
              <h3 className="text-base font-semibold text-white">No Live Incidents Yet</h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Zero CI/CD failure incidents have been recorded in this workspace.
                When a connected repository receives a verified failing GitHub workflow_run or check_run webhook,
                an incident and durable investigation job will appear here automatically.
              </p>
            </div>
            <Link
              href="/repositories"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
            >
              Manage Connected Repositories <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          <div className="bg-[#121518] border border-[#2A3036] rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[#2A3036] text-[11px] font-mono uppercase text-gray-400 bg-[#191D21]/50">
                    <th className="py-3 px-4">Incident</th>
                    <th className="py-3 px-4">Repository</th>
                    <th className="py-3 px-4">Type / Source</th>
                    <th className="py-3 px-4">Branch / Commit</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Investigation</th>
                    <th className="py-3 px-4">Detected</th>
                    <th className="py-3 px-4 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#2A3036] text-xs">
                  {filteredIncidents.map((inc) => (
                    <tr key={inc.id} className="hover:bg-[#191D21]/40 transition-colors">
                      <td className="py-3.5 px-4">
                        <Link
                          href={`/incidents/${inc.id}`}
                          className="font-semibold text-white hover:text-blue-400 transition-colors block"
                        >
                          {inc.title}
                        </Link>
                        <span className="text-[11px] font-mono text-gray-500">
                          corr: {inc.correlation_id.slice(0, 8)}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-gray-300">
                        {inc.repository_full_name || inc.repository_id}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="text-gray-200 font-mono block">{inc.type}</span>
                        <span className="text-[11px] text-gray-500 font-mono">{inc.source}</span>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[11px] text-gray-300">
                        <div className="flex items-center gap-1">
                          <GitBranch className="w-3 h-3 text-purple-400" />
                          {inc.branch || "main"}
                        </div>
                        {inc.commit_sha && (
                          <div className="flex items-center gap-1 text-gray-500 mt-0.5">
                            <GitCommit className="w-3 h-3" />
                            {inc.commit_sha.slice(0, 7)}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">{getStatusBadge(inc.status)}</td>
                      <td className="py-3.5 px-4 font-mono text-[11px] text-gray-300">
                        {inc.investigation_status || (inc.latest_job ? `Job: ${inc.latest_job.status}` : "Pending")}
                      </td>
                      <td className="py-3.5 px-4 text-gray-400 text-[11px] font-mono">
                        {new Date(inc.detected_at).toLocaleString()}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <Link
                          href={`/incidents/${inc.id}`}
                          className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 font-medium"
                        >
                          Inspect <ArrowRight className="w-3 h-3" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )
      ) : (
        /* EVALUATION DATA MODE */
        <div className="space-y-4">
          <div className="p-4 rounded-lg bg-blue-500/5 border border-blue-500/20 text-xs text-gray-300">
            <span className="font-semibold text-white block">Evaluation Benchmark Incidents (Static Fixtures)</span>
            <span>Switch to LIVE TELEMETRY to inspect real workspace incidents ingested from GitHub webhooks.</span>
          </div>
          <div className="bg-[#121518] border border-[#2A3036] rounded-xl overflow-hidden">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#2A3036] text-[11px] font-mono uppercase text-gray-400 bg-[#191D21]/50">
                  <th className="py-3 px-4">ID</th>
                  <th className="py-3 px-4">Repository</th>
                  <th className="py-3 px-4">Title</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Branch / Commit</th>
                  <th className="py-3 px-4">Investigation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#2A3036]">
                {EVALUATION_INCIDENTS.map((row) => (
                  <tr key={row.id}>
                    <td className="py-3 px-4 font-mono text-purple-400">{row.id}</td>
                    <td className="py-3 px-4 font-mono text-gray-200">{row.repository}</td>
                    <td className="py-3 px-4 text-white">{row.title}</td>
                    <td className="py-3 px-4 font-mono text-gray-400">{row.type}</td>
                    <td className="py-3 px-4 font-mono text-gray-400">
                      {row.branch} @ {row.commit}
                    </td>
                    <td className="py-3 px-4 font-mono text-emerald-400">{row.investigation_state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
