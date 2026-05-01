"use client";

import { motion } from "framer-motion";
import { Brain, ChevronDown } from "lucide-react";
import { useState } from "react";
import type { Step } from "./types";
import type { RefObject } from "react";

interface Props {
  steps: Step[];
  latestThinking: string | null;
  isRunning: boolean;
  thinkingRef: RefObject<HTMLDivElement | null>;
}

export function ThinkingPanel({ steps, latestThinking, isRunning, thinkingRef }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const thinkingSteps = steps.filter((s) => s.thinking || s.ai_reasoning);
  const latestModel   = steps[steps.length - 1]?.model;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.12, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl glass-card overflow-hidden"
    >
      {/* Header */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="w-full px-4 py-3 border-b border-zinc-800/40 flex items-center gap-3 hover:bg-white/[0.02] transition-colors"
      >
        <Brain className="w-4 h-4 text-violet-400 flex-shrink-0" />
        <span className="text-[11px] text-zinc-400 font-semibold tracking-widest uppercase">Live Reasoning</span>
        {latestModel && (
          <span className="text-[9px] text-violet-400/50 font-mono hidden sm:inline">{latestModel}</span>
        )}
        {latestThinking && isRunning && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="typing-dot text-violet-400" />
            <span className="typing-dot text-violet-400" />
            <span className="typing-dot text-violet-400" />
            <span className="text-[9px] text-violet-400 uppercase tracking-widest ml-1">Thinking</span>
          </div>
        )}
        <ChevronDown
          className={`w-3.5 h-3.5 text-zinc-600 transition-transform duration-200 ml-auto ${collapsed ? "-rotate-90" : ""}`}
        />
      </button>

      {/* Body */}
      {!collapsed && (
        <div
          ref={thinkingRef}
          className="h-[180px] sm:h-[200px] overflow-y-auto p-3 space-y-2"
        >
          {thinkingSteps.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-[11px] text-zinc-700 uppercase tracking-widest text-center">
                {isRunning ? "Agent is reasoning…" : "Execute a task to see live reasoning"}
              </p>
            </div>
          ) : (
            thinkingSteps.map((step, i) => {
              const isLast = i === thinkingSteps.length - 1;
              return (
                <div
                  key={i}
                  className={`rounded-xl p-3 border transition-all duration-200 ${
                    isLast && isRunning
                      ? "bg-violet-950/25 border-violet-500/18"
                      : "bg-black/30 border-zinc-800/40"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[9px] text-zinc-700 font-mono">#{step.step}</span>
                    {step.duration_ms != null && (
                      <span className="text-[9px] text-zinc-700 font-mono">{step.duration_ms}ms</span>
                    )}
                    {isLast && isRunning && (
                      <div className="flex gap-1 ml-1">
                        <span className="typing-dot text-violet-400" />
                        <span className="typing-dot text-violet-400" />
                        <span className="typing-dot text-violet-400" />
                      </div>
                    )}
                  </div>
                  <pre className="text-[11px] text-zinc-400 whitespace-pre-wrap leading-relaxed font-mono">
                    {step.thinking || step.ai_reasoning}
                  </pre>
                </div>
              );
            })
          )}
        </div>
      )}
    </motion.div>
  );
}
