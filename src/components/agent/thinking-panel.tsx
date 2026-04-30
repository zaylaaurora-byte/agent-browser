"use client";

import { motion } from "framer-motion";
import { Brain } from "lucide-react";
import type { Step } from "./types";
import type { RefObject } from "react";

interface Props {
  steps: Step[];
  latestThinking: string | null;
  isRunning: boolean;
  thinkingRef: RefObject<HTMLDivElement | null>;
}

export function ThinkingPanel({ steps, latestThinking, isRunning, thinkingRef }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15 }}
      className="rounded-2xl glass overflow-hidden"
    >
      <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center gap-3">
        <Brain className="w-4 h-4 text-violet-400" />
        <span className="text-[11px] text-zinc-400 font-semibold tracking-wider uppercase">Live Reasoning</span>
        {steps[steps.length - 1]?.model && (
          <span className="text-[10px] text-violet-400/60 font-mono">{steps[steps.length - 1].model}</span>
        )}
        {latestThinking && isRunning && (
          <div className="ml-auto flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            <span className="text-[9px] text-violet-400 uppercase tracking-widest">Thinking</span>
          </div>
        )}
      </div>

      <div ref={thinkingRef} className="h-[200px] overflow-y-auto p-4 space-y-2">
        {steps.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-xs text-zinc-700 uppercase tracking-widest">
              {isRunning ? "Agent reasoning will appear here..." : "Execute a task to see live reasoning"}
            </p>
          </div>
        ) : (
          steps.map((step, i) => {
            if (!step.thinking && !step.ai_reasoning) return null;
            const isLast = i === steps.length - 1;
            return (
              <div
                key={i}
                className={`rounded-xl p-3 border transition-all duration-200 ${
                  isLast && isRunning ? "bg-violet-950/30 border-violet-500/20" : "bg-black/30 border-zinc-800/40"
                }`}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[9px] text-zinc-600 font-mono">#{step.step}</span>
                  {step.duration_ms != null && (
                    <span className="text-[9px] text-zinc-600 font-mono">{step.duration_ms}ms</span>
                  )}
                  {isLast && isRunning && (
                    <div className="flex gap-0.5 ml-1">
                      {[0, 1, 2].map((d) => (
                        <div
                          key={d}
                          className="w-1 h-1 rounded-full bg-violet-400 animate-bounce"
                          style={{ animationDelay: `${d * 0.15}s` }}
                        />
                      ))}
                    </div>
                  )}
                </div>
                <pre className="text-[11px] text-zinc-300 whitespace-pre-wrap leading-relaxed font-mono">
                  {step.thinking || step.ai_reasoning}
                </pre>
              </div>
            );
          })
        )}
      </div>
    </motion.div>
  );
}
