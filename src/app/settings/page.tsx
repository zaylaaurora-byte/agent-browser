"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Settings, Key, Brain, Globe, Shield, Save, RotateCcw } from "lucide-react";

interface Settings {
  provider: string;
  model: string;
  apiKey: string;
  maxSteps: number;
  defaultMode: string;
  screenshotInterval: number;
  headless: boolean;
  backendUrl: string;
  userAgent: string;
  viewportWidth: number;
  viewportHeight: number;
}

const DEFAULT_SETTINGS: Settings = {
  provider: "minimax",
  model: "MiniMax-M2.7",
  apiKey: "",
  maxSteps: 500,
  defaultMode: "deep",
  screenshotInterval: 1,
  headless: true,
  backendUrl: "http://localhost:8001",
  userAgent: "",
  viewportWidth: 1920,
  viewportHeight: 1080,
};

const PROVIDERS = [
  { value: "minimax", label: "MiniMax" },
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "ollama", label: "Ollama (Local)" },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("agent-browser-settings");
    if (stored) {
      try { setSettings({ ...DEFAULT_SETTINGS, ...JSON.parse(stored) }); } catch {}
    }
  }, []);

  const save = () => {
    localStorage.setItem("agent-browser-settings", JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const reset = () => {
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem("agent-browser-settings");
  };

  const update = (key: keyof Settings, value: string | number | boolean) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <main className="pt-14 min-h-screen">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          {/* Header */}
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center">
              <Settings className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Settings</h1>
              <p className="text-sm text-zinc-500">Configure your agent browser</p>
            </div>
          </div>

          <div className="space-y-6">
            {/* Model Config */}
            <div className="rounded-2xl glass p-6">
              <div className="flex items-center gap-2 mb-5">
                <Brain className="w-4 h-4 text-violet-400" />
                <h2 className="text-sm font-bold text-zinc-200 uppercase tracking-wider">Model</h2>
              </div>
              <div className="space-y-4">
                <div>
                  <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold block mb-1.5">Provider</label>
                  <select
                    value={settings.provider}
                    onChange={(e) => update("provider", e.target.value)}
                    className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all"
                  >
                    {PROVIDERS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold block mb-1.5">Model Name</label>
                  <input
                    type="text"
                    value={settings.model}
                    onChange={(e) => update("model", e.target.value)}
                    className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold block mb-1.5">API Key</label>
                  <div className="relative">
                    <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-600" />
                    <input
                      type="password"
                      value={settings.apiKey}
                      onChange={(e) => update("apiKey", e.target.value)}
                      placeholder="sk-..."
                      className="w-full bg-black/40 border border-zinc-800/60 rounded-xl pl-10 pr-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Agent Config */}
            <div className="rounded-2xl glass p-6">
              <div className="flex items-center gap-2 mb-5">
                <Shield className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-bold text-zinc-200 uppercase tracking-wider">Agent</h2>
              </div>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold block mb-1.5">Max Steps</label>
                    <input
                      type="number"
                      value={settings.maxSteps}
                      onChange={(e) => update("maxSteps", parseInt(e.target.value) || 100)}
                      className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold block mb-1.5">Default Mode</label>
                    <select
                      value={settings.defaultMode}
                      onChange={(e) => update("defaultMode", e.target.value)}
                      className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all"
                    >
                      <option value="fast">Fast</option>
                      <option value="stealth">Stealth</option>
                      <option value="deep">Deep</option>
                    </select>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm text-zinc-300 font-medium block">Headless Mode</label>
                    <p className="text-[11px] text-zinc-600">Run browser without visible window</p>
                  </div>
                  <button
                    onClick={() => update("headless", !settings.headless)}
                    className={`w-12 h-7 rounded-full transition-all duration-200 ${settings.headless ? "bg-violet-600" : "bg-zinc-700"}`}
                  >
                    <div className={`w-5 h-5 rounded-full bg-white shadow-md transition-all duration-200 ${settings.headless ? "translate-x-6" : "translate-x-1"}`} />
                  </button>
                </div>
              </div>
            </div>

            {/* Connection */}
            <div className="rounded-2xl glass p-6">
              <div className="flex items-center gap-2 mb-5">
                <Globe className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-bold text-zinc-200 uppercase tracking-wider">Connection</h2>
              </div>
              <div>
                <label className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold block mb-1.5">Backend URL</label>
                <input
                  type="text"
                  value={settings.backendUrl}
                  onChange={(e) => update("backendUrl", e.target.value)}
                  className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition-all"
                />
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={save}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm transition-all duration-200 active:scale-[0.97] ${
                  saved
                    ? "bg-emerald-600/20 border border-emerald-500/30 text-emerald-400"
                    : "bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-[0_0_20px_rgba(168,85,247,0.3)]"
                }`}
              >
                <Save className="w-4 h-4" />
                {saved ? "Saved!" : "Save Settings"}
              </button>
              <button
                onClick={reset}
                className="flex items-center gap-2 px-4 py-3 rounded-xl text-sm text-zinc-500 hover:text-zinc-300 border border-zinc-800/50 hover:border-zinc-700/50 transition-all"
              >
                <RotateCcw className="w-4 h-4" />
                Reset
              </button>
            </div>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
