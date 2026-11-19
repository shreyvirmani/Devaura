"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Search,
  CheckCircle2,
  AlertTriangle,
  FileCode,
  ShieldCheck,
  Check,
  X,
  Layers,
  ArrowRight,
  GitBranch,
} from "lucide-react";

export default function InvestigationsPage() {
  const [approved, setApproved] = useState(false);
  const [rejected, setRejected] = useState(false);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Issue Investigation #42</h1>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
              PLAN_READY
            </span>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
              Awaiting Approval
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Repository: <span className="font-mono text-gray-300">shreyvirmani/Devaura</span> &bull; Source:{" "}
            <span className="font-mono text-gray-300">GitHub Issue #42</span>
          </p>
        </div>

        {/* Human Approval Gate Controls */}
        <div className="flex items-center gap-3">
          {approved ? (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-sm font-semibold">
              <Check className="w-4 h-4" /> Plan Approved &bull; Repairing...
            </div>
          ) : rejected ? (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 text-sm font-semibold">
              <X className="w-4 h-4" /> Plan Rejected
            </div>
          ) : (
            <>
              <button
                onClick={() => setRejected(true)}
                className="px-4 py-2 rounded-lg bg-[#151c2d] hover:bg-red-500/10 hover:text-red-400 text-gray-300 text-sm font-medium border border-[#1e293b] transition-colors"
              >
                Reject
              </button>
              <button
                onClick={() => setApproved(true)}
                className="flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all"
              >
                <Check className="w-4 h-4" />
                Approve Repair Plan
              </button>
            </>
          )}
        </div>
      </div>

      {/* Main Grid: Diagnosis & Plan */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2 Cols): Root Cause, Evidence, Plan */}
        <div className="lg:col-span-2 space-y-6">
          {/* Root Cause Card */}
          <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Search className="w-4 h-4 text-blue-400" /> Root Cause Diagnosis
              </h2>
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-mono font-semibold">
                Confidence: 91%
              </div>
            </div>
            <p className="text-sm text-gray-200 leading-relaxed bg-[#090d16] p-4 rounded-lg border border-[#1e293b]">
              Authentication middleware receives malformed authorization header without standard Bearer prefix,
              causing unhandled index split exception during JWT decoding in <span className="font-mono text-blue-300">decode_auth_token</span>.
            </p>
          </div>

          {/* Evidence Gathered */}
          <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
            <h2 className="text-base font-semibold text-white mb-3">Collected Evidence</h2>
            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-semibold text-blue-400">CI Stack Trace &bull; test_auth.py:48</span>
                  <span className="text-gray-500">ci_log</span>
                </div>
                <code className="text-gray-300 block font-mono">
                  IndexError: list index out of range at middleware.py:34 in decode_token(header.split()[1])
                </code>
              </div>

              <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-semibold text-blue-400">Git Blame &bull; commit 7b1a20c</span>
                  <span className="text-gray-500">git_history</span>
                </div>
                <p className="text-gray-300">
                  Commit 7b1a20c removed length check on authorization header parts 2 commits ago.
                </p>
              </div>
            </div>
          </div>

          {/* Structured Repair Plan */}
          <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-base font-semibold text-white">Structured Repair Plan</h2>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                Risk: MEDIUM
              </span>
            </div>
            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold shrink-0">
                  1
                </span>
                <div>
                  <span className="font-semibold text-white block mb-0.5">Validate Header Structure</span>
                  <p className="text-gray-400">
                    Verify header starts with &apos;Bearer &apos; and contains exactly 2 whitespace-separated components before extracting token.
                  </p>
                  <span className="text-[11px] font-mono text-gray-500 mt-1 block">File: apps/api/auth.py</span>
                </div>
              </div>

              <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-start gap-3">
                <span className="w-5 h-5 rounded-full bg-blue-600/20 text-blue-400 flex items-center justify-center font-bold shrink-0">
                  2
                </span>
                <div>
                  <span className="font-semibold text-white block mb-0.5">Add Regression Test</span>
                  <p className="text-gray-400">
                    Assert malformed header strings return HTTP 401 without unhandled 500 exceptions.
                  </p>
                  <span className="text-[11px] font-mono text-gray-500 mt-1 block">File: tests/test_foundation.py</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Affected Components & State */}
        <div className="space-y-6">
          <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <FileCode className="w-4 h-4 text-purple-400" /> Affected Files
            </h3>
            <div className="space-y-2 text-xs font-mono">
              <div className="p-2.5 rounded bg-[#090d16] border border-[#1e293b] text-gray-300">
                apps/api/auth.py
              </div>
              <div className="p-2.5 rounded bg-[#090d16] border border-[#1e293b] text-gray-300">
                tests/test_foundation.py
              </div>
            </div>
          </div>

          <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
            <h3 className="text-sm font-semibold text-white mb-3">Verification Target</h3>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded bg-[#090d16]">
                <span className="text-gray-400">Unit Tests:</span>
                <span className="text-white font-mono font-semibold">10/10 expected</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-[#090d16]">
                <span className="text-gray-400">Linter:</span>
                <span className="text-emerald-400 font-mono">ruff / flake8</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-[#090d16]">
                <span className="text-gray-400">Sandbox Isolation:</span>
                <span className="text-emerald-400 font-mono">ENABLED</span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-[#1e293b]">
              <Link
                href="/repairs"
                className="w-full flex items-center justify-center gap-2 py-2 rounded-lg bg-[#151c2d] hover:bg-[#1f293d] text-xs font-medium text-gray-200 transition-colors"
              >
                View Repair Diff &amp; Workspace <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
