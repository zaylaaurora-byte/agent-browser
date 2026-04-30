"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Play, Square, Loader2 } from "lucide-react";

export type Mode = "fast" | "stealth" | "deep";

const MODE_CONFIG: Record<Mode, { label: string; color: string; border: string; glow: string }> = {
  fast: {
    label: "FAST",
    color: "text-amber-400",
    border: "border-amber-500/40",
    glow: "shadow-amber-500/20",
  },
  stealth: {
    label: "STEALTH",
    color: "text-slate-300",
    border: "border-slate-500/40",
    glow: "shadow-slate-500/20",
  },
  deep: {
    label: "DEEP",
    color: "text-violet-400",
    border: "border-violet-500/40",
    glow: "shadow-violet-500/20",
  },
};

const QUICK_SITES = [
  {
    name: "Pizza Form",
    icon: "🍕",
    url: "https://httpbin.org/forms/post",
    task: "Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page.",
  },
  {
    name: "Login Flow",
    icon: "🔐",
    url: "https://httpbin.org/basic-auth/user/passwd",
    task: "Navigate to the page. Type user in the username field and passwd in the password field. Click the submit button. Report the result — whether authentication succeeded or failed.",
  },
  {
    name: "Job Board",
    icon: "💼",
    url: "https://boards.greenhouse.io/embed/job_board?for_first=True",
    task: "Navigate to the job board. Report all visible job listings including job title, company name, and location. Take a screenshot.",
  },
  {
    name: "Travel Search",
    icon: "✈️",
    url: "https://www.booking.com",
    task: "Navigate to Booking.com. Report the page title and what search fields are visible (destination, dates, guests). Take a screenshot. Do not fill anything in yet.",
  },
];

interface TaskInputProps {
  url: string;
  setUrl: (url: string) => void;
  task: string;
  setTask: (task: string) => void;
  mode: Mode;
  setMode: (mode: Mode) => void;
  isRunning: boolean;
  onExecute: () => void;
  onStop: () => void;
}

export function TaskInput({
  url,
  setUrl,
  task,
  setTask,
  mode,
  setMode,
  isRunning,
  onExecute,
  onStop,
}: TaskInputProps) {
  return (
    <div className="space-y-4">
      {/* Main task card */}
      <div className="glass-card overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-white/[0.04] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600/20 to-cyan-600/20 border border-violet-500/20 flex items-center justify-center">
              <span className="text-sm">🎯</span>
            </div>
            <div>
              <span className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
                Task Input
              </span>
              <div className="text-[8px] text-zinc-700 mt-0.5">WebSocket streaming</div>
            </div>
          </div>
          <div
            className={`w-2 h-2 rounded-full transition-colors duration-300 ${
              isRunning
                ? "bg-violet-400 animate-pulse shadow-[0_0_8px_rgba(167,139,250,0.8)]"
                : "bg-zinc-700"
            }`}
          />
        </div>

        <div className="p-5 space-y-4">
          {/* URL field */}
          <div className="space-y-1.5">
            <label className="text-[9px] text-zinc-600 uppercase tracking-[0.25em] font-semibold">
              Target URL
            </label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isRunning}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-[13px] font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/40 transition-all duration-200 disabled:opacity-40"
              placeholder="https://..."
            />
          </div>

          {/* Task field */}
          <div className="space-y-1.5">
            <label className="text-[9px] text-zinc-600 uppercase tracking-[0.25em] font-semibold">
              Instructions
            </label>
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              disabled={isRunning}
              rows={5}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-[13px] text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/40 transition-all duration-200 resize-none disabled:opacity-40"
              placeholder="What should the agent do?"
            />
          </div>

          {/* Mode selector pills */}
          <div className="space-y-1.5">
            <label className="text-[9px] text-zinc-600 uppercase tracking-[0.25em] font-semibold">
              Mode
            </label>
            <div className="flex gap-2 bg-white/[0.02] rounded-xl p-1.5 border border-white/[0.04]">
              {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
                const cfg = MODE_CONFIG[m];
                const active = mode === m;
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`flex-1 px-4 py-2 text-[11px] font-bold tracking-[0.12em] rounded-lg transition-all duration-150 ${
                      active
                        ? `${cfg.color} bg-white/[0.06] border ${cfg.border} shadow-[0_0_12px_rgba(139,92,246,0.1)]`
                        : "text-zinc-600 hover:text-zinc-400 border border-transparent"
                    }`}
                  >
                    {cfg.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Execute / Stop button */}
          <AnimatePresence mode="wait">
            {isRunning ? (
              <motion.button
                key="stop"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                onClick={onStop}
                className="w-full py-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 font-bold text-sm tracking-wide flex items-center justify-center gap-2 hover:bg-red-500/20 hover:border-red-500/50 transition-all duration-150"
              >
                <Square className="w-4 h-4" />
                Stop Agent
              </motion.button>
            ) : (
              <motion.button
                key="execute"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                onClick={onExecute}
                disabled={!url || !task}
                className="w-full py-3.5 rounded-xl bg-gradient-to-r from-violet-600 via-fuchsia-600 to-cyan-500 text-white font-bold text-sm tracking-wide flex items-center justify-center gap-2 hover:shadow-[0_0_40px_rgba(139,92,246,0.4)] disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 active:scale-[0.98]"
              >
                <Play className="w-4 h-4" />
                Execute Agent
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Quick Launch */}
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-3 border-b border-white/[0.04]">
          <span className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
            Quick Launch
          </span>
        </div>
        <div className="p-3 grid grid-cols-2 gap-2">
          {QUICK_SITES.map((site, i) => (
            <motion.button
              key={site.name}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, duration: 0.3 }}
              onClick={() => {
                if (!isRunning) {
                  setUrl(site.url);
                  setTask(site.task);
                }
              }}
              disabled={isRunning}
              className="group p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:border-violet-500/30 hover:bg-white/[0.04] transition-all duration-150 text-left disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.97]"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="text-base">{site.icon}</span>
                <span className="text-[11px] font-semibold text-zinc-400 group-hover:text-white transition-colors">
                  {site.name}
                </span>
              </div>
              <p className="text-[9px] text-zinc-600 leading-relaxed line-clamp-2">
                {site.task.slice(0, 55)}...
              </p>
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  );
}
