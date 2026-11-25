"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  GitBranch,
  GitCommit,
  GitPullRequest,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
  Search,
  Code2,
  Lock,
  Globe,
  Radio,
  Clock,
  Layers,
  Database,
  Unplug,
  Wrench,
  Activity,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface RepoDetailData {
  repository: {
    id: string;
    workspace_id: string;
    owner: string;
    name: string;
    full_name: string;
    provider: string;
    default_branch: string;
    clone_url: string;
    private: boolean;
    connection_status: string;
    github_installation_id?: string;
    github_repository_id?: number;
    permissions_snapshot?: Record<string, boolean>;
    last_webhook_received_at?: string;
    last_indexed_at?: string;
    created_at: string;
    updated_at: string;
  };
  installation?: {
    id: string;
    installation_id: number;
    account_name: string;
    account_type: string;
    account_avatar_url?: string;
    is_active: boolean;
  };
  health: {
    connection_status: string;
    code_intelligence: {
      status: string;
      last_indexed_at?: string;
    };
    last_webhook_received_at?: string;
    active_incidents_count: number;
    recent_investigations_count: number;
    recent_repairs_count: number;
    recent_pull_requests_count: number;
  };
}

export default function RepositoryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const repoId = typeof params?.id === "string" ? params.id : Array.isArray(params?.id) ? params.id[0] : "";

  const { currentWorkspace } = useAuth();
  const [data, setData] = useState<RepoDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isDisconnecting, setIsDisconnecting] = useState(false);

  const getHeaders = () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("devaura_token") : null;
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchRepoDetail = async () => {
    if (!currentWorkspace?.id || !repoId) return;
    setIsLoading(true);
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/github/repositories/${repoId}/detail`,
        { headers: getHeaders() }
      );

      if (res.ok) {
        const json = await res.json();
        setData(json);
      } else {
        // Fallback to generic workspace repo endpoint
        const fallbackRes = await fetch(
          `${API_BASE}/workspaces/${currentWorkspace.id}/repositories/${repoId}`,
          { headers: getHeaders() }
        );
        if (fallbackRes.ok) {
          const fallbackData = await fallbackRes.json();
          setData({
            repository: fallbackData,
            health: {
              connection_status: fallbackData.connection_status || "CONNECTED",
              code_intelligence: {
                status: fallbackData.last_indexed_at ? "indexed" : "not_indexed",
                last_indexed_at: fallbackData.last_indexed_at,
              },
              last_webhook_received_at: fallbackData.last_webhook_received_at,
              active_incidents_count: 0,
              recent_investigations_count: 0,
              recent_repairs_count: 0,
              recent_pull_requests_count: 0,
            },
          });
        } else {
          setError("Repository not found or access denied in this workspace.");
        }
      }
    } catch {
      setError("Unable to connect to Devaura API backend.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRepoDetail();
  }, [currentWorkspace?.id, repoId]);

  const handleDisconnect = async () => {
    if (!currentWorkspace?.id || !repoId) return;
    if (!confirm("Are you sure you want to disconnect this repository from Devaura?")) return;

    setIsDisconnecting(true);
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/github/repositories/${repoId}`,
        {
          method: "DELETE",
          headers: getHeaders(),
        }
      );
      if (res.ok) {
        router.push("/repositories");
      } else {
        setError("Failed to disconnect repository.");
      }
    } catch {
      setError("Network error disconnecting repository.");
    } finally {
      setIsDisconnecting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-6xl mx-auto py-16 text-center space-y-4">
        <RefreshCw className="w-6 h-6 animate-spin text-blue-400 mx-auto" />
        <p className="text-xs text-gray-400 font-mono">Loading repository telemetry...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-4">
        <Link
          href="/repositories"
          className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Repositories
        </Link>
        <div className="p-6 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs flex items-center gap-3">
          <AlertCircle className="w-5 h-5 shrink-0" />
          <span>{error || "Repository telemetry could not be loaded."}</span>
        </div>
      </div>
    );
  }

  const { repository: repo, installation, health } = data;

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      {/* Back button and breadcrumb */}
      <div className="flex items-center justify-between">
        <Link
          href="/repositories"
          className="inline-flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Repositories
        </Link>

        <div className="flex items-center gap-3">
          <a
            href={repo.clone_url ? repo.clone_url.replace(".git", "") : `https://github.com/${repo.owner}/${repo.name}`}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#191D21] hover:bg-[#1a2337] border border-[#2A3036] text-xs font-medium text-gray-300 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" /> View on GitHub
          </a>
          <button
            onClick={handleDisconnect}
            disabled={isDisconnecting}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-xs font-medium text-red-400 transition-colors"
          >
            <Unplug className="w-3.5 h-3.5" />
            {isDisconnecting ? "Disconnecting..." : "Disconnect"}
          </button>
        </div>
      </div>

      {/* Repository Main Header Card */}
      <div className="bg-[#121518] border border-[#2A3036] rounded-xl p-6 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-white font-mono">
                {repo.full_name || `${repo.owner}/${repo.name}`}
              </h1>
              <span className="px-2 py-0.5 rounded text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center gap-1">
                {repo.private ? <Lock className="w-3 h-3 text-amber-400" /> : <Globe className="w-3 h-3 text-blue-400" />}
                {repo.private ? "Private" : "Public"}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-xs font-mono uppercase font-semibold ${
                  repo.connection_status === "CONNECTED"
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-red-500/10 text-red-400 border border-red-500/20"
                }`}
              >
                {repo.connection_status}
              </span>
            </div>
            <p className="text-xs text-gray-400 flex items-center gap-2">
              <span>Default Branch:</span>
              <span className="font-mono text-gray-200 flex items-center gap-1">
                <GitBranch className="w-3 h-3 text-purple-400" />
                {repo.default_branch}
              </span>
              <span>&bull;</span>
              <span>Provider:</span>
              <span className="font-mono text-gray-300">{repo.provider}</span>
            </p>
          </div>

          {installation && (
            <div className="text-right text-xs text-gray-400 space-y-0.5 bg-[#191D21] p-3 rounded-lg border border-[#2A3036]">
              <span className="block text-gray-500 text-[10px] uppercase font-mono">GitHub App Installation</span>
              <span className="font-semibold text-white block">{installation.account_name}</span>
              <span className="font-mono text-[11px] text-gray-400">ID #{installation.installation_id}</span>
            </div>
          )}
        </div>
      </div>

      {/* Devaura Readiness & Telemetry Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Code Intelligence */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Code2 className="w-3.5 h-3.5 text-blue-400" />
            Code Intelligence
          </div>
          <div className="text-base font-semibold text-white capitalize font-mono">
            {health.code_intelligence.status === "indexed" ? (
              <span className="text-emerald-400 flex items-center gap-1 text-sm">
                <CheckCircle2 className="w-4 h-4" /> Indexed
              </span>
            ) : (
              <span className="text-amber-400 text-sm">Ready to Index</span>
            )}
          </div>
          <p className="text-[11px] text-gray-500 truncate">
            {health.code_intelligence.last_indexed_at
              ? `Indexed: ${new Date(health.code_intelligence.last_indexed_at).toLocaleDateString()}`
              : "No AST index generated yet"}
          </p>
        </div>

        {/* Webhook Activity */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-purple-400" />
            Webhook Ingestion
          </div>
          <div className="text-base font-semibold text-white font-mono text-sm">
            {health.last_webhook_received_at ? (
              <span className="text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" /> Active
              </span>
            ) : (
              <span className="text-gray-400">Awaiting Events</span>
            )}
          </div>
          <p className="text-[11px] text-gray-500 truncate">
            {health.last_webhook_received_at
              ? new Date(health.last_webhook_received_at).toLocaleTimeString()
              : "No GitHub events received"}
          </p>
        </div>

        {/* Active Incidents */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
            Active Incidents
          </div>
          <div className="text-base font-semibold text-white font-mono">
            {health.active_incidents_count}
          </div>
          <p className="text-[11px] text-gray-500">
            {health.active_incidents_count === 0 ? "Zero ongoing investigations" : "In diagnosis"}
          </p>
        </div>

        {/* Verified Repairs */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-4 space-y-1">
          <div className="text-xs text-gray-400 flex items-center gap-1.5">
            <Wrench className="w-3.5 h-3.5 text-emerald-400" />
            Repairs &amp; PRs
          </div>
          <div className="text-base font-semibold text-white font-mono">
            {health.recent_repairs_count} Repairs &bull; {health.recent_pull_requests_count} PRs
          </div>
          <p className="text-[11px] text-gray-500">
            {health.recent_repairs_count === 0 ? "No repair attempts recorded" : "Sandbox verified"}
          </p>
        </div>
      </div>

      {/* Detailed Technical Information Tabs */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Repository Properties */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-6 space-y-4">
          <h3 className="text-sm font-semibold text-white">Repository Configuration</h3>
          <div className="space-y-3 text-xs">
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <span className="text-gray-400">Clone URL</span>
              <span className="font-mono text-gray-200 select-all">{repo.clone_url}</span>
            </div>
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <span className="text-gray-400">GitHub Repository ID</span>
              <span className="font-mono text-gray-200">{repo.github_repository_id || "N/A"}</span>
            </div>
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <span className="text-gray-400">Created At</span>
              <span className="font-mono text-gray-300">
                {new Date(repo.created_at).toLocaleString()}
              </span>
            </div>
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <span className="text-gray-400">Last Synced</span>
              <span className="font-mono text-gray-300">
                {new Date(repo.updated_at).toLocaleString()}
              </span>
            </div>
          </div>
        </div>

        {/* Operational Safety & Boundaries */}
        <div className="bg-[#121518] border border-[#2A3036] rounded-lg p-6 space-y-4">
          <h3 className="text-sm font-semibold text-white">Devaura Safety Boundary</h3>
          <div className="space-y-3 text-xs">
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <div>
                <span className="font-semibold text-gray-200 block">Isolated Verification Sandbox</span>
                <span className="text-gray-400 text-[11px]">All patches execute hidden validation tests in ephemeral environments</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono text-[10px]">
                ENFORCED
              </span>
            </div>
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <div>
                <span className="font-semibold text-gray-200 block">Human Approval Gate</span>
                <span className="text-gray-400 text-[11px]">Pull requests are never automatically merged or deployed</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono text-[10px]">
                MANDATORY
              </span>
            </div>
            <div className="p-3 rounded bg-[#191D21] border border-[#2A3036] flex items-center justify-between">
              <div>
                <span className="font-semibold text-gray-200 block">Replay-Resistant Webhooks</span>
                <span className="text-gray-400 text-[11px]">HMAC-SHA256 signature and delivery UUID uniqueness enforced</span>
              </div>
              <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono text-[10px]">
                ACTIVE
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
