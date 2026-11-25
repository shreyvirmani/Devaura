"use client";

import React from "react";
import Link from "next/link";
import { BlurText } from "@/components/motion/BlurText";
import { TechnicalGridBackground } from "@/components/motion/TechnicalGridBackground";
import { PipelineVisualization } from "@/components/hero/PipelineVisualization";
import {
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Terminal,
  Lock,
  Search,
  Wrench,
  GitPullRequest,
  Check,
} from "lucide-react";

export function HeroSection() {
  return (
    <TechnicalGridBackground className="py-6 sm:py-12 px-4 sm:px-8 border-b border-[#2A3036] w-full max-w-full overflow-hidden">
      <div className="max-w-6xl mx-auto space-y-8 sm:space-y-10">
        {/* Eyebrow & Headline Narrative */}
        <div className="space-y-3 sm:space-y-4 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-[4px] bg-[#121518] border border-[#2A3036] text-[10px] sm:text-[11px] font-mono text-[#9CE8CE]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#9CE8CE] animate-pulse" />
            DEVAURA / INTERFACE SYSTEM
          </div>

          <div className="space-y-2">
            <BlurText
              text="Engineering, with evidence."
              className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-[#EDF0F2] leading-tight"
              delay={80}
            />
            <p className="text-xs sm:text-sm md:text-base text-[#9AA4AC] leading-relaxed max-w-2xl font-sans">
              A restrained system for detection, repair, verification and human control.
              Devaura isolates root causes via AST symbol graphs, verifies candidate patches in ephemeral sandboxes, and enforces cryptographic human approval before any PR is staged.
            </p>
          </div>

          {/* Action CTAs matching Figma action buttons */}
          <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 pt-1 sm:pt-2">
            <Link
              href="/investigations"
              className="px-4 sm:px-5 py-2 sm:py-2.5 rounded-[4px] bg-[#9CE8CE] hover:bg-[#8CD8BE] text-[#0C0E10] font-semibold text-xs tracking-wide transition-colors duration-120 flex items-center gap-2 shadow-sm"
            >
              <span>Review repair</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>

            <Link
              href="/evaluation"
              className="px-4 sm:px-5 py-2 sm:py-2.5 rounded-[4px] bg-[#121518] hover:bg-[#191D21] text-[#EDF0F2] font-medium text-xs border border-[#2A3036] hover:border-[#3A424A] transition-colors duration-120 flex items-center gap-2"
            >
              <ShieldCheck className="w-3.5 h-3.5 text-[#9AA4AC]" />
              <span>Inspect benchmark audit</span>
            </Link>
          </div>
        </div>

        {/* Live Empirical Metrics Strip */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3 pt-2">
          <div className="p-3 sm:p-3.5 rounded-[4px] bg-[#121518] border border-[#2A3036] min-w-0">
            <div className="text-[10px] font-mono uppercase text-[#9AA4AC] truncate">
              HELD-OUT SUITE
            </div>
            <div className="text-base sm:text-xl md:text-2xl font-bold text-[#EDF0F2] mt-0.5 truncate">
              13 / 13
            </div>
            <div className="text-[10px] sm:text-[11px] text-[#85D9AE] font-mono mt-0.5 truncate">
              100% Repos Disjoint
            </div>
          </div>

          <div className="p-3 sm:p-3.5 rounded-[4px] bg-[#121518] border border-[#2A3036] min-w-0">
            <div className="text-[10px] font-mono uppercase text-[#9AA4AC] truncate">
              FALSE REPAIRS
            </div>
            <div className="text-base sm:text-xl md:text-2xl font-bold text-[#EDF0F2] mt-0.5 truncate">
              0 / 39
            </div>
            <div className="text-[10px] sm:text-[11px] text-[#85D9AE] font-mono mt-0.5 truncate">
              Hidden Tests Passed
            </div>
          </div>

          <div className="p-3 sm:p-3.5 rounded-[4px] bg-[#121518] border border-[#2A3036] min-w-0">
            <div className="text-[10px] font-mono uppercase text-[#9AA4AC] truncate">
              SANDBOX ISOLATION
            </div>
            <div className="text-base sm:text-xl md:text-2xl font-bold text-[#EDF0F2] mt-0.5 truncate">
              100%
            </div>
            <div className="text-[10px] sm:text-[11px] text-[#9CE8CE] font-mono mt-0.5 truncate">
              Ephemeral Container
            </div>
          </div>

          <div className="p-3 sm:p-3.5 rounded-[4px] bg-[#121518] border border-[#2A3036] min-w-0">
            <div className="text-[10px] font-mono uppercase text-[#9AA4AC] truncate">
              MERGE &amp; DEPLOY
            </div>
            <div className="text-base sm:text-xl md:text-2xl font-bold text-[#EDF0F2] mt-0.5 truncate">
              MANUAL
            </div>
            <div className="text-[10px] sm:text-[11px] text-[#E5BD7D] font-mono mt-0.5 truncate">
              Strict Gate Enforced
            </div>
          </div>
        </div>

        {/* Visual Engine: The Interactive Pipeline */}
        <div className="w-full overflow-hidden">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] sm:text-[11px] font-mono uppercase tracking-wider text-[#9AA4AC]">
              Live Engine Visualization
            </span>
            <span className="text-[10px] sm:text-[11px] font-mono text-[#9AA4AC] hidden sm:inline">
              Click any stage to inspect execution state
            </span>
          </div>
          <PipelineVisualization />
        </div>
      </div>
    </TechnicalGridBackground>
  );
}

export default HeroSection;
