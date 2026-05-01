"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { ArrowDown } from "lucide-react";

const PILLS = [
  { color: "bg-violet-500", label: "3 Agent Modes"  },
  { color: "bg-cyan-500",   label: "Live Streaming" },
  { color: "bg-emerald-500",label: "Stealth Ready"  },
];

export function HeroSection() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const y       = useTransform(scrollYProgress, [0, 1], ["0%", "32%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);
  const scale   = useTransform(scrollYProgress, [0, 0.7], [1, 0.97]);

  return (
    <div ref={ref} className="relative h-[46vh] min-h-[320px] sm:min-h-[380px] overflow-hidden flex items-center justify-center">
      {/* Orbs */}
      <motion.div style={{ y }} className="absolute inset-0 pointer-events-none select-none">
        <div className="absolute top-[5%] left-[8%] w-[320px] sm:w-[500px] h-[320px] sm:h-[500px] rounded-full bg-violet-700/10 blur-[90px] sm:blur-[110px]"
          style={{ animation: "float 10s ease-in-out infinite" }} />
        <div className="absolute bottom-[-5%] right-[5%] w-[260px] sm:w-[400px] h-[260px] sm:h-[400px] rounded-full bg-cyan-500/7 blur-[80px] sm:blur-[100px]"
          style={{ animation: "float-b 12s ease-in-out infinite" }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[460px] h-[460px] rounded-full bg-fuchsia-700/5 blur-[120px]" />
      </motion.div>

      {/* Grid */}
      <div className="absolute inset-0 opacity-[0.016] pointer-events-none"
        style={{ backgroundImage: "linear-gradient(rgba(255,255,255,0.07) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.07) 1px,transparent 1px)", backgroundSize: "52px 52px" }} />

      {/* Noise */}
      <div className="absolute inset-0 opacity-[0.022] pointer-events-none"
        style={{ backgroundImage: "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")" }} />

      {/* Content */}
      <motion.div style={{ opacity, scale }} className="relative z-10 text-center px-4 sm:px-8 w-full max-w-3xl mx-auto">

        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: [0.16, 1, 0.3, 1] }}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full glass-surface mb-5 sm:mb-7"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-dot 2s ease-in-out infinite" }} />
          <span className="text-[10px] sm:text-[11px] text-zinc-400 font-semibold tracking-widest uppercase">AI-Powered Browser Automation</span>
        </motion.div>

        {/* Heading */}
        <motion.h1
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.07, ease: [0.16, 1, 0.3, 1] }}
          className="font-black tracking-tight leading-[0.9] mb-4 sm:mb-5"
          style={{ fontSize: "clamp(2.8rem, 8vw, 5.5rem)" }}
        >
          <span className="text-transparent bg-clip-text bg-gradient-to-br from-white via-zinc-100 to-zinc-400">
            Agent
          </span>
          <br />
          <span className="text-gradient-brand">Browser</span>
        </motion.h1>

        {/* Tagline */}
        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.14, ease: [0.16, 1, 0.3, 1] }}
          className="text-zinc-500 text-base sm:text-lg max-w-sm sm:max-w-md mx-auto mb-7 sm:mb-9 leading-relaxed"
        >
          Watch AI agents navigate the web in real-time — fill forms, extract data, automate workflows.
        </motion.p>

        {/* Pills + CTA */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.21, ease: [0.16, 1, 0.3, 1] }}
          className="flex flex-wrap items-center justify-center gap-4 sm:gap-6"
        >
          {PILLS.map((p) => (
            <div key={p.label} className="flex items-center gap-1.5 text-[11px] text-zinc-600">
              <span className={`w-1.5 h-1.5 rounded-full ${p.color} flex-shrink-0`} />
              {p.label}
            </div>
          ))}
          <button
            onClick={() => document.getElementById("agent-section")?.scrollIntoView({ behavior: "smooth" })}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl glass-surface text-[11px] text-zinc-400 hover:text-zinc-200 font-semibold tracking-wide transition-all hover:border-violet-500/25 active:scale-95"
          >
            Launch Agent <ArrowDown className="w-3.5 h-3.5" />
          </button>
        </motion.div>
      </motion.div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-[#07070d] to-transparent pointer-events-none" />
    </div>
  );
}
