"use client";

import React from "react";
import {
  ShieldCheck,
  ShieldAlert,
  Lock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Check,
  Cpu,
  Layers,
  Terminal,
} from "lucide-react";

export function TrustVerificationSection() {
  return (
    <section className="py-12 px-4 sm:px-8 border-b border-[#2A3036] bg-[#0C0E10]">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Section Header */}
        <div className="space-y-2">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#9CE8CE]">
            Verification &amp; Safety Boundary
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#EDF0F2]">
            Evidence over intuition.
          </h2>
          <p className="text-xs sm:text-sm text-[#9AA4AC] max-w-2xl leading-relaxed">
            Generated code is not considered fixed merely because an LLM emitted text.
            Devaura subjects every patch to an automated, isolated four-tier verification gauntlet before presenting it for human sign-off.
          </p>
        </div>

        {/* 4 Unit Test & Verification Metric Cards matching Figma */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Card 1: Passed */}
          <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#9AA4AC]">CHECK 01</span>
              <span className="px-1.5 py-0.5 rounded-[2px] bg-[#85D9AE]/10 text-[#85D9AE] border border-[#85D9AE]/20 font-semibold">
                ✓ Passed
              </span>
            </div>
            <div>
              <div className="text-sm font-semibold text-[#EDF0F2]">Unit &amp; Regression Tests</div>
              <div className="text-xs text-[#9AA4AC] mt-1 font-mono">23 tests passed &bull; 4.8s</div>
            </div>
            <div className="text-[11px] text-[#85D9AE] font-mono pt-2 border-t border-[#2A3036] flex items-center gap-1.5">
              <Check className="w-3.5 h-3.5" /> Zero false repairs detected
            </div>
          </div>

          {/* Card 2: Running */}
          <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#9AA4AC]">CHECK 02</span>
              <span className="px-1.5 py-0.5 rounded-[2px] bg-[#9CE8CE]/10 text-[#9CE8CE] border border-[#9CE8CE]/20 font-semibold">
                ● Running
              </span>
            </div>
            <div>
              <div className="text-sm font-semibold text-[#EDF0F2]">Hidden Edge Cases</div>
              <div className="text-xs text-[#9AA4AC] mt-1 font-mono">18 of 23 checks complete</div>
            </div>
            <div className="text-[11px] text-[#9CE8CE] font-mono pt-2 border-t border-[#2A3036] flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#9CE8CE] animate-pulse" /> Ephemeral container active
            </div>
          </div>

          {/* Card 3: Failed / Guard Block */}
          <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#9AA4AC]">CHECK 03</span>
              <span className="px-1.5 py-0.5 rounded-[2px] bg-[#EE9393]/10 text-[#EE9393] border border-[#EE9393]/20 font-semibold">
                ✕ Guard Block
              </span>
            </div>
            <div>
              <div className="text-sm font-semibold text-[#EDF0F2]">Security &amp; AST Linter</div>
              <div className="text-xs text-[#9AA4AC] mt-1 font-mono">1 regression &bull; review blocked</div>
            </div>
            <div className="text-[11px] text-[#EE9393] font-mono pt-2 border-t border-[#2A3036] flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5" /> Flawed patches never reach PR
            </div>
          </div>

          {/* Card 4: Queued */}
          <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
            <div className="flex items-center justify-between text-xs font-mono">
              <span className="text-[#9AA4AC]">CHECK 04</span>
              <span className="px-1.5 py-0.5 rounded-[2px] bg-[#191D21] text-[#9AA4AC] border border-[#2A3036] font-semibold">
                Queued
              </span>
            </div>
            <div>
              <div className="text-sm font-semibold text-[#EDF0F2]">Blast Radius Analysis</div>
              <div className="text-xs text-[#9AA4AC] mt-1 font-mono">Waiting for isolated runner</div>
            </div>
            <div className="text-[11px] text-[#9AA4AC] font-mono pt-2 border-t border-[#2A3036] flex items-center gap-1.5">
              <RotateCcw className="w-3.5 h-3.5" /> Quota bounded execution
            </div>
          </div>
        </div>

        {/* Security Policy States Grid */}
        <div className="space-y-3">
          <div className="text-xs font-mono uppercase text-[#9AA4AC] tracking-wider">
            Deterministic Security Architecture
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2.5">
            <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
              <div className="text-xs font-mono font-bold text-[#EDF0F2] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#85D9AE]" /> SAFE
              </div>
              <p className="text-[11px] text-[#9AA4AC] leading-relaxed">
                Read-only AST parsing, code intelligence graph traversal, and zero mutation.
              </p>
            </div>

            <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
              <div className="text-xs font-mono font-bold text-[#EDF0F2] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#9CE8CE]" /> CONTROLLED
              </div>
              <p className="text-[11px] text-[#9AA4AC] leading-relaxed">
                Isolated sandbox execution with bounded CPU, RAM, and zero egress access.
              </p>
            </div>

            <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
              <div className="text-xs font-mono font-bold text-[#EDF0F2] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#E5BD7D]" /> REQUIRES APPROVAL
              </div>
              <p className="text-[11px] text-[#9AA4AC] leading-relaxed">
                Branch push blocked until an authenticated maintainer signs the patch SHA.
              </p>
            </div>

            <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
              <div className="text-xs font-mono font-bold text-[#EDF0F2] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#EE9393]" /> BLOCKED
              </div>
              <p className="text-[11px] text-[#9AA4AC] leading-relaxed">
                Secret credential access (.env, tokens) and direct push to protected branches forbidden.
              </p>
            </div>

            <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
              <div className="text-xs font-mono font-bold text-[#EDF0F2] flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#85D9AE]" /> VERIFIED
              </div>
              <p className="text-[11px] text-[#9AA4AC] leading-relaxed">
                Reproduction passes and all held-out regression tests produce exit code 0.
              </p>
            </div>
          </div>
        </div>

        {/* Clear Non-Autonomous Policy Banner matching Figma */}
        <div className="p-4 rounded-[6px] bg-[#121518] border border-[#2A3036] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold text-[#EDF0F2]">
              <Lock className="w-4 h-4 text-[#9CE8CE]" />
              Strict Engineering Governance
            </div>
            <p className="text-xs text-[#9AA4AC]">
              Devaura prepares pull requests with comprehensive verification proof, but does <strong className="text-[#EDF0F2]">NOT</strong> autonomously merge branches or trigger production deployments.
            </p>
          </div>
          <span className="px-2.5 py-1 rounded-[4px] bg-[#0C0E10] text-[#E5BD7D] border border-[#2A3036] text-[11px] font-mono whitespace-nowrap self-start sm:self-auto">
            MERGE = MANUAL ONLY
          </span>
        </div>
      </div>
    </section>
  );
}

export default TrustVerificationSection;
