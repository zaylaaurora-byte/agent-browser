"use client";

import { motion } from "framer-motion";
import { X, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

interface Settings {
  apiKey: string;
  model: string;
  provider: "minimax" | "openai" | "anthropic" | "ollama";
  backendUrl: string;
}

interface Props { onClose: () => void; }

const PROVIDER_MODELS: Record<string, string[]> = {
  minimax: ["MiniMax-M2.7", "MiniMax-M2.0"],
  openai:  ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-sonnet-4", "claude-opus-4", "claude-3-5-sonnet", "claude-3-opus"],
  ollama:  ["llama3", "llama3.1", "codellama", "mistral", "mixtral"],
};

export function SettingsModal({ onClose }: Props) {
  const [form, setForm] = useState<Settings>({
    apiKey: "",
    model: "MiniMax-M2.7",
    provider: "minimax",
    backendUrl: "ws://localhost:8001/ws/agent",
  });
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "ok" | "fail">("idle");
  const [testError, setTestError] = useState("");
  const [saved, setSaved] = useState(false);

  // Load existing settings on mount
  useEffect(() => {
    const stored = localStorage.getItem("agent-browser-settings");
    if (stored) {
      try { setForm({ ...form, ...JSON.parse(stored) }); } catch { /* ignore */ }
    }
  }, []);

  const handleSave = useCallback(() => {
    localStorage.setItem("agent-browser-settings", JSON.stringify(form));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
    onClose();
  }, [form, onClose]);

  const testConnection = async () => {
    setTestStatus("testing");
    setTestError("");
    try {
      const health = await fetch("http://localhost:8001/api/health", { signal: AbortSignal.timeout(5000) });
      if (health.ok) {
        setTestStatus("ok");
      } else {
        setTestStatus("fail");
        setTestError(`HTTP ${health.status}`);
      }
    } catch (e: unknown) {
      setTestStatus("fail");
      setTestError(e instanceof Error ? e.message : "Connection failed");
    }
  };

  const isOllama = form.provider === "ollama";

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
        className="rounded-2xl glass border border-zinc-800/60 p-6 w-[440px] space-y-4"
      >
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-zinc-200">Settings</h2>
          <button onClick={onClose} className="text-zinc-500 hover:text-zinc-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Provider */}
        <div>
          <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider mb-1.5 block">Provider</label>
          <div className="grid grid-cols-2 gap-2">
            {(["minimax", "openai", "anthropic", "ollama"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setForm((f) => ({ ...f, provider: p, model: PROVIDER_MODELS[p][0] }))}
                className={`py-2 px-3 rounded-xl text-xs font-bold tracking-wide border transition-all ${
                  form.provider === p
                    ? "bg-violet-600/20 border-violet-500/50 text-violet-300"
                    : "bg-black/40 border-zinc-800/60 text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Model */}
        <div>
          <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider mb-1.5 block">Model</label>
          <select
            value={form.model}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
            className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-2.5 text-xs text-zinc-200 font-mono focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
          >
            {PROVIDER_MODELS[form.provider].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        {/* API Key */}
        {!isOllama && (
          <div>
            <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider mb-1.5 block">
              API Key {form.provider === "minimax" ? "(optional if set in .env)" : ""}
            </label>
            <input
              type="password"
              value={form.apiKey}
              onChange={(e) => setForm((f) => ({ ...f, apiKey: e.target.value }))}
              placeholder={isOllama ? "" : "sk-..."}
              className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-2.5 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
            />
          </div>
        )}

        {/* Ollama base URL */}
        {isOllama && (
          <div>
            <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider mb-1.5 block">Ollama Base URL</label>
            <input
              type="text"
              value={form.backendUrl.replace("/ws/agent", "")}
              onChange={(e) => setForm((f) => ({ ...f, backendUrl: `${e.target.value.replace(/\/$/, "")}/ws/agent` }))}
              placeholder="http://localhost:11434"
              className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-2.5 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
            />
          </div>
        )}

        {/* Backend WebSocket URL */}
        {!isOllama && (
          <div>
            <label className="text-[11px] text-zinc-500 font-semibold uppercase tracking-wider mb-1.5 block">Backend WebSocket URL</label>
            <input
              type="text"
              value={form.backendUrl}
              onChange={(e) => setForm((f) => ({ ...f, backendUrl: e.target.value }))}
              placeholder="ws://localhost:8001/ws/agent"
              className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-2.5 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
            />
          </div>
        )}

        {/* Test Connection */}
        <div className="flex items-center gap-2">
          <button
            onClick={testConnection}
            disabled={testStatus === "testing"}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-black/40 border border-zinc-800/60 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-all disabled:opacity-50"
          >
            {testStatus === "testing" && <Loader2 className="w-3 h-3 animate-spin" />}
            {testStatus === "ok" && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
            {testStatus === "fail" && <AlertCircle className="w-3 h-3 text-red-400" />}
            {testStatus === "idle" && "Test Connection"}
            {testStatus === "testing" && "Testing..."}
            {testStatus === "ok" && "Connected!"}
            {testStatus === "fail" && "Failed"}
          </button>
          {testError && <span className="text-[10px] text-red-400 font-mono">{testError}</span>}
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl border border-zinc-800/60 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-xs font-bold text-white shadow-[0_0_20px_rgba(168,85,247,0.2)] hover:shadow-[0_0_30px_rgba(168,85,247,0.4)] transition-all"
          >
            {saved ? "✓ Saved!" : "Save Settings"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
