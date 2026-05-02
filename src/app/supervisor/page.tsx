"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap, Pause, Play, Undo2, Save, Download,
  Clock, CheckCircle2, AlertCircle, RotateCcw,
  ChevronDown, Globe, MousePointer, Type,
  ScrollText, Timer, Camera, Brain, Rocket,
  ArrowLeft, Activity, HardDrive,
} from "lucide-react";
import type { Step } from "@/components/agent/types";

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
}

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

function StepRow({ step }: { step: Step }) {
  const Icon = ACTION_ICON_MAP[step.action] || MousePointer;
  const color = ACTION_COLOR_MAP[step.action] || "text-zinc-500";

  return (
    <div className="flex items-start gap-2.5 p-2 rounded-lg hover:bg-white/[0.03] transition-colors">
      <div className="w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 mt-0.5">
        <Icon className={`w-3 h-3 ${color}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider">{step.action}</span>
          {step.argument && (
            <span className="text-[9px] text-zinc-600 font-mono truncate">{step.argument}</span>
          )}
        </div>
        {step.observation && (
          <p className="text-[9px] text-zinc-700 font-mono mt-0.5 line-clamp-1">{step.observation}</p>
        )}
      </div>
      <span className="text-[9px] text-zinc-800 font-mono flex-shrink-0">
        {formatTimestamp(step.timestamp)}
      </span>
    </div>
  );
}

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
  });

  const [saveName, setSaveName] = useState("");
  const [loadSessionId, setLoadSessionId] = useState("");
  const [exportLoading, setExportLoading] = useState(false);
  const [undoLoading, setUndoLoading] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const startRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Fetch session list ─────────────────────────────────────────────────────
  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/sessions?limit=50");
      const data = await res.json();
      setState((s) => ({ ...s, sessions: data.sessions || [] }));
    } catch { /* ignore */ }
  }, []);

  // ─── Fetch agent status ────────────────────────────────────────────────────
  const fetchAgentStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/supervisor/status");
      const data = await res.json();
      setState((s) => ({
        ...s,
        isPaused: data.paused ?? false,
        currentSessionId: data.session ?? s.currentSessionId,
        agentStatus: data.paused ? "paused" : s.agentStatus === "paused" ? "paused" : s.agentStatus,
      }));
    } catch { /* ignore */ }
  }, []);

  // ─── WebSocket connection ───────────────────────────────────────────────────
  const connectWs = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`ws://${window.location.host}/ws/agent`);
    wsRef.current = ws;

    ws.onopen = () => {
      // Send a heartbeat task to start receiving steps
      ws.send(JSON.stringify({ task: "__supervisor__", url: "about:blank", mode: "fast" }));
    };

    ws.onmessage = (e) => {
      try {
        const d: Step = JSON.parse(e.data);
        d.timestamp = Date.now();

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
            const newSteps = [...s.steps.filter((x) => !(x.step === d.step && x.status === "thinking")), d];
            const completedSteps = newSteps.filter((x) => x.status === "completed" || x.action === "done").length;
            return { ...s, steps: newSteps, agentStatus: "completed", completedSteps };
          });
          stopTimer();
          return;
        }

        if (d.status === "thinking") {
          setState((s) => {
            const without = s.steps.filter((x) => !(x.step === d.step && x.status === "thinking"));
            return { ...s, steps: [...without, d], latestThinking: d.thinking ?? d.ai_reasoning ?? null };
          });
        } else if (d.status === "completed" || d.status === "snapshot") {
          setState((s) => {
            const without = s.steps.filter((x) => !(x.step === d.step && x.status === "thinking"));
            const newSteps = [...without, d];
            const completedSteps = newSteps.filter((x) => x.status === "completed" || x.action === "done").length;
            return { ...s, steps: newSteps, completedSteps, latestThinking: null };
          });
        }
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      setWsStatus((s) => s === "connected" ? "disconnected" : s);
      // Reconnect after 2s
      setTimeout(connectWs, 2000);
    };

    ws.onerror = () => { ws.close(); };
  }, []);

  const [, setWsStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");

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

  // ─── Pause / Resume ────────────────────────────────────────────────────────
  const pauseAgent = useCallback(async () => {
    try {
      await fetch("/api/supervisor/pause", { method: "POST" });
      setState((s) => ({ ...s, isPaused: true, agentStatus: "paused" }));
      stopTimer();
    } catch (e) { console.error("pause failed", e); }
  }, [stopTimer]);

  const resumeAgent = useCallback(async () => {
    try {
      await fetch("/api/supervisor/resume", { method: "POST" });
      setState((s) => ({ ...s, isPaused: false, agentStatus: "running" }));
      startTimer();
    } catch (e) { console.error("resume failed", e); }
  }, [startTimer]);

  // ─── Save session ──────────────────────────────────────────────────────────
  const saveSession = useCallback(async () => {
    if (!saveName.trim()) return;
    try {
      await fetch(`/api/persistent-sessions/${encodeURIComponent(saveName)}/save`, { method: "POST" });
      setSaveName("");
    } catch (e) { console.error("save failed", e); }
  }, [saveName]);

  // ─── Load session ──────────────────────────────────────────────────────────
  const loadSession = useCallback(async () => {
    if (!loadSessionId) return;
    try {
      const res = await fetch(`/api/persistent-sessions/${encodeURIComponent(loadSessionId)}/load`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) alert(data.error || "Load failed");
    } catch (e) { console.error("load failed", e); }
  }, [loadSessionId]);

  // ─── Undo last action ──────────────────────────────────────────────────────
  const undoLastAction = useCallback(async () => {
    setUndoLoading(true);
    try {
      const res = await fetch("/api/supervisor/undo", { method: "POST" });
      if (res.ok) {
        setState((s) => ({ ...s, steps: s.steps.slice(0, -1) }));
      }
    } catch (e) { console.error("undo failed", e); }
    setUndoLoading(false);
  }, []);

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
    try {
      const res = await fetch(`/api/sessions/${sessionId}`);
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
  }, []);

  // ─── Init ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchSessions();
    fetchAgentStatus();
    connectWs();
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

  const last10 = state.steps.slice(-10);
  const statusCfg = STATUS_CONFIG[state.agentStatus];

  return (
    <div className="max-w-screen-2xl mx-auto w-full px-4 sm:px-6 lg:px-6 pb-16">
      {/* Header */}
      <div className="flex items-center gap-4 pt-8 pb-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-zinc-500 hover:text-zinc-200 transition-colors text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <Activity className="w-4 h-4 text-violet-400" />
          </div>
          <div>
            <h1 className="text-[15px] font-black tracking-widest uppercase text-zinc-200">Supervisor</h1>
            <p className="text-[10px] text-zinc-700 tracking-wider">Human-in-the-loop control</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 lg:gap-5">
        {/* ── Left column: Live Feed + Timeline ── */}
        <div className="xl:col-span-2 space-y-4">
          {/* Live Feed */}
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="panel-header">
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              <span className="panel-label">Live Feed</span>
              {state.agentStatus === "running" && (
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              )}
              <div className="ml-auto flex items-center gap-3 text-[10px] font-mono">
                {state.completedSteps > 0 && <span className="text-emerald-400">{state.completedSteps} ✓</span>}
                {state.failedSteps > 0 && <span className="text-red-400">{state.failedSteps} ✗</span>}
              </div>
            </div>
            <div
              ref={feedRef}
              className="max-h-52 overflow-y-auto p-2 space-y-0.5"
            >
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
              <span className="ml-auto text-[10px] text-zinc-700 font-mono">{state.steps.length} total</span>
            </div>
            <div className="max-h-80 overflow-y-auto p-3 space-y-1">
              {state.steps.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-24 gap-2">
                  <p className="text-[11px] text-zinc-700 uppercase tracking-widest">No actions yet</p>
                </div>
              ) : (
                state.steps.map((step, i) => (
                  <div key={`${step.step}-${i}`} className="flex items-start gap-3">
                    {/* Timeline dot + line */}
                    <div className="flex flex-col items-center flex-shrink-0">
                      <div className={`w-2 h-2 rounded-full mt-1.5 ${step.status === "failed" || step.action === "error" ? "bg-red-400" : step.action === "done" ? "bg-emerald-400" : "bg-zinc-700"}`} />
                      {i < state.steps.length - 1 && <div className="w-px flex-1 bg-zinc-800/60 mt-1" style={{ minHeight: 20 }} />}
                    </div>
                    <div className="flex-1 min-w-0 pb-3">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[10px] font-bold text-zinc-300 uppercase">{step.action}</span>
                        {step.argument && <span className="text-[9px] text-zinc-600 font-mono truncate">{step.argument}</span>}
                      </div>
                      {step.observation && (
                        <p className="text-[9px] text-zinc-700 font-mono mt-0.5 line-clamp-1">{step.observation}</p>
                      )}
                      {step.error && (
                        <p className="text-[9px] text-red-400 font-mono mt-0.5">{step.error}</p>
                      )}
                    </div>
                    <span className="text-[9px] text-zinc-800 font-mono flex-shrink-0">
                      {formatTimestamp(step.timestamp)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ── Right column: Status + Controls + Session ── */}
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
              {!state.isPaused && state.agentStatus === "running" ? (
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
    </div>
  );
}
