"use client";

import React, { useState } from "react";
import {
  Cpu,
  CheckCircle2,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Play,
  Terminal,
  RefreshCw,
  Plus,
  Power,
  PowerOff,
  Code2,
  Shield,
  Layers,
  Check,
} from "lucide-react";

interface MCPTool {
  name: string;
  risk: "SAFE" | "CONTROLLED" | "DANGEROUS";
  desc: string;
  enabled: boolean;
}

interface MCPServer {
  id: string;
  name: string;
  transport: string;
  endpoint: string;
  status: "CONNECTED" | "DISCONNECTED" | "ERROR";
  trust: "TRUSTED" | "UNTRUSTED" | "DISABLED";
  tools: MCPTool[];
}

const initialServers: MCPServer[] = [
  {
    id: "srv_devaura_native",
    name: "Devaura Native MCP Server",
    transport: "native (Official MCP 2.x SDK)",
    endpoint: "internal://devaura-native",
    status: "CONNECTED",
    trust: "TRUSTED",
    tools: [
      { name: "read_file", risk: "SAFE", desc: "Read file contents bounded by line numbers with path traversal protection.", enabled: true },
      { name: "search_code", risk: "SAFE", desc: "Search repository source code for keyword or regex matches.", enabled: true },
      { name: "git_history", risk: "SAFE", desc: "Inspect git commit history and blame for repository files.", enabled: true },
      { name: "inspect_diff", risk: "SAFE", desc: "Inspect current workspace git diff with automated secret sanitization.", enabled: true },
      { name: "analyze_repository", risk: "SAFE", desc: "Deterministic analysis of repository languages, frameworks, package managers, and test suites.", enabled: true },
      { name: "find_related_tests", risk: "SAFE", desc: "Find unit and integration tests associated with a target source file.", enabled: true },
      { name: "run_tests", risk: "CONTROLLED", desc: "Execute unit tests inside bounded execution workspace (policy enforced).", enabled: true },
      { name: "run_linter", risk: "CONTROLLED", desc: "Run code linter checks inside workspace.", enabled: true },
      { name: "run_typecheck", risk: "CONTROLLED", desc: "Run type checking inside workspace.", enabled: true },
    ],
  },
  {
    id: "srv_github_mcp",
    name: "GitHub MCP Server",
    transport: "stdio (npx @modelcontextprotocol/server-github)",
    endpoint: "npx -y @modelcontextprotocol/server-github",
    status: "CONNECTED",
    trust: "TRUSTED",
    tools: [
      { name: "get_issue", risk: "SAFE", desc: "Fetches GitHub issue body, labels, and metadata.", enabled: true },
      { name: "get_comments", risk: "SAFE", desc: "Retrieves issue conversation thread.", enabled: true },
      { name: "get_workflow_run", risk: "SAFE", desc: "Retrieves CI logs and test run outputs.", enabled: true },
      { name: "create_pull_request", risk: "DANGEROUS", desc: "Opens Pull Request on GitHub with mandatory human sign-off.", enabled: true },
    ],
  },
  {
    id: "srv_mock_test",
    name: "Mock Test Server",
    transport: "native (internal://mock)",
    endpoint: "internal://mock",
    status: "DISCONNECTED",
    trust: "TRUSTED",
    tools: [
      { name: "mock_get_issue", risk: "SAFE", desc: "Fetches simulated issue context.", enabled: true },
      { name: "mock_search_code", risk: "SAFE", desc: "Simulated code search.", enabled: true },
      { name: "mock_run_tests", risk: "CONTROLLED", desc: "Simulated test execution.", enabled: true },
      { name: "mock_dangerous_push", risk: "DANGEROUS", desc: "Simulated dangerous push requiring human approval.", enabled: true },
    ],
  },
];

export default function MCPServerPage() {
  const [servers, setServers] = useState<MCPServer[]>(initialServers);
  const [selectedServer, setSelectedServer] = useState<MCPServer>(servers[0]);
  const [activeTab, setActiveTab] = useState<"tools" | "execute" | "register">("tools");
  const [filterRisk, setFilterRisk] = useState<string>("ALL");
  const [executingTool, setExecutingTool] = useState<string>("read_file");
  const [toolArgs, setToolArgs] = useState<string>('{\n  "path": "README.md",\n  "start_line": 1,\n  "end_line": 10\n}');
  const [execOutput, setExecOutput] = useState<string | null>(null);
  const [policyDecision, setPolicyDecision] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [newServerName, setNewServerName] = useState("");
  const [newServerEndpoint, setNewServerEndpoint] = useState("");
  const [newServerTransport, setNewServerTransport] = useState("stdio");

  // Toggle server connection status
  const toggleConnection = (serverId: string) => {
    setServers((prev) =>
      prev.map((s) => {
        if (s.id === serverId) {
          const nextStatus = s.status === "CONNECTED" ? "DISCONNECTED" : "CONNECTED";
          const updated = { ...s, status: nextStatus as any };
          if (selectedServer.id === serverId) {
            setSelectedServer(updated);
          }
          return updated;
        }
        return s;
      })
    );
  };

  // Run Tool Simulation with Policy Evaluation
  const handleExecuteTool = () => {
    setIsExecuting(true);
    setExecOutput(null);
    setPolicyDecision(null);

    setTimeout(() => {
      setIsExecuting(false);
      const toolObj = selectedServer.tools.find((t) => t.name === executingTool);
      const risk = toolObj ? toolObj.risk : "SAFE";

      if (risk === "DANGEROUS") {
        setPolicyDecision("REQUIRE_APPROVAL");
        setExecOutput(
          JSON.stringify(
            {
              status: "approval_required",
              reason: `Tool '${executingTool}' is classified as DANGEROUS and requires explicit human approval before execution.`,
              approval_token: "appr_demo_gate_9921",
              policy_action: "REQUIRE_APPROVAL",
            },
            null,
            2
          )
        );
      } else {
        setPolicyDecision("ALLOW");
        setExecOutput(
          JSON.stringify(
            {
              status: "success",
              server: selectedServer.name,
              tool: executingTool,
              latency_ms: 18.4,
              content: `--- README.md (lines 1-10 of 210) ---\n1: # Devaura — AI Software Repair & Maintenance Platform\n2: > Devaura — From failure to verified fix.\n... Verified tool execution ...`,
            },
            null,
            2
          )
        );
      }
    }, 600);
  };

  const filteredTools = selectedServer.tools.filter((t) => {
    if (filterRisk === "ALL") return true;
    return t.risk === filterRisk;
  });

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-[#1e293b]">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-white">Model Context Protocol (MCP) Hub</h1>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
              Host &bull; Client &bull; Native Server
            </span>
            <span className="px-2.5 py-0.5 rounded text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Policy Engine Active
            </span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Official MCP 2.x SDK integration layer: discover capabilities, enforce risk policies, and execute sandboxed operations.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("register")}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors shadow-lg shadow-blue-500/20"
          >
            <Plus className="w-4 h-4" />
            Register Server
          </button>
        </div>
      </div>

      {/* Main Grid: Server List & Tool Explorer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Server List (1 Col) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Registered Servers</h2>
            <span className="text-xs font-mono text-gray-500">{servers.length} configured</span>
          </div>

          {servers.map((server) => {
            const isSelected = selectedServer.id === server.id;
            const isConnected = server.status === "CONNECTED";
            return (
              <div
                key={server.id}
                onClick={() => setSelectedServer(server)}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? "bg-[#111726] border-blue-500 shadow-md shadow-blue-500/10"
                    : "bg-[#0d131f] border-[#1e293b] hover:border-gray-700"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-sm text-white">{server.name}</span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono border ${
                      isConnected
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-gray-500/10 text-gray-400 border-gray-500/20"
                    }`}
                  >
                    {server.status}
                  </span>
                </div>
                <div className="text-xs text-gray-400 font-mono mb-2 truncate">{server.transport}</div>
                <div className="flex items-center justify-between text-xs text-gray-500 pt-2 border-t border-[#1e293b]/60">
                  <span>{server.tools.length} Tools</span>
                  <span className="text-blue-400 font-mono text-[11px]">{server.trust}</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Server Operations & Tool Matrix (2 Cols) */}
        <div className="lg:col-span-2 bg-[#111726] border border-[#1e293b] rounded-xl p-6 space-y-6">
          {/* Top Server Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-[#1e293b] gap-3">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-white">{selectedServer.name}</h2>
                <span className="text-xs px-2 py-0.5 rounded font-mono bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {selectedServer.trust}
                </span>
              </div>
              <span className="text-xs text-gray-400 font-mono">{selectedServer.endpoint}</span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => toggleConnection(selectedServer.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-colors ${
                  selectedServer.status === "CONNECTED"
                    ? "bg-red-500/10 hover:bg-red-500/20 text-red-400 border-red-500/20"
                    : "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/20"
                }`}
              >
                {selectedServer.status === "CONNECTED" ? (
                  <>
                    <PowerOff className="w-3.5 h-3.5" /> Disconnect
                  </>
                ) : (
                  <>
                    <Power className="w-3.5 h-3.5" /> Connect
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Subtabs */}
          <div className="flex items-center gap-4 border-b border-[#1e293b] pb-2 text-xs">
            <button
              onClick={() => setActiveTab("tools")}
              className={`pb-1 font-semibold border-b-2 transition-colors ${
                activeTab === "tools"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              Tool Matrix ({selectedServer.tools.length})
            </button>
            <button
              onClick={() => setActiveTab("execute")}
              className={`pb-1 font-semibold border-b-2 transition-colors ${
                activeTab === "execute"
                  ? "border-blue-500 text-blue-400"
                  : "border-transparent text-gray-400 hover:text-gray-200"
              }`}
            >
              Test Tool Execution
            </button>
          </div>

          {/* Subtab 1: Tool Matrix */}
          {activeTab === "tools" && (
            <div className="space-y-4">
              {/* Risk Filter */}
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-400 font-medium">Risk Filter:</span>
                {(["ALL", "SAFE", "CONTROLLED", "DANGEROUS"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setFilterRisk(r)}
                    className={`px-2.5 py-1 rounded text-xs font-mono transition-colors ${
                      filterRisk === r
                        ? "bg-blue-600 text-white"
                        : "bg-[#0d131f] text-gray-400 hover:text-gray-200 border border-[#1e293b]"
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>

              {/* Tools List */}
              <div className="space-y-3">
                {filteredTools.map((tool) => {
                  const badgeStyle =
                    tool.risk === "SAFE"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : tool.risk === "CONTROLLED"
                      ? "bg-blue-500/10 text-blue-400 border-blue-500/20"
                      : "bg-red-500/10 text-red-400 border-red-500/20";

                  return (
                    <div
                      key={tool.name}
                      className="p-3.5 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-start justify-between gap-4"
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-xs font-semibold text-white">{tool.name}</span>
                          <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${badgeStyle}`}>
                            {tool.risk}
                          </span>
                        </div>
                        <p className="text-xs text-gray-400">{tool.desc}</p>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => {
                            setExecutingTool(tool.name);
                            setActiveTab("execute");
                          }}
                          className="px-2.5 py-1 rounded bg-[#151c2d] hover:bg-[#1a2337] text-gray-300 text-xs font-mono border border-[#1e293b] transition-colors"
                        >
                          Execute
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Subtab 2: Tool Execution Studio */}
          {activeTab === "execute" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-mono text-gray-300 block mb-1">Select Tool</label>
                  <select
                    value={executingTool}
                    onChange={(e) => setExecutingTool(e.target.value)}
                    className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-blue-500"
                  >
                    {selectedServer.tools.map((t) => (
                      <option key={t.name} value={t.name}>
                        {t.name} ({t.risk})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-mono text-gray-300 block mb-1">Policy Risk Level</label>
                  <div className="h-9 px-3 flex items-center rounded-lg bg-[#090d16] border border-[#1e293b] text-xs font-mono text-blue-400">
                    {selectedServer.tools.find((t) => t.name === executingTool)?.risk || "SAFE"}
                  </div>
                </div>
              </div>

              <div>
                <label className="text-xs font-mono text-gray-300 block mb-1">JSON Arguments</label>
                <textarea
                  value={toolArgs}
                  onChange={(e) => setToolArgs(e.target.value)}
                  rows={4}
                  className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg p-3 text-xs font-mono text-gray-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleExecuteTool}
                  disabled={isExecuting}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold flex items-center gap-2 transition-colors"
                >
                  <Play className="w-3.5 h-3.5" />
                  {isExecuting ? "Evaluating Policy & Executing..." : "Execute Through Policy Engine"}
                </button>

                {policyDecision && (
                  <span
                    className={`text-xs font-mono px-2.5 py-1 rounded border ${
                      policyDecision === "ALLOW"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    }`}
                  >
                    Policy Decision: {policyDecision}
                  </span>
                )}
              </div>

              {/* Execution Console Output */}
              {execOutput && (
                <div className="pt-2">
                  <label className="text-xs font-mono text-gray-400 block mb-1">Console Output &bull; Audit Verified</label>
                  <pre className="p-4 rounded-lg bg-[#090d16] border border-[#1e293b] font-mono text-xs text-gray-200 overflow-x-auto whitespace-pre-wrap">
                    {execOutput}
                  </pre>
                </div>
              )}
            </div>
          )}

          {/* Subtab 3: Register Server Form */}
          {activeTab === "register" && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-white">Register New MCP Server</h3>
              <div className="space-y-3 text-xs">
                <div>
                  <label className="font-mono text-gray-300 block mb-1">Server Name</label>
                  <input
                    type="text"
                    value={newServerName}
                    onChange={(e) => setNewServerName(e.target.value)}
                    placeholder="e.g. docker-mcp-server"
                    className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="font-mono text-gray-300 block mb-1">Transport</label>
                  <select
                    value={newServerTransport}
                    onChange={(e) => setNewServerTransport(e.target.value)}
                    className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                  >
                    <option value="stdio">stdio (Standard I/O)</option>
                    <option value="sse">sse (Server-Sent Events / HTTP)</option>
                    <option value="native">native (In-process Python)</option>
                  </select>
                </div>
                <div>
                  <label className="font-mono text-gray-300 block mb-1">Endpoint Command or URL</label>
                  <input
                    type="text"
                    value={newServerEndpoint}
                    onChange={(e) => setNewServerEndpoint(e.target.value)}
                    placeholder="e.g. npx -y @modelcontextprotocol/server-postgres"
                    className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>
                <button
                  onClick={() => {
                    if (newServerName && newServerEndpoint) {
                      const newSrv: MCPServer = {
                        id: `srv_${newServerName.toLowerCase().replace(/\s+/g, "_")}`,
                        name: newServerName,
                        transport: newServerTransport,
                        endpoint: newServerEndpoint,
                        status: "CONNECTED",
                        trust: "TRUSTED",
                        tools: [
                          { name: "sample_tool", risk: "SAFE", desc: "Sample discovered tool", enabled: true },
                        ],
                      };
                      setServers((prev) => [...prev, newSrv]);
                      setSelectedServer(newSrv);
                      setActiveTab("tools");
                      setNewServerName("");
                      setNewServerEndpoint("");
                    }
                  }}
                  className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs transition-colors"
                >
                  Confirm &amp; Connect Server
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
