"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Brain, LayoutDashboard, Settings, Activity } from "lucide-react";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 h-14 border-b border-white/[0.06] bg-[#050508]/80 backdrop-blur-2xl">
      <div className="max-w-[1920px] mx-auto px-6 h-full flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 via-fuchsia-600 to-cyan-500 flex items-center justify-center shadow-[0_0_20px_rgba(139,92,246,0.3)] group-hover:shadow-[0_0_30px_rgba(139,92,246,0.5)] transition-shadow duration-300">
              <Brain className="w-5 h-5 text-white" />
            </div>
          </div>
          <div>
            <h1 className="text-sm font-extrabold tracking-[0.12em] text-white leading-none">
              AGENT
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400">
                BROWSER
              </span>
            </h1>
            <p className="text-[8px] text-zinc-600 tracking-[0.25em] uppercase leading-none mt-0.5">
              AI Automation
            </p>
          </div>
        </Link>

        {/* Nav Links */}
        <nav className="flex items-center gap-1 bg-zinc-900/50 rounded-xl p-1 border border-white/[0.04]">
          {NAV_LINKS.map(({ href, label, icon: Icon }) => {
            const isActive = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className="relative flex items-center gap-2 px-4 py-2 rounded-lg text-[11px] font-semibold tracking-wide transition-colors duration-150"
              >
                {isActive && (
                  <motion.div
                    layoutId="nav-active"
                    className="absolute inset-0 bg-white/[0.06] border border-white/[0.08] rounded-lg"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
                <Icon className="w-3.5 h-3.5 relative z-10" />
                <span className={`relative z-10 ${isActive ? "text-white" : "text-zinc-500 hover:text-zinc-300"}`}>
                  {label}
                </span>
              </Link>
            );
          })}
        </nav>

        {/* Status indicator */}
        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-zinc-600" />
          <span className="text-[10px] text-zinc-600 uppercase tracking-widest">Online</span>
          <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(52,211,153,0.6)]" />
        </div>
      </div>
    </header>
  );
}
