"use client";

import { motion } from "framer-motion";
import { X, Download, ZoomIn, ZoomOut } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

interface Props {
  screenshot: string;
  onClose: () => void;
}

export function Lightbox({ screenshot, onClose }: Props) {
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [startPos, setStartPos] = useState({ x: 0, y: 0 });

  const resetView = useCallback(() => {
    setScale(1);
    setPosition({ x: 0, y: 0 });
  }, []);

  useEffect(() => {
    resetView();
  }, [screenshot, resetView]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setScale((s) => Math.min(s + 0.25, 5));
      if (e.key === "-") setScale((s) => Math.max(s - 0.25, 0.5));
      if (e.key === "0") resetView();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, resetView]);

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale((s) => Math.max(0.5, Math.min(5, s - e.deltaY * 0.002)));
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (scale <= 1) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
    setStartPos({ x: position.x, y: position.y });
  }, [scale, position]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setPosition({
      x: startPos.x + (e.clientX - dragStart.x),
      y: startPos.y + (e.clientY - dragStart.y),
    });
  }, [isDragging, dragStart, startPos]);

  const onMouseUp = useCallback(() => setIsDragging(false), []);

  const download = () => {
    const link = document.createElement("a");
    link.href = `data:image/png;base64,${screenshot}`;
    link.download = `screenshot-${Date.now()}.png`;
    link.click();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] bg-black/90 backdrop-blur-sm flex items-center justify-center"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Controls */}
      <div className="absolute top-4 right-4 flex items-center gap-2 z-10">
        <button onClick={() => setScale((s) => Math.max(s - 0.25, 0.5))} className="p-2 rounded-lg bg-zinc-800/80 border border-zinc-700 text-zinc-300 hover:text-white transition-colors">
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="px-2 py-1 text-xs font-mono text-zinc-400 bg-zinc-800/80 rounded border border-zinc-700">{Math.round(scale * 100)}%</span>
        <button onClick={() => setScale((s) => Math.min(s + 0.25, 5))} className="p-2 rounded-lg bg-zinc-800/80 border border-zinc-700 text-zinc-300 hover:text-white transition-colors">
          <ZoomIn className="w-4 h-4" />
        </button>
        <button onClick={download} className="p-2 rounded-lg bg-zinc-800/80 border border-zinc-700 text-zinc-300 hover:text-white transition-colors" title="Download">
          <Download className="w-4 h-4" />
        </button>
        <button onClick={onClose} className="p-2 rounded-lg bg-zinc-800/80 border border-zinc-700 text-zinc-300 hover:text-white transition-colors" title="Close (Esc)">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Hint */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 text-[10px] text-zinc-600 font-mono">
        Scroll to zoom · Drag to pan · +/- to resize · 0 to reset
      </div>

      {/* Image */}
      <div
        className="relative max-w-[90vw] max-h-[85vh] overflow-hidden cursor-grab active:cursor-grabbing"
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <img
          src={`data:image/png;base64,${screenshot}`}
          alt="Fullscreen screenshot"
          className="max-w-[90vw] max-h-[85vh] object-contain transition-transform duration-100"
          style={{ transform: `scale(${scale}) translate(${position.x / scale}px, ${position.y / scale}px)`, transformOrigin: "center" }}
          draggable={false}
        />
      </div>
    </motion.div>
  );
}
