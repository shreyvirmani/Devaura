"use client";

import React, { useState, useEffect } from "react";
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
  ShieldAlert,
  Info,
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
  id?: string;
  test_file: string;
  source_file: string;
  confidence: number;
  relationship_type: string;
  evidence?: string;
}

interface GraphEdgeItem {
  id: string;
  source_id: string;
  target_id: string;
  type: string;
  confidence: number;
  resolution_status: string;
  evidence?: string;
  source_location?: { file: string; line: number };
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

interface IndexStats {
  status: string;
  files_indexed: number;
  symbols_indexed: number;
  relationships_indexed: number;
  last_indexed_at?: string;
  duration_ms?: number;
}

export default function CodeIntelligencePage() {
  const [activeTab, setActiveTab] = useState<"search" | "symbols" | "graph" | "tests" | "git">("search");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchTier, setSearchTier] = useState<"all" | "ripgrep" | "symbol" | "path">("all");
  const [isSearching, setIsSearching] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [symbolKindFilter, setSymbolKindFilter] = useState("all");

  const [stats, setStats] = useState<IndexStats>({
    status: "READY",
    files_indexed: 0,
    symbols_indexed: 0,
    relationships_indexed: 0,
  });

  const [searchResults, setSearchResults] = useState<SearchMatchItem[]>([]);
  const [symbols, setSymbols] = useState<SymbolItem[]>([]);
  const [testMappings, setTestMappings] = useState<TestMappingItem[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdgeItem[]>([]);

  // Fetch real data on mount
  useEffect(() => {
    fetchIntelligenceData();
  }, []);

  const fetchIntelligenceData = async () => {
    try {
      // 1. Status
      const statusRes = await fetch("/api/v1/code-intelligence/status/local-workspace");
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStats(statusData);
      }

      // 2. Symbols
      const symRes = await fetch("/api/v1/code-intelligence/symbols/local-workspace?limit=100");
      if (symRes.ok) {
        const symData = await symRes.json();
        setSymbols(symData);
      }

      // 3. Graph
      const graphRes = await fetch("/api/v1/code-intelligence/graph/local-workspace");
      if (graphRes.ok) {
        const graphData = await graphRes.json();
        setGraphEdges(graphData.edges || []);
      }

      // 4. Test Mappings
      const testsRes = await fetch("/api/v1/code-intelligence/tests/local-workspace");
      if (testsRes.ok) {
        const testsData = await testsRes.json();
        setTestMappings(testsData);
      }
    } catch {
      // Fallback gracefully if API is offline during static prerender
    }
  };

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
          max_results: 25,
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data.matches || []);
      }
    } catch {
      // Offline fallback
    } finally {
      setIsSearching(false);
    }
  };

  const handleTriggerIndex = async () => {
    setIsIndexing(true);
    try {
      const res = await fetch("/api/v1/code-intelligence/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace: ".", force_full: true }),
      });
      if (res.ok) {
        await fetchIntelligenceData();
      }
    } catch {
      // Offline fallback
    } finally {
      setIsIndexing(false);
    }
  };

  const filteredSymbols = symbolKindFilter === "all"
    ? symbols
    : symbols.filter((s) => s.kind.toLowerCase() === symbolKindFilter.toLowerCase());

  const getResolutionBadge = (status: string) => {
    switch (status) {
      case "RESOLVED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "PARTIALLY_RESOLVED":
        return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
      case "AMBIGUOUS":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "UNRESOLVED":
      default:
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#2A3036] pb-6">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Code Intelligence</h1>
            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold font-mono border ${
              stats.status === "READY"
                ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                : stats.status === "STALE"
                ? "bg-amber-500/10 text-amber-400 border-amber-500/30"
                : "bg-blue-500/10 text-blue-400 border-blue-500/30"
            }`}>
              {stats.status}
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Deterministic AST symbol extraction, multi-tier search, call graph analysis, and evidence-backed test mapping.
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
        <div className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Indexed Files</span>
            <FileCode className="w-5 h-5 text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{stats.files_indexed}</p>
          <p className="text-xs text-gray-500 mt-1">Python, TypeScript, JavaScript</p>
        </div>

        <div className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">AST Symbols</span>
            <Code2 className="w-5 h-5 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{stats.symbols_indexed}</p>
          <p className="text-xs text-gray-500 mt-1">Classes, Methods, Functions</p>
        </div>

        <div className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Graph Relationships</span>
            <Network className="w-5 h-5 text-purple-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{stats.relationships_indexed}</p>
          <p className="text-xs text-gray-500 mt-1">Calls, Imports, Extends</p>
        </div>

        <div className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Discovered Tests</span>
            <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-2">{testMappings.length}</p>
          <p className="text-xs text-gray-500 mt-1">Mapped test-to-source pairs</p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-[#2A3036] pb-px">
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
                placeholder="Search functions, classes, regex, or file paths..."
                className="w-full pl-10 pr-4 py-2.5 bg-[#121518] border border-[#2A3036] rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={searchTier}
                onChange={(e) => setSearchTier(e.target.value as any)}
                className="px-3 py-2.5 bg-[#121518] border border-[#2A3036] rounded-lg text-sm text-gray-300 focus:outline-none focus:border-blue-500"
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
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Matches ({searchResults.length})
              </span>
              <span className="text-xs text-gray-500 font-mono">
                Tier 4 Semantic Search: <span className="text-amber-400">OPTIONAL / NOT ACTIVE</span>
              </span>
            </div>

            {searchResults.length === 0 ? (
              <div className="p-8 text-center bg-[#0f172a]/30 border border-[#2A3036] rounded-[6px] text-gray-500 text-sm">
                Enter a search query above to inspect code across AST symbols, Ripgrep matches, and paths.
              </div>
            ) : (
              searchResults.map((m, idx) => (
                <div
                  key={idx}
                  className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 hover:border-blue-500/40 transition-colors"
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
                    <div className="text-xs font-mono text-gray-300 bg-[#0C0E10] px-3 py-1.5 rounded border border-[#2A3036] mt-1">
                      {m.text}
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="text-xs font-mono text-gray-500">Confidence: {Math.round(m.score * 100)}%</span>
                  </div>
                </div>
              ))
            )}
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
                className="px-3 py-1.5 bg-[#121518] border border-[#2A3036] rounded-lg text-xs text-gray-300"
              >
                <option value="all">All Kinds</option>
                <option value="class">Class</option>
                <option value="method">Method</option>
                <option value="function">Function</option>
                <option value="interface">Interface</option>
                <option value="type_alias">Type Alias</option>
              </select>
            </div>
            <span className="text-xs text-gray-500 font-mono">Showing {filteredSymbols.length} symbols</span>
          </div>

          {filteredSymbols.length === 0 ? (
            <div className="p-8 text-center bg-[#0f172a]/30 border border-[#2A3036] rounded-[6px] text-gray-500 text-sm">
              No symbols extracted yet. Click &quot;Index Repository&quot; to parse workspace symbols.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {filteredSymbols.map((sym) => (
                <div
                  key={sym.id}
                  className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-5 hover:border-indigo-500/40 transition-colors space-y-2"
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
                    <div className="text-xs font-mono text-blue-300 bg-[#0C0E10] px-3 py-2 rounded border border-[#2A3036]">
                      {sym.signature}
                    </div>
                  )}

                  {sym.docstring && (
                    <p className="text-xs text-gray-400 italic pl-1">{sym.docstring}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Dependency Graph */}
      {activeTab === "graph" && (
        <div className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">Repository Knowledge Graph</h3>
            <span className="text-xs font-mono text-purple-400 bg-purple-500/10 px-2.5 py-1 rounded border border-purple-500/30">
              {graphEdges.length} Edges Discovered
            </span>
          </div>

          {graphEdges.length === 0 ? (
            <div className="p-8 text-center text-gray-500 text-sm">
              No graph relationships loaded. Index repository to generate dependencies.
            </div>
          ) : (
            <div className="space-y-3">
              {graphEdges.slice(0, 30).map((edge) => (
                <div
                  key={edge.id}
                  className="p-4 bg-[#0C0E10] rounded-lg border border-[#2A3036] flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs font-mono"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-3 text-gray-200">
                      <span className="text-blue-400 font-semibold">{edge.source_id.split(":").slice(1).join(":") || edge.source_id}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                      <span className="text-indigo-400 font-semibold">{edge.target_id.split(":").slice(1).join(":") || edge.target_id}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-400 border border-purple-500/30">
                        {edge.type}
                      </span>
                    </div>

                    {edge.evidence && (
                      <div className="text-[11px] text-gray-400 pl-1 flex items-center gap-1.5">
                        <Info className="w-3 h-3 text-gray-500" />
                        <span>Evidence: {edge.evidence}</span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${getResolutionBadge(edge.resolution_status)}`}>
                      {edge.resolution_status}
                    </span>
                    <span className="text-gray-500">
                      {Math.round(edge.confidence * 100)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 4: Test Relationships */}
      {activeTab === "tests" && (
        <div className="space-y-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Discovered Source-to-Test Associations ({testMappings.length})
          </div>

          {testMappings.length === 0 ? (
            <div className="p-8 text-center bg-[#0f172a]/30 border border-[#2A3036] rounded-[6px] text-gray-500 text-sm">
              No test relationships discovered. Index repository to map test suites to implementation sources.
            </div>
          ) : (
            testMappings.map((tm, idx) => (
              <div
                key={idx}
                className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-mono text-emerald-400 font-semibold">{tm.test_file}</span>
                    <ArrowRight className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-mono text-blue-400 font-semibold">{tm.source_file}</span>
                  </div>
                  {tm.evidence && (
                    <div className="text-xs text-gray-400 font-mono">
                      Evidence: <span className="text-gray-300">{tm.evidence}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-mono font-semibold">
                    Confidence: {Math.round(tm.confidence * 100)}%
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 5: Git Intelligence */}
      {activeTab === "git" && (
        <div className="bg-[#0f172a]/60 border border-[#2A3036] rounded-[6px] p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-white">Recent Git History & Provenance</h3>
            <span className="text-xs text-gray-500 font-mono">Commit Log</span>
          </div>

          <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-300 flex items-center gap-2">
            <Info className="w-4 h-4 shrink-0 text-amber-400" />
            <span>
              <strong>Note:</strong> Git commit co-occurrence measures historical correlation only. It does not establish structural dependency or causal relationships.
            </span>
          </div>

          <div className="space-y-3">
            {[
              {
                hash: "1e645b1",
                msg: "feat(code-intelligence): implement AST indexing, multi-tier search, repository graph, and MCP tools",
                author: "Devaura Agent",
                date: "Phase 3",
              },
              {
                hash: "1506bf6",
                msg: "feat(mcp): complete Phase 2 MCP client, native server, registry, and policy engine",
                author: "Devaura Agent",
                date: "Phase 2",
              },
              {
                hash: "86ae99d",
                msg: "feat(frontend): implement Next.js developer portal and interactive pages",
                author: "Devaura Agent",
                date: "Phase 1",
              },
            ].map((commit, idx) => (
              <div
                key={idx}
                className="p-3 bg-[#0C0E10] rounded-lg border border-[#2A3036] flex items-center justify-between gap-4 text-xs font-mono"
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
