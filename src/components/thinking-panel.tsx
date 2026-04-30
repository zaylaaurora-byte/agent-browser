"use client";

import { useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, Loader2 } from "lucide-react";

interface ThinkingPanelProps {
  thinkingHistory: string[];
  isRunning: boolean;
  latestThinking: string | null;
  model?: string;
  durationMs?: number;
}

export function ThinkingPanel({
  thinkingHistory,
  isRunning,
  latestThinking,
  model,
  durationMs,
}: ThinkingPanelProps) {
  const thinkingRef = useRef<HTMLDivElement>(null);

  const scrollThinkingToBottom = useCallback(() => {
    if (thinkingRef.current) {
      thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollThinkingToBottom();
  }, [thinkingHistory, scrollThinkingToBottom]);

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.04] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Brain className="w-4 h-4 text-violet-400" />
          <span className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
            Live Reasoning
          </span>
          {model && (
            <span className="text-[8px] text-violet-400/50 font-mono">{model}</span>
          )}
          {durationMs != null && (
            <span className="text-[8px] text-zinc-600 font-mono">{durationMs}ms</span>
          )}
        </div>
        {latestThinking && isRunning && (
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse shadow-[0_0_6px_rgba(167,139,250,0.8)]" />
            <span className="text-[9px] text-violet-400 uppercase tracking-widest">
              Thinking
            </span>
          </div>
        )}
      </div>

      {/* Scrolling thought history */}
      <div
        ref={thinkingRef}
        className="h-[180px] overflow-y-auto p-3 space-y-2"
        style={{ scrollbarWidth: "thin", scrollbarColor: "#27272a transparent" }}
      >
        {thinkingHistory.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-[11px] text-zinc-700 uppercase tracking-widest text-center">
              {isRunning
                ? "Agent reasoning will appear here..."
                : "Execute a task to see live reasoning"}
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {thinkingHistory.map((thought, i) => {
              const isLast = i === thinkingHistory.length - 1;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className={`rounded-xl p-3 border transition-colors duration-200 ${
                    isLast && isRunning
                      ? "bg-violet-500/[0.06] border-violet-500/20"
                      : "bg-white/[0.02] border-white/[0.04]"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[9px] text-zinc-600 font-mono uppercase tracking-widest">
                      #{i + 1}
                    </span>
                    {isLast && isRunning && (
                      <div className="flex gap-0.5">
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
                  <pre className="text-[11px] text-zinc-400 whitespace-pre-wrap leading-relaxed font-mono">
                    {thought}
                  </pre>
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
