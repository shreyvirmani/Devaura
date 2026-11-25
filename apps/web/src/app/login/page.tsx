"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Lock, Mail, ArrowRight, AlertCircle, RefreshCw, CheckCircle2 } from "lucide-react";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const result = await login(email, password);
    setLoading(false);

    if (result.success) {
      router.push("/");
    } else {
      setError(result.error || "Failed to sign in. Please verify your credentials.");
    }
  };

  return (
    <div className="min-h-[85vh] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md bg-[#121518] border border-[#2A3036] rounded-[8px] p-6 sm:p-8 space-y-6 shadow-2xl">
        {/* Brand Header */}
        <div className="space-y-2 text-center">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-[6px] bg-[#191D21] border border-[#2A3036] text-[#9CE8CE] font-mono font-bold text-sm mb-1">
            DV
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#EDF0F2]">
            Sign in to Devaura
          </h1>
          <p className="text-xs text-[#9AA4AC]">
            Evidence-first software maintenance and repair platform
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="p-3 rounded-[4px] bg-[#EE9393]/10 border border-[#EE9393]/30 flex items-start gap-2.5 text-xs text-[#EE9393]">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-mono text-[#9AA4AC] block">
              Work Email
            </label>
            <div className="relative">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="engineer@company.com"
                className="w-full bg-[#0C0E10] border border-[#2A3036] rounded-[4px] px-3 py-2 text-xs text-[#EDF0F2] placeholder-[#9AA4AC]/60 focus:outline-none focus:border-[#9CE8CE] transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-mono text-[#9AA4AC] block">
                Password
              </label>
            </div>
            <div className="relative">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••••••"
                className="w-full bg-[#0C0E10] border border-[#2A3036] rounded-[4px] px-3 py-2 text-xs text-[#EDF0F2] placeholder-[#9AA4AC]/60 focus:outline-none focus:border-[#9CE8CE] transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-[4px] bg-[#9CE8CE] hover:bg-[#8CD8BE] disabled:opacity-50 text-[#0C0E10] font-semibold text-xs transition-colors duration-120 flex items-center justify-center gap-2 shadow-sm"
          >
            {loading ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Verifying credentials...</span>
              </>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        {/* Footer links */}
        <div className="pt-4 border-t border-[#2A3036] text-center text-xs text-[#9AA4AC]">
          <span>Don&apos;t have a workspace account? </span>
          <Link href="/signup" className="text-[#9CE8CE] hover:underline font-medium">
            Create workspace
          </Link>
        </div>
      </div>
    </div>
  );
}
