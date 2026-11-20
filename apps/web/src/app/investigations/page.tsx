"use client";

import React, { useState, useEffect } from "react";
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
  Play,
  RefreshCw,
  AlertCircle,
  Terminal,
  Plus,
  Clock,
  ShieldAlert,
  Info,
  GitCommit,
  Activity,
  HelpCircle,
} from "lucide-react";

interface EvidenceItem {
  id: string;
  source: string;
  type: string;
  content: string;
  repository_path?: string;
  symbol_id?: string;
  line_start?: number;
  line_end?: number;
  commit_sha?: string;
  confidence: number;
  relevance: number;
  metadata_json: Record<string, any>;
  created_at: string;
}

interface RootCauseCandidate {
  id: string;
  title: string;
  description: string;
  confidence: number;
  affected_symbols: string[];
  affected_files: string[];
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  reasoning: string;
  created_at: string;
}

interface InvestigationStep {
  id: string;
  step_number: number;
  action: string;
  tool_name?: string;
  tool_input: Record<string, any>;
  tool_output: Record<string, any>;
  observation: string;
  created_at: string;
}

interface InvestigationData {
  id: string;
  repository_id: string;
  source_type: string;
  source_id: string;
  status: string;
  title?: string;
  summary: string;
  failure_type: string;
  error_message?: string;
  stack_trace?: string;
  failed_tests: any[];
  ci_run_id?: string;
  commit_sha?: string;
  branch?: string;
  evidence_sufficiency: string;
  root_cause?: string;
  confidence?: number;
  created_at: string;
  updated_at: string;
  evidence_items: EvidenceItem[];
  root_cause_candidates: RootCauseCandidate[];
  investigation_steps: InvestigationStep[];
}

export default function InvestigationsPage() {
  const [investigations, setInvestigations] = useState<InvestigationData[]>([]);
  const [selectedInv, setSelectedInv] = useState<InvestigationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<"overview" | "evidence" | "candidates" | "timeline">("overview");
  const [evidenceFilter, setEvidenceFilter] = useState<string>("ALL");
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Form states
  const [newTitle, setNewTitle] = useState("");
  const [newFailureType, setNewFailureType] = useState("RUNTIME_ERROR");
  const [newErrorMsg, setNewErrorMsg] = useState("");
  const [newStackTrace, setNewStackTrace] = useState("");
  const [newRepoId, setNewRepoId] = useState("");

  const fetchInvestigations = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/investigations");
      if (res.ok) {
        const data = await res.json();
        setInvestigations(data);
        if (data.length > 0 && !selectedInv) {
          setSelectedInv(data[0]);
        } else if (selectedInv) {
          const updated = data.find((inv: InvestigationData) => inv.id === selectedInv.id);
          if (updated) setSelectedInv(updated);
        }
      }
    } catch (e) {
      console.error("Failed to fetch investigations", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvestigations();
  }, []);

  const handleRunInvestigation = async (invId: string) => {
    setRunning(true);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/investigations/${invId}/run`, {
        method: "POST",
      });
      if (res.ok) {
        const updated = await res.json();
        setSelectedInv(updated);
        fetchInvestigations();
      }
    } catch (e) {
      console.error("Failed to run investigation", e);
    } finally {
      setRunning(false);
    }
  };

  const handleCreateInvestigation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        repository_id: newRepoId || (investigations[0]?.repository_id ?? "default-repo"),
        title: newTitle || "Reported Failure Investigation",
        failure_type: newFailureType,
        error_message: newErrorMsg || undefined,
        stack_trace: newStackTrace || undefined,
      };
      const res = await fetch("http://localhost:8000/api/v1/investigations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const created = await res.json();
        setShowCreateModal(false);
        setNewTitle("");
        setNewErrorMsg("");
        setNewStackTrace("");
        await fetchInvestigations();
        setSelectedInv(created);
        // Automatically run engine
        handleRunInvestigation(created.id);
      }
    } catch (e) {
      console.error("Failed to create investigation", e);
    }
  };

  const getSufficiencyBadge = (sufficiency: string) => {
    switch (sufficiency) {
      case "SUFFICIENT":
        return (
          <span className="px-2.5 py-1 rounded text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" /> SUFFICIENT EVIDENCE
          </span>
        );
      case "PARTIALLY_SUFFICIENT":
        return (
          <span className="px-2.5 py-1 rounded text-xs font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" /> PARTIALLY SUFFICIENT
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded text-xs font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center gap-1.5">
            <AlertCircle className="w-3.5 h-3.5" /> INSUFFICIENT EVIDENCE
          </span>
        );
    }
  };

  const filteredEvidence = selectedInv?.evidence_items.filter((item) => {
    if (evidenceFilter === "ALL") return true;
    return item.source === evidenceFilter || item.type === evidenceFilter;
  }) || [];

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Top Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
              <Search className="w-6 h-6 text-blue-400" /> Issue Investigation
            </h1>
            {selectedInv && getSufficiencyBadge(selectedInv.evidence_sufficiency)}
            {selectedInv && (
              <span className="px-2.5 py-1 rounded text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
                {selectedInv.status}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Deterministic root cause analysis and evidence provenance for software failures.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#151c2d] hover:bg-[#1a233a] text-gray-200 text-sm font-medium border border-[#1e293b] transition-colors"
          >
            <Plus className="w-4 h-4 text-blue-400" /> New Investigation
          </button>
          {selectedInv && (
            <button
              onClick={() => handleRunInvestigation(selectedInv.id)}
              disabled={running}
              className="flex items-center gap-2 px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50"
            >
              {running ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" /> Investigating...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" /> Run Investigation
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Select Investigation Selector Bar */}
      {investigations.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto pb-2">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider mr-2">History:</span>
          {investigations.map((inv) => (
            <button
              key={inv.id}
              onClick={() => setSelectedInv(inv)}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono border whitespace-nowrap transition-all ${
                selectedInv?.id === inv.id
                  ? "bg-blue-600/20 text-blue-300 border-blue-500/50 shadow-sm"
                  : "bg-[#111726] text-gray-400 border-[#1e293b] hover:text-white"
              }`}
            >
              {inv.title || inv.summary.slice(0, 30)} &bull; {inv.status}
            </button>
          ))}
        </div>
      )}

      {selectedInv ? (
        <div className="space-y-6">
          {/* Navigation Tabs */}
          <div className="flex items-center gap-4 border-b border-[#1e293b]">
            <button
              onClick={() => setActiveTab("overview")}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "overview"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              Overview & Candidates
            </button>
            <button
              onClick={() => setActiveTab("evidence")}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "evidence"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              Ranked Evidence
              <span className="px-1.5 py-0.5 rounded-full text-xs bg-[#1e293b] text-gray-300">
                {selectedInv.evidence_items.length}
              </span>
            </button>
            <button
              onClick={() => setActiveTab("timeline")}
              className={`pb-3 text-sm font-medium border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "timeline"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              Investigation Steps
              <span className="px-1.5 py-0.5 rounded-full text-xs bg-[#1e293b] text-gray-300">
                {selectedInv.investigation_steps.length}
              </span>
            </button>
          </div>

          {/* TAB 1: OVERVIEW & CANDIDATES */}
          {activeTab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column (2 Cols): Root Cause Candidates & Diagnosis */}
              <div className="lg:col-span-2 space-y-6">
                {/* Failure Context Summary */}
                <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Terminal className="w-4 h-4 text-blue-400" /> Failure Information
                    </h2>
                    <span className="px-2 py-0.5 rounded text-xs font-mono bg-[#151c2d] text-gray-300 border border-[#1e293b]">
                      {selectedInv.failure_type}
                    </span>
                  </div>

                  {selectedInv.error_message && (
                    <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs font-mono">
                      {selectedInv.error_message}
                    </div>
                  )}

                  {selectedInv.stack_trace && (
                    <div className="space-y-1">
                      <span className="text-xs text-gray-400 font-mono">Stack Trace:</span>
                      <pre className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] text-xs font-mono text-gray-300 overflow-x-auto max-h-48">
                        {selectedInv.stack_trace}
                      </pre>
                    </div>
                  )}

                  {selectedInv.failed_tests && selectedInv.failed_tests.length > 0 && (
                    <div className="space-y-1">
                      <span className="text-xs text-gray-400 font-mono">Failing Tests:</span>
                      <div className="p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] space-y-1 text-xs">
                        {selectedInv.failed_tests.map((ft: any, i: number) => (
                          <div key={i} className="text-rose-400 font-mono">
                            &bull; {typeof ft === "string" ? ft : `${ft.test_file}::${ft.test_function}`}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Root Cause Candidates */}
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-semibold text-white flex items-center gap-2">
                      <Activity className="w-4 h-4 text-emerald-400" /> Root Cause Hypotheses
                    </h2>
                    <span className="text-xs text-gray-400">
                      {selectedInv.root_cause_candidates.length} candidate(s) synthesized
                    </span>
                  </div>

                  {selectedInv.root_cause_candidates.length === 0 ? (
                    <div className="p-6 rounded-xl bg-[#111726] border border-[#1e293b] text-center space-y-2">
                      <HelpCircle className="w-8 h-8 text-gray-500 mx-auto" />
                      <p className="text-sm text-gray-300 font-medium">No root cause candidates generated yet.</p>
                      <p className="text-xs text-gray-500">
                        {selectedInv.evidence_sufficiency === "INSUFFICIENT"
                          ? "Insufficient evidence to determine root cause. Provide a complete stack trace or failing test."
                          : "Click 'Run Investigation' to collect and analyze repository evidence."}
                      </p>
                    </div>
                  ) : (
                    selectedInv.root_cause_candidates.map((cand, idx) => (
                      <div
                        key={cand.id}
                        className={`rounded-xl border p-5 space-y-3 transition-all ${
                          idx === 0
                            ? "bg-[#111726] border-blue-500/30 shadow-md"
                            : "bg-[#0d131f] border-[#1e293b]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 rounded text-xs font-mono font-semibold bg-[#1e293b] text-gray-300">
                                #{idx + 1}
                              </span>
                              <h3 className="text-sm font-semibold text-white">{cand.title}</h3>
                            </div>
                            <p className="text-xs text-gray-400 mt-1">{cand.description}</p>
                          </div>
                          <div className="text-right">
                            <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-mono font-semibold">
                              Confidence: {Math.round(cand.confidence * 100)}%
                            </span>
                          </div>
                        </div>

                        {/* Affected Components */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-[#1e293b]/50 text-xs font-mono">
                          <div>
                            <span className="text-gray-500">Affected Files:</span>
                            <div className="text-blue-300 truncate">
                              {cand.affected_files.join(", ") || "None specified"}
                            </div>
                          </div>
                          <div>
                            <span className="text-gray-500">Affected Symbols:</span>
                            <div className="text-amber-300 truncate">
                              {cand.affected_symbols.join(", ") || "None specified"}
                            </div>
                          </div>
                        </div>

                        {/* Reasoning */}
                        {cand.reasoning && (
                          <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b]/60 text-xs text-gray-300">
                            <span className="text-gray-500 block mb-0.5">Reasoning:</span>
                            {cand.reasoning}
                          </div>
                        )}

                        {/* Provenance Evidence Tags */}
                        {cand.supporting_evidence_ids.length > 0 && (
                          <div className="flex items-center gap-2 text-xs">
                            <span className="text-gray-500">Supporting Evidence:</span>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              {cand.supporting_evidence_ids.map((evId) => (
                                <span
                                  key={evId}
                                  className="px-2 py-0.5 rounded bg-[#1e293b] text-blue-400 font-mono text-[11px]"
                                >
                                  {evId}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Right Column: Evidence Graph & Sufficiency Checklist */}
              <div className="space-y-6">
                {/* Evidence Sufficiency Status */}
                <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4 text-blue-400" /> Evidence Sufficiency
                  </h3>
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between text-gray-300">
                      <span>Stack Trace Frame</span>
                      {selectedInv.stack_trace ? (
                        <Check className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <X className="w-4 h-4 text-gray-500" />
                      )}
                    </div>
                    <div className="flex items-center justify-between text-gray-300">
                      <span>Regression Test Mapping</span>
                      {selectedInv.failed_tests.length > 0 ? (
                        <Check className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <X className="w-4 h-4 text-gray-500" />
                      )}
                    </div>
                    <div className="flex items-center justify-between text-gray-300">
                      <span>Resolved AST Call Graph</span>
                      {selectedInv.evidence_items.some((e) => e.type === "CALL_RELATIONSHIP") ? (
                        <Check className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <X className="w-4 h-4 text-gray-500" />
                      )}
                    </div>
                  </div>
                </div>

                {/* Evidence Traceability Graph Flow */}
                <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-5 space-y-3">
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Layers className="w-4 h-4 text-purple-400" /> Evidence Provenance Flow
                  </h3>
                  <div className="space-y-2 text-xs">
                    <div className="p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] font-mono">
                      <span className="text-rose-400 font-semibold block">1. Failure Event</span>
                      <span className="text-gray-400 truncate block">
                        {selectedInv.failure_type} &bull; {selectedInv.title || selectedInv.summary}
                      </span>
                    </div>
                    <div className="flex justify-center text-gray-600">&darr;</div>
                    <div className="p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] font-mono">
                      <span className="text-blue-400 font-semibold block">2. Failing Symbol</span>
                      <span className="text-gray-400 truncate block">
                        {selectedInv.root_cause_candidates[0]?.affected_symbols[0] || "Target Symbol (Resolving...)"}
                      </span>
                    </div>
                    <div className="flex justify-center text-gray-600">&darr;</div>
                    <div className="p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] font-mono">
                      <span className="text-amber-400 font-semibold block">3. Call Graph & Tests</span>
                      <span className="text-gray-400 truncate block">
                        {selectedInv.evidence_items.filter((e) => e.type === "CALL_RELATIONSHIP").length} Call(s),{" "}
                        {selectedInv.evidence_items.filter((e) => e.type === "TEST_RELATIONSHIP").length} Test(s)
                      </span>
                    </div>
                    <div className="flex justify-center text-gray-600">&darr;</div>
                    <div className="p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] font-mono">
                      <span className="text-emerald-400 font-semibold block">4. Verified Change Context</span>
                      <span className="text-gray-400 truncate block">
                        {selectedInv.evidence_items.filter((e) => e.type === "COMMIT").length} Recent Commit(s)
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: RANKED EVIDENCE LIST */}
          {activeTab === "evidence" && (
            <div className="space-y-4">
              {/* Category Filter Pills */}
              <div className="flex items-center gap-2 overflow-x-auto pb-2">
                {["ALL", "CODE_INTELLIGENCE", "GIT", "STACK_TRACE", "TEST"].map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setEvidenceFilter(cat)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-all ${
                      evidenceFilter === cat
                        ? "bg-blue-600/20 text-blue-300 border-blue-500/50"
                        : "bg-[#111726] text-gray-400 border-[#1e293b] hover:text-white"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              {filteredEvidence.length === 0 ? (
                <div className="p-8 text-center text-gray-500 text-sm bg-[#111726] rounded-xl border border-[#1e293b]">
                  No evidence matching current filter.
                </div>
              ) : (
                <div className="space-y-3">
                  {filteredEvidence.map((ev) => (
                    <div
                      key={ev.id}
                      className="p-4 rounded-xl bg-[#111726] border border-[#1e293b] flex flex-col md:flex-row md:items-center justify-between gap-4 text-xs font-mono"
                    >
                      <div className="space-y-1 max-w-3xl">
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded text-[11px] bg-[#1e293b] text-blue-400 font-semibold">
                            {ev.id}
                          </span>
                          <span className="text-gray-400 font-semibold">{ev.type}</span>
                          <span className="text-gray-600">&bull;</span>
                          <span className="text-gray-400">{ev.source}</span>
                          {ev.metadata_json?.resolution_status && (
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] ${
                                ev.metadata_json.resolution_status === "RESOLVED"
                                  ? "bg-emerald-500/10 text-emerald-400"
                                  : "bg-amber-500/10 text-amber-400"
                              }`}
                            >
                              {ev.metadata_json.resolution_status}
                            </span>
                          )}
                        </div>
                        <p className="text-gray-200 text-sm font-sans">{ev.content}</p>
                        {ev.repository_path && (
                          <span className="text-gray-500 text-[11px] block">
                            Location: {ev.repository_path}
                            {ev.line_start ? `:${ev.line_start}` : ""}
                          </span>
                        )}
                        {ev.metadata_json?.disclaimer && (
                          <span className="text-amber-400 text-[11px] block font-sans">
                            &bull; {ev.metadata_json.disclaimer}
                          </span>
                        )}
                      </div>

                      <div className="flex md:flex-col items-end gap-2 text-right">
                        <div className="space-y-0.5">
                          <span className="text-[10px] text-gray-500">Relevance</span>
                          <div className="w-24 bg-[#090d16] rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-blue-500 h-1.5 rounded-full"
                              style={{ width: `${Math.round(ev.relevance * 100)}%` }}
                            />
                          </div>
                        </div>
                        <div className="space-y-0.5">
                          <span className="text-[10px] text-gray-500">Confidence</span>
                          <div className="w-24 bg-[#090d16] rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-emerald-500 h-1.5 rounded-full"
                              style={{ width: `${Math.round(ev.confidence * 100)}%` }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: TIMELINE & STEPS */}
          {activeTab === "timeline" && (
            <div className="space-y-4">
              <h2 className="text-base font-semibold text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-blue-400" /> Bounded Execution Loop (Max 5 Iterations)
              </h2>

              <div className="space-y-3">
                {selectedInv.investigation_steps.map((step) => (
                  <div
                    key={step.id || step.step_number}
                    className="p-4 rounded-xl bg-[#111726] border border-[#1e293b] space-y-2 text-xs font-mono"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-400 font-semibold">
                          Step #{step.step_number}
                        </span>
                        <span className="text-white font-semibold">{step.action}</span>
                        {step.tool_name && (
                          <span className="text-gray-400 font-sans text-xs">
                            via <code className="text-amber-400 font-mono">{step.tool_name}</code>
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-gray-300 font-sans">{step.observation}</p>
                    {step.tool_output && Object.keys(step.tool_output).length > 0 && (
                      <pre className="p-2.5 rounded bg-[#090d16] border border-[#1e293b]/60 text-gray-400 overflow-x-auto">
                        {JSON.stringify(step.tool_output, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-12 text-center text-gray-400 bg-[#111726] rounded-xl border border-[#1e293b]">
          Select or create an investigation above.
        </div>
      )}

      {/* Modal: New Investigation */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#111726] border border-[#1e293b] rounded-xl max-w-xl w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Create New Investigation</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateInvestigation} className="space-y-4 text-xs font-mono">
              <div>
                <label className="text-gray-300 block mb-1">Investigation Title</label>
                <input
                  type="text"
                  placeholder="e.g. TypeError in UserService"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] text-white focus:outline-none focus:border-blue-500 font-sans text-sm"
                  required
                />
              </div>

              <div>
                <label className="text-gray-300 block mb-1">Failure Type</label>
                <select
                  value={newFailureType}
                  onChange={(e) => setNewFailureType(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] text-white focus:outline-none focus:border-blue-500 text-xs"
                >
                  <option value="RUNTIME_ERROR">RUNTIME_ERROR</option>
                  <option value="TEST_FAILURE">TEST_FAILURE</option>
                  <option value="BUILD_FAILURE">BUILD_FAILURE</option>
                  <option value="TYPECHECK_FAILURE">TYPECHECK_FAILURE</option>
                  <option value="LINT_FAILURE">LINT_FAILURE</option>
                  <option value="UNKNOWN">UNKNOWN</option>
                </select>
              </div>

              <div>
                <label className="text-gray-300 block mb-1">Error Message</label>
                <input
                  type="text"
                  placeholder="e.g. TypeError: 'NoneType' object is not subscriptable"
                  value={newErrorMsg}
                  onChange={(e) => setNewErrorMsg(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] text-white focus:outline-none focus:border-blue-500 font-sans text-xs"
                />
              </div>

              <div>
                <label className="text-gray-300 block mb-1">Stack Trace (Optional)</label>
                <textarea
                  rows={4}
                  placeholder="Paste Python, Pytest, or JS stack trace..."
                  value={newStackTrace}
                  onChange={(e) => setNewStackTrace(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#090d16] border border-[#1e293b] text-white focus:outline-none focus:border-blue-500 text-xs"
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-lg bg-[#151c2d] hover:bg-[#1a233a] text-gray-300 text-xs font-semibold border border-[#1e293b]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-500/20"
                >
                  Start Investigation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
