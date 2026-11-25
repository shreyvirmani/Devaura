"use client";

import React, { useState } from "react";
import {
  AlertCircle,
  Search,
  Wrench,
  CheckCircle2,
  GitPullRequest,
  Check,
  ShieldCheck,
  FileCode,
  Terminal,
  Lock,
  ArrowRight,
  ShieldAlert,
  Play,
  Copy,
  ExternalLink,
} from "lucide-react";

interface PipelineStage {
  id: "failure" | "investigation" | "patch" | "verification" | "review";
  name: string;
  status: "DETECTED" | "DIAGNOSED" | "GENERATED" | "VERIFIED" | "AWAITING_REVIEW";
  label: string;
  badgeColor: string;
  progressBarColor: string;
}

const STAGES: PipelineStage[] = [
  {
    id: "failure",
    name: "01 / Failure",
    status: "DETECTED",
    label: "CI Failure Captured",
    badgeColor: "bg-[#EE9393]/10 text-[#EE9393] border-[#EE9393]/20",
    progressBarColor: "bg-[#EE9393]",
  },
  {
    id: "investigation",
    name: "02 / Investigation",
    status: "DIAGNOSED",
    label: "Root Cause Ranked (94%)",
    badgeColor: "bg-[#9CE8CE]/10 text-[#9CE8CE] border-[#9CE8CE]/20",
    progressBarColor: "bg-[#9CE8CE]",
  },
  {
    id: "patch",
    name: "03 / Patch",
    status: "GENERATED",
    label: "AST Validated Hunk",
    badgeColor: "bg-[#EDF0F2]/10 text-[#EDF0F2] border-[#2A3036]",
    progressBarColor: "bg-[#EDF0F2]",
  },
  {
    id: "verification",
    name: "04 / Sandbox",
    status: "VERIFIED",
    label: "All 4 Checks Passed",
    badgeColor: "bg-[#85D9AE]/10 text-[#85D9AE] border-[#85D9AE]/20",
    progressBarColor: "bg-[#85D9AE]",
  },
  {
    id: "review",
    name: "05 / Review & PR",
    status: "AWAITING_REVIEW",
    label: "Human Sign-off Required",
    badgeColor: "bg-[#E5BD7D]/10 text-[#E5BD7D] border-[#E5BD7D]/20",
    progressBarColor: "bg-[#E5BD7D]",
  },
];

export function PipelineVisualization() {
  const [activeStage, setActiveStage] = useState<PipelineStage["id"]>("verification");
  const [isApproved, setIsApproved] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);

  return (
    <div className="w-full bg-[#121518] border border-[#2A3036] rounded-[6px] p-4 sm:p-6 space-y-6">
      {/* Header with Title and Current Safety State */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#2A3036]">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#9CE8CE]">
              Repair Lifecycle
            </span>
            <span className="text-[11px] font-mono text-[#9AA4AC]">&bull;</span>
            <span className="text-[11px] font-mono text-[#EDF0F2]">
              Incident #DVA-142
            </span>
          </div>
          <h3 className="text-base sm:text-lg font-semibold text-[#EDF0F2] mt-0.5">
            payment_service &bull; enterprise_discount calculation
          </h3>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className="px-2 py-1 rounded-[4px] bg-[#0C0E10] border border-[#2A3036] text-[11px] font-mono text-[#9AA4AC]">
            SHA <code className="text-[#EDF0F2]">9d2c7e1</code>
          </span>
          <span className="px-2 py-1 rounded-[4px] bg-[#191D21] border border-[#2A3036] text-[11px] font-mono text-[#9CE8CE] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#9CE8CE] animate-pulse" />
            CONTROLLED
          </span>
        </div>
      </div>

      {/* 5-Stage Interactive Tabs matching Figma */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
        {STAGES.map((s) => {
          const isSelected = activeStage === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setActiveStage(s.id)}
              className={`
                p-3 rounded-[4px] text-left transition-all duration-120 flex flex-col justify-between relative overflow-hidden border
                ${
                  isSelected
                    ? "bg-[#191D21] border-[#9CE8CE]/40 shadow-sm"
                    : "bg-[#0C0E10] border-[#2A3036] hover:bg-[#191D21] hover:border-[#3A424A]"
                }
              `}
            >
              <div>
                <div className="text-[10px] font-mono uppercase text-[#9AA4AC] tracking-wider">
                  {s.name}
                </div>
                <div className="text-xs font-semibold text-[#EDF0F2] mt-1 truncate">
                  {s.label}
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <span
                  className={`text-[9px] font-mono px-1.5 py-0.5 rounded-[2px] border ${s.badgeColor}`}
                >
                  {s.status}
                </span>
                {isSelected && (
                  <span className="text-[10px] text-[#9CE8CE] font-mono">active</span>
                )}
              </div>

              {/* Thin bottom indicator bar */}
              <div
                className={`absolute bottom-0 left-0 right-0 h-[2px] ${
                  isSelected ? s.progressBarColor : "bg-transparent"
                }`}
              />
            </button>
          );
        })}
      </div>

      {/* Detailed Stage Content Card */}
      <div className="bg-[#0C0E10] border border-[#2A3036] rounded-[6px] p-4 sm:p-5 space-y-4">
        {/* Stage 1: Failure */}
        {activeStage === "failure" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-[#EE9393] flex items-center gap-1.5 font-semibold">
                <AlertCircle className="w-4 h-4" /> CI FAILURE DETECTED &bull; PYTEST EXIT 1
              </span>
              <span className="text-[11px] font-mono text-[#9AA4AC]">GitHub Actions #1042</span>
            </div>

            <div className="bg-[#121518] border border-[#2A3036] p-3 rounded-[4px] font-mono text-xs text-[#EDF0F2] overflow-x-auto space-y-1">
              <div className="text-[#EE9393]">FAIL tests/test_discounts.py::test_enterprise_tier_discount</div>
              <div className="text-[#9AA4AC]">----------------------------- Captured Failure -----------------------------</div>
              <div className="text-[#EDF0F2]">
                AssertionError: expected <span className="text-[#85D9AE]">75.0</span>, received <span className="text-[#EE9393]">100.0</span>
              </div>
              <div className="text-[#9AA4AC]">
                &gt;       calculator.calculate_total(base_rate=100.0, tier=&quot;ENTERPRISE&quot;)
              </div>
              <div className="text-[#9AA4AC]">
                E       pricing_service/calculator.py:84: in calculate_total
              </div>
            </div>

            <div className="text-xs text-[#9AA4AC] flex items-center justify-between">
              <span>Repository: <code className="text-[#EDF0F2]">acme/payment-service</code></span>
              <span>Branch: <code className="text-[#EDF0F2]">main</code> (commit: <code className="text-[#EDF0F2]">f4b1a20</code>)</span>
            </div>
          </div>
        )}

        {/* Stage 2: Investigation */}
        {activeStage === "investigation" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-[#9CE8CE] flex items-center gap-1.5 font-semibold">
                <Search className="w-4 h-4" /> ROOT CAUSE ISOLATED &bull; CONFIDENCE 94%
              </span>
              <span className="text-[11px] font-mono text-[#9AA4AC]">7 Evidence Items Ranked</span>
            </div>

            <div className="bg-[#121518] border border-[#2A3036] p-3 rounded-[4px] space-y-2">
              <div className="text-xs font-medium text-[#EDF0F2]">
                Diagnosis: Enterprise discount coefficient branch omitted from subtotal accumulator
              </div>
              <p className="text-xs text-[#9AA4AC] leading-relaxed">
                AST inspection of <code className="text-[#9CE8CE]">pricing_service/calculator.py:84</code> reveals that the conditional block for tier <code className="text-[#EDF0F2]">&quot;ENTERPRISE&quot;</code> computes the discount coefficient but fails to apply it before returning the invoice subtotal.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs font-mono">
              <div className="p-2.5 rounded-[4px] bg-[#121518] border border-[#2A3036]">
                <div className="text-[#9AA4AC] text-[10px]">TARGET FILE</div>
                <div className="text-[#EDF0F2] truncate mt-0.5">pricing_service/calculator.py</div>
              </div>
              <div className="p-2.5 rounded-[4px] bg-[#121518] border border-[#2A3036]">
                <div className="text-[#9AA4AC] text-[10px]">AFFECTED SYMBOL</div>
                <div className="text-[#EDF0F2] truncate mt-0.5">calculate_total()</div>
              </div>
              <div className="p-2.5 rounded-[4px] bg-[#121518] border border-[#2A3036]">
                <div className="text-[#9AA4AC] text-[10px]">LOCALIZATION RANK</div>
                <div className="text-[#85D9AE] font-semibold mt-0.5">Top-1 (0.94)</div>
              </div>
            </div>
          </div>
        )}

        {/* Stage 3: Patch */}
        {activeStage === "patch" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-[#EDF0F2] flex items-center gap-1.5 font-semibold">
                <FileCode className="w-4 h-4 text-[#9CE8CE]" /> UNIFIED DIFF &bull; +2 -1 LINES
              </span>
              <span className="text-[11px] font-mono text-[#9AA4AC]">pricing_service/calculator.py:84</span>
            </div>

            <div className="bg-[#121518] border border-[#2A3036] rounded-[4px] overflow-hidden font-mono text-xs">
              <div className="px-3 py-1.5 bg-[#191D21] border-b border-[#2A3036] text-[11px] text-[#9AA4AC] flex items-center justify-between">
                <span>--- a/pricing_service/calculator.py</span>
                <span>+++ b/pricing_service/calculator.py</span>
              </div>
              <div className="p-3 space-y-1">
                <div className="text-[#9AA4AC]">@@ -82,3 +82,4 @@ def calculate_total(base_rate: float, tier: str) -&gt; float:</div>
                <div className="text-[#9AA4AC]">&nbsp;    discount = get_tier_discount(tier)</div>
                <div className="bg-[#EE9393]/10 text-[#EE9393] px-2 py-0.5 rounded-[2px] flex items-center">
                  <span>-&nbsp;&nbsp;&nbsp;&nbsp;return base_rate</span>
                </div>
                <div className="bg-[#85D9AE]/10 text-[#85D9AE] px-2 py-0.5 rounded-[2px] flex items-center">
                  <span>+&nbsp;&nbsp;&nbsp;&nbsp;effective_rate = base_rate * (1.0 - discount)</span>
                </div>
                <div className="bg-[#85D9AE]/10 text-[#85D9AE] px-2 py-0.5 rounded-[2px] flex items-center">
                  <span>+&nbsp;&nbsp;&nbsp;&nbsp;return round(effective_rate, 2)</span>
                </div>
              </div>
            </div>

            <div className="text-xs text-[#9AA4AC] flex items-center justify-between">
              <span>Patch Hash: <code className="text-[#EDF0F2]">sha256:4a8b...19c3</code></span>
              <span className="text-[#85D9AE] font-mono">✓ AST Syntactically Valid</span>
            </div>
          </div>
        )}

        {/* Stage 4: Verification */}
        {activeStage === "verification" && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-[#85D9AE] flex items-center gap-1.5 font-semibold">
                <CheckCircle2 className="w-4 h-4" /> 4/4 CHECKS PASSED &bull; ISOLATED SANDBOX
              </span>
              <span className="text-[11px] font-mono text-[#9AA4AC]">Duration: 4.8s</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-[#EDF0F2]">
                  <span>AST Validation</span>
                  <Check className="w-3.5 h-3.5 text-[#85D9AE]" />
                </div>
                <div className="text-[11px] text-[#85D9AE] font-mono">PASSED</div>
                <div className="text-[10px] text-[#9AA4AC]">Clean parse, no globals</div>
              </div>

              <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-[#EDF0F2]">
                  <span>Reproduction Test</span>
                  <Check className="w-3.5 h-3.5 text-[#85D9AE]" />
                </div>
                <div className="text-[11px] text-[#85D9AE] font-mono">PASSED (1/1)</div>
                <div className="text-[10px] text-[#9AA4AC]">test_enterprise_discount</div>
              </div>

              <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-[#EDF0F2]">
                  <span>Hidden Edge Cases</span>
                  <Check className="w-3.5 h-3.5 text-[#85D9AE]" />
                </div>
                <div className="text-[11px] text-[#85D9AE] font-mono">PASSED (3/3)</div>
                <div className="text-[10px] text-[#9AA4AC]">Zero-regression boundary</div>
              </div>

              <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-1">
                <div className="flex items-center justify-between text-xs font-semibold text-[#EDF0F2]">
                  <span>Lint &amp; Mypy</span>
                  <Check className="w-3.5 h-3.5 text-[#85D9AE]" />
                </div>
                <div className="text-[11px] text-[#85D9AE] font-mono">PASSED (0 errors)</div>
                <div className="text-[10px] text-[#9AA4AC]">Strict type adherence</div>
              </div>
            </div>

            <div className="p-3 rounded-[4px] bg-[#121518] border border-[#2A3036] flex items-center justify-between text-xs">
              <span className="text-[#9AA4AC]">
                Workspace: <code className="text-[#EDF0F2]">/tmp/devaura-sbx-9d2c7e1</code> (Cleanly destroyed after execution)
              </span>
              <span className="font-mono text-[#85D9AE] font-medium">Zero False Repairs</span>
            </div>
          </div>
        )}

        {/* Stage 5: Review & PR */}
        {activeStage === "review" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-[#E5BD7D] flex items-center gap-1.5 font-semibold">
                <Lock className="w-4 h-4" /> HUMAN-IN-THE-LOOP APPROVAL REQUIRED
              </span>
              <span className="text-[11px] font-mono text-[#9AA4AC]">Branch Protection Active</span>
            </div>

            {isApproved ? (
              <div className="p-4 rounded-[4px] bg-[#85D9AE]/10 border border-[#85D9AE]/30 space-y-2">
                <div className="flex items-center gap-2 text-xs font-semibold text-[#85D9AE]">
                  <CheckCircle2 className="w-4 h-4" />
                  Repair Approved &bull; Pull Request Prepared
                </div>
                <p className="text-xs text-[#EDF0F2] font-sans">
                  Approval signature recorded: <code className="font-mono text-[#9CE8CE]">token_9d2c7e1_shrey</code>.
                  Pull Request <strong className="font-mono">#128</strong> staged on branch <code className="font-mono text-[#EDF0F2]">repair/enterprise-discount-fix</code>.
                </p>
                <div className="text-[11px] font-mono text-[#9AA4AC] pt-1">
                  Note: Devaura never autonomously merges or deploys to production. Merge remains strictly manual.
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-[4px] bg-[#121518] border border-[#2A3036] space-y-3">
                <p className="text-xs text-[#EDF0F2] leading-relaxed">
                  The candidate patch has completed sandbox verification without regressions. Before any PR branch is created on GitHub, an explicit human approval token must be cryptographically bound to the verified diff.
                </p>
                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <button
                    onClick={() => setShowApprovalModal(true)}
                    className="px-4 py-2 rounded-[4px] bg-[#9CE8CE] hover:bg-[#8CD8BE] text-[#0C0E10] font-semibold text-xs transition-colors duration-120 flex items-center gap-2"
                  >
                    <Check className="w-3.5 h-3.5" />
                    Review &amp; Approve Repair
                  </button>
                  <button
                    onClick={() => setActiveStage("patch")}
                    className="px-4 py-2 rounded-[4px] bg-[#191D21] hover:bg-[#20252A] text-[#EDF0F2] text-xs font-medium border border-[#2A3036] transition-colors duration-120"
                  >
                    Inspect Diff Again
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Human-in-the-Loop Modal matching Figma spec */}
      {showApprovalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg bg-[#121518] border border-[#2A3036] rounded-[8px] p-6 space-y-4 shadow-2xl animate-in fade-in zoom-in-95 duration-120">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="text-base font-semibold text-[#EDF0F2]">
                  Approve repair?
                </h4>
                <p className="text-xs text-[#9AA4AC] mt-1">
                  Authorize creation of repair branch and PR for patch <code className="text-[#9CE8CE]">9d2c7e1</code>.
                </p>
              </div>
            </div>

            <div className="p-3 rounded-[4px] bg-[#0C0E10] border border-[#2A3036] space-y-2 text-xs font-mono">
              <div className="flex justify-between text-[#9AA4AC]">
                <span>Repository</span>
                <span className="text-[#EDF0F2]">acme/payment-service</span>
              </div>
              <div className="flex justify-between text-[#9AA4AC]">
                <span>Target Branch</span>
                <span className="text-[#EDF0F2]">main</span>
              </div>
              <div className="flex justify-between text-[#9AA4AC]">
                <span>Repair Branch</span>
                <span className="text-[#EDF0F2]">repair/enterprise-discount-fix</span>
              </div>
              <div className="flex justify-between text-[#9AA4AC]">
                <span>Patch Signature</span>
                <span className="text-[#9CE8CE]">sha256:4a8b...19c3</span>
              </div>
            </div>

            <div className="p-3 rounded-[4px] bg-[#191D21] border border-[#2A3036] text-[11px] text-[#9AA4AC] leading-relaxed">
              <strong className="text-[#EDF0F2]">Safety guarantee:</strong> Approving this patch will trigger PR creation on GitHub. This does <span className="text-[#EE9393] font-semibold">NOT</span> merge or deploy the change. Merge and production deployment remain entirely under human control.
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                onClick={() => setShowApprovalModal(false)}
                className="px-4 py-2 rounded-[4px] bg-[#191D21] hover:bg-[#20252A] text-[#EDF0F2] text-xs font-medium border border-[#2A3036]"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setIsApproved(true);
                  setShowApprovalModal(false);
                }}
                className="px-5 py-2 rounded-[4px] bg-[#9CE8CE] hover:bg-[#8CD8BE] text-[#0C0E10] text-xs font-semibold shadow-sm transition-colors duration-120"
              >
                Approve repair
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PipelineVisualization;
