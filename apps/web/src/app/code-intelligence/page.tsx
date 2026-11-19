"use client";

import React, { useState } from "react";
import {
  Network,
  Search,
  Code2,
  FileCode,
  GitCommit,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Layers,
  ArrowRight,
  Filter,
  Terminal,
  Zap,
} from "lucide-react";

interface SymbolItem {
  id: string;
  name: string;
  qualified_name: string;
  kind: string;
  file_path: string;
  start_line: number;
  end_line: number;
  signature?: string;
  docstring?: string;
}

interface TestMappingItem {
  test_file: string;
  source_file: string;
  confidence: number;
  relationship_type: string;
}

interface SearchMatchItem {
  tier: string;
  file: string;
  line: number;
  text: string;
  symbol_name?: string;
  kind?: string;
  score: number;
}

export default function CodeIntelligencePage() {
  const [activeTab, setActiveTab] = useState<"search" | "symbols" | "graph" | "tests" | "git">("search");
  const [searchQuery, setSearchQuery] = useState("Calculator");
  const [searchTier, setSearchTier] = useState<"all" | "ripgrep" | "symbol" | "path">("all");
  const [isSearching, setIsSearching] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [symbolKindFilter, setSymbolKindFilter] = useState("all");

  // Sample and loaded data
  const [searchResults, setSearchResults] = useState<SearchMatchItem[]>([
    {
      tier: "symbol",
      file: "calculator/core.py",
      line: 10,
      text: "class Calculator",
      symbol_name: "Calculator",
      kind: "class",
      score: 1.0,
    },
    {
      tier: "symbol",
      file: "calculator/advanced.py",
      line: 7,
      text: "class ScientificCalculator(Calculator)",
      symbol_name: "ScientificCalculator",
      kind: "class",
      score: 0.9,
    },
    {
      tier: "ripgrep",
      file: "tests/test_calculator.py",
      line: 6,
      text: "calc = Calculator()",
      score: 0.85,
    },
  ]);

  const [symbols] = useState<SymbolItem[]>([
    {
      id: "sym-1",
      name: "Calculator",
      qualified_name: "calculator.core.Calculator",
      kind: "class",
      file_path: "calculator/core.py",
      start_line: 10,
      end_line: 52,
      signature: "class Calculator",
      docstring: "Standard calculator performing basic arithmetic.",
    },
    {
      id: "sym-2",
      name: "add",
      qualified_name: "Calculator.add",
      kind: "method",
      file_path: "calculator/core.py",
      start_line: 16,
      end_line: 21,
      signature: "def add(self, a: Number, b: Number) -> Number",
      docstring: "Adds two numbers.",
    },
    {
      id: "sym-3",
      name: "divide",
      qualified_name: "Calculator.divide",
      kind: "method",
      file_path: "calculator/core.py",
      start_line: 35,
      end_line: 43,
      signature: "def divide(self, a: Number, b: Number) -> Number",
      docstring: "Divides a by b with zero-division safeguard.",
    },
    {
      id: "sym-4",
      name: "ScientificCalculator",
      qualified_name: "calculator.advanced.ScientificCalculator",
      kind: "class",
      file_path: "calculator/advanced.py",
      start_line: 7,
      end_line: 25,
      signature: "class ScientificCalculator(Calculator)",
      docstring: "Scientific calculator extending core arithmetic.",
    },
    {
      id: "sym-5",
      name: "power",
      qualified_name: "ScientificCalculator.power",
      kind: "method",
      file_path: "calculator/advanced.py",
      start_line: 10,
      end_line: 15,
      signature: "def power(self, base: Number, exponent: Number) -> Number",
      docstring: "Raises base to the power of exponent.",
    },
  ]);

  const [testMappings] = useState<TestMappingItem[]>([
    {
      test_file: "tests/test_calculator.py",
      source_file: "calculator/core.py",
      confidence: 0.95,
      relationship_type: "TESTS_FILE",
    },
    {
      test_file: "tests/test_advanced.py",
      source_file: "calculator/advanced.py",
      confidence: 0.95,
      relationship_type: "TESTS_FILE",
    },
  ]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    try {
      const res = await fetch("/api/v1/code-intelligence/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          tier: searchTier,
          max_results: 20,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.matches || []);
      }
    } catch {
      // Keep existing matches if offline during dev
    } finally {
      setIsSearching(false);
    }
  };

  const handleTriggerIndex = async () => {
    setIsIndexing(true);
    try {
      await fetch("/api/v1/code-intelligence/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace: ".", force_full: true }),
      });
    } catch {
      // Handled gracefully
    } finally {
      setIsIndexing(false);
    }
  };

  const filteredSymbols = symbolKindFilter === "all"
    ? symbols
    : symbols.filter((s) => s.kind.toLowerCase() === symbolKindFilter.toLowerCase());

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#1e293b] pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Code Intelligence</h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/30">
              AST Knowledge Graph
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Deterministic AST symbol extraction, multi-tier search, call graph analysis, and test mapping.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleTriggerIndex}
            disabled={isIndexing}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-blue-600/20"
          >
            <RefreshCw className={`w-4 h-4 ${isIndexing ? "animate-spin" : ""}`} />
            {isIndexing ? "Indexing Repository..." : "Index Repository"}
          </button>
        </div>
      </div>

      {/* Summary Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Indexed Files</span>
            <FileCode className="w-5 h-5 text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">12</p>
          <p className="text-xs text-gray-500 mt-1">Python, TypeScript, JS</p>
        </div>

        <div className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">AST Symbols</span>
            <Code2 className="w-5 h-5 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">48</p>
          <p className="text-xs text-gray-500 mt-1">Classes, Methods, Functions</p>
        </div>

        <div className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Graph Relationships</span>
            <Network className="w-5 h-5 text-purple-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">34</p>
          <p className="text-xs text-gray-500 mt-1">Imports, Calls, Extends</p>
        </div>

        <div className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Test Mappings</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">6</p>
          <p className="text-xs text-gray-500 mt-1">Source-to-test links</p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-[#1e293b] pb-px">
        {[
          { key: "search", label: "Multi-Tier Search", icon: Search },
          { key: "symbols", label: "Symbol Explorer", icon: Code2 },
          { key: "graph", label: "Dependency Graph", icon: Network },
          { key: "tests", label: "Test Relationships", icon: Layers },
          { key: "git", label: "Git Intelligence", icon: GitCommit },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                isActive
                  ? "border-blue-500 text-blue-400 bg-blue-500/5"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Multi-Tier Search */}
      {activeTab === "search" && (
        <div className="space-y-6">
          <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-3.5 text-gray-500" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search symbols, functions, or regex patterns..."
                className="w-full pl-10 pr-4 py-2.5 bg-[#0d131f] border border-[#1e293b] rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={searchTier}
                onChange={(e) => setSearchTier(e.target.value as any)}
                className="px-3 py-2.5 bg-[#0d131f] border border-[#1e293b] rounded-lg text-sm text-gray-300 focus:outline-none focus:border-blue-500"
              >
                <option value="all">All Tiers (Unified)</option>
                <option value="symbol">Tier 2: AST Symbols</option>
                <option value="ripgrep">Tier 1: Ripgrep Text</option>
                <option value="path">Tier 3: File Paths</option>
              </select>

              <button
                type="submit"
                disabled={isSearching}
                className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {isSearching ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                Search
              </button>
            </div>
          </form>

          {/* Results List */}
          <div className="space-y-3">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Matches ({searchResults.length})
            </div>
            {searchResults.map((m, idx) => (
              <div
                key={idx}
                className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-blue-500/40 transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase ${
                        m.tier === "symbol"
                          ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/30"
                          : m.tier === "ripgrep"
                          ? "bg-blue-500/10 text-blue-400 border border-blue-500/30"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {m.tier}
                    </span>
                    <span className="text-sm font-semibold text-white">{m.symbol_name || m.file}</span>
                    {m.kind && <span className="text-xs text-gray-400 font-mono">({m.kind})</span>}
                  </div>
                  <div className="text-xs font-mono text-gray-400">
                    {m.file}:{m.line}
                  </div>
                  <div className="text-xs font-mono text-gray-300 bg-[#090d16] px-3 py-1.5 rounded border border-[#1e293b] mt-1">
                    {m.text}
                  </div>
                </div>

                <div className="text-right shrink-0">
                  <span className="text-xs font-mono text-gray-500">Score: {Math.round(m.score * 100)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Symbol Explorer */}
      {activeTab === "symbols" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <span className="text-xs text-gray-400 font-medium">Filter by Kind:</span>
              <select
                value={symbolKindFilter}
                onChange={(e) => setSymbolKindFilter(e.target.value)}
                className="px-3 py-1.5 bg-[#0d131f] border border-[#1e293b] rounded-lg text-xs text-gray-300"
              >
                <option value="all">All Kinds</option>
                <option value="class">Class</option>
                <option value="method">Method</option>
                <option value="function">Function</option>
              </select>
            </div>
            <span className="text-xs text-gray-500 font-mono">Showing {filteredSymbols.length} symbols</span>
          </div>

          <div className="grid grid-cols-1 gap-3">
            {filteredSymbols.map((sym) => (
              <div
                key={sym.id}
                className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-5 hover:border-indigo-500/40 transition-colors space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-500/10 text-indigo-400 border border-indigo-500/30">
                      {sym.kind}
                    </span>
                    <span className="text-base font-semibold text-white">{sym.name}</span>
                    <span className="text-xs text-gray-400 font-mono">({sym.qualified_name})</span>
                  </div>
                  <span className="text-xs font-mono text-gray-500">
                    {sym.file_path}:{sym.start_line}-{sym.end_line}
                  </span>
                </div>

                {sym.signature && (
                  <div className="text-xs font-mono text-blue-300 bg-[#090d16] px-3 py-2 rounded border border-[#1e293b]">
                    {sym.signature}
                  </div>
                )}

                {sym.docstring && (
                  <p className="text-xs text-gray-400 italic pl-1">{sym.docstring}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Dependency Graph */}
      {activeTab === "graph" && (
        <div className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">Repository Knowledge Graph</h3>
            <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2.5 py-1 rounded border border-purple-500/30">
              34 Edges Resolved
            </span>
          </div>

          <div className="space-y-4">
            <div className="p-4 bg-[#090d16] rounded-lg border border-[#1e293b] space-y-2">
              <span className="text-xs font-mono text-gray-400 block uppercase tracking-wider">
                Inheritance Hierarchy
              </span>
              <div className="flex items-center gap-3 text-sm font-mono text-gray-200">
                <span className="text-blue-400">ScientificCalculator</span>
                <ArrowRight className="w-4 h-4 text-gray-500" />
                <span className="text-indigo-400">Calculator</span>
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  EXTENDS
                </span>
              </div>
            </div>

            <div className="p-4 bg-[#090d16] rounded-lg border border-[#1e293b] space-y-2">
              <span className="text-xs font-mono text-gray-400 block uppercase tracking-wider">
                Key Call Relationships
              </span>
              <div className="space-y-2 text-sm font-mono text-gray-200">
                <div className="flex items-center gap-3">
                  <span className="text-blue-400">Calculator.add</span>
                  <ArrowRight className="w-4 h-4 text-gray-500" />
                  <span className="text-purple-400">_validate_number</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    CALLS
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-blue-400">Calculator.divide</span>
                  <ArrowRight className="w-4 h-4 text-gray-500" />
                  <span className="text-purple-400">format_result</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    CALLS
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Test Relationships */}
      {activeTab === "tests" && (
        <div className="space-y-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Discovered Source-to-Test Associations
          </div>
          {testMappings.map((tm, idx) => (
            <div
              key={idx}
              className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono text-emerald-400 font-semibold">{tm.test_file}</span>
                  <ArrowRight className="w-4 h-4 text-gray-500" />
                  <span className="text-sm font-mono text-blue-400 font-semibold">{tm.source_file}</span>
                </div>
                <span className="text-xs text-gray-500 font-mono">
                  Relationship: {tm.relationship_type}
                </span>
              </div>

              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-mono font-semibold">
                  Confidence: {Math.round(tm.confidence * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tab 5: Git Intelligence */}
      {activeTab === "git" && (
        <div className="bg-[#0f172a]/60 border border-[#1e293b] rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">Recent Git History & Attribution</h3>
            <span className="text-xs text-gray-500 font-mono">Analyzed from local branch</span>
          </div>

          <div className="space-y-3">
            {[
              {
                hash: "1506bf6",
                msg: "feat(mcp): complete Phase 2 MCP client, native server, registry, and policy engine",
                author: "Devaura Agent",
                date: "Recent",
              },
              {
                hash: "86ae99d",
                msg: "feat(frontend): implement Next.js developer portal and interactive pages",
                author: "Devaura Agent",
                date: "Phase 1",
              },
              {
                hash: "66da821",
                msg: "feat(backend): implement FastAPI core routes, database models, and secret redaction",
                author: "Devaura Agent",
                date: "Phase 1",
              },
            ].map((commit, idx) => (
              <div
                key={idx}
                className="p-3 bg-[#090d16] rounded-lg border border-[#1e293b] flex items-center justify-between gap-4 text-xs font-mono"
              >
                <div className="flex items-center gap-3">
                  <span className="text-blue-400 font-bold">{commit.hash}</span>
                  <span className="text-gray-200">{commit.msg}</span>
                </div>
                <div className="text-gray-500 shrink-0">
                  {commit.author} &bull; {commit.date}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
