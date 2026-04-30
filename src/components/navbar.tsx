"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Globe, Settings, Zap } from "lucide-react";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: Globe },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="fixed top-0 left-0 right-0 z-50 glass">
      <div className="max-w-[1920px] mx-auto px-6 h-14 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 via-fuchsia-600 to-cyan-500 flex items-center justify-center shadow-lg group-hover:shadow-violet-500/30 transition-shadow duration-300">
              <Brain className="w-4 h-4 text-white" />
            </div>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-sm font-bold tracking-[0.1em] text-white">AGENT</span>
            <span className="text-sm font-bold tracking-[0.1em] text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400">BROWSER</span>
          </div>
        </Link>

        {/* Nav Links */}
        <nav className="flex items-center gap-1">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href;
            const Icon = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-[11px] font-semibold tracking-wide uppercase transition-all duration-200 ${
                  active
                    ? "bg-zinc-800/80 text-white border border-zinc-700/60"
                    : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/40 border border-transparent"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Status */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-zinc-900/60 border border-zinc-800/50">
            <Zap className="w-3 h-3 text-violet-400" />
            <span className="text-[10px] text-zinc-400 font-semibold tracking-wider uppercase">Live</span>
          </div>
        </div>
      </div>
    </header>
  );
}
