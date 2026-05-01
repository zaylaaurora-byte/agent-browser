"use client";

import { motion } from "framer-motion";
import { Play, Square, Settings, Loader2 } from "lucide-react";
import { QUICK_SITES, MODE_STYLES } from "./types";
import type { Mode } from "./types";

interface Props {
  url: string;       setUrl: (v: string) => void;
  task: string;      setTask: (v: string) => void;
  mode: Mode;        setMode: (m: Mode) => void;
  isRunning: boolean;
  completedSteps: number;
  onExecute: () => void;
  onStop: () => void;
  onShowSettings: () => void;
}

export function TaskInput({
  url, setUrl, task, setTask, mode, setMode,
  isRunning, completedSteps, onExecute, onStop, onShowSettings,
}: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="mb-5"
    >
      <div className={`rounded-2xl glass-card overflow-hidden ${isRunning ? "glow-running" : "glow-violet"}`}>
        <div className="p-4 sm:p-5 space-y-3">

          {/* URL row */}
          <div className="flex gap-2 items-center">
            <div className="flex-1 min-w-0">
              <input
                type="url"
                inputMode="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isRunning}
                placeholder="https://target-url.com"
                className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all disabled:opacity-40 min-h-[44px]"
              />
            </div>

            {/* Settings — always visible */}
            <button
              onClick={onShowSettings}
              className="flex-shrink-0 w-11 h-11 rounded-xl bg-black/40 border border-zinc-800/60 text-zinc-500 hover:text-zinc-200 hover:border-zinc-700 transition-all flex items-center justify-center active:scale-95"
              title="Settings (API key, model)"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>

          {/* Task textarea */}
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            disabled={isRunning}
            rows={2}
            placeholder="What should the agent do? e.g. Extract all product names and prices from this page."
            className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all resize-none disabled:opacity-40 leading-relaxed"
          />

          {/* Mode selector + Execute row */}
          <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">

            {/* Mode pills */}
            <div className="flex items-center gap-0.5 bg-black/40 rounded-xl p-1 border border-zinc-800/60 flex-shrink-0">
              {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
                const s = MODE_STYLES[m];
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    disabled={isRunning}
                    className={`px-3.5 py-2 text-[11px] font-bold tracking-widest rounded-lg transition-all duration-150 min-h-[36px] disabled:pointer-events-none ${
                      mode === m
                        ? `${s.color} border ${s.border} bg-zinc-800/70`
                        : "text-zinc-600 hover:text-zinc-300 border border-transparent"
                    }`}
                  >
                    {s.label}
                  </button>
                );
              })}
            </div>

            {/* Execute / Stop */}
            <button
              onClick={isRunning ? onStop : onExecute}
              disabled={!isRunning && (!url || !task)}
              className={`flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm tracking-wide transition-all duration-150 active:scale-[0.97] min-h-[44px] flex-1 sm:flex-none ${
                isRunning
                  ? "bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20"
                  : "bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-[0_0_28px_rgba(168,85,247,0.28)] hover:shadow-[0_0_40px_rgba(168,85,247,0.45)] disabled:opacity-25 disabled:cursor-not-allowed disabled:shadow-none"
              }`}
            >
              {isRunning ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Stop ({completedSteps})</>
              ) : (
                <><Play className="w-4 h-4 fill-current" /> Execute</>
              )}
            </button>
          </div>

          {/* Quick launch sites */}
          <div className="flex gap-2 flex-wrap">
            {QUICK_SITES.map((site) => (
              <button
                key={site.name}
                onClick={() => { setUrl(site.url); setTask(site.task); }}
                disabled={isRunning}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-black/30 border border-zinc-800/50 hover:border-violet-500/30 hover:bg-violet-500/5 text-left transition-all disabled:opacity-30 active:scale-[0.97] group min-h-[36px]"
              >
                <span className="text-sm leading-none">{site.icon}</span>
                <span className="text-[11px] font-semibold text-zinc-500 group-hover:text-zinc-200 transition-colors">
                  {site.name}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Progress bar */}
        {isRunning && (
          <div className="h-[2px] bg-zinc-900/80">
            <motion.div
              className="h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-500"
              initial={{ width: "0%" }}
              animate={{ width: `${Math.min((completedSteps / 30) * 100, 92)}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
            />
          </div>
        )}
      </div>
    </motion.div>
  );
}
