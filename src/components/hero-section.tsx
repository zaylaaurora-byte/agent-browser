"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { ChevronDown } from "lucide-react";

const FEATURES = [
  { dot: "bg-violet-500", label: "3 Agent Modes" },
  { dot: "bg-cyan-500",   label: "Live Streaming" },
  { dot: "bg-emerald-500",label: "Stealth Ready"  },
];

export function HeroSection() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const y       = useTransform(scrollYProgress, [0, 1], ["0%", "35%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.75], [1, 0]);
  const scale   = useTransform(scrollYProgress, [0, 0.75], [1, 0.96]);

  const scrollToAgent = () => {
    document.getElementById("agent-section")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div
      ref={ref}
      className="relative h-[46vh] min-h-[340px] sm:min-h-[400px] overflow-hidden flex items-center justify-center"
    >
      {/* Parallax background orbs */}
      <motion.div style={{ y }} className="absolute inset-0 pointer-events-none select-none">
        <div
          className="absolute top-[8%] left-[10%] w-[360px] sm:w-[520px] h-[360px] sm:h-[520px] rounded-full bg-violet-600/12 blur-[100px] sm:blur-[120px]"
          style={{ animation: "float 9s ease-in-out infinite" }}
        />
        <div
          className="absolute bottom-[0%] right-[5%] w-[280px] sm:w-[420px] h-[280px] sm:h-[420px] rounded-full bg-cyan-500/8 blur-[80px] sm:blur-[110px]"
          style={{ animation: "float-delayed 11s ease-in-out infinite" }}
        />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full bg-fuchsia-600/6 blur-[140px]" />
      </motion.div>

      {/* Noise texture */}
      <div
        className="absolute inset-0 opacity-[0.025] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.018] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.06) 1px, transparent 1px)`,
          backgroundSize: "56px 56px",
        }}
      />

      {/* Content */}
      <motion.div style={{ opacity, scale }} className="relative z-10 text-center px-5 sm:px-8 w-full max-w-3xl mx-auto">

        {/* Status badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full glass-surface mb-6 sm:mb-8"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]" />
          <span className="text-[10px] sm:text-[11px] text-zinc-400 font-semibold tracking-widest uppercase">
            AI-Powered Browser Automation
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
          className="text-5xl sm:text-7xl md:text-8xl font-black tracking-tight mb-4 sm:mb-6 leading-[0.92]"
        >
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-zinc-200 to-zinc-400">
            Agent
          </span>
          <br />
          <span className="text-gradient-brand">Browser</span>
        </motion.h1>

        {/* Tagline */}
        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.16, ease: [0.16, 1, 0.3, 1] }}
          className="text-zinc-500 text-base sm:text-lg max-w-md mx-auto mb-8 sm:mb-10 leading-relaxed"
        >
          Watch AI agents navigate the web in real-time. Fill forms, extract data,
          automate workflows — with live reasoning.
        </motion.p>

        {/* Feature dots + CTA */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.24, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-6"
        >
          <div className="flex items-center gap-4 sm:gap-6">
            {FEATURES.map((f) => (
              <div key={f.label} className="flex items-center gap-1.5 text-[11px] sm:text-[12px] text-zinc-600">
                <span className={`w-1.5 h-1.5 rounded-full ${f.dot} flex-shrink-0`} />
                <span>{f.label}</span>
              </div>
            ))}
          </div>

          <button
            onClick={scrollToAgent}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl glass-surface text-[11px] text-zinc-400 hover:text-zinc-200 font-semibold tracking-wider transition-all hover:border-violet-500/30 active:scale-95"
          >
            Launch Agent
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
        </motion.div>
      </motion.div>

      {/* Bottom gradient */}
      <div className="absolute bottom-0 left-0 right-0 h-28 bg-gradient-to-t from-[#060609] to-transparent pointer-events-none" />
    </div>
  );
}
