"use client";

import { useRef } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import { Zap, CheckCircle2, Clock } from "lucide-react";

function FloatingOrb({
  className,
  delay = 0,
}: {
  className: string;
  delay?: number;
}) {
  return (
    <motion.div
      className={`absolute rounded-full blur-[120px] pointer-events-none ${className}`}
      animate={{
        y: [0, -20, 10, 0],
        x: [0, 15, -10, 0],
        scale: [1, 1.1, 0.95, 1],
      }}
      transition={{
        duration: 8,
        repeat: Infinity,
        delay,
        ease: "easeInOut",
      }}
    />
  );
}

export function HeroSection() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end start"],
  });

  const y = useTransform(scrollYProgress, [0, 1], [0, 150]);
  const opacity = useTransform(scrollYProgress, [0, 0.8], [1, 0]);
  const scale = useTransform(scrollYProgress, [0, 0.8], [1, 0.95]);

  return (
    <section ref={ref} className="relative min-h-[480px] flex flex-col items-center justify-center overflow-hidden pt-14">
      {/* Animated background orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <FloatingOrb
          className="top-[-15%] left-[8%] w-[500px] h-[500px] bg-violet-600/10"
          delay={0}
        />
        <FloatingOrb
          className="bottom-[-10%] right-[5%] w-[400px] h-[400px] bg-cyan-500/8"
          delay={2}
        />
        <FloatingOrb
          className="top-[30%] right-[25%] w-[300px] h-[300px] bg-fuchsia-600/6"
          delay={4}
        />
        <FloatingOrb
          className="bottom-[20%] left-[30%] w-[250px] h-[250px] bg-emerald-500/5"
          delay={1}
        />
      </div>

      {/* Noise overlay */}
      <div
        className="absolute inset-0 opacity-[0.025] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      <motion.div
        style={{ y, opacity, scale }}
        className="relative z-10 text-center max-w-4xl mx-auto px-6"
      >
        {/* Badge */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] mb-8"
        >
          <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
          <span className="text-[10px] text-zinc-400 uppercase tracking-[0.2em] font-semibold">
            AI-Powered Automation
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="text-6xl md:text-7xl lg:text-8xl font-black tracking-tight mb-4"
        >
          <span className="text-gradient">Agent Browser</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="text-lg md:text-xl text-zinc-400 mb-12 max-w-2xl mx-auto"
        >
          Watch AI browse the web in real-time. Execute tasks, observe reasoning, and
          automate any browser workflow.
        </motion.p>

        {/* Stats bar */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="flex items-center justify-center gap-8 md:gap-12"
        >
          {[
            { icon: Zap, label: "Tasks Completed", value: "∞", color: "text-violet-400" },
            { icon: CheckCircle2, label: "Success Rate", value: "99%", color: "text-emerald-400" },
            { icon: Clock, label: "Avg. Time", value: "~12s", color: "text-cyan-400" },
          ].map(({ icon: Icon, label, value, color }) => (
            <div key={label} className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.06] flex items-center justify-center">
                <Icon className={`w-5 h-5 ${color}`} />
              </div>
              <div className="text-left">
                <div className="text-lg font-bold text-white">{value}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider">{label}</div>
              </div>
            </div>
          ))}
        </motion.div>
      </motion.div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#050508] to-transparent pointer-events-none" />
    </section>
  );
}
