"use client";

import { motion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";

interface Props {
  finalAnswer: string;
  executionTime: number | null;
  stepsCount: number;
}

export function ResultPanel({ finalAnswer, executionTime, stepsCount }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-950/30 to-black/60 backdrop-blur-xl overflow-hidden glow-emerald"
    >
      <div className="px-4 py-3 border-b border-emerald-500/20 flex items-center gap-3">
        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        <span className="text-[11px] text-emerald-400 font-semibold tracking-wider uppercase">Agent Result</span>
        {executionTime !== null && (
          <span className="text-[10px] text-zinc-600 ml-auto">{executionTime}s</span>
        )}
        <span className="text-[10px] text-zinc-600">{stepsCount} steps</span>
      </div>
      <div className="p-5">
        <pre className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed font-mono">{finalAnswer}</pre>
      </div>
    </motion.div>
  );
}
