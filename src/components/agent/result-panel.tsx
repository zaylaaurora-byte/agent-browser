"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, Copy, Check, Clock, Hash } from "lucide-react";

interface Props {
  finalAnswer: string;
  executionTime: number | null;
  stepsCount: number;
}

export function ResultPanel({ finalAnswer, executionTime, stepsCount }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(finalAnswer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.99 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl overflow-hidden glow-emerald"
      style={{
        background: "linear-gradient(rgba(5,10,8,0.85), rgba(5,10,8,0.85)) padding-box, linear-gradient(145deg, rgba(52,211,153,0.22), rgba(255,255,255,0.04), rgba(34,211,238,0.10)) border-box",
        border: "1px solid transparent",
        backdropFilter: "blur(32px)",
      }}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-emerald-500/15 flex items-center gap-2.5">
        <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
        <span className="text-[11px] text-emerald-400 font-semibold tracking-widest uppercase">Agent Result</span>

        {/* Stats */}
        <div className="flex items-center gap-3 ml-auto text-[10px] font-mono text-zinc-600">
          {executionTime !== null && (
            <div className="flex items-center gap-1">
              <Clock className="w-2.5 h-2.5" />
              {executionTime}s
            </div>
          )}
          <div className="flex items-center gap-1">
            <Hash className="w-2.5 h-2.5" />
            {stepsCount} steps
          </div>
        </div>

        {/* Copy button */}
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/8 border border-emerald-500/20 text-[10px] text-emerald-400 hover:bg-emerald-500/15 transition-all active:scale-95"
          title="Copy result"
        >
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          <span className="hidden sm:inline">{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>

      {/* Content */}
      <div className="p-4 sm:p-5">
        <pre className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed font-mono break-words">
          {finalAnswer}
        </pre>
      </div>
    </motion.div>
  );
}
