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

  const copy = async () => {
    try { await navigator.clipboard.writeText(finalAnswer); } catch { /* ignore */ }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.99 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.38, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl overflow-hidden glow-emerald"
      style={{
        background: "rgba(6, 22, 14, 0.85)",
        border: "1px solid rgba(52,211,153,0.18)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
      }}
    >
      <div className="panel-header">
        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
        <span className="panel-label text-emerald-400/80">Agent Result</span>
        <div className="ml-auto flex items-center gap-3 text-[10px] font-mono text-zinc-600">
          {executionTime !== null && (
            <span className="flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{executionTime}s</span>
          )}
          <span className="flex items-center gap-1"><Hash className="w-2.5 h-2.5" />{stepsCount}</span>
        </div>
        <button
          onClick={copy}
          className="ml-2 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-500/8 border border-emerald-500/18 text-[10px] text-emerald-400 hover:bg-emerald-500/14 transition-all active:scale-95"
        >
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          <span className="hidden sm:inline">{copied ? "Copied!" : "Copy"}</span>
        </button>
      </div>
      <div className="p-4 sm:p-5">
        <pre className="text-sm text-zinc-200 font-mono whitespace-pre-wrap leading-relaxed break-words">
          {finalAnswer}
        </pre>
      </div>
    </motion.div>
  );
}
