"use client";

import React, { useState } from "react";
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
} from "lucide-react";

export default function RepositoriesPage() {
  const [activeTab, setActiveTab] = useState<"overview" | "commits" | "prs" | "ci">("overview");

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#2A3036]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">shreyvirmani / Devaura</h1>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
              public
            </span>
            <span className="px-2 py-0.5 rounded text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              MCP Monitored
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Devaura AI Software Repair &amp; Maintenance Platform &bull; Branch:{" "}
            <span className="font-mono text-gray-300">main</span>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="https://github.com/shreyvirmani/Devaura"
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#191D21] hover:bg-[#1a2337] border border-[#2A3036] text-xs font-medium text-gray-300 transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            View on GitHub
          </a>
        </div>
      </div>

      {/* Repository Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-4">
          <div className="text-xs text-gray-400 mb-1 flex items-center gap-1.5">
            <Code2 className="w-3.5 h-3.5 text-blue-400" />
            Language Stack
          </div>
          <div className="text-sm font-semibold text-white">Python 3.12 / Next.js 15</div>
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-4">
          <div className="text-xs text-gray-400 mb-1 flex items-center gap-1.5">
            <GitBranch className="w-3.5 h-3.5 text-purple-400" />
            Default Branch
          </div>
          <div className="text-sm font-semibold text-white font-mono">main</div>
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-4">
          <div className="text-xs text-gray-400 mb-1 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            CI Status
          </div>
          <div className="text-sm font-semibold text-emerald-400 flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4" /> Passing (10/10)
          </div>
        </div>

        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-4">
          <div className="text-xs text-gray-400 mb-1 flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5 text-amber-400" />
            Active Issues
          </div>
          <div className="text-sm font-semibold text-white">1 Under Diagnosis</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-[#2A3036] space-x-6">
        {(["overview", "commits", "prs", "ci"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-3 text-sm font-medium capitalize border-b-2 transition-colors ${
              activeTab === tab
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            {tab === "prs" ? "Pull Requests" : tab === "ci" ? "CI Workflows" : tab}
          </button>
        ))}
      </div>

      {/* Tab Contents */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6">
              <h3 className="text-base font-semibold text-white mb-3">Repository Architecture Profile</h3>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036]">
                  <span className="text-gray-500 block mb-1">Backend Framework</span>
                  <span className="text-gray-200 font-mono font-medium">FastAPI + Async SQLAlchemy</span>
                </div>
                <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036]">
                  <span className="text-gray-500 block mb-1">Frontend Framework</span>
                  <span className="text-gray-200 font-mono font-medium">Next.js 14/15 App Router</span>
                </div>
                <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036]">
                  <span className="text-gray-500 block mb-1">Testing Framework</span>
                  <span className="text-gray-200 font-mono font-medium">Pytest + Asyncio Runner</span>
                </div>
                <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036]">
                  <span className="text-gray-500 block mb-1">Protocol Standard</span>
                  <span className="text-gray-200 font-mono font-medium">MCP Native Specification</span>
                </div>
              </div>
            </div>

            <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6">
              <h3 className="text-base font-semibold text-white mb-3">Devaura Analysis History</h3>
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036] flex items-center justify-between text-xs">
                  <div>
                    <span className="font-semibold text-gray-200 block">Analysis #01: Issue #42 Initial Intake</span>
                    <span className="text-gray-400">Diagnosis complete &bull; Malformed token handling</span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                    PASS
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6 space-y-4">
            <h3 className="text-base font-semibold text-white">Connected Branches</h3>
            <div className="space-y-2 text-xs font-mono">
              <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036] flex items-center justify-between">
                <span className="text-blue-400 flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5" /> main
                </span>
                <span className="text-gray-500">default</span>
              </div>
              <div className="p-2.5 rounded bg-[#121518] border border-[#2A3036] flex items-center justify-between text-gray-400">
                <span className="flex items-center gap-1.5">
                  <GitBranch className="w-3.5 h-3.5" /> devaura/repair-issue-42
                </span>
                <span className="text-amber-400 text-[10px]">staged</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === "commits" && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6">
          <h3 className="text-base font-semibold text-white mb-4">Recent Git History</h3>
          <div className="space-y-3 font-mono text-xs">
            <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036] flex items-center justify-between">
              <div>
                <span className="text-gray-200 font-semibold block">feat(backend): implement FastAPI application, SQLAlchemy models, health & lifecycle routes</span>
                <span className="text-gray-500 text-[11px]">Shrey Virmani &bull; main</span>
              </div>
              <span className="text-blue-400">66da821</span>
            </div>
            <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036] flex items-center justify-between">
              <div>
                <span className="text-gray-200 font-semibold block">docs: establish architecture specifications, security model, and initial foundation</span>
                <span className="text-gray-500 text-[11px]">Shrey Virmani &bull; main</span>
              </div>
              <span className="text-blue-400">99819cd</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === "prs" && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6">
          <h3 className="text-base font-semibold text-white mb-4">Pull Requests</h3>
          <p className="text-xs text-gray-400">No open human PRs currently. Devaura repair PRs require explicit Human Approval.</p>
        </div>
      )}

      {activeTab === "ci" && (
        <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-6">
          <h3 className="text-base font-semibold text-white mb-4">CI / CD Workflow Executions</h3>
          <div className="p-3 rounded-lg bg-[#121518] border border-[#2A3036] flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <div>
                <span className="font-semibold text-gray-200">pytest unit test matrix</span>
                <span className="text-gray-500 block text-[11px]">10/10 passed &bull; runtime: 3.37s</span>
              </div>
            </div>
            <span className="text-emerald-400 font-mono text-[11px]">SUCCESS</span>
          </div>
        </div>
      )}
    </div>
  );
}
