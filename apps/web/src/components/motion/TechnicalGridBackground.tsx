"use client";

import React from "react";

interface TechnicalGridBackgroundProps {
  children?: React.ReactNode;
  className?: string;
}

export function TechnicalGridBackground({
  children,
  className = "",
}: TechnicalGridBackgroundProps) {
  return (
    <div className={`relative overflow-hidden bg-[#0C0E10] ${className}`}>
      {/* Precision 1px grid pattern */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.14]"
        style={{
          backgroundImage: `
            linear-gradient(to right, #2A3036 1px, transparent 1px),
            linear-gradient(to bottom, #2A3036 1px, transparent 1px)
          `,
          backgroundSize: "32px 32px",
        }}
      />

      {/* Subtle radial illumination centered in the hero */}
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          background:
            "radial-gradient(ellipse 65% 50% at 50% 0%, rgba(156, 232, 206, 0.08), transparent 70%)",
        }}
      />

      {/* Perimeter vignette mask */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 80% at 50% 50%, transparent 40%, #0C0E10 100%)",
        }}
      />

      {/* Content wrapper */}
      <div className="relative z-10">{children}</div>
    </div>
  );
}

export default TechnicalGridBackground;
