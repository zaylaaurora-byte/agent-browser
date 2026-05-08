"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Pause, Play, Undo2, Save, Download,
  Clock, CheckCircle2, AlertCircle, RotateCcw,
  Globe, MousePointer, Type, ScrollText, Timer,
  Camera, Brain, Rocket, ArrowLeft, Activity,
  HardDrive, Loader2, Eye, Settings,
} from "lucide-react";
import type { Step, Mode } from "@/components/agent/types";

// ─── Types ────────────────────────────────────────────────────────────────────
type AgentStatus = "idle" | "running" | "paused" | "completed" | "failed";

interface SessionSummary {
  id: string;
  task: string;
  url: string;
  mode: string;
  status: string;
  steps_count: number;
  failed_count: number;
  created_at: string;
  completed_at: string | null;
}

interface SupervisorState {
  agentStatus: AgentStatus;
  isPaused: boolean;
  currentSessionId: string | null;
  sessionName: string;
  sessions: SessionSummary[];
  steps: Step[];
  completedSteps: number;
  failedSteps: number;
  totalDuration: number | null;
  latestThinking: string | null;
  startTime: number | null;
  // Supervisor-specific
  supervisorUrl: string;
  supervisorTask: string;
  supervisorMode: Mode;
  currentScreenshot: string | null;
  screenshotHistory: string[];
}

// ─── Constants ────────────────────────────────────────────────────────────────
const ACTION_ICON_MAP: Record<string, React.ElementType> = {
  navigate:   Globe,
  click:      MousePointer,
  type:       Type,
  scroll:     ScrollText,
  wait:       Timer,
  screenshot: Camera,
  done:       CheckCircle2,
  error:      AlertCircle,
  check:      CheckCircle2,
  submit:     Rocket,
  thinking:   Brain,
};

const ACTION_COLOR_MAP: Record<string, string> = {
  navigate:   "text-sky-400",
  click:      "text-amber-400",
  type:       "text-emerald-400",
  scroll:     "text-zinc-500",
  wait:       "text-zinc-500",
  screenshot: "text-pink-400",
  done:       "text-emerald-400",
  error:      "text-red-400",
  check:      "text-cyan-400",
  submit:     "text-violet-400",
  thinking:   "text-violet-400",
};

const STATUS_CONFIG: Record<AgentStatus, { label: string; color: string; dot: string }> = {
  idle:      { label: "Idle",      color: "text-zinc-500", dot: "bg-zinc-600" },
  running:   { label: "Running",   color: "text-cyan-400",  dot: "bg-cyan-400 animate-pulse" },
  paused:    { label: "Paused",    color: "text-amber-400", dot: "bg-amber-400" },
  completed: { label: "Completed", color: "text-emerald-400", dot: "bg-emerald-400" },
  failed:    { label: "Failed",    color: "text-red-400",   dot: "bg-red-400" },
};

const MODE_META: Record<Mode, { label: string; color: string; border: string }> = {
  fast:    { label: "Fast",    color: "text-amber-400",   border: "border-amber-400/30"   },
  stealth: { label: "Stealth", color: "text-violet-400",  border: "border-violet-400/30" },
  deep:    { label: "Deep",    color: "text-sky-400",     border: "border-sky-400/30"     },
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatTimestamp(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}

// ─── Step Row Component ───────────────────────────────────────────────────────
function StepRow({ step }: { step: Step }) {
  const Icon = ACTION_ICON_MAP[step.action] || MousePointer;
  const color = ACTION_COLOR_MAP[step.action] || "text-zinc-500";

  return (
    <div className="flex items-start gap-3 p-3 rounded-xl border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] transition-colors">
      <div className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5">
        <Icon className={`w-3 h-3 ${color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-[11px] font-semibold text-zinc-200 uppercase tracking-wide">{step.action}</span>
          {step.argument && (
            <span className="text-[11px] text-zinc-400 font-mono truncate">{step.argument}</span>
          )}
        </div>
        {step.observation && (
          <p className="text-[11px] text-zinc-300 font-mono mt-1 line-clamp-2">{step.observation}</p>
        )}
      </div>
      <span className="text-[10px] text-zinc-500 font-mono flex-shrink-0">
        {formatTimestamp(step.timestamp)}
      </span>
    </div>
  );
}

// ─── Main Supervisor Page ────────────────────────────────────────────────────
export default function SupervisorPage() {
  const [state, setState] = useState<SupervisorState>({
    agentStatus: "idle",
    isPaused: false,
    currentSessionId: null,
    sessionName: "",
    sessions: [],
    steps: [],
    completedSteps: 0,
    failedSteps: 0,
    totalDuration: null,
    latestThinking: null,
    startTime: null,
    supervisorUrl: "https://httpbin.org/forms/post",
    supervisorTask: "Go to the page and describe what you see — identify any forms, buttons, and interactive elements.",
    supervisorMode: "deep",
    currentScreenshot: null,
    screenshotHistory: [],
  });

  const [saveName, setSaveName]       = useState("");
  const [loadSessionId, setLoadSessionId] = useState("");
  const [exportLoading, setExportLoading] = useState(false);
  const [undoLoading, setUndoLoading]   = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [wsStatus, setWsStatus]       = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKey, setApiKey]           = useState("");
  const [modelName, setModelName]     = useState("MiniMax-M2.7");

  const wsRef      = useRef<WebSocket | null>(null);
  const feedRef    = useRef<HTMLDivElement>(null);
  const startRef   = useRef<number | null>(null);
  const timerRef   = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Backend URL resolver ───────────────────────────────────────────────────
  const getBackendUrl = useCallback((): string => {
    // Try localStorage settings first
    try {
      const cfg = JSON.parse(localStorage.getItem("agent-browser-settings") || "{}");
      if (cfg.backendUrl) return cfg.backendUrl.replace(/^ws:\/\//, "ws://").replace(/^https?:\/\//, "ws://").replace(/\/$/, "") + "/ws/agent";
    } catch { /* ignore */ }
    return "ws://localhost:8000/ws/agent";
  }, []);

  // ─── Fetch session list ─────────────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
    try {
      const res = await fetch(`${backendUrl}/api/sessions?limit=50`);
      const data = await res.json();
      setState((s) => ({ ...s, sessions: data.sessions || [] }));
    } catch { /* ignore */ }
  }, [getBackendUrl]);

  // ─── Fetch agent status ─────────────────────────────────────────────────────
  const fetchAgentStatus = useCallback(async () => {
    const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
    try {
      const res = await fetch(`${backendUrl}/api/supervisor/status`);
      const data = await res.json();
      setState((s) => ({
        ...s,
        isPaused: data.paused ?? false,
        currentSessionId: data.session ?? s.currentSessionId,
        agentStatus: data.paused ? "paused" : s.agentStatus === "paused" ? "paused" : s.agentStatus,
      }));
    } catch { /* ignore */ }
  }, [getBackendUrl]);

  // ─── Disconnect helper ──────────────────────────────────────────────────────
  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setWsStatus("disconnected");
  }, []);

  // ─── WebSocket connection ───────────────────────────────────────────────────
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = getBackendUrl();
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      setWsStatus("connected");
    };

    ws.onmessage = (e) => {
      try {
        const d: Step = JSON.parse(e.data);
        d.timestamp = Date.now();

        // Sync pause/resume state from echoed control messages
        if (d.ctrl === "pause") {
          setState((s) => ({ ...s, isPaused: true, agentStatus: "paused" }));
          stopTimer();
          return;
        }
        if (d.ctrl === "resume") {
          setState((s) => ({ ...s, isPaused: false, agentStatus: "running" }));
          startTimer();
          return;
        }

        if (d.action === "error" || d.status === "failed") {
          setState((s) => {
            const newSteps = [...s.steps.filter((x) => !(x.step === d.step && x.status === "thinking")), d];
            const failedSteps = newSteps.filter((x) => x.status === "retrying" || x.status === "failed").length;
            return { ...s, steps: newSteps, agentStatus: "failed", failedSteps, isPaused: false };
          });
          stopTimer();
          return;
        }

        if (d.action === "done") {
          setState((s) => {
            const newSteps = [...s.steps.filter((x) => !(x.step === d.step && s.steps.some(p => p.step === x.step && p.status === "thinking"))), d];
            const completedSteps = newSteps.filter((x) => x.status === "completed" || x.action === "done").length;
            return {
              ...s, steps: newSteps, agentStatus: "completed", completedSteps,
              currentScreenshot: d.screenshot ?? s.currentScreenshot,
            };
          });
          stopTimer();
          return;
        }

        if (d.status === "thinking") {
          setState((s) => {
            const without = s.steps.filter((x) => !(x.step === d.step && x.status === "thinking"));
            const newSteps = [...without, d];
            return {
              ...s,
              steps: newSteps,
              latestThinking: d.thinking ?? d.ai_reasoning ?? null,
              currentScreenshot: d.screenshot ?? s.currentScreenshot,
            };
          });
        } else if (d.status === "completed" || d.status === "snapshot") {
          setState((s) => {
            const without = s.steps.filter((x) => !(x.step === d.step && x.status === "thinking"));
            const newSteps = [...without, d];
            const completedSteps = newSteps.filter((x) => x.status === "completed" || x.action === "done").length;
            const newHistory = d.screenshot
              ? [...s.screenshotHistory, d.screenshot].slice(-20)
              : s.screenshotHistory;
            return {
              ...s,
              steps: newSteps,
              completedSteps,
              latestThinking: null,
              currentScreenshot: d.screenshot ?? s.currentScreenshot,
              screenshotHistory: newHistory,
            };
          });
        }
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      if (state.agentStatus === "running") {
        setTimeout(connectWs, 2000);
      }
    };

    ws.onerror = () => { ws.close(); };
  }, [getBackendUrl, state.agentStatus]);

  // ─── Timer ─────────────────────────────────────────────────────────────────
  const stopTimer = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  }, []);

  const startTimer = useCallback(() => {
    stopTimer();
    startRef.current = Date.now();
    timerRef.current = setInterval(() => {
      if (startRef.current) {
        setState((s) => ({ ...s, totalDuration: Date.now() - startRef.current! }));
      }
    }, 1000);
  }, [stopTimer]);

  // ─── Execute task via HTTP (non-streaming, polling-based) ─────────────────────
  const executeTask = useCallback(() => {
    // Read form values directly from DOM to avoid React synthetic event issues
    // (browser automation tools can't fire React onChange events)
    const urlInput = document.querySelector<HTMLInputElement>('input[type="url"]');
    const taskInput = document.querySelector<HTMLTextAreaElement>('textarea.resize-none');
    const taskUrl = urlInput?.value?.trim() || state.supervisorUrl;
    const taskDesc = taskInput?.value?.trim() || state.supervisorTask;

    if (!taskUrl || !taskDesc) {
      console.warn("[Supervisor] URL or Task is empty — cannot execute");
      return;
    }

    disconnect();
    setState((s) => ({
      ...s,
      agentStatus: "running",
      isPaused: false,
      steps: [],
      completedSteps: 0,
      failedSteps: 0,
      totalDuration: null,
      latestThinking: null,
      currentScreenshot: null,
      screenshotHistory: [],
    }));

    const baseUrl = getBackendUrl().replace("ws://", "http://").replace("wss://", "https://").replace("/ws/agent", "");
    const apiBase = baseUrl || "http://localhost:8000";
    setWsStatus("connecting");

    const startTime = Date.now();
    const timer = setInterval(() => {
      setState((s) => ({ ...s, totalDuration: Date.now() - startTime }));
    }, 1000);

    fetch(`${apiBase}/api/execute-async`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: taskUrl,
        task: taskDesc,
        mode: state.supervisorMode,
        api_key: apiKey,
        model_name: modelName,
      }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(({ session_id }) => {
        setWsStatus("connected");

        function pollResult(sid: string) {
          fetch(`${apiBase}/api/execute-async/${sid}`)
            .then((r) => r.json())
            .then((result) => {
              if (result.status === "started" || result.status === "not_found") {
                setTimeout(() => pollResult(sid), 1000);
                return;
              }

              clearInterval(timer);
              setWsStatus("disconnected");

              if (result.status === "completed") {
                const items: Step[] = result.items || [];
                const completedSteps = items.filter((x) => x.status === "completed" || x.action === "done").length;
                const failedSteps = items.filter((x) => x.status === "failed" || x.status === "retrying").length;
                items.forEach((d) => { d.timestamp = Date.now(); });
                setState((s) => ({
                  ...s,
                  agentStatus: "completed",
                  steps: items,
                  completedSteps,
                  failedSteps,
                  latestThinking: null,
                  currentScreenshot: items.at(-1)?.screenshot ?? s.currentScreenshot,
                  totalDuration: Date.now() - startTime,
                }));
              } else {
                setState((s) => ({
                  ...s,
                  agentStatus: "failed",
                  totalDuration: Date.now() - startTime,
                }));
              }
            })
            .catch(() => {
              clearInterval(timer);
              setWsStatus("disconnected");
              setState((s) => ({ ...s, agentStatus: "failed" }));
            });
        }

        pollResult(session_id);
      })
      .catch(() => {
        clearInterval(timer);
        setState((s) => ({ ...s, agentStatus: "failed" }));
        setWsStatus("disconnected");
      });
  }, [state.supervisorMode, apiKey, modelName]); // eslint-disable-line

  // ─── Stop ──────────────────────────────────────────────────────────────────
  const stopAgent = useCallback(() => {
    disconnect();
    stopTimer();
    setState((s) => ({ ...s, agentStatus: "idle", isPaused: false }));
  }, [disconnect, stopTimer]);

  // ─── Pause / Resume ─────────────────────────────────────────────────────────
  const pauseAgent = useCallback(() => {
    // Prefer WebSocket when connected
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "control", action: "pause" }));
    } else {
      // Fallback to REST API
      const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
      fetch(`${backendUrl}/api/supervisor/pause`, { method: "POST" }).catch(() => {});
    }
    setState((s) => ({ ...s, isPaused: true, agentStatus: "paused" }));
    stopTimer();
  }, [getBackendUrl, stopTimer]);

  const resumeAgent = useCallback(() => {
    // Prefer WebSocket when connected
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "control", action: "resume" }));
    } else {
      // Fallback to REST API
      const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
      fetch(`${backendUrl}/api/supervisor/resume`, { method: "POST" }).catch(() => {});
    }
    setState((s) => ({ ...s, isPaused: false, agentStatus: "running" }));
    startTimer();
  }, [getBackendUrl, startTimer]);

  // ─── Save session ───────────────────────────────────────────────────────────
  const saveSession = useCallback(async () => {
    if (!saveName.trim()) return;
    const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
    try {
      await fetch(`${backendUrl}/api/persistent-sessions/${encodeURIComponent(saveName)}/save`, { method: "POST" });
      setSaveName("");
      fetchSessions();
    } catch (e) { console.error("save failed", e); }
  }, [saveName, getBackendUrl, fetchSessions]);

  // ─── Load session ───────────────────────────────────────────────────────────
  const loadSession = useCallback(async () => {
    if (!loadSessionId) return;
    const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
    try {
      const res = await fetch(`${backendUrl}/api/persistent-sessions/${encodeURIComponent(loadSessionId)}/load`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) alert(data.error || "Load failed");
    } catch (e) { console.error("load failed", e); }
  }, [loadSessionId, getBackendUrl]);

  // ─── Undo last action ──────────────────────────────────────────────────────
  const undoLastAction = useCallback(async () => {
    const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
    setUndoLoading(true);
    try {
      const res = await fetch(`${backendUrl}/api/supervisor/undo`, { method: "POST" });
      if (res.ok) {
        setState((s) => ({ ...s, steps: s.steps.slice(0, -1) }));
      }
    } catch (e) { console.error("undo failed", e); }
    setUndoLoading(false);
  }, [getBackendUrl]);

  // ─── Export log ────────────────────────────────────────────────────────────
  const exportLog = useCallback(async () => {
    setExportLoading(true);
    try {
      const log = state.steps.map((s) =>
        `[${new Date(s.timestamp).toISOString()}] ${s.action} — ${s.argument || s.observation || ""}`
      ).join("\n");
      const blob = new Blob([log], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `agent-log-${Date.now()}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { console.error("export failed", e); }
    setExportLoading(false);
  }, [state.steps]);

  // ─── Load session steps ─────────────────────────────────────────────────────
  const loadSessionSteps = useCallback(async (sessionId: string) => {
    const backendUrl = getBackendUrl().replace("/ws/agent", "").replace("ws://", "http://");
    try {
      const res = await fetch(`${backendUrl}/api/sessions/${sessionId}`);
      const data = await res.json();
      if (data.steps) {
        const steps = data.steps.map((s: Step) => ({ ...s, timestamp: new Date(s.timestamp || Date.now()).getTime() }));
        const completedSteps = steps.filter((s: Step) => s.status === "completed" || s.action === "done").length;
        const failedSteps = steps.filter((s: Step) => s.status === "retrying" || s.status === "failed").length;
        setState((sv) => ({
          ...sv,
          steps,
          completedSteps,
          failedSteps,
          agentStatus: data.status as AgentStatus,
          currentSessionId: sessionId,
        }));
      }
    } catch (e) { console.error("load session failed", e); }
  }, [getBackendUrl]);

  // ─── Init ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchSessions();
    fetchAgentStatus();
    connectWs();
    // Load settings from localStorage
    try {
      const cfg = JSON.parse(localStorage.getItem("agent-browser-settings") || "{}");
      if (cfg.apiKey) setApiKey(cfg.apiKey);
      if (cfg.model) setModelName(cfg.model);
    } catch { /* ignore */ }
    return () => {
      wsRef.current?.close();
      stopTimer();
    };
  }, [fetchSessions, fetchAgentStatus, connectWs, stopTimer]);

  // Scroll feed
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [state.steps]);

  const last10      = state.steps.slice(-10);
  const statusCfg  = STATUS_CONFIG[state.agentStatus];
  const isRunning  = state.agentStatus === "running";
  const canExecute = !isRunning && !!state.supervisorUrl && !!state.supervisorTask;

  return (
    <div className="max-w-screen-2xl mx-auto w-full px-4 sm:px-6 lg:px-6 pb-16">

      {/* ── Header ── */}
      <div className="flex items-center gap-4 pt-8 pb-6">
        <Link href="/" className="flex items-center gap-2 text-zinc-500 hover:text-zinc-200 transition-colors text-sm">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <Activity className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <h1 className="text-[15px] font-black tracking-widest uppercase text-zinc-200">Supervisor</h1>
            <p className="text-[10px] text-zinc-700 tracking-wider">Human-in-the-loop browser control</p>
          </div>
        </div>
        {/* WS status badge */}
        <div className="ml-auto flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${wsStatus === "connected" ? "bg-emerald-400" : wsStatus === "connecting" ? "bg-amber-400 animate-pulse" : "bg-zinc-700"}`} />
          <span className="text-[10px] text-zinc-600 font-mono uppercase">{wsStatus}</span>
        </div>
      </div>

      {/* ── Task Input Card ── */}
      <div className="glass-card rounded-2xl overflow-hidden mb-5">
        <div className="flex items-center gap-2 p-3 sm:p-4 pb-0">
          <div className="relative flex-1 min-w-0">
            <Globe className="absolute left-3.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-600 pointer-events-none" />
            <input
              type="url"
              inputMode="url"
              value={state.supervisorUrl}
              onChange={(e) => setState((s) => ({ ...s, supervisorUrl: e.target.value }))}
              disabled={isRunning}
              placeholder="https://target-url.com"
              className="input-field w-full pl-9 pr-4 py-2.5 text-sm font-mono min-h-[44px]"
            />
          </div>
          <button
            onClick={() => setSettingsOpen((v) => !v)}
            className="flex-shrink-0 w-11 h-11 rounded-xl glass-surface flex items-center justify-center text-zinc-500 hover:text-zinc-200 transition-all active:scale-95"
            title="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>

        {/* Settings panel */}
        <AnimatePresence>
          {settingsOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              <div className="px-3 sm:px-4 pt-2 pb-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] text-zinc-700 uppercase tracking-widest mb-1 block">Model</label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    disabled={isRunning}
                    placeholder="MiniMax-M2.7"
                    className="input-field w-full px-3 py-2 text-xs font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-zinc-700 uppercase tracking-widest mb-1 block">API Key (optional)</label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    disabled={isRunning}
                    placeholder="sk-... (leave empty for default)"
                    className="input-field w-full px-3 py-2 text-xs font-mono"
                  />
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="px-3 sm:px-4 pt-2.5">
          <textarea
            value={state.supervisorTask}
            onChange={(e) => setState((s) => ({ ...s, supervisorTask: e.target.value }))}
            disabled={isRunning}
            rows={2}
            placeholder="Describe what the agent should do..."
            className="input-field w-full px-4 py-3 text-sm resize-none leading-relaxed min-h-[76px]"
          />
        </div>

        {/* Mode + Execute */}
        <div className="flex items-center gap-2 px-3 sm:px-4 py-3 flex-wrap">
          {/* Mode selector */}
          <div className="flex items-center gap-0.5 rounded-xl glass-surface p-1 flex-shrink-0">
            {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
              const meta = MODE_META[m];
              return (
                <button
                  key={m}
                  onClick={() => setState((s) => ({ ...s, supervisorMode: m }))}
                  disabled={isRunning}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[11px] font-bold tracking-wider transition-all min-h-[36px] disabled:pointer-events-none ${
                    state.supervisorMode === m
                      ? `${meta.color} border ${meta.border} bg-white/[0.07]`
                      : "text-zinc-600 hover:text-zinc-300 border border-transparent"
                  }`}
                >
                  {m === "fast" ? <Zap className="w-3 h-3" /> : m === "stealth" ? <Eye className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
                  {meta.label}
                </button>
              );
            })}
          </div>

          {/* Execute / Stop button */}
          <button
            onClick={isRunning ? stopAgent : executeTask}
            disabled={!isRunning && !canExecute}
            className={`flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-bold text-sm tracking-wide transition-all min-h-[44px] flex-1 sm:flex-none sm:min-w-[130px] ${
              isRunning
                ? "bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500/18 active:scale-[0.97]"
                : "btn-execute"
            }`}
          >
            {isRunning ? (
              <><Loader2 className="w-4 h-4 animate-spin" /><span>Stop · {state.completedSteps}</span></>
            ) : (
              <><Play className="w-4 h-4 fill-current" /><span>Execute</span></>
            )}
          </button>
        </div>
      </div>

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 lg:gap-5">

        {/* ── Left: Live Feed + Action History ── */}
        <div className="xl:col-span-2 space-y-4">
          {/* Live Feed */}
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="panel-header">
              <Camera className="w-3.5 h-3.5 text-cyan-400" />
              <span className="panel-label">Live Feed</span>
              {isRunning && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />}
              <div className="ml-auto flex items-center gap-3 text-[10px] font-mono">
                {state.completedSteps > 0 && <span className="text-emerald-400">{state.completedSteps} ✓</span>}
                {state.failedSteps > 0 && <span className="text-red-400">{state.failedSteps} ✗</span>}
              </div>
            </div>
            <div ref={feedRef} className="max-h-52 overflow-y-auto p-2 space-y-0.5">
              {last10.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 gap-2">
                  <p className="text-[11px] text-zinc-700 uppercase tracking-widest">No activity</p>
                </div>
              ) : (
                last10.map((step, i) => <StepRow key={`${step.step}-${i}`} step={step} />)
              )}
            </div>
          </div>

          {/* Action History Timeline */}
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="panel-header">
              <Clock className="w-3.5 h-3.5 text-violet-400" />
              <span className="panel-label">Action History</span>
              <span className="ml-auto text-[11px] text-zinc-400 font-mono">{state.steps.length} total</span>
            </div>
            <div className="max-h-80 overflow-y-auto p-3 space-y-1">
              {state.steps.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-24 gap-2">
                  <p className="text-[11px] text-zinc-700 uppercase tracking-widest">No actions yet</p>
                </div>
              ) : (
                state.steps.map((step, i) => (
                  <div key={`${step.step}-${i}`} className="flex items-start gap-3">
                    <div className="flex flex-col items-center flex-shrink-0">
                      <div className={`w-2 h-2 rounded-full mt-1.5 ${
                        step.status === "failed" || step.action === "error" ? "bg-red-400"
                          : step.action === "done" ? "bg-emerald-400"
                          : "bg-zinc-700"
                      }`} />
                      {i < state.steps.length - 1 && <div className="w-px flex-1 bg-zinc-800/60 mt-1" style={{ minHeight: 20 }} />}
                    </div>
                    <div className="flex-1 min-w-0 pb-3">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[11px] font-semibold text-zinc-200 uppercase">{step.action}</span>
                        {step.argument && <span className="text-[11px] text-zinc-400 font-mono truncate">{step.argument}</span>}
                      </div>
                      {step.observation && <p className="text-[11px] text-zinc-300 font-mono mt-1 line-clamp-2">{step.observation}</p>}
                      {step.error && <p className="text-[9px] text-red-400 font-mono mt-0.5">{step.error}</p>}
                    </div>
                    <span className="text-[10px] text-zinc-500 font-mono flex-shrink-0">{formatTimestamp(step.timestamp)}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ── Right: Status + Controls + Session ── */}
        <div className="space-y-4">
          {/* Agent Status Card */}
          <div className="glass-card rounded-2xl p-4">
            <div className="panel-header mb-4">
              <HardDrive className="w-3.5 h-3.5 text-violet-400" />
              <span className="panel-label">Agent Status</span>
            </div>
            <div className="flex items-center gap-2 mb-4">
              <span className={`w-2.5 h-2.5 rounded-full ${statusCfg.dot}`} />
              <span className={`text-sm font-bold ${statusCfg.color}`}>{statusCfg.label}</span>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-zinc-900/60 rounded-lg p-2.5">
                <p className="text-[9px] text-zinc-700 uppercase tracking-widest mb-1">Completed</p>
                <p className="text-lg font-bold text-emerald-400">{state.completedSteps}</p>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2.5">
                <p className="text-[9px] text-zinc-700 uppercase tracking-widest mb-1">Failed</p>
                <p className="text-lg font-bold text-red-400">{state.failedSteps}</p>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2.5 col-span-2">
                <p className="text-[9px] text-zinc-700 uppercase tracking-widest mb-1">Duration</p>
                <p className="text-lg font-bold text-zinc-300">{formatDuration(state.totalDuration)}</p>
              </div>
            </div>
            {/* Pause / Resume */}
            <div className="flex gap-2">
              {!state.isPaused && isRunning ? (
                <button
                  onClick={pauseAgent}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold hover:bg-amber-500/20 transition-colors"
                >
                  <Pause className="w-3.5 h-3.5" /> Pause
                </button>
              ) : state.isPaused ? (
                <button
                  onClick={resumeAgent}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-bold hover:bg-cyan-500/20 transition-colors"
                >
                  <Play className="w-3.5 h-3.5" /> Resume
                </button>
              ) : (
                <button
                  disabled
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-zinc-900/60 border border-zinc-800/60 text-zinc-700 text-xs font-bold cursor-not-allowed"
                >
                  <Play className="w-3.5 h-3.5" /> Resume
                </button>
              )}
            </div>
          </div>

          {/* Session Management */}
          <div className="glass-card rounded-2xl p-4">
            <div className="panel-header mb-4">
              <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
              <span className="panel-label">Session</span>
              {state.currentSessionId && (
                <span className="ml-auto text-[9px] text-zinc-700 font-mono truncate max-w-[120px]">
                  {state.currentSessionId.slice(0, 16)}…
                </span>
              )}
            </div>
            {/* Save */}
            <div className="mb-3">
              <p className="text-[9px] text-zinc-700 uppercase tracking-widest mb-1.5">Save Current</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="session-name"
                  className="flex-1 bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 placeholder:text-zinc-800 focus:outline-none focus:border-violet-500/40 font-mono"
                  onKeyDown={(e) => e.key === "Enter" && saveSession()}
                />
                <button
                  onClick={saveSession}
                  disabled={!saveName.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-500/10 border border-violet-500/30 text-violet-400 text-xs font-bold hover:bg-violet-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <Save className="w-3 h-3" /> Save
                </button>
              </div>
            </div>
            {/* Load */}
            <div>
              <p className="text-[9px] text-zinc-700 uppercase tracking-widest mb-1.5">Load Session</p>
              <div className="flex gap-2">
                <select
                  value={loadSessionId}
                  onChange={(e) => setLoadSessionId(e.target.value)}
                  className="flex-1 bg-zinc-900/60 border border-zinc-800/60 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-violet-500/40 font-mono appearance-none cursor-pointer"
                >
                  <option value="">— select session —</option>
                  {state.sessions.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.task.slice(0, 30)} [{s.status}]
                    </option>
                  ))}
                </select>
                <button
                  onClick={loadSession}
                  disabled={!loadSessionId}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-bold hover:bg-cyan-500/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Load
                </button>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="glass-card rounded-2xl p-4">
            <div className="panel-header mb-4">
              <Rocket className="w-3.5 h-3.5 text-amber-400" />
              <span className="panel-label">Actions</span>
            </div>
            <div className="space-y-2">
              <button
                onClick={undoLastAction}
                disabled={state.steps.length === 0 || undoLoading}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800/60 text-zinc-400 text-xs font-bold hover:bg-zinc-800/60 hover:text-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Undo2 className="w-3.5 h-3.5" /> Undo Last Action
              </button>
              <button
                onClick={exportLog}
                disabled={state.steps.length === 0 || exportLoading}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800/60 text-zinc-400 text-xs font-bold hover:bg-zinc-800/60 hover:text-zinc-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Export Log
              </button>
              <button
                onClick={fetchSessions}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl bg-zinc-900/60 border border-zinc-800/60 text-zinc-500 text-xs font-bold hover:bg-zinc-800/60 hover:text-zinc-300 transition-colors"
              >
                <RotateCcw className="w-3.5 h-3.5" /> Refresh Sessions
              </button>
            </div>
          </div>

          {/* Latest Thinking */}
          {state.latestThinking && (
            <div className="glass-card rounded-2xl p-4">
              <div className="panel-header mb-3">
                <Brain className="w-3.5 h-3.5 text-violet-400" />
                <span className="panel-label">Thinking</span>
              </div>
              <p className="text-[10px] text-zinc-400 font-mono leading-relaxed line-clamp-4">
                {state.latestThinking}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Lightbox ── */}
      <AnimatePresence>
        {lightboxOpen && state.currentScreenshot && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
            onClick={() => setLightboxOpen(false)}
          >
            <motion.img
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
              src={`data:image/jpeg;base64,${state.currentScreenshot}`}
              alt="Screenshot"
              className="max-w-full max-h-full rounded-xl"
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
