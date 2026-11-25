"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Search,
  CheckCircle2,
  AlertCircle,
  Clock,
  ArrowUpRight,
  Filter,
  ShieldCheck,
  Wrench,
  ChevronRight,
  Layers,
} from "lucide-react";

interface IncidentRow {
  id: string;
  issue: string;
  repository: string;
  language: string;
  severity: "High" | "Medium" | "Low";
  status: "VERIFIED" | "INVESTIGATING" | "REPAIRING" | "AWAITING_REVIEW" | "FAILED";
  detected: string;
  repairSha?: string;
  verificationStatus: "Passed (4/4)" | "Running" | "Blocked" | "Pending";
}

const INCIDENTS: IncidentRow[] = [
  {
    id: "DVA-142",
    issue: "Enterprise discount branch omitted in calculate_total",
    repository: "acme/payment-service",
    language: "Python 3.12",
    severity: "High",
    status: "AWAITING_REVIEW",
    detected: "4m ago",
    repairSha: "9d2c7e1",
    verificationStatus: "Passed (4/4)",
  },
  {
    id: "DVA-141",
    issue: "Safe webhook payload dictionary KeyError in processor",
    repository: "acme/events-worker",
    language: "Python 3.11",
    severity: "Medium",
    status: "VERIFIED",
    detected: "18m ago",
    repairSha: "3f8e12a",
    verificationStatus: "Passed (4/4)",
  },
  {
    id: "DVA-140",
    issue: "Century leap year Gregorian boundary assertion error",
    repository: "acme/calendar-util",
    language: "Python 3.12",
    severity: "Low",
    status: "VERIFIED",
    detected: "1h ago",
    repairSha: "7b4c901",
    verificationStatus: "Passed (4/4)",
  },
  {
    id: "DVA-139",
    issue: "Missing hashlib import in security token hasher",
    repository: "acme/auth-service",
    language: "Python 3.10",
    severity: "High",
    status: "VERIFIED",
    detected: "2h ago",
    repairSha: "5a1d882",
    verificationStatus: "Passed (4/4)",
  },
  {
    id: "DVA-138",
    issue: "Zero quantity division guard in unit pricing formula",
    repository: "acme/billing-api",
    language: "Python 3.12",
    severity: "Medium",
    status: "VERIFIED",
    detected: "3h ago",
    repairSha: "2c7e449",
    verificationStatus: "Passed (4/4)",
  },
];

export function ActiveIncidentsTable() {
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  const filtered = INCIDENTS.filter(
    (i) => filterSeverity === "ALL" || i.severity === filterSeverity
  );

  const getSeverityBadge = (sev: IncidentRow["severity"]) => {
    switch (sev) {
      case "High":
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#E5BD7D]/10 text-[#E5BD7D] border border-[#E5BD7D]/20 font-mono text-[10px]">
            High
          </span>
        );
      case "Medium":
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#9CE8CE]/10 text-[#9CE8CE] border border-[#9CE8CE]/20 font-mono text-[10px]">
            Medium
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#191D21] text-[#9AA4AC] border border-[#2A3036] font-mono text-[10px]">
            Low
          </span>
        );
    }
  };

  const getStatusBadge = (status: IncidentRow["status"]) => {
    switch (status) {
      case "VERIFIED":
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#85D9AE]/10 text-[#85D9AE] border border-[#85D9AE]/20 font-mono text-[10px]">
            ✓ Verified
          </span>
        );
      case "AWAITING_REVIEW":
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#E5BD7D]/10 text-[#E5BD7D] border border-[#E5BD7D]/20 font-mono text-[10px]">
            Awaiting Review
          </span>
        );
      case "REPAIRING":
      case "INVESTIGATING":
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#9CE8CE]/10 text-[#9CE8CE] border border-[#9CE8CE]/20 font-mono text-[10px]">
            Processing
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 rounded-[2px] bg-[#EE9393]/10 text-[#EE9393] border border-[#EE9393]/20 font-mono text-[10px]">
            Failed
          </span>
        );
    }
  };

  return (
    <div className="bg-[#121518] border border-[#2A3036] rounded-[6px] p-4 sm:p-5 space-y-4 w-full max-w-full overflow-hidden">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#2A3036]">
        <div>
          <h3 className="text-sm font-semibold text-[#EDF0F2] flex items-center gap-2">
            <Layers className="w-4 h-4 text-[#9CE8CE]" /> Active Maintenance Incidents
          </h3>
          <p className="text-xs text-[#9AA4AC] mt-0.5 font-sans">
            Live defect queue, fault localization top-1, and sandbox verification audit.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs font-mono text-[#9AA4AC] bg-[#0C0E10] border border-[#2A3036] rounded-[4px] p-0.5">
            <button
              onClick={() => setFilterSeverity("ALL")}
              className={`px-2 py-0.5 rounded-[2px] transition-colors duration-120 ${
                filterSeverity === "ALL" ? "bg-[#191D21] text-[#EDF0F2]" : "hover:text-[#EDF0F2]"
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterSeverity("High")}
              className={`px-2 py-0.5 rounded-[2px] transition-colors duration-120 ${
                filterSeverity === "High" ? "bg-[#191D21] text-[#E5BD7D]" : "hover:text-[#EDF0F2]"
              }`}
            >
              High
            </button>
            <button
              onClick={() => setFilterSeverity("Medium")}
              className={`px-2 py-0.5 rounded-[2px] transition-colors duration-120 ${
                filterSeverity === "Medium" ? "bg-[#191D21] text-[#9CE8CE]" : "hover:text-[#EDF0F2]"
              }`}
            >
              Medium
            </button>
          </div>

          <Link
            href="/investigations"
            className="text-xs font-mono text-[#9CE8CE] hover:underline flex items-center gap-1 pl-2"
          >
            <span>All Issues</span>
            <ArrowUpRight className="w-3 h-3" />
          </Link>
        </div>
      </div>

      {/* Standalone compact skeleton row matching Figma ("Scanning issue evidence...") */}
      <div className="p-3 rounded-[4px] bg-[#0C0E10] border border-[#2A3036] flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2.5">
          <span className="w-2 h-2 rounded-full bg-[#9CE8CE] animate-pulse" />
          <span className="text-[#9CE8CE]">SCANNING:</span>
          <span className="text-[#EDF0F2]">DVA-143 &bull; acme/pricing-engine (pytest failure captured)</span>
        </div>
        <span className="text-[10px] text-[#9AA4AC] animate-pulse">Running AST search...</span>
      </div>

      {/* 7-Column Data Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-[#2A3036] text-[11px] font-mono text-[#9AA4AC]">
              <th className="pb-2.5 font-medium">Issue</th>
              <th className="pb-2.5 font-medium">Repository</th>
              <th className="pb-2.5 font-medium">Severity</th>
              <th className="pb-2.5 font-medium">Status</th>
              <th className="pb-2.5 font-medium">Detected</th>
              <th className="pb-2.5 font-medium">Repair SHA</th>
              <th className="pb-2.5 font-medium text-right">Verification</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#2A3036]/60 font-sans">
            {filtered.map((item) => (
              <tr
                key={item.id}
                className="hover:bg-[#191D21] transition-colors duration-120 group cursor-pointer"
              >
                <td className="py-3 pr-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-[#9CE8CE]">{item.id}</span>
                    <span className="font-medium text-[#EDF0F2] group-hover:text-white truncate max-w-[280px]">
                      {item.issue}
                    </span>
                  </div>
                </td>
                <td className="py-3 px-3 font-mono text-[11px] text-[#9AA4AC]">
                  {item.repository}
                </td>
                <td className="py-3 px-3">
                  {getSeverityBadge(item.severity)}
                </td>
                <td className="py-3 px-3">
                  {getStatusBadge(item.status)}
                </td>
                <td className="py-3 px-3 font-mono text-[11px] text-[#9AA4AC]">
                  {item.detected}
                </td>
                <td className="py-3 px-3 font-mono text-[11px]">
                  {item.repairSha ? (
                    <span className="text-[#EDF0F2] bg-[#0C0E10] px-1.5 py-0.5 rounded-[2px] border border-[#2A3036]">
                      {item.repairSha}
                    </span>
                  ) : (
                    <span className="text-[#9AA4AC]">—</span>
                  )}
                </td>
                <td className="py-3 pl-3 text-right font-mono text-[11px]">
                  <span className="text-[#85D9AE] font-semibold">{item.verificationStatus}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default ActiveIncidentsTable;
