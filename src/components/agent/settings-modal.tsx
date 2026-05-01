"use client";

import { motion } from "framer-motion";
import { X, CheckCircle2, AlertCircle, Loader2, Smartphone, Download, Upload, Sun, Moon, FlaskConical } from "lucide-react";
import { useState, useEffect, useCallback } from "react";

interface Settings {
  apiKey: string;
  model: string;
  provider: "minimax" | "openai" | "anthropic" | "ollama";
  backendUrl: string;
  baseUrl: string;        // Ollama base URL
  theme: "dark" | "light";
}

interface Props { onClose: () => void; }

const PROVIDER_MODELS: Record<string, string[]> = {
  minimax:   ["MiniMax-M2.7", "MiniMax-M2.0"],
  openai:    ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5-20251001"],
  ollama:    ["llama3", "llama3.1", "codellama", "mistral", "mixtral"],
};

const MIN_KEY_LENGTHS: Record<string, number> = {
  minimax:   20,
  openai:    20,
  anthropic: 20,
  ollama:    0,
};

function validateApiKey(provider: string, key: string): string | null {
  if (provider === "ollama") return null;
  if (!key) return null; // optional for minimax if .env is set
  if (key.length < (MIN_KEY_LENGTHS[provider] ?? 20)) {
    return `Key looks too short (${key.length} chars — ${provider} keys are typically longer)`;
  }
  if (provider === "openai" && !key.startsWith("sk-")) {
    return "OpenAI keys usually start with sk-";
  }
  return null;
}

export function SettingsModal({ onClose }: Props) {
  const [form, setForm] = useState<Settings>({
    apiKey: "", model: "MiniMax-M2.7", provider: "minimax",
    backendUrl: "ws://localhost:8001/ws/agent", baseUrl: "http://localhost:11434",
    theme: "dark",
  });
  const [testStatus, setTestStatus]     = useState<"idle"|"testing"|"ok"|"fail">("idle");
  const [testError, setTestError]       = useState("");
  const [testModelStatus, setTestModelStatus] = useState<"idle"|"testing"|"ok"|"fail">("idle");
  const [testModelError, setTestModelError]   = useState("");
  const [testModelLatency, setTestModelLatency] = useState<number|null>(null);
  const [testModelResponse, setTestModelResponse] = useState("");
  const [saved, setSaved]               = useState(false);
  const [keyWarning, setKeyWarning]     = useState<string|null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("agent-browser-settings");
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setForm((f) => ({ ...f, ...parsed }));
      } catch { /* ignore */ }
    }
    // Also respect system theme preference as default for light mode
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    setForm((f) => ({ ...f, theme: prefersDark ? "dark" : "light" }));
  }, []);

  // Validate API key whenever it or provider changes
  useEffect(() => {
    setKeyWarning(validateApiKey(form.provider, form.apiKey));
  }, [form.provider, form.apiKey]);

  const handleSave = useCallback(() => {
    localStorage.setItem("agent-browser-settings", JSON.stringify(form));
    // Apply theme to <html> tag
    document.documentElement.classList.toggle("light", form.theme === "light");
    document.documentElement.classList.toggle("dark", form.theme === "dark");
    setSaved(true);
    setTimeout(() => { setSaved(false); onClose(); }, 800);
  }, [form, onClose]);

  const testConnection = async () => {
    setTestStatus("testing");
    setTestError("");
    const httpUrl = form.backendUrl.replace(/^ws(s)?:\/\//, "http$1://").replace("/ws/agent", "/api/health");
    try {
      const res = await fetch(httpUrl, { signal: AbortSignal.timeout(5000) });
      setTestStatus(res.ok ? "ok" : "fail");
      if (!res.ok) setTestError(`HTTP ${res.status}`);
    } catch (e: unknown) {
      setTestStatus("fail");
      setTestError(e instanceof Error ? e.message : "Connection failed");
    }
  };

  const testModel = async () => {
    setTestModelStatus("testing");
    setTestModelError("");
    setTestModelLatency(null);
    setTestModelResponse("");
    const httpUrl = form.backendUrl.replace(/^ws(s)?:\/\//, "http$1://").replace("/ws/agent", "/api/test-model");
    try {
      const res = await fetch(httpUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: form.provider,
          api_key: form.provider === "ollama" ? undefined : form.apiKey,
          model_name: form.model,
          base_url: form.provider === "ollama" ? form.baseUrl : undefined,
        }),
        signal: AbortSignal.timeout(40_000),
      });
      const data = await res.json();
      if (data.ok) {
        setTestModelStatus("ok");
        setTestModelLatency(data.latency_ms);
        setTestModelResponse(data.response ?? "");
      } else {
        setTestModelStatus("fail");
        setTestModelError(data.error ?? "Unknown error");
      }
    } catch (e: unknown) {
      setTestModelStatus("fail");
      setTestModelError(e instanceof Error ? e.message : "Request failed");
    }
  };

  const exportSettings = () => {
    const blob = new Blob([JSON.stringify(form, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-browser-settings-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importSettings = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const imported = JSON.parse(ev.target?.result as string);
        setForm((f) => ({ ...f, ...imported }));
      } catch {
        setTestError("Invalid settings file");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  };

  const isOllama = form.provider === "ollama";
  const isMiniMax = form.provider === "minimax";

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.18 }}
      className="fixed inset-0 z-[100] bg-black/70 flex items-end sm:items-center justify-center p-0 sm:p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 20, scale: 0.98 }}
        transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
        className="glass-overlay rounded-t-3xl sm:rounded-2xl w-full sm:max-w-[500px] p-5 sm:p-6 space-y-4 max-h-[90vh] overflow-y-auto"
      >
        {/* Drag handle (mobile) */}
        <div className="flex justify-center mb-1 sm:hidden">
          <div className="w-10 h-1 rounded-full bg-zinc-700" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-zinc-200 tracking-wide">Agent Settings</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.06] transition-all"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Theme */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] text-zinc-400 font-semibold uppercase tracking-wider">Theme</p>
            <p className="text-[10px] text-zinc-600 mt-0.5">Toggle dark / light mode</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setForm((f) => ({ ...f, theme: "dark" }))}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-medium border transition-all ${
                form.theme === "dark"
                  ? "bg-violet-600/18 border-violet-500/45 text-violet-300"
                  : "bg-black/40 border-zinc-800/60 text-zinc-600 hover:text-zinc-300"
              }`}
            >
              <Moon className="w-3.5 h-3.5" /> Dark
            </button>
            <button
              onClick={() => setForm((f) => ({ ...f, theme: "light" }))}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-[11px] font-medium border transition-all ${
                form.theme === "light"
                  ? "bg-amber-500/18 border-amber-500/45 text-amber-300"
                  : "bg-black/40 border-zinc-800/60 text-zinc-600 hover:text-zinc-300"
              }`}
            >
              <Sun className="w-3.5 h-3.5" /> Light
            </button>
          </div>
        </div>

        {/* Provider */}
        <div>
          <label className="text-[11px] text-zinc-600 font-semibold uppercase tracking-wider mb-2 block">Provider</label>
          <div className="grid grid-cols-4 gap-1.5">
            {(["minimax", "openai", "anthropic", "ollama"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setForm((f) => ({ ...f, provider: p, model: PROVIDER_MODELS[p][0] }))}
                className={`py-2 px-1 rounded-xl text-[10px] font-bold uppercase tracking-wide border transition-all ${
                  form.provider === p
                    ? "bg-violet-600/18 border-violet-500/45 text-violet-300"
                    : "bg-black/40 border-zinc-800/60 text-zinc-600 hover:text-zinc-300 hover:border-zinc-700"
                }`}
              >
                {p === "anthropic" ? "Claude" : p === "minimax" ? "Mini" : p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Model */}
        <div>
          <label className="text-[11px] text-zinc-600 font-semibold uppercase tracking-wider mb-2 block">Model</label>
          <select
            value={form.model}
            onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
            className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-3 text-xs text-zinc-200 font-mono focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
          >
            {PROVIDER_MODELS[form.provider].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        {/* API Key */}
        {!isOllama && (
          <div>
            <label className="text-[11px] text-zinc-600 font-semibold uppercase tracking-wider mb-2 block">
              API Key
              {isMiniMax && (
                <span className="ml-1.5 text-zinc-700 normal-case tracking-normal">(optional if set in .env)</span>
              )}
            </label>
            <input
              type="password"
              value={form.apiKey}
              onChange={(e) => setForm((f) => ({ ...f, apiKey: e.target.value }))}
              placeholder="sk-... / api key"
              className={`w-full bg-black/60 border rounded-xl px-4 py-3 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:ring-2 transition-all ${
                keyWarning ? "border-amber-500/50 focus:ring-amber-500/40" : "border-zinc-800/60 focus:ring-violet-500/40 focus:border-violet-500/50"
              }`}
            />
            {keyWarning && (
              <p className="mt-1.5 text-[10px] text-amber-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> {keyWarning}
              </p>
            )}
          </div>
        )}

        {/* Ollama Base URL */}
        {isOllama && (
          <div>
            <label className="text-[11px] text-zinc-600 font-semibold uppercase tracking-wider mb-2 block">Base URL</label>
            <input
              type="text"
              value={form.baseUrl}
              onChange={(e) => setForm((f) => ({ ...f, baseUrl: e.target.value }))}
              placeholder="http://localhost:11434"
              className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-3 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
            />
          </div>
        )}

        {/* Backend URL */}
        <div>
          <label className="text-[11px] text-zinc-600 font-semibold uppercase tracking-wider mb-2 block">
            Backend WebSocket URL
          </label>
          <input
            type="text"
            value={form.backendUrl}
            onChange={(e) => setForm((f) => ({ ...f, backendUrl: e.target.value }))}
            placeholder="ws://localhost:8001/ws/agent"
            className="w-full bg-black/60 border border-zinc-800/60 rounded-xl px-4 py-3 text-xs text-zinc-200 font-mono placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all"
          />
          {/* Phone access hint */}
          <div className="flex items-start gap-2 mt-2 p-2.5 rounded-xl bg-violet-950/20 border border-violet-800/20">
            <Smartphone className="w-3.5 h-3.5 text-violet-400 flex-shrink-0 mt-0.5" />
            <p className="text-[10px] text-violet-400/70 leading-relaxed">
              <strong className="text-violet-400">Phone access:</strong> Replace <code className="font-mono text-violet-300">localhost</code> with your computer&apos;s LAN IP (e.g. <code className="font-mono text-violet-300">192.168.x.x</code>) when connecting from another device on the same network.
            </p>
          </div>
        </div>

        {/* Test Connection */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={testConnection}
            disabled={testStatus === "testing"}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-black/40 border border-zinc-800/60 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-all disabled:opacity-50 active:scale-95"
          >
            {testStatus === "testing" && <Loader2 className="w-3 h-3 animate-spin" />}
            {testStatus === "ok" && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
            {testStatus === "fail" && <AlertCircle className="w-3 h-3 text-red-400" />}
            {testStatus === "idle" && "Test Connection"}
            {testStatus === "testing" && "Testing…"}
            {testStatus === "ok" && "Backend online"}
            {testStatus === "fail" && "Failed"}
          </button>
          {testError && (
            <span className="text-[10px] text-red-400 font-mono truncate">{testError}</span>
          )}
        </div>

        {/* Test Model */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={testModel}
              disabled={testModelStatus === "testing"}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-black/40 border border-zinc-800/60 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-all disabled:opacity-50 active:scale-95"
            >
              {testModelStatus === "testing" && <Loader2 className="w-3 h-3 animate-spin" />}
              {testModelStatus === "ok" && <CheckCircle2 className="w-3 h-3 text-emerald-400" />}
              {testModelStatus === "fail" && <AlertCircle className="w-3 h-3 text-red-400" />}
              {testModelStatus === "idle" && <FlaskConical className="w-3 h-3" />}
              {testModelStatus === "testing" && "Testing model…"}
              {testModelStatus === "ok" && "Model works"}
              {testModelStatus === "fail" && "Model failed"}
              {(testModelStatus === "idle") && "Test Model"}
            </button>
            {testModelLatency !== null && (
              <span className="text-[10px] text-emerald-400 font-mono">{testModelLatency}ms</span>
            )}
            {testModelResponse && (
              <span className="text-[10px] text-zinc-400 font-mono truncate">
                → &ldquo;{testModelResponse}&rdquo;
              </span>
            )}
          </div>
          {testModelError && (
            <p className="text-[10px] text-red-400 font-mono">{testModelError}</p>
          )}
        </div>

        {/* Import / Export */}
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={exportSettings}
            className="flex items-center gap-2 px-3 py-2 rounded-xl bg-black/40 border border-zinc-800/60 text-[10px] text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all"
          >
            <Download className="w-3 h-3" /> Export JSON
          </button>
          <label className="flex items-center gap-2 px-3 py-2 rounded-xl bg-black/40 border border-zinc-800/60 text-[10px] text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all cursor-pointer">
            <Upload className="w-3 h-3" /> Import JSON
            <input type="file" accept=".json" onChange={importSettings} className="hidden" />
          </label>
        </div>

        {/* Actions */}
        <div className="flex gap-2 pt-1">
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl border border-zinc-800/60 text-xs text-zinc-500 hover:text-zinc-300 hover:border-zinc-700 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className={`flex-1 py-3 rounded-xl text-xs font-bold text-white transition-all ${
              saved
                ? "bg-emerald-600/80 border border-emerald-500/40"
                : "bg-gradient-to-r from-violet-600 to-fuchsia-600 shadow-[0_0_20px_rgba(168,85,247,0.2)] hover:shadow-[0_0_30px_rgba(168,85,247,0.35)] active:scale-[0.98]"
            }`}
          >
            {saved ? "✓ Saved!" : "Save Settings"}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
