"use client";

import { motion } from "framer-motion";
import { Globe, Clock, Loader2, Maximize2 } from "lucide-react";
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
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl glass-card overflow-hidden"
    >
      {/* Chrome bar */}
      <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-2.5 bg-black/50 border-b border-zinc-800/40">
        {/* Traffic lights */}
        <div className="flex gap-1.5 flex-shrink-0">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500/70" />
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500/70" />
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/70" />
        </div>

        {/* URL bar */}
        <div className="flex-1 mx-1 sm:mx-2 min-w-0">
          <div className="bg-black/50 rounded-lg px-3 py-1.5 text-[11px] text-zinc-500 truncate font-mono border border-zinc-800/40 max-w-xl mx-auto">
            {currentUrl || "about:blank"}
          </div>
        </div>

        {/* Right badges */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <div className={`hidden sm:flex px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest ${modeStyle.color} border ${modeStyle.border} ${modeStyle.bg}`}>
            {modeStyle.label}
          </div>
          {wsStatus === "connected" && (
            <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/8 border border-emerald-500/25">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_5px_rgba(52,211,153,0.9)]" />
              <span className="text-[9px] text-emerald-400 font-bold uppercase tracking-widest hidden sm:inline">Live</span>
            </div>
          )}
          {isRunning && (
            <div className="px-2 py-1 rounded-lg bg-zinc-900/70 border border-zinc-800/50">
              <span className="text-[9px] text-zinc-400 font-mono">{completedSteps}s</span>
            </div>
          )}
          {executionTime !== null && (
            <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-zinc-900/70 border border-zinc-800/50">
              <Clock className="w-2.5 h-2.5 text-emerald-400" />
              <span className="text-[9px] text-emerald-400 font-mono">{executionTime}s</span>
            </div>
          )}
        </div>
      </div>

      {/* Viewport area */}
      <div className={`relative bg-black aspect-video ${isRunning && !currentScreenshot ? "scan-running shimmer" : ""}`}>
        {currentScreenshot ? (
          <button
            onClick={onScreenshotClick}
            className="w-full h-full cursor-zoom-in group relative block"
            title="Click to expand"
          >
            <img
              src={`data:image/png;base64,${currentScreenshot}`}
              alt="Browser view"
              className="w-full h-full object-contain group-hover:brightness-90 transition-all duration-200"
            />
            {/* Hover overlay */}
            <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
              <div className="flex items-center gap-2 bg-black/70 rounded-xl px-3 py-2 border border-zinc-700/60 text-xs text-zinc-300 font-medium">
                <Maximize2 className="w-3.5 h-3.5" />
                Fullscreen
              </div>
            </div>
            {/* Running border pulse */}
            {isRunning && (
              <div className="absolute inset-0 border border-violet-500/25 pointer-events-none animate-pulse rounded-none" />
            )}
          </button>
        ) : isRunning ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center space-y-3">
              <Loader2 className="w-10 h-10 text-violet-500/70 animate-spin mx-auto" />
              <p className="text-[10px] text-zinc-700 uppercase tracking-widest">Starting browser…</p>
            </div>
          </div>
        ) : (
          <EmptyViewport />
        )}
      </div>

      {/* Filmstrip */}
      {screenshotHistory.length > 1 && (
        <div className="border-t border-zinc-800/40 px-3 py-2.5 bg-black/30">
          <div className="flex gap-2 overflow-x-auto pb-0.5" style={{ scrollbarWidth: "thin" }}>
            {screenshotHistory.map((ss, i) => (
              <button
                key={i}
                onClick={() => onThumbnailClick(ss, i)}
                className={`flex-shrink-0 w-16 sm:w-20 h-10 sm:h-12 rounded-lg overflow-hidden border-2 transition-all duration-150 ${
                  activeScreenshotIndex === i
                    ? "border-violet-500 shadow-[0_0_10px_rgba(168,85,247,0.35)]"
                    : "border-zinc-800/60 hover:border-zinc-600/80"
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

function EmptyViewport() {
  return (
    <div className="absolute inset-0 flex items-center justify-center">
      {/* Animated grid background */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(139,92,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(139,92,246,0.5) 1px, transparent 1px)`,
          backgroundSize: "48px 48px",
        }}
      />
      <div className="relative text-center space-y-4">
        <div className="relative mx-auto w-16 h-16">
          <div className="w-16 h-16 rounded-2xl border border-zinc-800/60 flex items-center justify-center bg-zinc-900/40">
            <Globe className="w-7 h-7 text-zinc-700" />
          </div>
          {/* Orbiting dot */}
          <div
            className="absolute w-2.5 h-2.5 rounded-full bg-violet-500/60"
            style={{
              top: "50%",
              left: "50%",
              marginTop: "-5px",
              marginLeft: "-5px",
              animation: "orbit 4s linear infinite",
              transformOrigin: "center center",
            }}
          />
        </div>
        <div>
          <p className="text-[11px] text-zinc-700 uppercase tracking-widest">No browser session</p>
          <p className="text-[10px] text-zinc-800 mt-1">Enter a URL and task above, then press Execute</p>
        </div>
      </div>
    </div>
  );
}
