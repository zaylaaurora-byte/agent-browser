"use client";

import { motion } from "framer-motion";
import { Globe, Brain, Clock, Loader2 } from "lucide-react";
import { MODE_STYLES } from "./types";
import type { Mode } from "./types";

interface Props {
  currentScreenshot: string | null;
  currentUrl: string;
  mode: Mode;
  isRunning: boolean;
  wsStatus: "disconnected" | "connecting" | "connected";
  completedSteps: number;
  executionTime: number | null;
  screenshotHistory: string[];
  activeScreenshotIndex: number;
  onScreenshotClick: () => void;
  onThumbnailClick: (ss: string, i: number) => void;
}

export function BrowserViewport({
  currentScreenshot, currentUrl, mode, isRunning, wsStatus,
  completedSteps, executionTime, screenshotHistory, activeScreenshotIndex,
  onScreenshotClick, onThumbnailClick,
}: Props) {
  const modeStyle = MODE_STYLES[mode];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
      className="rounded-2xl glass overflow-hidden"
    >
      {/* Chrome bar */}
      <div className="flex items-center gap-3 px-4 py-3 bg-black/60 border-b border-zinc-800/40">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500/70" />
          <div className="w-3 h-3 rounded-full bg-amber-500/70" />
          <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
        </div>
        <div className="flex-1 mx-3">
          <div className="bg-black/60 rounded-lg px-3 py-1.5 text-xs text-zinc-500 truncate font-mono border border-zinc-800/40 max-w-lg mx-auto">
            {currentUrl}
          </div>
        </div>
        <div className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest ${modeStyle.color} border ${modeStyle.border} ${modeStyle.bg}`}>
          {modeStyle.label}
        </div>
        <div className="flex items-center gap-2">
          {wsStatus === "connected" && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
              <span className="text-[9px] text-emerald-400 font-bold uppercase tracking-wider">Live</span>
            </div>
          )}
          {isRunning && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-zinc-900/60 border border-zinc-800/50">
              <span className="text-[10px] text-zinc-400 font-mono">{completedSteps} steps</span>
            </div>
          )}
          {executionTime !== null && (
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-zinc-900/60 border border-zinc-800/50">
              <Clock className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] text-emerald-400 font-mono">{executionTime}s</span>
            </div>
          )}
        </div>
      </div>

      {/* Screenshot */}
      <div className="relative bg-black aspect-[16/9]">
        {currentScreenshot ? (
          <button onClick={onScreenshotClick} className="w-full h-full cursor-zoom-in group relative">
            <img
              src={`data:image/png;base64,${currentScreenshot}`}
              alt="Browser view"
              className="w-full h-full object-contain group-hover:brightness-90 transition-all"
            />
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <div className="bg-black/70 rounded-xl px-4 py-2 text-xs text-zinc-300 font-mono border border-zinc-700">
                Click to expand
              </div>
            </div>
          </button>
        ) : isRunning ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center space-y-4">
              <Loader2 className="w-12 h-12 text-violet-500 animate-spin mx-auto" />
              <p className="text-xs text-zinc-600 uppercase tracking-widest">Initializing browser...</p>
            </div>
          </div>
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center space-y-3">
              <Globe className="w-12 h-12 text-zinc-800 mx-auto" />
              <p className="text-xs text-zinc-700 uppercase tracking-widest">Execute a task to see the browser</p>
            </div>
          </div>
        )}
        {isRunning && (
          <div className="absolute inset-0 border-2 border-violet-500/20 rounded-b-2xl pointer-events-none animate-pulse" />
        )}
      </div>

      {/* Screenshot filmstrip */}
      {screenshotHistory.length > 1 && (
        <div className="border-t border-zinc-800/40 p-3 bg-black/40">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {screenshotHistory.map((ss, i) => (
              <button
                key={i}
                onClick={() => onThumbnailClick(ss, i)}
                className={`flex-shrink-0 w-20 h-12 rounded-lg overflow-hidden border-2 transition-all ${
                  activeScreenshotIndex === i ? "border-violet-500 shadow-[0_0_10px_rgba(168,85,247,0.3)]" : "border-zinc-800/50 hover:border-zinc-600"
                }`}
              >
                <img src={`data:image/png;base64,${ss}`} alt={`Step ${i + 1}`} className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
