"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard,
  GitBranch,
  Search,
  Wrench,
  Cpu,
  Settings,
  ShieldCheck,
  Network,
  ChevronDown,
  Check,
  Plus,
  LogOut,
  LogIn,
  X,
  Layers,
  ShieldAlert,
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
  const {
    user,
    workspaces,
    currentWorkspace,
    isAuthenticated,
    isLiveMode,
    switchWorkspace,
    createWorkspace,
    logout,
  } = useAuth();

  const [workspaceMenuOpen, setWorkspaceMenuOpen] = useState(false);
  const [showCreateWsInput, setShowCreateWsInput] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [createLoading, setCreateLoading] = useState(false);

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setCreateLoading(true);
    await createWorkspace(newWsName.trim());
    setCreateLoading(false);
    setNewWsName("");
    setShowCreateWsInput(false);
    setWorkspaceMenuOpen(false);
  };

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
                v1.3.0-saas
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-1.5">
            <span
              className={`text-[9px] font-mono px-1.5 py-0.5 rounded-[4px] border ${
                isLiveMode
                  ? "bg-[#9CE8CE]/10 text-[#9CE8CE] border-[#9CE8CE]/30"
                  : "bg-[#E5BD7D]/10 text-[#E5BD7D] border-[#E5BD7D]/30"
              }`}
            >
              {isLiveMode ? "LIVE" : "DEMO"}
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

        {/* Dynamic Workspace Switcher Pill & Dropdown */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setWorkspaceMenuOpen((prev) => !prev)}
            className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-[4px] bg-[#0C0E10] hover:bg-[#191D21] border border-[#2A3036] text-xs transition-colors duration-120 text-left"
          >
            <div className="flex items-center gap-2 min-w-0">
              <div
                className={`w-2 h-2 rounded-full shrink-0 ${
                  isLiveMode ? "bg-[#85D9AE]" : "bg-[#E5BD7D]"
                }`}
              />
              <span className="font-mono text-[11px] text-[#EDF0F2] truncate font-medium">
                {currentWorkspace?.name || "Acme Engineering (Demo)"}
              </span>
            </div>
            <ChevronDown className="w-3 h-3 text-[#9AA4AC] shrink-0 ml-1" />
          </button>

          {/* Dropdown Menu */}
          {workspaceMenuOpen && (
            <div className="absolute top-full left-0 right-0 mt-1 z-50 bg-[#121518] border border-[#2A3036] rounded-[6px] shadow-2xl p-2 space-y-1 animate-in fade-in zoom-in-95 duration-120">
              <div className="px-2 py-1 text-[10px] font-mono uppercase text-[#9AA4AC] tracking-wider border-b border-[#2A3036]/60">
                Workspaces ({workspaces.length})
              </div>

              <div className="max-h-44 overflow-y-auto space-y-0.5">
                {workspaces.map((ws) => {
                  const isSelected = ws.id === currentWorkspace?.id;
                  return (
                    <button
                      key={ws.id}
                      type="button"
                      onClick={() => {
                        switchWorkspace(ws.id);
                        setWorkspaceMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between px-2 py-1.5 rounded-[4px] text-xs font-mono transition-colors text-left ${
                        isSelected
                          ? "bg-[#191D21] text-[#9CE8CE] font-semibold"
                          : "text-[#EDF0F2] hover:bg-[#191D21]"
                      }`}
                    >
                      <span className="truncate pr-2">{ws.name}</span>
                      {isSelected && <Check className="w-3 h-3 text-[#9CE8CE] shrink-0" />}
                    </button>
                  );
                })}
              </div>

              {/* Add Workspace Action */}
              <div className="pt-1 border-t border-[#2A3036]/60">
                {showCreateWsInput ? (
                  <form onSubmit={handleCreateWorkspace} className="space-y-1.5 p-1">
                    <input
                      type="text"
                      value={newWsName}
                      onChange={(e) => setNewWsName(e.target.value)}
                      placeholder="Workspace name"
                      autoFocus
                      className="w-full bg-[#0C0E10] border border-[#2A3036] rounded-[4px] px-2 py-1 text-xs text-[#EDF0F2] placeholder-[#9AA4AC]/60 focus:outline-none focus:border-[#9CE8CE]"
                    />
                    <div className="flex gap-1 justify-end">
                      <button
                        type="button"
                        onClick={() => setShowCreateWsInput(false)}
                        className="px-2 py-0.5 rounded text-[10px] text-[#9AA4AC] hover:text-white"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={createLoading || !newWsName.trim()}
                        className="px-2 py-0.5 rounded bg-[#9CE8CE] text-[#0C0E10] font-semibold text-[10px]"
                      >
                        {createLoading ? "..." : "Create"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      if (!isAuthenticated) {
                        window.location.href = "/signup";
                      } else {
                        setShowCreateWsInput(true);
                      }
                    }}
                    className="w-full flex items-center gap-1.5 px-2 py-1.5 rounded-[4px] text-xs font-mono text-[#9AA4AC] hover:text-[#9CE8CE] hover:bg-[#191D21] transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Create Workspace</span>
                  </button>
                )}
              </div>
            </div>
          )}
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

      {/* Dynamic User Profile & Status Footer */}
      <div className="p-3 border-t border-[#2A3036] bg-[#0C0E10] space-y-2">
        <div className="flex items-center justify-between text-[11px] font-mono">
          <span className="text-[#9AA4AC] flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#85D9AE] animate-pulse" />
            Tenant Sandbox
          </span>
          <span className="px-1.5 py-0.5 rounded-[4px] bg-[#121518] text-[#85D9AE] border border-[#2A3036]">
            BOUNDED
          </span>
        </div>

        {isAuthenticated && user ? (
          <div className="flex items-center justify-between pt-1 border-t border-[#2A3036]/60">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-full bg-[#191D21] border border-[#2A3036] flex items-center justify-center text-[10px] font-mono text-[#9CE8CE] shrink-0">
                {user.name.slice(0, 2).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-medium text-[#EDF0F2] truncate">
                  {user.name}
                </div>
                <div className="text-[10px] text-[#9AA4AC] font-mono truncate">
                  {user.email}
                </div>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="p-1 text-[#9AA4AC] hover:text-[#EE9393] transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between pt-1 border-t border-[#2A3036]/60">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-6 h-6 rounded-full bg-[#191D21] border border-[#2A3036] flex items-center justify-center text-[10px] font-mono text-[#9AA4AC] shrink-0">
                G
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[11px] font-medium text-[#EDF0F2] truncate">
                  Evaluation Guest
                </div>
                <div className="text-[10px] text-[#9AA4AC] font-mono truncate">
                  Demo Mode
                </div>
              </div>
            </div>
            <Link
              href="/login"
              title="Sign In"
              className="p-1 text-[#9CE8CE] hover:underline text-[11px] font-mono flex items-center gap-1"
            >
              <LogIn className="w-3 h-3" />
              <span>Login</span>
            </Link>
          </div>
        )}
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
