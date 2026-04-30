"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Brain,
  Globe,
  Zap,
  Settings,
  Key,
  Cpu,
  Monitor,
  Wifi,
  Save,
  RotateCcw,
  Server,
} from "lucide-react";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

interface AgentSettings {
  // Model
  provider: string;
  model: string;
  apiKey: string;

  // Agent
  maxSteps: number;
  defaultMode: string;
  screenshotInterval: number;

  // Browser
  headless: boolean;
  stealthUserAgent: boolean;
  stealthViewport: boolean;

  // Connection
  backendUrl: string;
}

const DEFAULT_SETTINGS: AgentSettings = {
  provider: "minimax",
  model: "MiniMax-M1",
  apiKey: "",
  maxSteps: 500,
  defaultMode: "deep",
  screenshotInterval: 1,
  headless: true,
  stealthUserAgent: true,
  stealthViewport: true,
  backendUrl: "http://localhost:8001",
};

const PROVIDERS = [
  { value: "minimax", label: "MiniMax" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
];

const MODES = [
  { value: "fast", label: "Fast" },
  { value: "stealth", label: "Stealth" },
  { value: "deep", label: "Deep" },
];

export function SettingsForm() {
  const [settings, setSettings] = useState<AgentSettings>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);
  const [wsStatus, setWsStatus] = useState<"connected" | "disconnected">("disconnected");

  // Load from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("agent-browser-settings");
      if (stored) {
        const parsed = JSON.parse(stored);
        setSettings({ ...DEFAULT_SETTINGS, ...parsed });
      }
    } catch {
      // ignore
    }
  }, []);

  // Check WebSocket connection
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${settings.backendUrl}/api/health`, {
          signal: AbortSignal.timeout(3000),
        });
        setWsStatus(res.ok ? "connected" : "disconnected");
      } catch {
        setWsStatus("disconnected");
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, [settings.backendUrl]);

  const updateSetting = <K extends keyof AgentSettings>(key: K, value: AgentSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const saveSettings = () => {
    try {
      localStorage.setItem("agent-browser-settings", JSON.stringify(settings));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // ignore
    }
  };

  const resetSettings = () => {
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem("agent-browser-settings");
    setSaved(false);
  };

  const sectionVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: i * 0.1, duration: 0.4, ease: [0.22, 1, 0.36, 1] as [number, number, number, number] },
    }),
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="mb-10"
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600/20 to-cyan-600/20 border border-violet-500/20 flex items-center justify-center">
            <Settings className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Settings</h1>
            <p className="text-sm text-zinc-500">Configure your agent and browser preferences</p>
          </div>
        </div>
      </motion.div>

      <div className="space-y-6">
        {/* Model Configuration */}
        <motion.div
          custom={0}
          variants={sectionVariants}
          initial="hidden"
          animate="visible"
          className="glass-card p-6 space-y-5"
        >
          <div className="flex items-center gap-2.5 mb-1">
            <Brain className="w-4 h-4 text-violet-400" />
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Model Configuration
            </h2>
          </div>

          {/* Provider */}
          <div className="space-y-2">
            <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
              Provider
            </label>
            <div className="flex gap-2">
              {PROVIDERS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => updateSetting("provider", p.value)}
                  className={`flex-1 px-4 py-2.5 rounded-xl text-[11px] font-semibold tracking-wide transition-all duration-150 ${
                    settings.provider === p.value
                      ? "bg-violet-500/20 text-violet-400 border border-violet-500/30"
                      : "bg-white/[0.02] text-zinc-500 border border-white/[0.04] hover:border-white/[0.08]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Model name */}
          <div className="space-y-2">
            <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
              Model Name
            </label>
            <input
              type="text"
              value={settings.model}
              onChange={(e) => updateSetting("model", e.target.value)}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/40 transition-all duration-200"
              placeholder="e.g. MiniMax-M1"
            />
          </div>

          {/* API Key */}
          <div className="space-y-2">
            <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold flex items-center gap-1.5">
              <Key className="w-3 h-3" />
              API Key
            </label>
            <input
              type="password"
              value={settings.apiKey}
              onChange={(e) => updateSetting("apiKey", e.target.value)}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/40 transition-all duration-200"
              placeholder="sk-..."
            />
          </div>
        </motion.div>

        {/* Agent Settings */}
        <motion.div
          custom={1}
          variants={sectionVariants}
          initial="hidden"
          animate="visible"
          className="glass-card p-6 space-y-5"
        >
          <div className="flex items-center gap-2.5 mb-1">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Agent Settings
            </h2>
          </div>

          {/* Max steps */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
                Max Steps
              </label>
              <span className="text-sm font-bold text-white tabular-nums">{settings.maxSteps}</span>
            </div>
            <Slider
              value={[settings.maxSteps]}
              onValueChange={([v]) => updateSetting("maxSteps", v)}
              min={10}
              max={1000}
              step={10}
              className="w-full"
            />
            <div className="flex justify-between text-[9px] text-zinc-600">
              <span>10</span>
              <span>1000</span>
            </div>
          </div>

          {/* Default mode */}
          <div className="space-y-2">
            <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
              Default Mode
            </label>
            <div className="flex gap-2">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  onClick={() => updateSetting("defaultMode", m.value)}
                  className={`flex-1 px-4 py-2.5 rounded-xl text-[11px] font-semibold tracking-wide transition-all duration-150 ${
                    settings.defaultMode === m.value
                      ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                      : "bg-white/[0.02] text-zinc-500 border border-white/[0.04] hover:border-white/[0.08]"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* Screenshot interval */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
                Screenshot Interval
              </label>
              <span className="text-sm font-bold text-white tabular-nums">
                {settings.screenshotInterval}s
              </span>
            </div>
            <Slider
              value={[settings.screenshotInterval]}
              onValueChange={([v]) => updateSetting("screenshotInterval", v)}
              min={0.5}
              max={5}
              step={0.5}
              className="w-full"
            />
            <div className="flex justify-between text-[9px] text-zinc-600">
              <span>0.5s</span>
              <span>5s</span>
            </div>
          </div>
        </motion.div>

        {/* Browser Settings */}
        <motion.div
          custom={2}
          variants={sectionVariants}
          initial="hidden"
          animate="visible"
          className="glass-card p-6 space-y-5"
        >
          <div className="flex items-center gap-2.5 mb-1">
            <Monitor className="w-4 h-4 text-emerald-400" />
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Browser Settings
            </h2>
          </div>

          {/* Headless toggle */}
          <div className="flex items-center justify-between">
            <div>
              <label className="text-[11px] text-zinc-300 font-semibold">Headless Mode</label>
              <p className="text-[10px] text-zinc-600 mt-0.5">Run browser without visible window</p>
            </div>
            <Switch
              checked={settings.headless}
              onCheckedChange={(v) => updateSetting("headless", v)}
            />
          </div>

          {/* Stealth options */}
          <div className="space-y-4 pt-2 border-t border-white/[0.04]">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-[11px] text-zinc-300 font-semibold">
                  Custom User Agent
                </label>
                <p className="text-[10px] text-zinc-600 mt-0.5">
                  Spoof browser user agent string
                </p>
              </div>
              <Switch
                checked={settings.stealthUserAgent}
                onCheckedChange={(v) => updateSetting("stealthUserAgent", v)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <label className="text-[11px] text-zinc-300 font-semibold">
                  Random Viewport Size
                </label>
                <p className="text-[10px] text-zinc-600 mt-0.5">
                  Vary viewport dimensions per session
                </p>
              </div>
              <Switch
                checked={settings.stealthViewport}
                onCheckedChange={(v) => updateSetting("stealthViewport", v)}
              />
            </div>
          </div>
        </motion.div>

        {/* Connection */}
        <motion.div
          custom={3}
          variants={sectionVariants}
          initial="hidden"
          animate="visible"
          className="glass-card p-6 space-y-5"
        >
          <div className="flex items-center gap-2.5 mb-1">
            <Server className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider">
              Connection
            </h2>
          </div>

          {/* Backend URL */}
          <div className="space-y-2">
            <label className="text-[10px] text-zinc-500 uppercase tracking-[0.2em] font-semibold">
              Backend URL
            </label>
            <input
              type="text"
              value={settings.backendUrl}
              onChange={(e) => updateSetting("backendUrl", e.target.value)}
              className="w-full bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/40 transition-all duration-200"
              placeholder="http://localhost:8001"
            />
          </div>

          {/* WebSocket status */}
          <div className="flex items-center justify-between">
            <div>
              <label className="text-[11px] text-zinc-300 font-semibold">
                WebSocket Status
              </label>
              <p className="text-[10px] text-zinc-600 mt-0.5">
                ws://{new URL(settings.backendUrl).host}/ws/agent
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${
                  wsStatus === "connected"
                    ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]"
                    : "bg-zinc-600"
                }`}
              />
              <span
                className={`text-[10px] uppercase tracking-widest font-semibold ${
                  wsStatus === "connected" ? "text-emerald-400" : "text-zinc-600"
                }`}
              >
                {wsStatus === "connected" ? "Connected" : "Disconnected"}
              </span>
            </div>
          </div>
        </motion.div>

        {/* Action buttons */}
        <motion.div
          custom={4}
          variants={sectionVariants}
          initial="hidden"
          animate="visible"
          className="flex gap-3"
        >
          <button
            onClick={saveSettings}
            className={`flex-1 py-3.5 rounded-xl font-bold text-sm tracking-wide flex items-center justify-center gap-2 transition-all duration-200 active:scale-[0.98] ${
              saved
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "bg-gradient-to-r from-violet-600 via-fuchsia-600 to-cyan-500 text-white hover:shadow-[0_0_40px_rgba(139,92,246,0.3)]"
            }`}
          >
            <Save className="w-4 h-4" />
            {saved ? "Saved!" : "Save Settings"}
          </button>

          <button
            onClick={resetSettings}
            className="px-6 py-3.5 rounded-xl font-semibold text-sm text-zinc-500 border border-white/[0.06] hover:border-white/[0.12] hover:text-zinc-300 transition-all duration-150 flex items-center gap-2"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
        </motion.div>
      </div>
    </div>
  );
}
