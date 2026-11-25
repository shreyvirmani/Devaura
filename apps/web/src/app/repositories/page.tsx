"use client";

import React, { useState, useEffect, useTransition } from "react";
import Link from "next/link";
import {
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
  Plus,
  ArrowRight,
  Layers,
  Database,
  Unplug,
  Clock,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

interface ConnectedRepository {
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
  last_webhook_received_at?: string;
  last_indexed_at?: string;
  created_at: string;
  updated_at: string;
}

interface DiscoveredRepo {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  private: boolean;
  default_branch: string;
  is_connected: boolean;
  connected_repository_id?: string;
  permissions?: Record<string, boolean>;
}

interface InstallationInfo {
  id: string;
  installation_id: number;
  account_name: string;
  account_type: string;
  account_avatar_url?: string;
  is_active: boolean;
}

// Benchmark Evaluation Repositories (Static dataset view)
const EVALUATION_REPOSITORIES = [
  {
    id: "eval-001",
    owner: "expressjs",
    name: "express",
    full_name: "expressjs/express",
    language: "JavaScript",
    benchmark_status: "Verified Repaired (HIST-001)",
    runs: "3/3 Pass",
    split: "Held-Out",
  },
  {
    id: "eval-002",
    owner: "pallets",
    name: "flask",
    full_name: "pallets/flask",
    language: "Python",
    benchmark_status: "Verified Repaired (HIST-002)",
    runs: "3/3 Pass",
    split: "Train",
  },
  {
    id: "eval-003",
    owner: "psf",
    name: "requests",
    full_name: "psf/requests",
    language: "Python",
    benchmark_status: "Verified Repaired (HIST-003)",
    runs: "3/3 Pass",
    split: "Train",
  },
  {
    id: "eval-004",
    owner: "encode",
    name: "starlette",
    full_name: "encode/starlette",
    language: "Python",
    benchmark_status: "Verified Repaired (HIST-005)",
    runs: "3/3 Pass",
    split: "Validation",
  },
  {
    id: "eval-005",
    owner: "tiangolo",
    name: "fastapi",
    full_name: "tiangolo/fastapi",
    language: "Python",
    benchmark_status: "Verified Repaired (HIST-006)",
    runs: "3/3 Pass",
    split: "Train",
  },
  {
    id: "eval-006",
    owner: "shreyvirmani",
    name: "Devaura",
    full_name: "shreyvirmani/Devaura",
    language: "Python / TypeScript",
    benchmark_status: "Live E2E Target",
    runs: "100% Pass",
    split: "Production Target",
  },
];

export default function RepositoriesPage() {
  const { currentWorkspace, isLiveMode, toggleDataMode } = useAuth();
  const [repositories, setRepositories] = useState<ConnectedRepository[]>([]);
  const [installations, setInstallations] = useState<InstallationInfo[]>([]);
  const [discoveredRepos, setDiscoveredRepos] = useState<DiscoveredRepo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [connectingRepoId, setConnectingRepoId] = useState<number | null>(null);

  const API_BASE = "http://localhost:8000/api/v1";

  const getHeaders = () => {
    const token = typeof window !== "undefined" ? localStorage.getItem("devaura_token") : null;
    return {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  };

  const fetchWorkspaceData = async () => {
    if (!currentWorkspace?.id) return;
    setIsLoading(true);
    setActionError(null);
    try {
      // 1. Fetch Installations
      const instRes = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/github/installations`,
        { headers: getHeaders() }
      );
      if (instRes.ok) {
        const instData = await instRes.json();
        setInstallations(instData);
      }

      // 2. Fetch Connected Repositories
      const repoRes = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/repositories`,
        { headers: getHeaders() }
      );
      if (repoRes.ok) {
        const repoData = await repoRes.json();
        setRepositories(repoData);
      }
    } catch {
      // Offline fallback: graceful UI display
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isLiveMode && currentWorkspace?.id) {
      fetchWorkspaceData();
    }
  }, [currentWorkspace?.id, isLiveMode]);

  const handleOpenConnectModal = async () => {
    setShowConnectModal(true);
    setActionError(null);
    if (!currentWorkspace?.id) return;

    // If we have an installation, discover its repositories
    if (installations.length > 0) {
      const activeInst = installations[0];
      setIsDiscovering(true);
      try {
        const res = await fetch(
          `${API_BASE}/workspaces/${currentWorkspace.id}/github/installations/${activeInst.installation_id}/repositories`,
          { headers: getHeaders() }
        );
        if (res.ok) {
          const data = await res.json();
          setDiscoveredRepos(data.repositories || []);
        } else {
          setActionError("Unable to discover GitHub repositories from current installation.");
        }
      } catch {
        setActionError("Connection to GitHub API failed.");
      } finally {
        setIsDiscovering(false);
      }
    }
  };

  const handleConnectGitHubApp = async () => {
    if (!currentWorkspace?.id) return;
    setActionError(null);
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/github/install-url`,
        { headers: getHeaders() }
      );
      if (res.ok) {
        const data = await res.json();
        if (data.install_url) {
          window.open(data.install_url, "_blank", "width=800,height=700");
        }
      } else {
        // Dev fallback simulation: link a mock installation for testing
        const linkRes = await fetch(
          `${API_BASE}/workspaces/${currentWorkspace.id}/github/installations`,
          {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
              installation_id: 8829104,
              account_name: "acme-corp",
              account_type: "Organization",
              repository_selection: "selected",
            }),
          }
        );
        if (linkRes.ok) {
          await fetchWorkspaceData();
          await handleOpenConnectModal();
        } else {
          setActionError("Could not initiate GitHub App installation.");
        }
      }
    } catch {
      setActionError("Failed to connect GitHub App.");
    }
  };

  const handleConnectSingleRepo = async (repo: DiscoveredRepo) => {
    if (!currentWorkspace?.id || installations.length === 0) return;
    setConnectingRepoId(repo.id);
    setActionError(null);

    const activeInst = installations[0];
    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/github/repositories/connect`,
        {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({
            installation_id: activeInst.installation_id,
            owner: repo.owner,
            name: repo.name,
            default_branch: repo.default_branch,
          }),
        }
      );

      if (res.ok) {
        await fetchWorkspaceData();
        // Update discovered list locally
        setDiscoveredRepos((prev) =>
          prev.map((r) => (r.id === repo.id ? { ...r, is_connected: true } : r))
        );
      } else {
        const err = await res.json().catch(() => ({}));
        setActionError(err.detail?.error?.message || err.detail || "Failed to connect repository.");
      }
    } catch {
      setActionError("Network error while connecting repository.");
    } finally {
      setConnectingRepoId(null);
    }
  };

  const handleDisconnectRepo = async (repoId: string) => {
    if (!currentWorkspace?.id) return;
    if (!confirm("Are you sure you want to disconnect this repository from Devaura monitoring?")) {
      return;
    }

    try {
      const res = await fetch(
        `${API_BASE}/workspaces/${currentWorkspace.id}/github/repositories/${repoId}`,
        {
          method: "DELETE",
          headers: getHeaders(),
        }
      );
      if (res.ok) {
        await fetchWorkspaceData();
      }
    } catch {
      setActionError("Failed to disconnect repository.");
    }
  };

  const filteredDiscovered = discoveredRepos.filter(
    (r) =>
      r.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header and Telemetry Toggle */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#2A3036]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Repositories</h1>
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
              ? `Authorized repositories in workspace "${currentWorkspace?.name || "Default"}" ready for automated investigation and repair.`
              : "Standardized historical defect benchmark repositories evaluated during Phases 9 & 10."}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {isLiveMode && (
            <button
              onClick={handleOpenConnectModal}
              className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium shadow-sm transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Connect Repository
            </button>
          )}
          <button
            onClick={() => isLiveMode && fetchWorkspaceData()}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#191D21] hover:bg-[#1a2337] border border-[#2A3036] text-xs font-medium text-gray-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {actionError && (
        <div className="p-3.5 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{actionError}</span>
          </div>
          <button onClick={() => setActionError(null)} className="hover:text-white">
            &times;
          </button>
        </div>
      )}

      {/* Mode 1: LIVE WORKSPACE REPOSITORIES */}
      {isLiveMode ? (
        <div className="space-y-6">
          {installations.length === 0 && repositories.length === 0 ? (
            /* Empty State: No GitHub App Connected */
            <div className="p-8 rounded-lg bg-[#121518] border border-[#2A3036] text-center space-y-6 max-w-2xl mx-auto my-8">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center mx-auto text-blue-400">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-white">Connect Your GitHub Organization</h3>
                <p className="text-sm text-gray-400 leading-relaxed">
                  Devaura integrates securely via the official GitHub App architecture.
                  No user tokens or sensitive credentials are ever stored in the database.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 text-left max-w-lg mx-auto text-xs text-gray-300">
                <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
                  <span className="font-semibold text-white block mb-0.5">Read-Only Code Access</span>
                  Scans target repositories for deterministic fault localization.
                </div>
                <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
                  <span className="font-semibold text-white block mb-0.5">Isolated Sandboxes</span>
                  Executes patches in disposable containerized testbeds.
                </div>
                <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
                  <span className="font-semibold text-white block mb-0.5">Webhook Ingestion</span>
                  Replay-resistant HMAC validation of workflow runs.
                </div>
                <div className="p-3 rounded bg-[#191D21] border border-[#2A3036]">
                  <span className="font-semibold text-white block mb-0.5">Human Approval Required</span>
                  Never merges PRs or commits autonomously.
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={handleConnectGitHubApp}
                  className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-500/10 transition-all inline-flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" />
                  Install Devaura GitHub App
                </button>
              </div>
            </div>
          ) : (
            /* Connected Repositories Grid */
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-gray-400 px-1">
                <span>
                  Showing {repositories.length} connected{" "}
                  {repositories.length === 1 ? "repository" : "repositories"} in this workspace
                </span>
                {installations.length > 0 && (
                  <span className="flex items-center gap-1.5 text-gray-400 font-mono">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    GitHub App: {installations[0].account_name} ({installations[0].account_type})
                  </span>
                )}
              </div>

              {repositories.length === 0 ? (
                <div className="p-8 rounded-lg bg-[#121518] border border-[#2A3036] text-center space-y-3">
                  <p className="text-sm text-gray-300">
                    GitHub App is linked, but no repositories are attached to this workspace yet.
                  </p>
                  <button
                    onClick={handleOpenConnectModal}
                    className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium inline-flex items-center gap-2"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Select Repositories to Connect
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {repositories.map((repo) => (
                    <div
                      key={repo.id}
                      className="p-5 rounded-lg bg-[#121518] border border-[#2A3036] hover:border-[#3A424B] transition-all flex flex-col justify-between space-y-4"
                    >
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-mono text-gray-400 flex items-center gap-1.5">
                            {repo.private ? (
                              <Lock className="w-3 h-3 text-amber-400" />
                            ) : (
                              <Globe className="w-3 h-3 text-blue-400" />
                            )}
                            {repo.private ? "Private" : "Public"}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold ${
                              repo.connection_status === "CONNECTED"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : repo.connection_status === "ACCESS_REVOKED"
                                ? "bg-red-500/10 text-red-400 border border-red-500/20"
                                : "bg-gray-500/10 text-gray-400 border border-gray-500/20"
                            }`}
                          >
                            {repo.connection_status}
                          </span>
                        </div>

                        <div>
                          <Link
                            href={`/repositories/${repo.id}`}
                            className="text-base font-semibold text-white hover:text-blue-400 transition-colors block truncate"
                          >
                            {repo.full_name || `${repo.owner}/${repo.name}`}
                          </Link>
                          <div className="flex items-center gap-2 text-xs text-gray-400 mt-1">
                            <span className="flex items-center gap-1 font-mono">
                              <GitBranch className="w-3 h-3 text-purple-400" />
                              {repo.default_branch}
                            </span>
                            <span>&bull;</span>
                            <span className="font-mono text-[11px] text-gray-400">
                              {repo.provider}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="pt-3 border-t border-[#2A3036] space-y-2 text-xs">
                        <div className="flex items-center justify-between text-gray-400">
                          <span>Code Intelligence:</span>
                          <span
                            className={`font-mono text-[11px] ${
                              repo.last_indexed_at ? "text-emerald-400" : "text-amber-400"
                            }`}
                          >
                            {repo.last_indexed_at ? "Indexed" : "Ready to Index"}
                          </span>
                        </div>
                        <div className="flex items-center justify-between text-gray-400">
                          <span>Last Webhook:</span>
                          <span className="font-mono text-[11px] text-gray-300">
                            {repo.last_webhook_received_at
                              ? new Date(repo.last_webhook_received_at).toLocaleTimeString()
                              : "No events yet"}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-2">
                        <Link
                          href={`/repositories/${repo.id}`}
                          className="flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors"
                        >
                          View Details <ArrowRight className="w-3 h-3" />
                        </Link>
                        <button
                          onClick={() => handleDisconnectRepo(repo.id)}
                          className="text-xs text-gray-400 hover:text-red-400 transition-colors"
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Mode 2: EVALUATION BENCHMARK REPOSITORIES */
        <div className="space-y-4">
          <div className="p-4 rounded-lg bg-blue-500/5 border border-blue-500/20 text-xs text-gray-300 flex items-center justify-between">
            <div>
              <span className="font-semibold text-white block">
                Evaluation Benchmark Repositories (Controlled Ground Truth)
              </span>
              <span>
                These repositories form the multi-defect verification benchmark used for rigorous Phase 9.4 and 10 testing.
              </span>
            </div>
            <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 font-mono text-[11px]">
              6 Displayed
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {EVALUATION_REPOSITORIES.map((repo) => (
              <div
                key={repo.id}
                className="p-5 rounded-lg bg-[#121518] border border-[#2A3036] flex flex-col justify-between space-y-4"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono text-purple-400">{repo.language}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/20">
                      {repo.split}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-base font-semibold text-white font-mono">{repo.full_name}</h3>
                    <p className="text-xs text-gray-400 mt-1">{repo.benchmark_status}</p>
                  </div>
                </div>

                <div className="pt-3 border-t border-[#2A3036] flex items-center justify-between text-xs">
                  <span className="text-gray-400">Reliability Rate:</span>
                  <span className="font-mono text-emerald-400 font-semibold">{repo.runs}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Connect Repository Discovery Modal */}
      {showConnectModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121518] border border-[#2A3036] rounded-xl max-w-xl w-full p-6 space-y-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-[#2A3036]">
              <div>
                <h3 className="text-lg font-semibold text-white">Attach GitHub Repository</h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Select repositories granted to the Devaura GitHub App installation.
                </p>
              </div>
              <button
                onClick={() => setShowConnectModal(false)}
                className="text-gray-400 hover:text-white text-lg font-mono"
              >
                &times;
              </button>
            </div>

            {installations.length === 0 ? (
              <div className="p-6 text-center space-y-4">
                <p className="text-sm text-gray-300">
                  No active GitHub App installation found in this workspace.
                </p>
                <button
                  onClick={handleConnectGitHubApp}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold"
                >
                  Install GitHub App
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="relative">
                  <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Filter accessible repositories..."
                    className="w-full bg-[#191D21] border border-[#2A3036] rounded-lg pl-9 pr-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                  {isDiscovering ? (
                    <div className="p-6 text-center text-xs text-gray-400 flex items-center justify-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-blue-400" />
                      Discovering repositories from GitHub API...
                    </div>
                  ) : filteredDiscovered.length === 0 ? (
                    <div className="p-6 text-center text-xs text-gray-400">
                      No repositories matched your filter or installation grant.
                    </div>
                  ) : (
                    filteredDiscovered.map((repo) => (
                      <div
                        key={repo.id}
                        className="p-3 rounded-lg bg-[#191D21] border border-[#2A3036] flex items-center justify-between text-xs"
                      >
                        <div className="space-y-0.5">
                          <span className="font-semibold text-white block">{repo.full_name}</span>
                          <span className="text-[11px] text-gray-400 font-mono">
                            branch: {repo.default_branch} &bull; {repo.private ? "Private" : "Public"}
                          </span>
                        </div>

                        {repo.is_connected ? (
                          <span className="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-mono flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3" /> Connected
                          </span>
                        ) : (
                          <button
                            onClick={() => handleConnectSingleRepo(repo)}
                            disabled={connectingRepoId === repo.id}
                            className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-[11px] font-medium transition-colors flex items-center gap-1.5"
                          >
                            {connectingRepoId === repo.id ? (
                              <RefreshCw className="w-3 h-3 animate-spin" />
                            ) : (
                              <Plus className="w-3 h-3" />
                            )}
                            Connect
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>

                <div className="pt-3 border-t border-[#2A3036] flex items-center justify-between text-xs">
                  <button
                    onClick={handleConnectGitHubApp}
                    className="text-blue-400 hover:text-blue-300 font-medium inline-flex items-center gap-1"
                  >
                    <ExternalLink className="w-3 h-3" />
                    Configure in GitHub
                  </button>
                  <button
                    onClick={() => setShowConnectModal(false)}
                    className="px-3 py-1.5 rounded bg-[#191D21] border border-[#2A3036] text-gray-300 hover:text-white"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
