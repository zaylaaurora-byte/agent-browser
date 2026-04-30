"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Globe, Loader2, Monitor } from "lucide-react";
import type { Mode } from "./task-input";

const MODE_STYLES: Record<Mode, { label: string; color: string; border: string }> = {
  fast: { label: "FAST", color: "text-amber-400", border: "border-amber-500/40" },
  stealth: { label: "STEALTH", color: "text-slate-300", border: "border-slate-500/40" },
  deep: { label: "DEEP", color: "text-violet-400", border: "border-violet-500/40" },
};

interface BrowserViewportProps {
  currentScreenshot: string | null;
  currentUrl: string;
  targetUrl: string;
  isRunning: boolean;
  mode: Mode;
  completedSteps: number;
  screenshotHistory: string[];
  activeScreenshotIndex: number;
  onScreenshotSelect: (ss: string, index: number) => void;
  latestStepUrl?: string;
}

export function BrowserViewport({
  currentScreenshot,
  currentUrl,
  targetUrl,
  isRunning,
  mode,
  completedSteps,
  screenshotHistory,
  activeScreenshotIndex,
  onScreenshotSelect,
  latestStepUrl,
}: BrowserViewportProps) {
  const modeStyle = MODE_STYLES[mode];
  const displayUrl = latestStepUrl || currentUrl || targetUrl;

  return (
    <div className="glass-card overflow-hidden">
      {/* Chrome-style browser bar */}
      <div className="flex items-center gap-3 px-4 py-3 bg-white/[0.02] border-b border-white/[0.04]">
        {/* Traffic lights */}
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500/70" />
          <div className="w-3 h-3 rounded-full bg-amber-500/70" />
          <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
        </div>

        {/* URL bar */}
        <div className="flex-1 mx-2">
          <div className="bg-black/60 rounded-lg px-4 py-1.5 text-[11px] text-zinc-500 truncate font-mono border border-white/[0.04] max-w-xl mx-auto">
            {displayUrl || "about:blank"}
          </div>
        </div>

        {/* Mode badge */}
        <div
          className={`px-3 py-1 rounded-lg text-[9px] font-bold uppercase tracking-widest ${modeStyle.color} border ${modeStyle.border} bg-white/[0.03]`}
        >
          {modeStyle.label}
        </div>
      </div>

      {/* Screenshot viewport */}
      <div className="relative bg-black">
        <div className="aspect-[16/9] relative">
          <AnimatePresence mode="wait">
            {currentScreenshot ? (
              <motion.img
                key={activeScreenshotIndex + "-main"}
                initial={{ opacity: 0.7 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
                src={`data:image/png;base64,${currentScreenshot}`}
                alt="Browser view"
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center">
                {isRunning ? (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="text-center space-y-4"
                  >
                    <div className="relative mx-auto w-16 h-16">
                      <div className="absolute inset-0 border-2 border-white/[0.06] rounded-full" />
                      <div className="absolute inset-0 border-2 border-transparent border-t-violet-500 rounded-full animate-spin" />
                    </div>
                    <p className="text-xs text-zinc-600 animate-pulse tracking-widest uppercase">
                      Initializing browser...
                    </p>
                  </motion.div>
                ) : (
                  <div className="text-center space-y-3">
                    <div className="w-16 h-16 mx-auto rounded-2xl bg-white/[0.03] border border-white/[0.06] flex items-center justify-center">
                      <Monitor className="w-8 h-8 text-zinc-700" />
                    </div>
                    <p className="text-xs text-zinc-700 tracking-widest uppercase">
                      Execute a task to see the browser
                    </p>
                  </div>
                )}
              </div>
            )}
          </AnimatePresence>

          {/* Step badge overlay */}
          {isRunning && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="absolute top-3 right-3 bg-black/80 border border-white/[0.08] rounded-xl px-3 py-2 backdrop-blur-xl"
            >
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest">Step </span>
              <span className="text-sm font-bold text-white tabular-nums">{completedSteps}</span>
            </motion.div>
          )}

          {/* Live URL overlay */}
          {latestStepUrl && (
            <div className="absolute bottom-3 left-3 bg-black/80 border border-white/[0.06] rounded-lg px-3 py-1.5 backdrop-blur-xl">
              <span className="text-[9px] text-zinc-500 truncate max-w-xs font-mono">
                {latestStepUrl}
              </span>
            </div>
          )}

          {/* Pulsing border when running */}
          {isRunning && (
            <div className="absolute inset-0 border-2 border-violet-500/20 animate-pulse pointer-events-none" />
          )}
        </div>

        {/* Screenshot filmstrip */}
        {screenshotHistory.length > 0 && (
          <div className="border-t border-white/[0.04] p-2.5 bg-black/40">
            <div className="flex gap-1.5 overflow-x-auto pb-1">
              {screenshotHistory.map((ss, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: i * 0.02 }}
                  onClick={() => onScreenshotSelect(ss, i)}
                  className={`flex-shrink-0 w-20 h-12 rounded-lg overflow-hidden border-2 transition-all duration-150 ${
                    activeScreenshotIndex === i
                      ? "border-violet-500 shadow-[0_0_10px_rgba(139,92,246,0.3)]"
                      : "border-white/[0.06] hover:border-white/[0.12]"
                  }`}
                >
                  <img
                    src={`data:image/png;base64,${ss}`}
                    alt={`Step ${i + 1}`}
                    className="w-full h-full object-cover"
                  />
                </motion.button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
