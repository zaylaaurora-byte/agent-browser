"use client";

import { motion } from "framer-motion";
import { Clock, Loader2, Maximize2, Globe } from "lucide-react";
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
  const ms = MODE_STYLES[mode];

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, delay: 0.06, ease: [0.16, 1, 0.3, 1] }}
      className="glass-card rounded-2xl overflow-hidden"
    >
      {/* Chrome bar */}
      <div className="flex items-center gap-2 sm:gap-3 px-3 py-2.5 bg-black/40 border-b border-white/[0.07]">
        {/* Traffic lights */}
        <div className="flex gap-1.5 flex-shrink-0">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500/60" />
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/60" />
        </div>

        {/* URL display */}
        <div className="flex-1 mx-1 min-w-0">
          <div className="flex items-center gap-1.5 bg-black/50 rounded-lg px-3 py-1.5 max-w-xl mx-auto">
            <Globe className="w-3 h-3 text-zinc-700 flex-shrink-0" />
            <span className="text-[11px] text-zinc-500 font-mono truncate">
              {currentUrl || "about:blank"}
            </span>
          </div>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className={`hidden sm:inline px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest ${ms.color} border ${ms.border} ${ms.bg}`}>
            {ms.label}
          </span>
          {wsStatus === "connected" && (
            <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/8 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-dot 1.5s ease-in-out infinite" }} />
              <span className="text-[9px] text-emerald-400 font-bold uppercase tracking-wider hidden sm:inline">Live</span>
            </span>
          )}
          {isRunning && completedSteps > 0 && (
            <span className="px-2 py-1 rounded-lg bg-zinc-900/70 border border-zinc-800/50 text-[9px] text-zinc-400 font-mono">
              {completedSteps} steps
            </span>
          )}
          {executionTime !== null && (
            <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-zinc-900/70 border border-zinc-800/50 text-[9px] text-emerald-400 font-mono">
              <Clock className="w-2.5 h-2.5" />{executionTime}s
            </span>
          )}
        </div>
      </div>

      {/* Viewport area */}
      <div className={`relative bg-zinc-950 aspect-video ${isRunning && !currentScreenshot ? "scan-running shimmer" : ""}`}>
        {currentScreenshot ? (
          <button
            onClick={onScreenshotClick}
            className="w-full h-full group relative block focus:outline-none"
          >
            <img
              src={`data:image/png;base64,${currentScreenshot}`}
              alt="Browser view"
              className="w-full h-full object-contain transition-[filter] duration-200 group-hover:brightness-90"
            />
            {isRunning && (
              <span className="absolute inset-0 border border-violet-500/20 pointer-events-none animate-pulse" />
            )}
            <span className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <span className="flex items-center gap-1.5 bg-black/70 rounded-xl px-3 py-1.5 border border-zinc-700/50 text-[11px] text-zinc-200 font-medium">
                <Maximize2 className="w-3.5 h-3.5" />Fullscreen
              </span>
            </span>
          </button>
        ) : isRunning ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center space-y-3">
              <Loader2 className="w-9 h-9 text-violet-500/60 animate-spin mx-auto" />
              <p className="text-[10px] text-zinc-700 uppercase tracking-widest">Starting browser…</p>
            </div>
          </div>
        ) : (
          <EmptyState />
        )}
      </div>

      {/* Filmstrip */}
      {screenshotHistory.length > 1 && (
        <div className="border-t border-white/[0.06] px-3 py-2 bg-black/25">
          <div className="flex gap-1.5 overflow-x-auto">
            {screenshotHistory.map((ss, i) => (
              <button
                key={i}
                onClick={() => onThumbnailClick(ss, i)}
                className={`flex-shrink-0 w-14 sm:w-18 h-9 sm:h-11 rounded-lg overflow-hidden border-2 transition-all duration-100 ${
                  activeScreenshotIndex === i
                    ? "border-violet-500 shadow-[0_0_8px_rgba(124,58,237,0.4)]"
                    : "border-zinc-800/60 hover:border-zinc-600"
                }`}
              >
                <img
                  src={`data:image/png;base64,${ss}`}
                  alt={`Step ${i + 1}`}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}

function EmptyState() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage: `linear-gradient(rgba(124,58,237,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.6) 1px, transparent 1px)`,
          backgroundSize: "44px 44px",
        }}
      />
      <div className="relative text-center space-y-4">
        <div className="relative mx-auto w-14 h-14">
          <div className="w-14 h-14 rounded-2xl border border-zinc-800/60 flex items-center justify-center bg-zinc-900/50">
            <Globe className="w-6 h-6 text-zinc-700" />
          </div>
          <span
            className="absolute w-3 h-3 rounded-full bg-violet-600/70 border-2 border-zinc-950"
            style={{ top: "50%", left: "50%", marginTop: "-6px", marginLeft: "-6px", animation: "orbit 3.5s linear infinite" }}
          />
        </div>
        <div>
          <p className="text-[11px] text-zinc-600 uppercase tracking-widest">No browser session</p>
          <p className="text-[10px] text-zinc-800 mt-1">Enter a URL and task, then hit Execute</p>
        </div>
      </div>
    </div>
  );
}
