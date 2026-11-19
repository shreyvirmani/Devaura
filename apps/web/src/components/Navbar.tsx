"use client";

import React from "react";
import { Terminal, Shield, Bell, Github } from "lucide-react";

export function Navbar() {
  return (
    <header className="h-16 border-b border-[#1e293b] bg-[#0d131f]/80 backdrop-blur-md px-8 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#151c2d] border border-[#1e293b] text-xs font-mono text-gray-300">
          <Terminal className="w-3.5 h-3.5 text-blue-400" />
          <span>FSM: IDLE</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-xs font-mono text-emerald-400">
          <Shield className="w-3.5 h-3.5" />
          <span>Sandbox: Local Bounded</span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <a
          href="https://github.com/shreyvirmani/Devaura"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 text-xs font-medium text-gray-400 hover:text-white px-3 py-1.5 rounded-md hover:bg-[#151c2d] transition-colors"
        >
          <Github className="w-4 h-4" />
          <span>shreyvirmani/Devaura</span>
        </a>
        <div className="w-px h-5 bg-[#1e293b]" />
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-xs font-semibold text-blue-400">
            SV
          </div>
          <span className="text-xs font-medium text-gray-300">Shrey Virmani</span>
        </div>
      </div>
    </header>
  );
}
