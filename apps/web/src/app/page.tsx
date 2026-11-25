"use client";

import React from "react";
import { HeroSection } from "@/components/hero/HeroSection";
import { ActiveIncidentsTable } from "@/components/dashboard/ActiveIncidentsTable";
import { WorkflowSection } from "@/components/workflow/WorkflowSection";
import { TrustVerificationSection } from "@/components/trust/TrustVerificationSection";

export default function HomePage() {
  return (
    <div className="space-y-0 pb-16">
      {/* 1. Hero & Pipeline Visualization */}
      <HeroSection />

      {/* 2. Active Incidents & Data Table */}
      <div className="py-10 px-4 sm:px-8 max-w-6xl mx-auto">
        <ActiveIncidentsTable />
      </div>

      {/* 3. Orchestrated Lifecycle Architecture */}
      <WorkflowSection />

      {/* 4. Verification Gauntlet & Trust Policy */}
      <TrustVerificationSection />
    </div>
  );
}
