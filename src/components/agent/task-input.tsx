"use client";

import { motion } from "framer-motion";
import { Play, Square, Settings } from "lucide-react";
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

export function TaskInput({ url, setUrl, task, setTask, mode, setMode, isRunning, completedSteps, onExecute, onStop, onShowSettings }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="mb-6"
    >
      <div className="rounded-2xl glass overflow-hidden glow-violet">
        <div className="p-5 space-y-4">
          <div className="flex gap-3 items-start">
            {/* URL */}
            <div className="flex-1">
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={isRunning}
                placeholder="https://target-url.com"
                className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all disabled:opacity-40"
              />
            </div>

            {/* Mode selector */}
            <div className="flex items-center gap-1 bg-black/40 rounded-xl p-1 border border-zinc-800/60">
              {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
                const s = MODE_STYLES[m];
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`px-4 py-2.5 text-[11px] font-bold tracking-wider rounded-lg transition-all duration-200 ${
                      mode === m ? `${s.color} ${s.border} border bg-zinc-800/60` : "text-zinc-500 hover:text-zinc-300 border border-transparent"
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
              className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm tracking-wide transition-all duration-200 active:scale-[0.97] ${
                isRunning
                  ? "bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20"
                  : "bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-[0_0_30px_rgba(168,85,247,0.3)] hover:shadow-[0_0_40px_rgba(168,85,247,0.5)] disabled:opacity-30 disabled:cursor-not-allowed"
              }`}
            >
              {isRunning ? <><Square className="w-4 h-4" /> Stop</> : <><Play className="w-4 h-4" /> Execute</>}
            </button>

            {/* Settings gear */}
            <button
              onClick={onShowSettings}
              className="p-3 rounded-xl bg-black/40 border border-zinc-800/60 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all"
              title="Settings"
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
            placeholder="What should the agent do?"
            className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all resize-none disabled:opacity-40"
          />

          {/* Quick launches */}
          <div className="flex gap-2 flex-wrap">
            {QUICK_SITES.map((site) => (
              <button
                key={site.name}
                onClick={() => { setUrl(site.url); setTask(site.task); }}
                disabled={isRunning}
                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-black/30 border border-zinc-800/50 hover:border-violet-500/30 text-left transition-all disabled:opacity-30 active:scale-[0.97] group"
              >
                <span className="text-sm">{site.icon}</span>
                <span className="text-[11px] font-semibold text-zinc-400 group-hover:text-zinc-200 transition-colors">{site.name}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Progress bar */}
        {isRunning && (
          <div className="h-[2px] bg-zinc-900">
            <motion.div
              className="h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-500"
              initial={{ width: "0%" }}
              animate={{ width: `${Math.min((completedSteps / 500) * 100, 100)}%` }}
              transition={{ duration: 0.5, ease: "easeOut" }}
            />
          </div>
        )}
      </div>
    </motion.div>
  );
}
