"use client";

import React, { useState } from "react";
import { AuthProvider } from "@/context/AuthContext";
import { Sidebar } from "@/components/Sidebar";
import { Navbar } from "@/components/Navbar";
import { CommandPalette } from "@/components/CommandPalette";

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <AuthProvider>
      <div className="bg-[#0C0E10] text-[#EDF0F2] flex min-h-screen max-w-[100vw] overflow-x-hidden">
        <Sidebar
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
          mobileOpen={mobileSidebarOpen}
          onMobileClose={() => setMobileSidebarOpen(false)}
        />
        <div className="flex-1 flex flex-col min-w-0 max-w-full overflow-x-hidden">
          <Navbar
            onOpenCommandPalette={() => setCommandPaletteOpen(true)}
            onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
          />
          <main className="flex-1 overflow-x-hidden">{children}</main>
        </div>
        <CommandPalette
          isOpen={commandPaletteOpen}
          onClose={() => setCommandPaletteOpen(false)}
        />
      </div>
    </AuthProvider>
  );
}

export default AppShell;
