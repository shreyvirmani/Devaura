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
  ExternalLink,
  Plus,
} from "lucide-react";

const mcpServers = [
  {
    id: "srv_devaura_native",
    name: "Devaura Native MCP Server",
    transport: "stdio (In-process / Python SDK)",
    status: "CONNECTED",
    toolsCount: 10,
    tools: [
      { name: "analyze_repository", risk: "SAFE", desc: "Analyzes project structure, frameworks, package managers" },
      { name: "search_code", risk: "SAFE", desc: "Multi-tier code search (ripgrep, exact AST token match)" },
      { name: "read_file", risk: "SAFE", desc: "Bounded file reader with path traversal protection" },
      { name: "git_history", risk: "SAFE", desc: "Inspects blame, commit history, and diff evolutions" },
      { name: "inspect_diff", risk: "SAFE", desc: "Computes semantic unified diff within a repair sandbox" },
      { name: "find_related_tests", risk: "SAFE", desc: "Discovers unit tests associated with affected symbols" },
      { name: "run_tests", risk: "CONTROLLED", desc: "Executes test runner inside isolated sandbox" },
      { name: "run_linter", risk: "CONTROLLED", desc: "Runs ruff/eslint within isolated environment" },
      { name: "apply_patch", risk: "CONTROLLED", desc: "Applies unified diff patch to workspace" },
      { name: "push_branch", risk: "DANGEROUS", desc: "Pushes fix branch to remote git repository" },
    ],
  },
  {
    id: "srv_github_mcp",
    name: "GitHub MCP Server",
    transport: "stdio (npx @modelcontextprotocol/server-github)",
    status: "CONNECTED",
    toolsCount: 5,
    tools: [
      { name: "get_issue", risk: "SAFE", desc: "Fetches issue body and labels" },
      { name: "get_comments", risk: "SAFE", desc: "Retrieves issue conversation thread" },
      { name: "get_workflow_run", risk: "SAFE", desc: "Retrieves CI logs and test run outputs" },
      { name: "create_pull_request", risk: "DANGEROUS", desc: "Opens PR on GitHub with human sign-off" },
    ],
  },
];

export default function MCPServerPage() {
  const [selectedServer, setSelectedServer] = useState(mcpServers[0]);

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
          </div>
          <p className="text-sm text-gray-400 mt-1">
            Registered MCP tool providers, protocol transport bindings, and security risk policies.
          </p>
        </div>

        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors shadow-lg shadow-blue-500/20">
          <Plus className="w-4 h-4" />
          Connect MCP Server
        </button>
      </div>

      {/* Main Grid: Server List & Tool Explorer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Server List (1 Col) */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Connected Servers</h2>
          {mcpServers.map((server) => {
            const isSelected = selectedServer.id === server.id;
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
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                    {server.status}
                  </span>
                </div>
                <div className="text-xs text-gray-400 font-mono mb-2">{server.transport}</div>
                <div className="text-xs text-gray-500">{server.toolsCount} Tools discovered</div>
              </div>
            );
          })}
        </div>

        {/* Tools & Permissions Matrix (2 Cols) */}
        <div className="lg:col-span-2 bg-[#111726] border border-[#1e293b] rounded-xl p-6">
          <div className="flex items-center justify-between pb-4 border-b border-[#1e293b] mb-4">
            <div>
              <h2 className="text-base font-semibold text-white">{selectedServer.name}</h2>
              <span className="text-xs text-gray-400">Tool definitions &bull; JSON-Schema validated</span>
            </div>
            <div className="flex items-center gap-2 text-xs font-mono">
              <span className="text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                SAFE
              </span>
              <span className="text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                CONTROLLED
              </span>
              <span className="text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
                DANGEROUS
              </span>
            </div>
          </div>

          <div className="space-y-3">
            {selectedServer.tools.map((tool) => {
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
                  <span className="text-[11px] font-mono text-gray-500 shrink-0">Policy: Enforced</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
