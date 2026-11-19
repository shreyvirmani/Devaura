"use client";

import React, { useState } from "react";
import {
  Settings,
  Key,
  Shield,
  Layers,
  Save,
  Check,
  Github,
} from "lucide-react";

export default function SettingsPage() {
  const [provider, setProvider] = useState("gemini");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-[#1e293b]">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">System Settings</h1>
          <p className="text-sm text-gray-400 mt-1">
            Configure LLM inference providers, GitHub integrations, sandbox constraints, and tool permissions.
          </p>
        </div>
        <button
          onClick={handleSave}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-colors"
        >
          {saved ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />}
          {saved ? "Saved!" : "Save Changes"}
        </button>
      </div>

      {/* LLM Provider Configuration */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-base font-semibold text-white">
          <Key className="w-4 h-4 text-blue-400" />
          <span>LLM Inference Provider</span>
        </div>
        <p className="text-xs text-gray-400">
          Devaura utilizes a modular provider abstraction. Select your active backend:
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {(["gemini", "openai", "anthropic"] as const).map((prov) => (
            <div
              key={prov}
              onClick={() => setProvider(prov)}
              className={`p-3.5 rounded-lg border cursor-pointer text-center transition-all ${
                provider === prov
                  ? "bg-blue-600/15 border-blue-500 text-blue-300 font-semibold"
                  : "bg-[#090d16] border-[#1e293b] text-gray-400 hover:border-gray-700"
              }`}
            >
              <div className="capitalize text-sm">{prov}</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                {prov === "gemini" ? "Google Gemini 2.5 / 3.0" : prov === "openai" ? "GPT-4o / o1" : "Claude 3.5 Sonnet"}
              </div>
            </div>
          ))}
        </div>

        <div className="space-y-2 pt-2">
          <label className="text-xs font-mono text-gray-300 block">
            {provider.toUpperCase()}_API_KEY
          </label>
          <input
            type="password"
            defaultValue="••••••••••••••••••••••••••••••••"
            className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg px-4 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* GitHub Integration */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-base font-semibold text-white">
          <Github className="w-4 h-4 text-purple-400" />
          <span>GitHub Integration Credentials</span>
        </div>
        <p className="text-xs text-gray-400">
          Personal Access Token (PAT) used by the GitHub MCP Server for fetching issues, PRs, and posting verified fixes.
        </p>

        <div className="space-y-2">
          <label className="text-xs font-mono text-gray-300 block">GITHUB_TOKEN</label>
          <input
            type="password"
            defaultValue="ghp_••••••••••••••••••••••••••••••••••••"
            className="w-full bg-[#090d16] border border-[#1e293b] rounded-lg px-4 py-2 text-sm text-gray-200 font-mono focus:outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Sandbox Isolation Constraints */}
      <div className="bg-[#111726] border border-[#1e293b] rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 text-base font-semibold text-white">
          <Shield className="w-4 h-4 text-emerald-400" />
          <span>Execution Sandbox Boundaries</span>
        </div>
        <p className="text-xs text-gray-400">
          Enforce strict execution bounds when running tests, linters, and generated patches.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-center justify-between">
            <span className="text-gray-400">Max Execution Timeout:</span>
            <span className="text-white">120 seconds</span>
          </div>
          <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-center justify-between">
            <span className="text-gray-400">Memory Cap:</span>
            <span className="text-white">2048 MB</span>
          </div>
          <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-center justify-between">
            <span className="text-gray-400">CPU Core Quota:</span>
            <span className="text-white">2.0 vCPUs</span>
          </div>
          <div className="p-3 rounded-lg bg-[#090d16] border border-[#1e293b] flex items-center justify-between">
            <span className="text-gray-400">Repair Attempt Cap:</span>
            <span className="text-white">3 iterations max</span>
          </div>
        </div>
      </div>
    </div>
  );
}
