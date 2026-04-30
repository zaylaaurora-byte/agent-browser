"use client";

import { HeroSection } from "@/components/hero-section";
import { AgentBrowser } from "@/components/agent-browser";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-[#050508] text-zinc-100 overflow-x-hidden">
      <HeroSection />
      <AgentBrowser />
    </div>
  );
}
