"use client";

import React from "react";
import { motion } from "motion/react";

interface InteractiveCardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  accentBorder?: boolean;
}

export function InteractiveCard({
  children,
  className = "",
  onClick,
  accentBorder = false,
}: InteractiveCardProps) {
  return (
    <motion.div
      onClick={onClick}
      whileHover={{ y: -1 }}
      transition={{ duration: 0.12, ease: "easeOut" }}
      className={`
        bg-[#121518] border border-[#2A3036] rounded-[6px] transition-colors duration-120
        hover:bg-[#191D21] hover:border-[#3A424A]
        ${accentBorder ? "hover:border-[#9CE8CE]/40" : ""}
        ${onClick ? "cursor-pointer" : ""}
        ${className}
      `}
    >
      {children}
    </motion.div>
  );
}

export default InteractiveCard;
