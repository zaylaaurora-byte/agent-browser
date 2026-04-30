"use client";

import { motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect } from "react";

const SHORTCUTS = [
  { key: "⌘ / Ctrl + ↵", action: "Execute task" },
  { key: "Esc", action: "Stop running task" },
  { key: "r", action: "Replay last task" },
  { key: "?", action: "Show this overlay" },
  { key: "Esc", action: "Close modal / overlay" },
  { key: "+ / -", action: "Zoom in / out (lightbox)" },
  { key: "0", action: "Reset zoom (lightbox)" },
];

interface Props { onClose: () => void; }

export function KeyboardShortcutsOverlay({ onClose }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        className="rounded-2xl glass border border-zinc-800/60 p-6 w-80"
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-zinc-200">Keyboard Shortcuts</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-2">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1.5 border-b border-zinc-800/30 last:border-0">
              <span className="text-xs text-zinc-400">{s.action}</span>
              <kbd className="px-2 py-1 text-[10px] font-mono bg-zinc-800 border border-zinc-700 rounded text-zinc-300">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>
      </motion.div>
    </motion.div>
  );
}
