"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Eye, Globe, MousePointer, Type,
  ScrollText, Timer, Camera, CheckCircle2, AlertCircle, Rocket, Brain, ChevronRight, ChevronDown,
} from "lucide-react";
import type { Step } from "./types";
import type { RefObject, SetStateAction, Dispatch } from "react";

const ACTION_ICON: Record<string, React.ElementType> = {
  navigate:   Globe,
  click:      MousePointer,
  type:       Type,
  scroll:     ScrollText,
  wait:       Timer,
  screenshot: Camera,
  done:       CheckCircle2,
  error:      AlertCircle,
  check:      CheckCircle2,
  submit:     Rocket,
  thinking:   Brain,
};

const ACTION_COLOR: Record<string, string> = {
  navigate:   "text-blue-400",
  click:      "text-amber-400",
  type:       "text-emerald-400",
  scroll:     "text-zinc-500",
  wait:       "text-zinc-500",
  screenshot: "text-pink-400",
  done:       "text-emerald-400",
  error:      "text-red-400",
  check:      "text-cyan-400",
  submit:     "text-violet-400",
  thinking:   "text-violet-400",
};

const ACTION_BG: Record<string, string> = {
  done:    "bg-emerald-500/12",
  error:   "bg-red-500/12",
  submit:  "bg-violet-500/12",
  default: "bg-zinc-800/50",
};

interface Props {
  steps: Step[];
  isRunning: boolean;
  completedSteps: number;
  failedSteps: number;
  expandedSteps: Set<number>;
  setExpandedSteps: Dispatch<SetStateAction<Set<number>>>;
  feedRef: RefObject<HTMLDivElement | null>;
}

export function ActivityFeed({
  steps, isRunning, completedSteps, failedSteps,
  expandedSteps, setExpandedSteps, feedRef,
}: Props) {
  const toggleExpand = (stepNum: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      next.has(stepNum) ? next.delete(stepNum) : next.add(stepNum);
      return next;
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.45, delay: 0.18, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl glass-card overflow-hidden xl:h-[calc(100vh-120px)] xl:sticky xl:top-20 flex flex-col"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center gap-2.5 flex-shrink-0">
        <Zap className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
        <span className="text-[11px] text-zinc-400 font-semibold tracking-widest uppercase">Activity</span>

        {isRunning && (
          <div className="flex items-center gap-1.5 ml-1">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" style={{ animation: "pulse-glow 1.2s ease-in-out infinite" }} />
          </div>
        )}

        <div className="flex items-center gap-2 ml-auto text-[10px] font-mono">
          {completedSteps > 0 && (
            <span className="text-emerald-400">{completedSteps} ✓</span>
          )}
          {failedSteps > 0 && (
            <span className="text-red-400">{failedSteps} ✗</span>
          )}
          {completedSteps === 0 && !isRunning && (
            <span className="text-zinc-700">idle</span>
          )}
        </div>
      </div>

      {/* Feed */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto p-3 space-y-1.5 min-h-[200px] xl:min-h-0"
      >
        {steps.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 xl:h-full gap-3">
            <div className="w-10 h-10 rounded-xl bg-zinc-900/60 flex items-center justify-center">
              <Eye className="w-5 h-5 text-zinc-800" />
            </div>
            <p className="text-[11px] text-zinc-700 uppercase tracking-widest">No activity yet</p>
            <p className="text-[10px] text-zinc-800">
              Press{" "}
              <kbd className="bg-zinc-800/80 border border-zinc-700/60 px-1.5 py-0.5 rounded text-zinc-400 font-mono text-[9px]">?</kbd>
              {" "}for shortcuts
            </p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {steps.map((step, i) => {
              const Icon       = ACTION_ICON[step.action] || MousePointer;
              const color      = ACTION_COLOR[step.action] || "text-zinc-500";
              const iconBg     = ACTION_BG[step.action] || ACTION_BG.default;
              const isError    = step.status === "retrying" || step.status === "failed";
              const isDone     = step.action === "done";
              const isExpanded = expandedSteps.has(step.step);
              const hasExtra   = !!(step.ai_reasoning || step.thinking);

              return (
                <motion.div
                  key={`${step.step}-${i}`}
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                  className={`rounded-xl border transition-colors duration-150 ${
                    isError
                      ? "bg-red-950/15 border-red-500/18"
                      : isDone
                        ? "bg-emerald-950/15 border-emerald-500/18"
                        : "bg-black/25 border-zinc-800/40 hover:border-zinc-700/50"
                  }`}
                >
                  <div className="flex items-start gap-2.5 p-2.5">
                    {/* Icon */}
                    <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${iconBg}`}>
                      <Icon className={`w-3 h-3 ${color}`} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-1.5 flex-wrap">
                        <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider">{step.action}</span>
                        {step.duration_ms != null && (
                          <span className="text-[9px] text-zinc-700 font-mono">{step.duration_ms}ms</span>
                        )}
                      </div>
                      {step.argument && (
                        <p className="text-[10px] text-zinc-600 font-mono truncate mt-0.5">{step.argument}</p>
                      )}
                      {step.observation && (
                        <div className="mt-1.5 p-2 bg-cyan-950/15 rounded-lg border border-cyan-800/12">
                          <p className="text-[9px] text-cyan-400/70 uppercase tracking-widest mb-0.5">Observation</p>
                          <p className="text-[9px] text-zinc-500 font-mono leading-relaxed line-clamp-2">{step.observation}</p>
                        </div>
                      )}
                      {step.error && (
                        <p className="text-[9px] text-red-400 mt-1 font-mono leading-relaxed">{step.error}</p>
                      )}
                      {step.url && (
                        <div className="mt-1 flex items-center gap-1">
                          <Globe className="w-2.5 h-2.5 text-zinc-700 flex-shrink-0" />
                          <span className="text-[9px] text-zinc-700 font-mono truncate">{step.url}</span>
                        </div>
                      )}
                      {hasExtra && (
                        <button
                          onClick={() => toggleExpand(step.step)}
                          className="mt-1.5 flex items-center gap-1 text-[9px] text-violet-400/50 hover:text-violet-400 transition-colors"
                        >
                          {isExpanded
                            ? <><ChevronDown className="w-3 h-3" /> Hide reasoning</>
                            : <><ChevronRight className="w-3 h-3" /> Show reasoning</>
                          }
                        </button>
                      )}
                      {isExpanded && hasExtra && (
                        <div className="mt-1.5 p-2 bg-zinc-900/50 rounded-lg border border-zinc-800/40">
                          <pre className="text-[9px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap">
                            {step.thinking || step.ai_reasoning}
                          </pre>
                        </div>
                      )}
                    </div>

                    {/* Step number badge */}
                    <span className="text-[9px] text-zinc-800 font-mono flex-shrink-0 mt-0.5">#{step.step}</span>
                  </div>

                  {/* Inline screenshot */}
                  {step.screenshot && step.action !== "thinking" && step.status !== "thinking" && (
                    <div className="px-2.5 pb-2.5">
                      <img
                        src={`data:image/png;base64,${step.screenshot}`}
                        alt={`Step ${step.step}`}
                        className="w-full h-16 object-cover rounded-lg border border-zinc-800/40"
                        loading="lazy"
                      />
                    </div>
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}
      </div>
    </motion.div>
  );
}
