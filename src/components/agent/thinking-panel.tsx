"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Brain, ChevronDown } from "lucide-react";
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
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      className="glass-card rounded-2xl overflow-hidden"
    >
      {/* Header — clickable to collapse */}
      <button
        onClick={() => setCollapsed((v) => !v)}
        className="w-full panel-header hover:bg-white/[0.02] transition-colors"
      >
        <Brain className="w-3.5 h-3.5 text-violet-400 flex-shrink-0" />
        <span className="panel-label">Live Reasoning</span>
        {latestModel && (
          <span className="text-[9px] text-violet-400/40 font-mono hidden sm:inline">{latestModel}</span>
        )}
        {latestThinking && isRunning && (
          <div className="flex items-center gap-1.5 ml-auto mr-2">
            <span className="typing-dot text-violet-400" />
            <span className="typing-dot text-violet-400" />
            <span className="typing-dot text-violet-400" />
          </div>
        )}
        <ChevronDown
          className={`w-3.5 h-3.5 text-zinc-700 transition-transform duration-200 ${collapsed ? "-rotate-90" : ""} ml-auto`}
        />
      </button>

      {!collapsed && (
        <div
          ref={thinkingRef}
          className="h-[170px] sm:h-[190px] overflow-y-auto p-3 space-y-2"
        >
          {thinkingSteps.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-[11px] text-zinc-700 uppercase tracking-widest text-center px-4">
                {isRunning ? "Agent is reasoning…" : "Execute a task to see live reasoning"}
              </p>
            </div>
          ) : (
            thinkingSteps.map((step, i) => {
              const isLast = i === thinkingSteps.length - 1;
              return (
                <div
                  key={i}
                  className={`rounded-xl p-3 border transition-colors duration-150 ${
                    isLast && isRunning
                      ? "bg-violet-950/20 border-violet-500/16"
                      : "bg-black/25 border-zinc-800/40"
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
                  <pre className="text-[11px] text-zinc-400 font-mono whitespace-pre-wrap leading-relaxed break-words">
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
