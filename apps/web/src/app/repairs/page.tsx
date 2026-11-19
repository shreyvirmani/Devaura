"use client";

import React, { useState } from "react";
import {
  Wrench,
  CheckCircle2,
  FileDiff,
  Terminal,
  ShieldCheck,
  GitPullRequest,
  Check,
  Sparkles,
} from "lucide-react";

export default function RepairWorkspacePage() {
  const [activeAttempt, setActiveAttempt] = useState<number>(1);
  const [prCreated, setPrCreated] = useState(false);

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Repair Workspace &amp; Diff Studio</h1>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              VERIFIED
            </span>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-purple-500/10 text-purple-400 border border-purple-500/20">
              REVIEWED
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Target: <span className="font-mono text-gray-300">apps/api/auth.py</span> &bull; Sandbox Attempt 1 of 3
          </p>
        </div>

        {/* PR Approval Gate */}
        <div className="flex items-center gap-3">
          {prCreated ? (
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-sm font-semibold">
              <Check className="w-4 h-4" /> PR #43 Created on GitHub!
            </div>
          ) : (
            <button
              onClick={() => setPrCreated(true)}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold shadow-lg shadow-emerald-500/20 transition-all"
            >
              <GitPullRequest className="w-4 h-4" />
              Approve &amp; Create Pull Request
            </button>
          )}
        </div>
      </div>

      {/* Attempt Selector */}
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Attempts:</span>
        <button
          onClick={() => setActiveAttempt(1)}
          className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors ${
            activeAttempt === 1
              ? "bg-blue-600 text-white"
              : "bg-[#111726] text-gray-400 hover:bg-[#151c2d] border border-[#1e293b]"
          }`}
        >
          Attempt #1 (VERIFIED &bull; 100% Tests)
        </button>
        <button
          disabled
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-[#111726]/40 text-gray-600 border border-[#1e293b]/40 cursor-not-allowed"
        >
          Attempt #2 (Unneeded)
        </button>
        <button
          disabled
          className="px-3 py-1.5 rounded-lg text-xs font-mono bg-[#111726]/40 text-gray-600 border border-[#1e293b]/40 cursor-not-allowed"
        >
          Attempt #3 (Unneeded)
        </button>
      </div>

      {/* Diff Viewer Card */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-xl overflow-hidden">
        <div className="h-10 bg-[#0d131f] border-b border-[#1e293b] px-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-mono text-gray-300">
            <FileDiff className="w-4 h-4 text-blue-400" />
            <span>diff --git a/apps/api/auth.py b/apps/api/auth.py</span>
          </div>
          <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
            +6 / -1 lines
          </span>
        </div>

        {/* Diff Code Representation */}
        <pre className="p-4 font-mono text-xs overflow-x-auto bg-[#090d16] text-gray-200 leading-relaxed">
          <code>
{`@@ -27,7 +27,12 @@ async def get_current_user(
     if authorization:
-        token = authorization.split()[1]
+        parts = authorization.split()
+        if len(parts) == 2 and parts[0].lower() == "bearer":
+            token = parts[1]
+        else:
+            raise HTTPException(
+                status_code=401, detail="Invalid authorization header format"
+            )`}
          </code>
        </pre>
      </div>

      {/* Semantic Diff Explanation (Prompt section 40 requirement) */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6">
        <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-amber-400" /> Diff Intelligence Explanation
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs mt-3">
          <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
            <span className="text-gray-500 block mb-1">What Changed</span>
            <span className="text-gray-200">Replaced direct indexing with length and scheme validation.</span>
          </div>
          <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
            <span className="text-gray-500 block mb-1">Problem Solved</span>
            <span className="text-gray-200">Prevents IndexError crash when client sends naked token or empty header.</span>
          </div>
          <div className="p-3 rounded-lg bg-[#0d131f] border border-[#1e293b]">
            <span className="text-gray-500 block mb-1">Regression Test</span>
            <span className="text-emerald-400 font-mono">tests/test_foundation.py::test_health_endpoints</span>
          </div>
        </div>
      </div>

      {/* Verification Results Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Tests */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-300">Unit Tests (Pytest)</span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
              PASSED
            </span>
          </div>
          <div className="text-xl font-bold text-white mb-1">10 / 10 Passed</div>
          <div className="text-xs text-gray-500 font-mono">Duration: 3.37s &bull; 0 Failures</div>
        </div>

        {/* Linter */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-300">Linter (Ruff / Flake8)</span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
              PASSED
            </span>
          </div>
          <div className="text-xl font-bold text-white mb-1">0 Errors</div>
          <div className="text-xs text-gray-500 font-mono">Code style clean</div>
        </div>

        {/* Typecheck */}
        <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-300">Typecheck (Mypy)</span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
              PASSED
            </span>
          </div>
          <div className="text-xl font-bold text-white mb-1">Strict Typed</div>
          <div className="text-xs text-gray-500 font-mono">0 Type Violations</div>
        </div>
      </div>
    </div>
  );
}
