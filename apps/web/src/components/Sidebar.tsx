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
  Network,
  Command,
  User,
  CheckCircle2,
  ChevronDown,
  Activity,
  Layers,
  X,
} from "lucide-react";

interface SidebarProps {
  onOpenCommandPalette?: () => void;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

const navigation = [
  { name: "Overview", href: "/", icon: LayoutDashboard },
  { name: "Issues", href: "/investigations", icon: Search },
  { name: "Repairs", href: "/repairs", icon: Wrench },
  { name: "Code Intelligence", href: "/code-intelligence", icon: Network },
  { name: "Repositories", href: "/repositories", icon: GitBranch },
  { name: "MCP Hub", href: "/mcp", icon: Cpu },
  { name: "Evaluation", href: "/evaluation", icon: ShieldCheck },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Sidebar({
  onOpenCommandPalette,
  mobileOpen = false,
  onMobileClose,
}: SidebarProps) {
  const pathname = usePathname();

  const sidebarContent = (
    <aside className="w-64 bg-[#121518] border-r border-[#2A3036] flex flex-col shrink-0 h-screen sticky top-0 overflow-y-auto z-40">
      {/* Brand Header & Workspace Selector */}
      <div className="p-4 border-b border-[#2A3036] space-y-3">
        <div className="flex items-center justify-between">
          <Link
            href="/"
            onClick={onMobileClose}
            className="flex items-center gap-2.5"
          >
            <div className="w-7 h-7 rounded-[4px] bg-[#191D21] border border-[#2A3036] flex items-center justify-center font-mono font-bold text-xs text-[#9CE8CE]">
              DV
            </div>
            <div className="flex flex-col">
              <span className="font-semibold text-sm tracking-tight text-[#EDF0F2] leading-none">
                devaura
              </span>
              <span className="text-[10px] text-[#9AA4AC] font-mono tracking-wider mt-0.5">
                v1.2.0-core
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-[4px] bg-[#191D21] text-[#9CE8CE] border border-[#2A3036]">
              SANDBOX
            </span>
            {mobileOpen && (
              <button
                onClick={onMobileClose}
                className="md:hidden p-1 text-[#9AA4AC] hover:text-white"
                aria-label="Close navigation menu"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        {/* Workspace Pill */}
        <div className="flex items-center justify-between px-2.5 py-1.5 rounded-[4px] bg-[#0C0E10] border border-[#2A3036] text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-2 h-2 rounded-full bg-[#85D9AE]" />
            <span className="font-mono text-[11px] text-[#EDF0F2] truncate font-medium">
              ACME ENGINEERING
            </span>
          </div>
          <ChevronDown className="w-3 h-3 text-[#9AA4AC] shrink-0" />
        </div>

        {/* Command Palette Trigger */}
        <button
          onClick={() => {
            if (onMobileClose) onMobileClose();
            if (onOpenCommandPalette) onOpenCommandPalette();
          }}
          type="button"
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-[4px] bg-[#191D21] hover:bg-[#20252A] border border-[#2A3036] text-xs text-[#9AA4AC] hover:text-[#EDF0F2] transition-colors duration-120"
        >
          <div className="flex items-center gap-2">
            <Search className="w-3.5 h-3.5" />
            <span className="text-[11px] font-sans">Search anything...</span>
          </div>
          <kbd className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[#0C0E10] border border-[#2A3036] text-[#9AA4AC]">
            ⌘K
          </kbd>
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <div className="px-2 pb-2 text-[10px] font-mono font-semibold text-[#9AA4AC] uppercase tracking-wider">
          Platform
        </div>
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.name}
              href={item.href}
              onClick={onMobileClose}
              className={`
                flex items-center justify-between px-2.5 py-2 rounded-[4px] text-xs font-medium transition-colors duration-120
                ${
                  isActive
                    ? "bg-[#191D21] text-[#EDF0F2] border border-[#2A3036]"
                    : "text-[#9AA4AC] hover:text-[#EDF0F2] hover:bg-[#191D21] border border-transparent"
                }
              `}
            >
              <div className="flex items-center gap-2.5">
                <Icon
                  className={`w-4 h-4 ${
                    isActive ? "text-[#9CE8CE]" : "text-[#9AA4AC]"
                  }`}
                />
                <span>{item.name}</span>
              </div>
              {isActive && (
                <div className="w-1.5 h-1.5 rounded-full bg-[#9CE8CE]" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* System Status & Developer Footer */}
      <div className="p-3 border-t border-[#2A3036] bg-[#0C0E10] space-y-2">
        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-[#9AA4AC] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#85D9AE] animate-pulse" />
            Agent Engine
          </span>
          <span className="px-1.5 py-0.5 rounded-[4px] bg-[#121518] text-[#85D9AE] border border-[#2A3036]">
            ONLINE
          </span>
        </div>

        <div className="flex items-center gap-2 pt-1 border-t border-[#2A3036]/60">
          <div className="w-6 h-6 rounded-full bg-[#191D21] border border-[#2A3036] flex items-center justify-center text-[10px] font-mono text-[#EDF0F2]">
            SV
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-medium text-[#EDF0F2] truncate">
              Shrey Virmani
            </div>
            <div className="text-[10px] text-[#9AA4AC] font-mono truncate">
              Lead Maintainer
            </div>
          </div>
        </div>
      </div>
    </aside>
  );

  return (
    <>
      {/* Desktop Persistent Sticky Sidebar */}
      <div className="hidden md:block">{sidebarContent}</div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onMobileClose}
          />
          <div className="relative z-50">{sidebarContent}</div>
        </div>
      )}
    </>
  );
}

export default Sidebar;
