"use client";

import { useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Globe, Clock, Cpu, AlertCircle, CheckCircle2, Eye, Brain } from "lucide-react";
import type { Step } from "@/components/agent/types";

const ACTION_CONFIG: Record<string, { icon: string; label: string }> = {
  navigate: { icon: "🌐", label: "Navigate" },
  click: { icon: "👆", label: "Click" },
  type: { icon: "⌨️", label: "Type" },
  scroll: { icon: "📜", label: "Scroll" },
  wait: { icon: "⏳", label: "Wait" },
  screenshot: { icon: "📸", label: "Screenshot" },
  done: { icon: "✅", label: "Done" },
  error: { icon: "❌", label: "Error" },
  check: { icon: "☑", label: "Check" },
  submit: { icon: "🚀", label: "Submit" },
  thinking: { icon: "🧠", label: "Thinking" },
};

interface ActivityFeedProps {
  steps: Step[];
  isRunning: boolean;
  expandedSteps: Set<number>;
  onToggleExpanded: (step: number) => void;
}

export function ActivityFeed({
  steps,
  isRunning,
  expandedSteps,
  onToggleExpanded,
}: ActivityFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [steps, scrollToBottom]);

  return (
    <div className="glass-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/[0.04] flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="text-sm">📡</span>
          <span className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
            Activity
          </span>
        </div>
        {isRunning && (
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
            <span className="text-[9px] text-emerald-400 uppercase tracking-widest">
              Live
            </span>
          </div>
        )}
      </div>

      {/* Step list */}
      <div
        ref={feedRef}
        className="h-[calc(100vh-220px)] overflow-y-auto p-3 space-y-2"
        style={{ scrollbarWidth: "thin", scrollbarColor: "#27272a transparent" }}
      >
        {steps.length === 0 ? (
          <div className="flex items-center justify-center h-48">
            <div className="text-center space-y-3">
              <div className="w-12 h-12 mx-auto rounded-xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center text-lg">
                ⚡
              </div>
              <p className="text-[11px] text-zinc-700 uppercase tracking-widest">
                No activity yet
              </p>
            </div>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {steps.map((step, i) => {
              const isLatest = i === steps.length - 1;
              const config = ACTION_CONFIG[step.action] || { icon: "•", label: step.action };
              const isError = step.status === "retrying" || step.status === "failed";
              const isDone = step.action === "done";
              const isThinking = step.status === "thinking";
              const isExpanded = expandedSteps.has(step.step);
              const hasReasoning = !!(step.ai_reasoning || step.thinking);

              return (
                <motion.div
                  key={`${step.step}-${i}`}
                  initial={{ opacity: 0, y: 8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                  className={`rounded-xl border p-3 transition-colors duration-200 ${
                    isError
                      ? "bg-red-500/[0.06] border-red-500/20"
                      : isDone
                      ? "bg-emerald-500/[0.06] border-emerald-500/20"
                      : isThinking
                      ? "bg-violet-500/[0.06] border-violet-500/30 animate-pulse"
                      : isLatest && isRunning
                      ? "bg-white/[0.04] border-white/[0.08]"
                      : "bg-white/[0.02] border-white/[0.04] hover:border-white/[0.08]"
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    {/* Icon */}
                    <div
                      className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs flex-shrink-0 ${
                        isError
                          ? "bg-red-500/20"
                          : isDone
                          ? "bg-emerald-500/20"
                          : isThinking
                          ? "bg-violet-500/20"
                          : "bg-white/[0.04]"
                      }`}
                    >
                      {config.icon}
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                          {step.action}
                        </span>
                        {step.status === "thinking" && (
                          <span className="text-[8px] text-violet-400 uppercase tracking-widest flex items-center gap-1">
                            <Brain className="w-2.5 h-2.5" />
                            thinking
                          </span>
                        )}
                        {isError && (
                          <span className="text-[8px] text-red-400 uppercase tracking-widest flex items-center gap-1">
                            <AlertCircle className="w-2.5 h-2.5" />
                            error
                          </span>
                        )}
                        {step.duration_ms != null && (
                          <span className="text-[9px] text-zinc-600 font-mono flex items-center gap-1">
                            <Clock className="w-2.5 h-2.5" />
                            {step.duration_ms}ms
                          </span>
                        )}
                        {step.model && (
                          <span className="text-[8px] text-violet-400/50 font-mono flex items-center gap-1">
                            <Cpu className="w-2.5 h-2.5" />
                            {step.model}
                          </span>
                        )}
                      </div>

                      {step.argument && (
                        <p className="text-[11px] text-zinc-500 font-mono truncate">
                          {step.argument}
                        </p>
                      )}

                      {/* Observation */}
                      {step.observation && (
                        <div className="mt-2 p-2 bg-cyan-500/[0.04] rounded-lg border border-cyan-500/10">
                          <div className="text-[8px] text-cyan-500/70 uppercase tracking-widest mb-1 flex items-center gap-1">
                            <Eye className="w-2.5 h-2.5" />
                            Observation
                          </div>
                          <p className="text-[10px] text-zinc-500 font-mono leading-relaxed line-clamp-2">
                            {step.observation}
                          </p>
                        </div>
                      )}

                      {/* Expandable reasoning */}
                      {hasReasoning && (
                        <button
                          onClick={() => onToggleExpanded(step.step)}
                          className="mt-1.5 flex items-center gap-1 text-[9px] text-violet-400/60 hover:text-violet-400 transition-colors duration-150"
                        >
                          <ChevronDown
                            className={`w-2.5 h-2.5 transition-transform duration-200 ${
                              isExpanded ? "rotate-180" : ""
                            }`}
                          />
                          <span>{isExpanded ? "Hide" : "Show"} reasoning</span>
                        </button>
                      )}

                      <AnimatePresence>
                        {isExpanded && hasReasoning && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="mt-1.5 p-2 bg-white/[0.02] rounded-lg border border-white/[0.04]">
                              <div className="text-[8px] text-violet-400/60 uppercase tracking-widest mb-1 flex items-center gap-1">
                                <Brain className="w-2.5 h-2.5" />
                                Reasoning
                              </div>
                              <pre className="text-[10px] text-zinc-500 font-mono leading-relaxed whitespace-pre-wrap">
                                {step.thinking || step.ai_reasoning}
                              </pre>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>

                      {/* URL */}
                      {step.url && (
                        <div className="mt-1 flex items-center gap-1">
                          <Globe className="w-2.5 h-2.5 text-zinc-700" />
                          <span className="text-[9px] text-zinc-600 font-mono truncate">
                            {step.url}
                          </span>
                        </div>
                      )}

                      {/* Error */}
                      {step.error && (
                        <p className="text-[10px] text-red-400 mt-1 font-mono">{step.error}</p>
                      )}
                    </div>

                    {/* Step number */}
                    <span className="text-[9px] text-zinc-700 font-mono flex-shrink-0 mt-0.5">
                      #{step.step}
                    </span>
                  </div>

                  {/* Screenshot thumbnail */}
                  {step.screenshot && !isThinking && (
                    <div className="mt-2">
                      <img
                        src={`data:image/png;base64,${step.screenshot}`}
                        alt={`Step ${step.step}`}
                        className="w-full h-20 object-cover rounded-lg border border-white/[0.04]"
                      />
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
