"use client";

import React, { useState } from "react";
import { InteractiveCard } from "@/components/motion/InteractiveCard";
import {
  Search,
  Activity,
  FileCode,
  Wrench,
  ShieldCheck,
  CheckCircle2,
  Lock,
  GitPullRequest,
  Terminal,
  Cpu,
  Layers,
  Check,
} from "lucide-react";

interface WorkflowStep {
  number: string;
  title: string;
  engine: string;
  description: string;
  input: string;
  output: string;
  guarantee: string;
}

const LIFECYCLE_STEPS: WorkflowStep[] = [
  {
    number: "01",
    title: "Failure Detection",
    engine: "Webhook / CI Ingestion",
    description: "Captures CI traces, pytest logs, or issue webhooks with stack frame pointers.",
    input: "Pytest log / GitHub Issue",
    output: "FailureContext schema",
    guarantee: "100% deterministic ingestion",
  },
  {
    number: "02",
    title: "Context Discovery",
    engine: "Code Intelligence & AST",
    description: "Indexes the AST symbol graph, imports, and commit delta to map affected call paths.",
    input: "Git commit + Target files",
    output: "Ranked symbol subgraph",
    guarantee: "No hallucinations; strict AST query",
  },
  {
    number: "03",
    title: "Root Cause Diagnosis",
    engine: "Investigator Agent",
    description: "Ranks candidate causal sites by Bayesian confidence and cross-references git blame history.",
    input: "Symbol subgraph + Stacktrace",
    output: "RootCauseCandidate (Top-1)",
    guarantee: "Ranked evidence provenance",
  },
  {
    number: "04",
    title: "Repair Planning",
    engine: "RepairPlanner Agent",
    description: "Synthesizes minimal surgical fix constraints, ensuring backward compatibility.",
    input: "Diagnosed root cause",
    output: "Structured RepairPlan",
    guarantee: "Bounded scope; zero extra files",
  },
  {
    number: "05",
    title: "Patch Generation",
    engine: "PatchSynthesizer Engine",
    description: "Generates unified diff hunk and validates syntactical AST cleanliness before any run.",
    input: "RepairPlan constraints",
    output: "Unified diff hunk (+ / -)",
    guarantee: "AST parse verification",
  },
  {
    number: "06",
    title: "Sandbox Verification",
    engine: "Isolated Docker Runner",
    description: "Executes reproduction test, hidden edge cases, linter, and type checker in disposable container.",
    input: "Candidate patch + Workspace",
    output: "VerificationReport (4/4)",
    guarantee: "Zero leaked state; clean wipe",
  },
  {
    number: "07",
    title: "Human Approval Gate",
    engine: "Cryptographic Gate",
    description: "Binds an authorization token to the exact verified patch SHA. No branch push occurs without it.",
    input: "Verified patch SHA256",
    output: "ApprovalToken signature",
    guarantee: "Mandatory human sign-off",
  },
  {
    number: "08",
    title: "Pull Request Staging",
    engine: "GitHub MCP Integration",
    description: "Pushes patch to a dedicated ephemeral branch and creates an auditable review PR.",
    input: "ApprovalToken + Diff",
    output: "GitHub PR staged",
    guarantee: "Merge remains strictly manual",
  },
];

export function WorkflowSection() {
  const [selectedStep, setSelectedStep] = useState(0);

  return (
    <section className="py-12 px-4 sm:px-8 border-b border-[#2A3036] bg-[#0C0E10]">
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Section Header matching Figma */}
        <div className="space-y-2">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#9CE8CE]">
            Orchestrated Architecture
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#EDF0F2]">
            Every state has a purpose.
          </h2>
          <p className="text-xs sm:text-sm text-[#9AA4AC] max-w-2xl leading-relaxed">
            Devaura is not an unpredictable chat assistant. It is a deterministic, 8-phase orchestrated pipeline where each phase consumes verified artifacts from the previous phase.
          </p>
        </div>

        {/* 8-Step Interactive Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {LIFECYCLE_STEPS.map((step, index) => {
            const isSelected = selectedStep === index;
            return (
              <div
                key={step.number}
                onClick={() => setSelectedStep(index)}
                className={`
                  p-4 rounded-[6px] border cursor-pointer transition-all duration-120 flex flex-col justify-between
                  ${
                    isSelected
                      ? "bg-[#191D21] border-[#9CE8CE]/50 shadow-sm"
                      : "bg-[#121518] border-[#2A3036] hover:bg-[#191D21] hover:border-[#3A424A]"
                  }
                `}
              >
                <div>
                  <div className="flex items-center justify-between text-xs font-mono">
                    <span className="text-[#9CE8CE] font-semibold">{step.number}</span>
                    <span className="text-[10px] text-[#9AA4AC] px-1.5 py-0.5 rounded-[2px] bg-[#0C0E10] border border-[#2A3036]">
                      {step.engine}
                    </span>
                  </div>

                  <h3 className="text-sm font-semibold text-[#EDF0F2] mt-2">
                    {step.title}
                  </h3>
                  <p className="text-xs text-[#9AA4AC] mt-1 line-clamp-2 leading-relaxed">
                    {step.description}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-[#2A3036] flex items-center justify-between text-[11px] font-mono">
                  <span className="text-[#9AA4AC]">Artifact:</span>
                  <span className="text-[#EDF0F2] truncate max-w-[130px] font-medium">
                    {step.output}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Detailed Inspection Drawer of Selected Step */}
        <div className="p-5 rounded-[6px] bg-[#121518] border border-[#2A3036] space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-[#2A3036]">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-mono text-[#9CE8CE] font-bold">
                Phase {LIFECYCLE_STEPS[selectedStep].number} Detail:
              </span>
              <span className="text-sm font-semibold text-[#EDF0F2]">
                {LIFECYCLE_STEPS[selectedStep].title}
              </span>
            </div>
            <span className="text-xs font-mono px-2 py-0.5 rounded-[4px] bg-[#0C0E10] text-[#85D9AE] border border-[#2A3036] self-start sm:self-auto">
              ✓ {LIFECYCLE_STEPS[selectedStep].guarantee}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            <div className="space-y-1">
              <span className="text-[10px] uppercase text-[#9AA4AC]">Phase Description</span>
              <p className="text-[#EDF0F2] font-sans text-xs leading-relaxed">
                {LIFECYCLE_STEPS[selectedStep].description}
              </p>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] uppercase text-[#9AA4AC]">Input Contract</span>
              <div className="p-2 rounded-[4px] bg-[#0C0E10] border border-[#2A3036] text-[#EDF0F2]">
                {LIFECYCLE_STEPS[selectedStep].input}
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] uppercase text-[#9AA4AC]">Produced Verified Artifact</span>
              <div className="p-2 rounded-[4px] bg-[#0C0E10] border border-[#2A3036] text-[#9CE8CE]">
                {LIFECYCLE_STEPS[selectedStep].output}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default WorkflowSection;
