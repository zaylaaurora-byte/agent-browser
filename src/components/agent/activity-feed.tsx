"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Zap, Eye, ChevronDown, ChevronRight, Globe } from "lucide-react";
import {
  Play, Square, ChevronUp, ChevronDown as CDown, MousePointer, Type,
  ScrollText, Timer, Camera, CheckCircle2, AlertCircle, Rocket, Brain,
} from "lucide-react";
import type { Step } from "./types";
import type { RefObject, SetStateAction, Dispatch } from "react";

const ACTION_ICON: Record<string, React.ElementType> = {
  navigate:  Globe,
  click:     MousePointer,
  type:      Type,
  scroll:    ScrollText,
  wait:      Timer,
  screenshot:Camera,
  done:      CheckCircle2,
  error:     AlertCircle,
  check:     CheckCircle2,
  submit:    Rocket,
  thinking:  Brain,
};

const ACTION_COLOR: Record<string, string> = {
  navigate:  "text-blue-400",
  click:     "text-amber-400",
  type:      "text-emerald-400",
  scroll:    "text-zinc-400",
  wait:      "text-zinc-400",
  screenshot:"text-pink-400",
  done:      "text-emerald-400",
  error:     "text-red-400",
  check:     "text-cyan-400",
  submit:    "text-violet-400",
  thinking:  "text-violet-400",
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
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
      className="rounded-2xl glass overflow-hidden h-[calc(100vh-120px)] sticky top-20"
    >
      <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center gap-3">
        <Zap className="w-4 h-4 text-cyan-400" />
        <span className="text-[11px] text-zinc-400 font-semibold tracking-wider uppercase">Activity</span>
        {isRunning && (
          <div className="ml-auto flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-[9px] text-cyan-400 uppercase tracking-widest">Live</span>
          </div>
        )}
        <div className="flex items-center gap-2 text-[10px] ml-auto">
          <span className="text-emerald-400 font-mono">{completedSteps}</span>
          <span className="text-zinc-700">done</span>
          {failedSteps > 0 && (
            <>
              <span className="text-red-400 font-mono">{failedSteps}</span>
              <span className="text-zinc-700">fail</span>
            </>
          )}
        </div>
      </div>

      <div ref={feedRef} className="h-[calc(100%-48px)] overflow-y-auto p-3 space-y-2">
        {steps.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <Eye className="w-10 h-10 text-zinc-800" />
            <p className="text-xs text-zinc-700 uppercase tracking-widest">No activity yet</p>
            <p className="text-[10px] text-zinc-800">Press <kbd className="bg-zinc-800 px-1.5 py-0.5 rounded text-zinc-400 font-mono">?</kbd> for shortcuts</p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {steps.map((step, i) => {
              const Icon = ACTION_ICON[step.action] || MousePointer;
              const color = ACTION_COLOR[step.action] || "text-zinc-400";
              const isError   = step.status === "retrying" || step.status === "failed";
              const isDone    = step.action === "done";
              const isThinking= step.status === "thinking";
              const isExpanded = expandedSteps.has(step.step);
              const hasReasoning = !!(step.ai_reasoning || step.thinking);

              return (
                <motion.div
                  key={`${step.step}-${i}`}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                  className={`rounded-xl border p-3 transition-all duration-200 ${
                    isError   ? "bg-red-950/20 border-red-500/20" :
                    isDone    ? "bg-emerald-950/20 border-emerald-500/20" :
                    isThinking? "bg-violet-950/20 border-violet-500/20" :
                    "bg-black/30 border-zinc-800/40 hover:border-zinc-700/50"
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      isError ? "bg-red-500/15" : isDone ? "bg-emerald-500/15" : isThinking ? "bg-violet-500/15" : "bg-zinc-800/60"
                    }`}>
                      <Icon className={`w-3.5 h-3.5 ${color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider">{step.action}</span>
                        {step.duration_ms != null && (
                          <span className="text-[9px] text-zinc-600 font-mono">{step.duration_ms}ms</span>
                        )}
                        {step.model && (
                          <span className="text-[9px] text-violet-400/50 font-mono">{step.model}</span>
                        )}
                      </div>
                      {step.argument && (
                        <p className="text-[10px] text-zinc-500 font-mono truncate">{step.argument}</p>
                      )}
                      {step.observation && (
                        <div className="mt-1.5 p-2 bg-cyan-950/20 rounded-lg border border-cyan-800/15">
                          <div className="text-[8px] text-cyan-500 uppercase tracking-widest mb-0.5">Observation</div>
                          <p className="text-[9px] text-zinc-500 font-mono leading-relaxed line-clamp-2">{step.observation}</p>
                        </div>
                      )}
                      {hasReasoning && (
                        <button
                          onClick={() => setExpandedSteps((prev) => {
                            const next = new Set(prev);
                            next.has(step.step) ? next.delete(step.step) : next.add(step.step);
                            return next;
                          })}
                          className="mt-1.5 flex items-center gap-1 text-[9px] text-violet-400/60 hover:text-violet-400 transition-colors"
                        >
                          {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                          {isExpanded ? "Hide" : "Show"} reasoning
                        </button>
                      )}
                      {isExpanded && hasReasoning && (
                        <div className="mt-1.5 p-2 bg-zinc-900/60 rounded-lg border border-zinc-800/40">
                          <pre className="text-[9px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap">
                            {step.thinking || step.ai_reasoning}
                          </pre>
                        </div>
                      )}
                      {step.error && (
                        <p className="text-[9px] text-red-400 mt-1 font-mono">{step.error}</p>
                      )}
                      {step.url && (
                        <div className="mt-1 flex items-center gap-1">
                          <Globe className="w-2.5 h-2.5 text-zinc-600" />
                          <span className="text-[9px] text-zinc-600 font-mono truncate">{step.url}</span>
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-zinc-700 font-mono flex-shrink-0">#{step.step}</span>
                  </div>
                  {step.screenshot && !isThinking && (
                    <div className="mt-2">
                      <img
                        src={`data:image/png;base64,${step.screenshot}`}
                        alt={`Step ${step.step}`}
                        className="w-full h-20 object-cover rounded-lg border border-zinc-800/40"
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
