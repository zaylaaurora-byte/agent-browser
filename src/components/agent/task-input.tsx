"use client";

import { motion } from "framer-motion";
import { Play, Square, Settings, Loader2, Globe, Zap, Eye } from "lucide-react";
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

const MODE_META: Record<Mode, { icon: React.ElementType; desc: string }> = {
  fast:    { icon: Zap,   desc: "Quick scan, lower latency" },
  stealth: { icon: Eye,   desc: "Anti-detection patterns"  },
  deep:    { icon: Globe, desc: "Multi-step reasoning"      },
};

export function TaskInput({
  url, setUrl, task, setTask, mode, setMode,
  isRunning, completedSteps, onExecute, onStop, onShowSettings,
}: Props) {
  const canExecute = !isRunning && url.trim() && task.trim();

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
      className="mb-5"
    >
      <div className={`glass-card rounded-2xl overflow-hidden ${isRunning ? "glow-running" : "glow-violet"}`}>

        {/* Top bar: URL + settings */}
        <div className="flex items-center gap-2 p-3 sm:p-4 pb-0">
          <div className="relative flex-1 min-w-0">
            <Globe className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-600 pointer-events-none" />
            <input
              type="url"
              inputMode="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isRunning}
              placeholder="https://target-url.com"
              className="input-field w-full pl-9 pr-4 py-2.5 text-sm font-mono min-h-[44px]"
            />
          </div>
          <button
            onClick={onShowSettings}
            className="flex-shrink-0 w-11 h-11 rounded-xl glass-surface flex items-center justify-center text-zinc-500 hover:text-zinc-200 hover:border-zinc-700/60 transition-all active:scale-95"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>

        {/* Task textarea */}
        <div className="px-3 sm:px-4 pt-2.5">
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            disabled={isRunning}
            rows={2}
            placeholder="Describe what the agent should do — e.g. 'Extract all product names and prices, then click the first result.'"
            className="input-field w-full px-4 py-3 text-sm resize-none leading-relaxed min-h-[76px]"
          />
        </div>

        {/* Controls row */}
        <div className="flex items-center gap-2 px-3 sm:px-4 py-3 flex-wrap sm:flex-nowrap">

          {/* Mode selector */}
          <div className="flex items-center gap-0.5 rounded-xl glass-surface p-1 flex-shrink-0">
            {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
              const s   = MODE_STYLES[m];
              const meta = MODE_META[m];
              const Icon = meta.icon;
              return (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  disabled={isRunning}
                  title={meta.desc}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-bold tracking-wider transition-all duration-100 min-h-[36px] disabled:pointer-events-none ${
                    mode === m
                      ? `${s.color} border ${s.border} bg-white/[0.07]`
                      : "text-zinc-600 hover:text-zinc-300 border border-transparent"
                  }`}
                >
                  <Icon className="w-3 h-3" />
                  {s.label}
                </button>
              );
            })}
          </div>

          {/* Execute / Stop */}
          <button
            onClick={isRunning ? onStop : onExecute}
            disabled={!isRunning && !canExecute}
            className={`flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm tracking-wide transition-all min-h-[44px] flex-1 sm:flex-none sm:min-w-[130px] ${
              isRunning
                ? "bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500/18 active:scale-[0.97]"
                : "btn-execute"
            }`}
          >
            {isRunning ? (
              <><Loader2 className="w-4 h-4 animate-spin" /><span>Stop · {completedSteps}</span></>
            ) : (
              <><Play className="w-4 h-4 fill-current" /><span>Execute</span></>
            )}
          </button>
        </div>

        {/* Quick launch chips */}
        <div className="flex gap-2 px-3 sm:px-4 pb-3 flex-wrap">
          {QUICK_SITES.map((site) => (
            <button
              key={site.name}
              onClick={() => { setUrl(site.url); setTask(site.task); }}
              disabled={isRunning}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.07] hover:bg-white/[0.07] hover:border-violet-500/25 text-zinc-500 hover:text-zinc-200 transition-all text-[11px] font-medium disabled:opacity-30 active:scale-95"
            >
              <span className="text-sm leading-none">{site.icon}</span>
              {site.name}
            </button>
          ))}
        </div>

        {/* Progress strip */}
        {isRunning && (
          <div className="h-[2px] bg-zinc-900/80">
            <motion.div
              className="h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-500"
              initial={{ width: "0%" }}
              animate={{ width: `${Math.min((completedSteps / 25) * 100, 90)}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
        )}
      </div>
    </motion.div>
  );
}
