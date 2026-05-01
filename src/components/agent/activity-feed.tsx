"use client";

import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Eye, Globe, MousePointer, Type,
  ScrollText, Timer, Camera, CheckCircle2, AlertCircle,
  Rocket, Brain, ChevronRight, ChevronDown,
} from "lucide-react";
import type { Step } from "./types";
import type { RefObject, SetStateAction, Dispatch } from "react";

const ICON_MAP: Record<string, React.ElementType> = {
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
  paused:     Timer,
};

const COLOR_MAP: Record<string, string> = {
  navigate:   "text-sky-400",
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
  paused:     "text-amber-400",
};

const BG_MAP: Record<string, string> = {
  done:      "bg-emerald-500/12",
  error:     "bg-red-500/12",
  submit:    "bg-violet-500/12",
  navigate:  "bg-sky-500/10",
  click:     "bg-amber-500/10",
  type:      "bg-emerald-500/10",
  paused:    "bg-amber-500/10",
};

interface Props {
  steps: Step[];
  isRunning: boolean;
  completedSteps: number;
  failedSteps: number;
  expandedSteps: Set<number>;
  setExpandedSteps: Dispatch<SetStateAction<Set<number>>>;
  feedRef: RefObject<HTMLDivElement | null>;
  sessionExpired?: boolean;
}

export function ActivityFeed({
  steps, isRunning, completedSteps, failedSteps,
  expandedSteps, setExpandedSteps, feedRef,
  sessionExpired = false,
}: Props) {
  const toggle = (n: number) =>
    setExpandedSteps((p) => { const s = new Set(p); s.has(n) ? s.delete(n) : s.add(n); return s; });

  return (
    <motion.div
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.38, delay: 0.14, ease: [0.16, 1, 0.3, 1] }}
      className="glass-card rounded-2xl overflow-hidden flex flex-col flex-1 xl:flex-none xl:h-[calc(100vh-120px)] xl:sticky xl:top-20"
    >
      {/* Header */}
      <div className="panel-header flex-shrink-0">
        <Zap className="w-3.5 h-3.5 text-cyan-400 flex-shrink-0" />
        <span className="panel-label">Activity</span>
        {isRunning && (
          <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 flex-shrink-0" style={{ animation: "pulse-dot 1.2s ease-in-out infinite" }} />
        )}
        <div className="ml-auto flex items-center gap-2 text-[10px] font-mono">
          {completedSteps > 0 && <span className="text-emerald-400">{completedSteps} ✓</span>}
          {failedSteps    > 0 && <span className="text-red-400">{failedSteps} ✗</span>}
          {completedSteps === 0 && !isRunning && <span className="text-zinc-700">idle</span>}
        </div>
      </div>

      {/* Feed */}
      <div ref={feedRef} className="flex-1 overflow-y-auto p-2.5 space-y-1.5 min-h-[160px] xl:min-h-0">
        {steps.length === 0 ? (
          sessionExpired ? <SessionExpiredFeed /> : <BrandedEmptyState />
        ) : isRunning && steps.length < 4 ? (
          <>
            <SkeletonFeed />
            <AnimatePresence initial={false}>
              {steps.map((step, i) => {
                const Icon     = ICON_MAP[step.action]  || MousePointer;
                const color    = COLOR_MAP[step.action] || "text-zinc-500";
                const iconBg   = BG_MAP[step.action]    || "bg-zinc-800/50";
                const isError  = step.status === "retrying" || step.status === "failed";
                const isDone   = step.action === "done";
                const expanded = expandedSteps.has(step.step);
                const hasExtra = !!(step.ai_reasoning || step.thinking);

                return (
                  <motion.div
                    key={`${step.step}-${i}`}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                    className={`step-card ${isDone ? "done" : isError ? "error" : ""}`}
                  >
                    <div className="flex items-start gap-2.5 p-2.5">
                      <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-px ${iconBg}`}>
                        <Icon className={`w-3 h-3 ${color}`} />
                      </div>
                      <div className="flex-1 min-w-0 space-y-0.5">
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-[10px] font-bold text-zinc-200 uppercase tracking-wider">{step.action}</span>
                          {step.duration_ms != null && (
                            <span className="text-[9px] text-zinc-700 font-mono">{step.duration_ms}ms</span>
                          )}
                        </div>
                        {step.argument && (
                          <p className="text-[10px] text-zinc-600 font-mono truncate">{step.argument}</p>
                        )}
                        {step.observation && (
                          <div className="mt-1 p-2 rounded-lg bg-cyan-950/15 border border-cyan-800/12">
                            <p className="text-[9px] text-zinc-600 font-mono line-clamp-2">{step.observation}</p>
                          </div>
                        )}
                        {step.error && (
                          <p className="text-[9px] text-red-400 font-mono mt-0.5">{step.error}</p>
                        )}
                        {step.url && (
                          <div className="flex items-center gap-1 mt-0.5">
                            <Globe className="w-2.5 h-2.5 text-zinc-800 flex-shrink-0" />
                            <span className="text-[9px] text-zinc-700 font-mono truncate">{step.url}</span>
                          </div>
                        )}
                        {hasExtra && (
                          <button
                            onClick={() => toggle(step.step)}
                            className="mt-1 flex items-center gap-1 text-[9px] text-violet-400/50 hover:text-violet-400 transition-colors"
                          >
                            {expanded
                              ? <><ChevronDown className="w-3 h-3" />Hide reasoning</>
                              : <><ChevronRight className="w-3 h-3" />Show reasoning</>
                            }
                          </button>
                        )}
                        {expanded && hasExtra && (
                          <div className="mt-1.5 p-2 bg-zinc-900/60 rounded-lg border border-zinc-800/40">
                            <pre className="text-[9px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap break-words">
                              {step.thinking || step.ai_reasoning}
                            </pre>
                          </div>
                        )}
                      </div>
                      <span className="text-[9px] text-zinc-800 font-mono flex-shrink-0 mt-px">#{step.step}</span>
                    </div>
                    {step.screenshot && step.action !== "thinking" && step.status !== "thinking" && (
                      <div className="px-2.5 pb-2.5">
                        <img
                          src={`data:image/png;base64,${step.screenshot}`}
                          alt={`Step ${step.step}`}
                          className="w-full h-14 object-cover rounded-lg border border-zinc-800/40"
                          loading="lazy"
                        />
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </>
        ) : (
          <AnimatePresence initial={false}>
            {steps.map((step, i) => {
              const Icon     = ICON_MAP[step.action]  || MousePointer;
              const color    = COLOR_MAP[step.action] || "text-zinc-500";
              const iconBg   = BG_MAP[step.action]    || "bg-zinc-800/50";
              const isError  = step.status === "retrying" || step.status === "failed";
              const isDone   = step.action === "done";
              const expanded = expandedSteps.has(step.step);
              const hasExtra = !!(step.ai_reasoning || step.thinking);

              return (
                <motion.div
                  key={`${step.step}-${i}`}
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                  className={`step-card ${isDone ? "done" : isError ? "error" : ""}`}
                >
                  <div className="flex items-start gap-2.5 p-2.5">
                    <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-px ${iconBg}`}>
                      <Icon className={`w-3 h-3 ${color}`} />
                    </div>
                    <div className="flex-1 min-w-0 space-y-0.5">
                      <div className="flex items-baseline gap-1.5">
                        <span className="text-[10px] font-bold text-zinc-200 uppercase tracking-wider">{step.action}</span>
                        {step.duration_ms != null && (
                          <span className="text-[9px] text-zinc-700 font-mono">{step.duration_ms}ms</span>
                        )}
                      </div>
                      {step.argument && (
                        <p className="text-[10px] text-zinc-600 font-mono truncate">{step.argument}</p>
                      )}
                      {step.observation && (
                        <div className="mt-1 p-2 rounded-lg bg-cyan-950/15 border border-cyan-800/12">
                          <p className="text-[9px] text-zinc-600 font-mono line-clamp-2">{step.observation}</p>
                        </div>
                      )}
                      {step.error && (
                        <p className="text-[9px] text-red-400 font-mono mt-0.5">{step.error}</p>
                      )}
                      {step.url && (
                        <div className="flex items-center gap-1 mt-0.5">
                          <Globe className="w-2.5 h-2.5 text-zinc-800 flex-shrink-0" />
                          <span className="text-[9px] text-zinc-700 font-mono truncate">{step.url}</span>
                        </div>
                      )}
                      {hasExtra && (
                        <button
                          onClick={() => toggle(step.step)}
                          className="mt-1 flex items-center gap-1 text-[9px] text-violet-400/50 hover:text-violet-400 transition-colors"
                        >
                          {expanded
                            ? <><ChevronDown className="w-3 h-3" />Hide reasoning</>
                            : <><ChevronRight className="w-3 h-3" />Show reasoning</>
                          }
                        </button>
                      )}
                      {expanded && hasExtra && (
                        <div className="mt-1.5 p-2 bg-zinc-900/60 rounded-lg border border-zinc-800/40">
                          <pre className="text-[9px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap break-words">
                            {step.thinking || step.ai_reasoning}
                          </pre>
                        </div>
                      )}
                    </div>
                    <span className="text-[9px] text-zinc-800 font-mono flex-shrink-0 mt-px">#{step.step}</span>
                  </div>
                  {step.screenshot && step.action !== "thinking" && step.status !== "thinking" && (
                    <div className="px-2.5 pb-2.5">
                      <img
                        src={`data:image/png;base64,${step.screenshot}`}
                        alt={`Step ${step.step}`}
                        className="w-full h-14 object-cover rounded-lg border border-zinc-800/40"
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

// ─── Skeleton Loaders ──────────────────────────────────────────────────────────

function SkeletonCard({ delay }: { delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22, delay, ease: [0.16, 1, 0.3, 1] }}
      className="step-card"
    >
      <div className="flex items-start gap-2.5 p-2.5">
        <div className="w-6 h-6 rounded-lg bg-zinc-800/50 flex items-center justify-center flex-shrink-0 mt-px shimmer" />
        <div className="flex-1 min-w-0 space-y-1.5">
          <div className="flex items-baseline gap-1.5">
            <div className="h-2 w-12 rounded bg-zinc-800/60 shimmer" />
            <div className="h-1.5 w-8 rounded bg-zinc-800/40 shimmer" />
          </div>
          <div className="h-1.5 w-full rounded bg-zinc-800/40 shimmer" />
          <div className="h-3 w-24 rounded bg-zinc-800/30 shimmer mt-1" />
        </div>
        <div className="h-2 w-4 rounded bg-zinc-800/40 shimmer flex-shrink-0 mt-px" />
      </div>
    </motion.div>
  );
}

function SkeletonFeed() {
  return (
    <div className="space-y-1.5">
      <SkeletonCard delay={0.0} />
      <SkeletonCard delay={0.08} />
      <SkeletonCard delay={0.16} />
    </div>
  );
}

// ─── Branded Empty State ──────────────────────────────────────────────────────

function BrandedEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-40 xl:h-full gap-4 py-8">
      {/* Branded icon */}
      <div className="relative">
        <div className="w-14 h-14 rounded-2xl border border-zinc-800/50 flex items-center justify-center bg-zinc-900/50">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none" className="text-zinc-700">
            <rect x="3" y="5" width="22" height="18" rx="3" stroke="currentColor" strokeWidth="1.5" />
            <path d="M3 10h22" stroke="currentColor" strokeWidth="1.5" />
            <circle cx="7" cy="8" r="1" fill="currentColor" />
            <circle cx="10.5" cy="8" r="1" fill="currentColor" />
            <circle cx="14" cy="8" r="1" fill="currentColor" />
            <path d="M8 14h4M8 17h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
        {/* Orbit dot */}
        <span
          className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-violet-600/70 border-2 border-zinc-950"
          style={{ animation: "orbit 4s linear infinite" }}
        />
      </div>

      <div className="text-center space-y-1.5">
        <p className="text-[11px] text-zinc-600 uppercase tracking-widest font-medium">No activity yet</p>
        <p className="text-[10px] text-zinc-800">
          Enter a URL + task, then hit{" "}
          <kbd className="bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded text-zinc-600 font-mono text-[9px]">Execute</kbd>
          {" "}or press{" "}
          <kbd className="bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 rounded text-zinc-600 font-mono text-[9px]">?</kbd>
          {" "}for shortcuts
        </p>
      </div>
    </div>
  );
}

// ─── Session Expired State ─────────────────────────────────────────────────────

export function SessionExpiredFeed() {
  return (
    <div className="flex flex-col items-center justify-center h-40 xl:h-full gap-3 py-8 px-4">
      <div className="w-10 h-10 rounded-xl bg-zinc-900/60 border border-zinc-800/40 flex items-center justify-center">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="text-zinc-800">
          <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
          <path d="M10 6v4l2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      <div className="text-center space-y-1">
        <p className="text-[11px] text-zinc-700 uppercase tracking-widest">Session expired</p>
        <p className="text-[10px] text-zinc-800">Start a new task — previous session data is cleared after 24h</p>
      </div>
    </div>
  );
}
