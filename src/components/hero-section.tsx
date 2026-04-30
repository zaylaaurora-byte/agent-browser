"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";

export function HeroSection() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const y = useTransform(scrollYProgress, [0, 1], ["0%", "40%"]);
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.8], [1, 0.95]);

  return (
    <div ref={ref} className="relative h-[50vh] min-h-[400px] overflow-hidden flex items-center justify-center">
      {/* Parallax background orbs */}
      <motion.div style={{ y }} className="absolute inset-0 pointer-events-none">
        <div
          className="absolute top-[10%] left-[15%] w-[500px] h-[500px] rounded-full bg-violet-600/15 blur-[120px]"
          style={{ animation: "float 8s ease-in-out infinite" }}
        />
        <div
          className="absolute bottom-[5%] right-[10%] w-[400px] h-[400px] rounded-full bg-cyan-500/10 blur-[100px]"
          style={{ animation: "float-delayed 10s ease-in-out infinite" }}
        />
        <div
          className="absolute top-[50%] left-[50%] -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-fuchsia-600/8 blur-[150px]"
        />
      </motion.div>

      {/* Noise texture */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.02] pointer-events-none"
        style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)`,
          backgroundSize: "60px 60px",
        }}
      />

      {/* Content */}
      <motion.div style={{ opacity, scale }} className="relative z-10 text-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-zinc-900/60 border border-zinc-800/60 mb-8 backdrop-blur-xl">
            <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
            <span className="text-[11px] text-zinc-400 font-semibold tracking-wider uppercase">AI-Powered Browser Automation</span>
          </div>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-6xl md:text-8xl font-black tracking-tight mb-6"
        >
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-zinc-200 to-zinc-400">Agent</span>
          <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400">Browser</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="text-zinc-500 text-lg max-w-xl mx-auto mb-10"
        >
          Watch AI agents navigate the web in real-time. Fill forms, extract data, automate workflows — all with live reasoning.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="flex items-center justify-center gap-6"
        >
          <div className="flex items-center gap-2 text-[11px] text-zinc-600">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
            <span>3 Agent Modes</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-zinc-600">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" />
            <span>Live Streaming</span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-zinc-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>Stealth Ready</span>
          </div>
        </motion.div>
      </motion.div>

      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#050508] to-transparent pointer-events-none" />
    </div>
  );
}
