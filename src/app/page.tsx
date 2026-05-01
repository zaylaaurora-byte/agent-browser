"use client";

import { HeroSection } from "@/components/hero-section";
import { AgentBrowser } from "@/components/agent-browser";

export default function Home() {
  return (
    <main className="pt-14">
      <HeroSection />
      <section id="agent-section">
        <AgentBrowser />
      </section>
    </main>
  );
}
