"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  Search,
  Wrench,
  Cpu,
  Settings,
  ShieldCheck,
  CheckCircle2,
  Network,
} from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Repositories", href: "/repositories", icon: GitBranch },
  { name: "Code Intelligence", href: "/code-intelligence", icon: Network },
  { name: "Investigations", href: "/investigations", icon: Search },
  { name: "Repair Workspace", href: "/repairs", icon: Wrench },
  { name: "MCP Hub", href: "/mcp", icon: Cpu },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-[#0d131f] border-r border-[#1e293b] flex flex-col shrink-0 min-h-screen">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-6 border-b border-[#1e293b] gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center font-bold text-white shadow-md shadow-blue-500/20">
          D
        </div>
        <div>
          <span className="font-semibold text-lg tracking-tight text-white block leading-tight">
            Devaura
          </span>
          <span className="text-[10px] text-blue-400 font-mono tracking-wider uppercase block">
            MCP Repair Agent
          </span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-6 space-y-1">
        <div className="px-3 pb-2 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
          Platform
        </div>
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-600/15 text-blue-400 border border-blue-500/30"
                  : "text-gray-400 hover:text-gray-200 hover:bg-[#151c2d]"
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? "text-blue-400" : "text-gray-500"}`} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* System Status Footer */}
      <div className="p-4 border-t border-[#1e293b] bg-[#090d16]">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-400 font-medium flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Agent Engine
          </span>
          <span className="text-[11px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
            ONLINE
          </span>
        </div>
        <div className="text-[11px] text-gray-500 font-mono">
          MCP Host &bull; Policy Active
        </div>
      </div>
    </aside>
  );
}
