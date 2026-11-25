"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  ArrowRight,
  GitBranch,
  Wrench,
  ShieldCheck,
  Cpu,
  Layers,
  Settings,
  X,
  FileCode,
  Activity,
} from "lucide-react";

interface CommandItem {
  id: string;
  title: string;
  subtitle: string;
  href: string;
  shortcut?: string;
  icon: React.ComponentType<{ className?: string }>;
  category: "Navigation" | "Actions" | "Repositories";
}

const COMMANDS: CommandItem[] = [
  {
    id: "nav-overview",
    title: "Go to Overview",
    subtitle: "System overview, hero pipeline narrative, and live status",
    href: "/",
    shortcut: "G O",
    icon: Layers,
    category: "Navigation",
  },
  {
    id: "nav-issues",
    title: "Go to Issues & Investigations",
    subtitle: "Root cause analysis and evidence provenance",
    href: "/investigations",
    shortcut: "G I",
    icon: Search,
    category: "Navigation",
  },
  {
    id: "nav-repairs",
    title: "Go to Repair Workspace",
    subtitle: "Patch generation, AST validation, and verification",
    href: "/repairs",
    shortcut: "G R",
    icon: Wrench,
    category: "Navigation",
  },
  {
    id: "nav-evaluation",
    title: "Go to Evaluation & Benchmarks",
    subtitle: "Held-out real-world test suite and reliability metrics",
    href: "/evaluation",
    shortcut: "G E",
    icon: ShieldCheck,
    category: "Navigation",
  },
  {
    id: "nav-intel",
    title: "Go to Code Intelligence",
    subtitle: "Symbol graph, AST index, and blast-radius tracing",
    href: "/code-intelligence",
    shortcut: "G C",
    icon: FileCode,
    category: "Navigation",
  },
  {
    id: "nav-mcp",
    title: "Go to MCP Hub",
    subtitle: "Deterministic tool policies and MCP server status",
    href: "/mcp",
    shortcut: "G M",
    icon: Cpu,
    category: "Navigation",
  },
  {
    id: "nav-repos",
    title: "Go to Repositories",
    subtitle: "Connected GitHub repositories and active branches",
    href: "/repositories",
    shortcut: "G P",
    icon: GitBranch,
    category: "Repositories",
  },
  {
    id: "nav-settings",
    title: "System Settings & Keys",
    subtitle: "LLM providers, sandbox boundaries, and safety policies",
    href: "/settings",
    shortcut: "G S",
    icon: Settings,
    category: "Navigation",
  },
];

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();

  const filtered = COMMANDS.filter(
    (c) =>
      c.title.toLowerCase().includes(query.toLowerCase()) ||
      c.subtitle.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (isOpen) onClose();
        else setQuery("");
      }
      if (!isOpen) return;

      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % (filtered.length || 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + filtered.length) % (filtered.length || 1));
      } else if (e.key === "Enter" && filtered[selectedIndex]) {
        e.preventDefault();
        router.push(filtered[selectedIndex].href);
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, filtered, selectedIndex, router, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-xl bg-[#121518] border border-[#2A3036] rounded-[8px] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-120">
        {/* Search Input Bar */}
        <div className="flex items-center px-4 py-3 border-b border-[#2A3036] gap-3">
          <Search className="w-4 h-4 text-[#9AA4AC]" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search commands, issues, repositories... ⌘ K"
            autoFocus
            className="flex-1 bg-transparent text-[#EDF0F2] text-sm placeholder-[#9AA4AC] focus:outline-none font-sans"
          />
          <button
            onClick={onClose}
            className="p-1 rounded text-[#9AA4AC] hover:text-[#EDF0F2] hover:bg-[#191D21]"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Command Items List */}
        <div className="max-h-80 overflow-y-auto p-2 space-y-1">
          {filtered.length === 0 ? (
            <div className="p-6 text-center text-xs text-[#9AA4AC] font-mono">
              No matching commands found.
            </div>
          ) : (
            filtered.map((item, index) => {
              const Icon = item.icon;
              const isSelected = index === selectedIndex;
              return (
                <div
                  key={item.id}
                  onClick={() => {
                    router.push(item.href);
                    onClose();
                  }}
                  onMouseEnter={() => setSelectedIndex(index)}
                  className={`
                    flex items-center justify-between px-3 py-2.5 rounded-[4px] cursor-pointer transition-colors duration-120
                    ${
                      isSelected
                        ? "bg-[#191D21] text-[#EDF0F2] border border-[#2A3036]"
                        : "text-[#9AA4AC] hover:bg-[#191D21] hover:text-[#EDF0F2] border border-transparent"
                    }
                  `}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`p-1.5 rounded-[4px] ${
                        isSelected
                          ? "bg-[#9CE8CE]/10 text-[#9CE8CE]"
                          : "bg-[#191D21] text-[#9AA4AC]"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="truncate">
                      <div className="text-xs font-medium text-[#EDF0F2]">{item.title}</div>
                      <div className="text-[11px] text-[#9AA4AC] truncate font-sans">
                        {item.subtitle}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pl-3 shrink-0">
                    {item.shortcut && (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#0C0E10] border border-[#2A3036] text-[#9AA4AC]">
                        {item.shortcut}
                      </span>
                    )}
                    <ArrowRight className="w-3.5 h-3.5 text-[#9AA4AC]" />
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer info matching Figma */}
        <div className="px-4 py-2 border-t border-[#2A3036] bg-[#0C0E10] flex items-center justify-between text-[11px] font-mono text-[#9AA4AC]">
          <div className="flex items-center gap-3">
            <span>↑ ↓ navigate</span>
            <span>↵ select</span>
            <span>esc close</span>
          </div>
          <span className="text-[#9CE8CE]">Devaura Core</span>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;
