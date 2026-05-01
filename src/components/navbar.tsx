"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe, Settings, Menu, X, Activity } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const NAV_LINKS = [
  { href: "/",          label: "Dashboard", icon: Globe    },
  { href: "/supervisor", label: "Supervisor", icon: Activity },
  { href: "/settings", label: "Settings",  icon: Settings },
];

function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-hidden>
      <defs>
        <linearGradient id="lg" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#7c3aed" />
          <stop offset="55%"  stopColor="#a855f7" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      {/* Outer ring */}
      <circle cx="16" cy="16" r="13" stroke="url(#lg)" strokeWidth="1.5" />
      {/* Horizontal guide */}
      <line x1="3"  y1="16" x2="29" y2="16" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      {/* Vertical guide */}
      <line x1="16" y1="3"  x2="16" y2="29" stroke="rgba(255,255,255,0.10)" strokeWidth="1" />
      {/* Equator ellipse */}
      <ellipse cx="16" cy="16" rx="13" ry="5.5" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />
      {/* Centre dot */}
      <circle cx="16" cy="16" r="2.5" fill="url(#lg)" />
      {/* Agent dot */}
      <circle cx="23.5" cy="9.5" r="2.5" fill="#a78bfa" />
      <circle cx="23.5" cy="9.5" r="4.5" fill="#a78bfa" fillOpacity="0.15" />
    </svg>
  );
}

export function Navbar() {
  const pathname   = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/[0.07]">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group flex-shrink-0" aria-label="Agent Browser">
            <div className="group-hover:scale-105 transition-transform duration-200 flex-shrink-0">
              <LogoMark />
            </div>
            <div className="hidden sm:flex items-baseline gap-1">
              <span className="text-[13px] font-black tracking-[0.07em] text-white/90">AGENT</span>
              <span className="text-[13px] font-black tracking-[0.07em] text-gradient-brand">BROWSER</span>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-0.5">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-[11px] font-semibold tracking-widest uppercase transition-all duration-100 ${
                    active
                      ? "bg-violet-500/10 text-violet-300 border border-violet-500/24"
                      : "text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05] border border-transparent"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />{label}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center gap-2">
            {/* Live indicator */}
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-zinc-900/80 border border-zinc-800/60">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" style={{ animation: "pulse-dot 2s ease-in-out infinite" }} />
              <span className="text-[10px] text-zinc-400 font-bold tracking-widest uppercase hidden sm:inline">Live</span>
            </div>
            {/* Hamburger */}
            <button
              onClick={() => setOpen((v) => !v)}
              className="md:hidden w-10 h-10 rounded-xl glass-surface flex items-center justify-center text-zinc-400 hover:text-zinc-200 transition-colors"
              aria-label={open ? "Close menu" : "Open menu"}
            >
              {open ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* Mobile menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
            className="fixed top-14 left-0 right-0 z-40 glass-overlay border-b border-white/[0.07] md:hidden"
          >
            <nav className="max-w-screen-2xl mx-auto px-4 py-3 flex flex-col gap-1">
              {NAV_LINKS.map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-3 px-4 py-3.5 rounded-xl text-sm font-semibold transition-all ${
                    pathname === href
                      ? "bg-violet-500/10 text-violet-300 border border-violet-500/22"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.05] border border-transparent"
                  }`}
                >
                  <Icon className="w-4 h-4" />{label}
                </Link>
              ))}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
