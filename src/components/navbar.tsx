"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe, Settings, Menu, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: Globe },
  { href: "/settings", label: "Settings", icon: Settings },
];

function AgentBrowserLogo({ size = 36 }: { size?: number }) {
  const id = "logo-grad";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 36 36"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={id} x1="2" y1="2" x2="34" y2="34" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#8b5cf6" />
          <stop offset="50%"  stopColor="#d946ef" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stopColor="#8b5cf6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* Outer ring */}
      <circle cx="18" cy="18" r="15" stroke={`url(#${id})`} strokeWidth="1.5" />
      {/* Cross hairs — web grid */}
      <line x1="3"  y1="18" x2="33" y2="18" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      <line x1="18" y1="3"  x2="18" y2="33" stroke="rgba(255,255,255,0.12)" strokeWidth="1" />
      {/* Inner equator ellipse */}
      <ellipse cx="18" cy="18" rx="15" ry="6" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      {/* Center origin dot */}
      <circle cx="18" cy="18" r="2.5" fill={`url(#${id})`} />
      {/* Orbit accent — the "agent" dot */}
      <circle cx="27" cy="11" r="2.5" fill="#a78bfa" />
      <circle cx="27" cy="11" r="4"   fill="#a78bfa" fillOpacity="0.15" />
    </svg>
  );
}

export function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/[0.06]">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">

          {/* Logo */}
          <Link
            href="/"
            className="flex items-center gap-2.5 group flex-shrink-0"
            aria-label="Agent Browser home"
          >
            <div className="relative flex-shrink-0 group-hover:scale-105 transition-transform duration-200">
              <AgentBrowserLogo />
            </div>
            <div className="flex items-baseline gap-1 hidden sm:flex">
              <span className="text-[13px] font-black tracking-[0.08em] text-white">AGENT</span>
              <span className="text-[13px] font-black tracking-[0.08em] text-gradient-brand">BROWSER</span>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-0.5">
            {NAV_LINKS.map((link) => {
              const active = pathname === link.href;
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-[11px] font-semibold tracking-widest uppercase transition-all duration-150 ${
                    active
                      ? "bg-violet-500/10 text-violet-300 border border-violet-500/25"
                      : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05] border border-transparent"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {link.label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            {/* Live status badge */}
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-zinc-900/70 border border-zinc-800/60">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.9)]" />
              <span className="text-[10px] text-zinc-400 font-bold tracking-widest uppercase hidden sm:inline">Live</span>
            </div>

            {/* Mobile hamburger */}
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="md:hidden p-2 rounded-xl bg-zinc-900/60 border border-zinc-800/50 text-zinc-400 hover:text-zinc-200 transition-colors"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
            >
              {mobileOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile slide-down menu */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-14 left-0 right-0 z-40 glass-overlay border-b border-white/[0.07] md:hidden"
          >
            <nav className="max-w-screen-2xl mx-auto px-4 py-3 flex flex-col gap-1">
              {NAV_LINKS.map((link) => {
                const active = pathname === link.href;
                const Icon = link.icon;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setMobileOpen(false)}
                    className={`flex items-center gap-3 px-4 py-3.5 rounded-xl text-sm font-semibold transition-all ${
                      active
                        ? "bg-violet-500/12 text-violet-300 border border-violet-500/25"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] border border-transparent"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
