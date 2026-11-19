"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  GitBranch,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowUpRight,
  ShieldAlert,
  Play,
  Activity,
  Layers,
  Terminal,
} from "lucide-react";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtext: string;
  icon: React.ComponentType<{ className?: string }>;
  accentColor: string;
}

function MetricCard({ title, value, subtext, icon: Icon, accentColor }: MetricCardProps) {
  return (
    <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 hover:border-gray-700 transition-all">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-gray-400">{title}</span>
        <div className={`p-2 rounded-lg ${accentColor}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className="text-2xl font-bold tracking-tight text-white mb-1">{value}</div>
      <span className="text-xs text-gray-400">{subtext}</span>
    </div>
  );
}

export default function DashboardPage() {
  const [quickInput, setQuickInput] = useState("Analyze GitHub issue #42");
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#1e293b]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">Maintenance Operations</h1>
          <p className="text-sm text-gray-400">
            Autonomous software failure detection, root-cause diagnosis, and sandbox verification.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/investigations"
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors shadow-lg shadow-blue-500/20"
          >
            <Play className="w-4 h-4" />
            New Investigation
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Active Investigations"
          value="2"
          subtext="1 Diagnosed, 1 Awaiting Approval"
          icon={Search}
          accentColor="bg-blue-500/10 text-blue-400 border border-blue-500/20"
        />
        <MetricCard
          title="Verified Repairs"
          value="48"
          subtext="96.2% All checks passed"
          icon={CheckCircle2}
          accentColor="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
        />
        <MetricCard
          title="Pending Approvals"
          value="1"
          subtext="Requires human sign-off"
          icon={ShieldAlert}
          accentColor="bg-amber-500/10 text-amber-400 border border-amber-500/20"
        />
        <MetricCard
          title="MCP Tool Calls"
          value="1,420"
          subtext="100% Policy-enforced"
          icon={Terminal}
          accentColor="bg-purple-500/10 text-purple-400 border border-purple-500/20"
        />
      </div>

      {/* Primary Interaction Interface */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-white">One-Shot Repair Dispatch</h2>
            <p className="text-xs text-gray-400">
              Provide an issue number, PR identifier, or CI failure URL to trigger the autonomous loop.
            </p>
          </div>
          <span className="text-xs font-mono text-blue-400 bg-blue-500/10 px-2.5 py-1 rounded border border-blue-500/20">
            Target: shreyvirmani/Devaura (main)
          </span>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={quickInput}
            onChange={(e) => setQuickInput(e.target.value)}
            placeholder="e.g. Analyze GitHub issue #42"
            className="flex-1 bg-[#090d16] border border-[#1e293b] rounded-lg px-4 py-2.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
          <button
            onClick={() => setIsAnalyzing(true)}
            className="px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium transition-colors flex items-center justify-center gap-2 shrink-0"
          >
            <Play className="w-4 h-4" />
            Analyze & Plan
          </button>
        </div>

        {/* Live Execution Stepper */}
        <div className="mt-6 pt-6 border-t border-[#1e293b] grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-semibold text-gray-200">1. Context Discovery</div>
              <div className="text-[11px] text-gray-400 font-mono mt-0.5">GitHub MCP &bull; Issue #42</div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-semibold text-gray-200">2. Root Cause Analysis</div>
              <div className="text-[11px] text-gray-400 font-mono mt-0.5">AST &bull; 91% Confidence</div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
            <Clock className="w-5 h-5 text-amber-400 shrink-0 mt-0.5 animate-pulse" />
            <div>
              <div className="text-xs font-semibold text-amber-300">3. Human Approval Gate</div>
              <div className="text-[11px] text-amber-400/80 font-mono mt-0.5">Awaiting Plan Sign-off</div>
            </div>
          </div>
          <div className="flex items-start gap-3 p-3 rounded-lg bg-[#0d131f] border border-[#1e293b] opacity-50">
            <Layers className="w-5 h-5 text-gray-500 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-semibold text-gray-400">4. Sandbox Verification</div>
              <div className="text-[11px] text-gray-500 font-mono mt-0.5">Pytest, Lint, Diff</div>
            </div>
          </div>
        </div>
      </div>

      {/* Two Column Layout: Active Investigations & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Investigations (2 Cols) */}
        <div className="lg:col-span-2 bg-[#111726] border border-[#1e293b] rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-white">Active Investigations</h2>
            <Link href="/investigations" className="text-xs text-blue-400 hover:underline flex items-center gap-1">
              View all <ArrowUpRight className="w-3 h-3" />
            </Link>
          </div>

          <div className="space-y-3">
            <div className="p-4 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-blue-400 font-mono">#42</span>
                  <span className="text-sm font-medium text-white">Malformed token causes 500 error in auth middleware</span>
                </div>
                <div className="text-xs text-gray-400">
                  Target: <span className="font-mono text-gray-300">src/auth/middleware.py</span> &bull; Confidence: <span className="text-emerald-400 font-semibold">91%</span>
                </div>
              </div>
              <Link
                href="/investigations"
                className="px-3 py-1.5 rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 text-xs font-medium border border-blue-500/30 transition-colors"
              >
                Review Plan
              </Link>
            </div>

            <div className="p-4 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-blue-400 font-mono">#38</span>
                  <span className="text-sm font-medium text-white">CI failure on workflow run: test_matrix (Python 3.12)</span>
                </div>
                <div className="text-xs text-gray-400">
                  Target: <span className="font-mono text-gray-300">apps/api/routes/metrics.py</span> &bull; Status: <span className="text-blue-400 font-semibold">REPAIRING</span>
                </div>
              </div>
              <Link
                href="/repairs"
                className="px-3 py-1.5 rounded bg-purple-600/20 text-purple-400 hover:bg-purple-600/30 text-xs font-medium border border-purple-500/30 transition-colors"
              >
                View Workspace
              </Link>
            </div>
          </div>
        </div>

        {/* Audit Log / Activity */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-white">MCP Execution Trace</h2>
            <Activity className="w-4 h-4 text-gray-400" />
          </div>

          <div className="space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between text-gray-300 pb-2 border-b border-[#1e293b]">
              <span className="text-blue-400">GitHub.get_issue</span>
              <span className="text-emerald-400">200 OK (84ms)</span>
            </div>
            <div className="flex items-center justify-between text-gray-300 pb-2 border-b border-[#1e293b]">
              <span className="text-blue-400">Devaura.search_code</span>
              <span className="text-emerald-400">14 matches (12ms)</span>
            </div>
            <div className="flex items-center justify-between text-gray-300 pb-2 border-b border-[#1e293b]">
              <span className="text-blue-400">Devaura.git_history</span>
              <span className="text-emerald-400">3 commits (22ms)</span>
            </div>
            <div className="flex items-center justify-between text-gray-300 pb-2 border-b border-[#1e293b]">
              <span className="text-purple-400">Investigator</span>
              <span className="text-emerald-400">DIAGNOSED</span>
            </div>
            <div className="flex items-center justify-between text-gray-300">
              <span className="text-amber-400">RepairPlanner</span>
              <span className="text-amber-300">PLAN_READY</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
