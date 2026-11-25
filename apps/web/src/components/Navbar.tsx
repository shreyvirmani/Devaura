"use client";

import React from "react";
import { Terminal, Shield, Github, Search, Command, CheckCircle2, Lock, Menu } from "lucide-react";

interface NavbarProps {
  onOpenCommandPalette?: () => void;
  onOpenMobileSidebar?: () => void;
}

export function Navbar({ onOpenCommandPalette, onOpenMobileSidebar }: NavbarProps) {
  return (
    <header className="h-14 border-b border-[#2A3036] bg-[#0C0E10]/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Left: Mobile Menu Toggle & System Status Pills */}
      <div className="flex items-center gap-2 sm:gap-2.5 overflow-hidden">
        <button
          onClick={onOpenMobileSidebar}
          type="button"
          className="md:hidden p-1.5 rounded-[4px] bg-[#121518] border border-[#2A3036] text-[#EDF0F2] hover:bg-[#191D21]"
          aria-label="Open navigation menu"
        >
          <Menu className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-1.5 px-2 py-1 rounded-[4px] bg-[#121518] border border-[#2A3036] text-[11px] font-mono text-[#EDF0F2] whitespace-nowrap">
          <Terminal className="w-3.5 h-3.5 text-[#9CE8CE]" />
          <span>FSM: IDLE</span>
        </div>

        <div className="hidden xs:flex items-center gap-1.5 px-2 py-1 rounded-[4px] bg-[#121518] border border-[#2A3036] text-[11px] font-mono text-[#85D9AE] whitespace-nowrap">
          <Shield className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">SANDBOX: BOUNDED</span>
          <span className="sm:hidden">BOUNDED</span>
        </div>

        <div className="hidden lg:flex items-center gap-1.5 px-2 py-1 rounded-[4px] bg-[#121518] border border-[#2A3036] text-[11px] font-mono text-[#E5BD7D] whitespace-nowrap">
          <Lock className="w-3 h-3" />
          <span>APPROVAL GATE: REQUIRED</span>
        </div>
      </div>

      {/* Right: Quick actions and GitHub Repo */}
      <div className="flex items-center gap-2 sm:gap-3 shrink-0">
        <button
          onClick={onOpenCommandPalette}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] bg-[#121518] hover:bg-[#191D21] border border-[#2A3036] text-[11px] font-mono text-[#9AA4AC] hover:text-[#EDF0F2] transition-colors duration-120"
        >
          <Search className="w-3 h-3" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="px-1 py-0.2 rounded bg-[#0C0E10] border border-[#2A3036] text-[9px]">
            ⌘K
          </kbd>
        </button>

        <a
          href="https://github.com/shreyvirmani/Devaura"
          target="_blank"
          rel="noreferrer"
          className="hidden sm:flex items-center gap-1.5 text-xs font-mono text-[#9AA4AC] hover:text-[#EDF0F2] px-2.5 py-1 rounded-[4px] bg-[#121518] hover:bg-[#191D21] border border-[#2A3036] transition-colors duration-120"
        >
          <Github className="w-3.5 h-3.5" />
          <span className="hidden md:inline">shreyvirmani/Devaura</span>
        </a>

        <div className="hidden sm:block w-px h-4 bg-[#2A3036]" />

        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-[#191D21] border border-[#2A3036] flex items-center justify-center text-[10px] font-mono text-[#9CE8CE]">
            SV
          </div>
        </div>
      </div>
    </header>
  );
}

export default Navbar;
