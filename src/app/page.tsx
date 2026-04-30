"use client";

import { useState, useRef, useCallback, useEffect } from "react";

type Mode = "fast" | "stealth" | "deep";

interface Step {
  step: number;
  action: string;
  argument?: string;
  ai_reasoning?: string;
  status: string;
  screenshot?: string;
  answer?: string;
  error?: string;
  url?: string;
  page_title?: string;
  duration_ms?: number;
  model?: string;
  observation?: string;
  thinking?: string;
  timestamp: number;
}

const ACTION_ICONS: Record<string, string> = {
  navigate: "🌐",
  click: "👆",
  type: "⌨️",
  scroll: "📜",
  wait: "⏳",
  screenshot: "📸",
  done: "✅",
  error: "❌",
  check: "☑",
  submit: "🚀",
  thinking: "🧠",
};

const MODE_STYLES: Record<Mode, { label: string; color: string; glow: string; border: string }> = {
  fast: { label: "FAST", color: "text-amber-400", glow: "shadow-amber-500/30", border: "border-amber-500/40" },
  stealth: { label: "STEALTH", color: "text-slate-300", glow: "shadow-slate-500/30", border: "border-slate-500/40" },
  deep: { label: "DEEP", color: "text-violet-400", glow: "shadow-violet-500/30", border: "border-violet-500/40" },
};

const QUICK_SITES = [
  {
    name: "Pizza Form",
    icon: "🍕",
    url: "https://httpbin.org/forms/post",
    task: "Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page.",
  },
  {
    name: "Login Flow",
    icon: "🔐",
    url: "https://httpbin.org/basic-auth/user/passwd",
    task: "Navigate to the page. Type user in the username field and passwd in the password field. Click the submit button. Report the result — whether authentication succeeded or failed.",
  },
  {
    name: "Job Board",
    icon: "💼",
    url: "https://boards.greenhouse.io/embed/job_board?for_first=True",
    task: "Navigate to the job board. Report all visible job listings including job title, company name, and location. Take a screenshot.",
  },
  {
    name: "Travel Search",
    icon: "✈️",
    url: "https://www.booking.com",
    task: "Navigate to Booking.com. Report the page title and what search fields are visible (destination, dates, guests). Take a screenshot. Do not fill anything in yet.",
  },
];

export default function Home() {
  const [url, setUrl] = useState("https://httpbin.org/forms/post");
  const [task, setTask] = useState(
    "Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page."
  );
  const [mode, setMode] = useState<Mode>("deep");
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<string | null>(null);
  const [finalAnswer, setFinalAnswer] = useState<string | null>(null);
  const [backendUrl] = useState("http://localhost:8001");
  const [maxSteps] = useState(500);
  const [wsStatus, setWsStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [latestAiReasoning, setLatestAiReasoning] = useState<string | null>(null);
  const [currentUrl, setCurrentUrl] = useState("https://httpbin.org/forms/post");
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [latestThinking, setLatestThinking] = useState<string | null>(null);
  const [thinkingHistory, setThinkingHistory] = useState<string[]>([]);
  const [screenshotHistory, setScreenshotHistory] = useState<string[]>([]);
  const [activeScreenshotIndex, setActiveScreenshotIndex] = useState<number>(-1);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const thinkingRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef<number>(0);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, []);

  const scrollThinkingToBottom = useCallback(() => {
    if (thinkingRef.current) {
      thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [steps, scrollToBottom]);

  useEffect(() => {
    scrollThinkingToBottom();
  }, [thinkingHistory, scrollThinkingToBottom]);

  const disconnectWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setWsStatus("disconnected");
  }, []);

  const runTask = useCallback(async () => {
    if (!url || !task) return;

    disconnectWs();
    setIsRunning(true);
    setSteps([]);
    setCurrentScreenshot(null);
    setFinalAnswer(null);
    setLatestAiReasoning(null);
    setLatestThinking(null);
    setCurrentUrl(url);
    setExecutionTime(null);
    setThinkingHistory([]);
    setScreenshotHistory([]);
    setActiveScreenshotIndex(-1);
    setExpandedSteps(new Set());
    startTimeRef.current = Date.now();

    const wsUrl = `ws://localhost:8001/ws/agent`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      setWsStatus("connected");
      ws.send(JSON.stringify({ url, task, mode }));
    };

    ws.onmessage = (event) => {
      try {
        const data: Step = JSON.parse(event.data);
        data.timestamp = Date.now();

        // Handle thinking step — the agent's live reasoning
        if (data.status === "thinking") {
          setLatestThinking(data.thinking ?? data.ai_reasoning ?? null);
          setLatestAiReasoning(data.ai_reasoning ?? null);

          // Add to thinking history for the scrolling panel
          if (data.thinking) {
            setThinkingHistory((prev) => {
              const updated = [...prev, data.thinking!];
              return updated.slice(-30); // keep last 30 thoughts
            });
          }

          // Show screenshot that came with this step if available
          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
          }
        }

        // Handle completed action
        if (data.status === "completed" || data.status === "snapshot") {
          setSteps((prev) => {
            // Replace the thinking step with the completed version
            const withoutDupe = prev.filter((s) => !(s.step === data.step && s.status === "thinking"));
            return [...withoutDupe, data];
          });

          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
            setScreenshotHistory((prev) => {
              const updated = [...prev, data.screenshot!];
              return updated.slice(-20); // keep last 20 screenshots
            });
            setActiveScreenshotIndex(screenshotHistory.length);
          }

          setLatestThinking(null);
        }

        // Handle done
        if (data.action === "done") {
          setFinalAnswer(data.answer ?? null);
          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
            setScreenshotHistory((prev) => {
              const updated = [...prev, data.screenshot!];
              return updated.slice(-20);
            });
          }
          const elapsed = Math.round((Date.now() - startTimeRef.current) / 1000);
          setExecutionTime(elapsed);
          setIsRunning(false);
          setWsStatus("disconnected");
          disconnectWs();
        }

        // Handle error
        if (data.action === "error") {
          setSteps((prev) => {
            const withoutDupe = prev.filter((s) => !(s.step === data.step && s.status === "thinking"));
            return [...withoutDupe, data];
          });
          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
          }
        }
      } catch {
        // Ignore parse errors
      }
    };

    ws.onerror = () => {
      setWsStatus("disconnected");
      setIsRunning(false);
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      setIsRunning(false);
    };
  }, [url, task, mode, disconnectWs, screenshotHistory.length]);

  const stopTask = useCallback(() => {
    disconnectWs();
    setIsRunning(false);
    const elapsed = Math.round((Date.now() - startTimeRef.current) / 1000);
    setExecutionTime(elapsed);
  }, [disconnectWs]);

  const toggleExpanded = (step: number) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(step)) {
        next.delete(step);
      } else {
        next.add(step);
      }
      return next;
    });
  };

  const completedSteps = steps.filter(
    (s) => s.status === "completed" || s.action === "done"
  ).length;
  const failedSteps = steps.filter((s) => s.status === "retrying" || s.status === "failed").length;
  const progress = maxSteps > 0 ? Math.min((completedSteps / maxSteps) * 100, 100) : 0;
  const latestStep = steps[steps.length - 1];
  const modeStyle = MODE_STYLES[mode];

  const wsColor =
    wsStatus === "connected"
      ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
      : wsStatus === "connecting"
      ? "bg-amber-400 animate-pulse shadow-[0_0_8px_rgba(251,191,36,0.8)]"
      : "bg-zinc-600";

  // Build execution pipeline nodes
  const pipelineNodes = [
    { label: "Task", icon: "🎯", desc: task.slice(0, 30) + (task.length > 30 ? "..." : "") },
    { label: "Navigate", icon: "🌐" },
    { label: "Analyze", icon: "🧠" },
    { label: "Act", icon: "👆" },
    { label: "Observe", icon: "👁" },
    { label: "Done", icon: "✅" },
  ];
  const currentPhase = isRunning
    ? 2 + Math.min(Math.floor(completedSteps / 2), 4)
    : finalAnswer
    ? 5
    : 0;

  return (
    <div className="min-h-screen bg-[#030306] text-zinc-100 font-mono overflow-hidden relative">
      {/* Ambient background orbs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] left-[10%] w-[500px] h-[500px] rounded-full bg-violet-600/10 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[5%] w-[400px] h-[400px] rounded-full bg-cyan-500/8 blur-[100px]" />
        <div className="absolute top-[40%] right-[30%] w-[300px] h-[300px] rounded-full bg-fuchsia-600/6 blur-[80px]" />
      </div>

      {/* Noise texture overlay */}
      <div
        className="fixed inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E")`,
        }}
      />

      {/* Header */}
      <header className="relative z-50 border-b border-zinc-800/50 bg-zinc-950/60 backdrop-blur-2xl">
        <div className="max-w-[1920px] mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-violet-600 via-fuchsia-600 to-cyan-500 flex items-center justify-center shadow-[0_0_20px_rgba(168,85,247,0.4)]">
                <span className="text-white text-lg">🤖</span>
              </div>
              <div className={`absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full ${wsColor} border-2 border-[#030306]`} />
            </div>
            <div>
              <h1 className="text-sm font-black tracking-[0.15em] text-white">
                AGENT<span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-cyan-400">BROWSER</span>
              </h1>
              <p className="text-[9px] text-zinc-600 tracking-[0.25em] uppercase">Immersive Agent Viewer</p>
            </div>
          </div>

          {/* Execution Pipeline */}
          <div className="hidden xl:flex items-center gap-1">
            {pipelineNodes.map((node, i) => {
              const isDone = i < currentPhase;
              const isActive = i === currentPhase && isRunning;
              const isCurrent = i === currentPhase;
              return (
                <div key={i} className="flex items-center">
                  <div
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[10px] font-bold tracking-wide transition-all duration-300 ${
                      isDone
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : isActive
                        ? "bg-violet-500/20 text-violet-400 border border-violet-500/40 shadow-[0_0_15px_rgba(168,85,247,0.3)] animate-pulse"
                        : "bg-zinc-900/80 text-zinc-600 border border-zinc-800/50"
                    }`}
                  >
                    <span className="text-xs">{node.icon}</span>
                    <span>{node.label}</span>
                  </div>
                  {i < pipelineNodes.length - 1 && (
                    <div className={`w-4 h-[2px] mx-0.5 ${isDone ? "bg-emerald-500/40" : "bg-zinc-800/60"}`} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Mode Selector */}
          <div className="flex items-center gap-1 bg-zinc-900/80 rounded-2xl p-1.5 border border-zinc-800/60 backdrop-blur-xl">
            {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
              const s = MODE_STYLES[m];
              const active = mode === m;
              return (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`px-5 py-1.5 text-[11px] font-bold tracking-[0.15em] rounded-xl transition-all duration-200 ${
                    active
                      ? `${s.color} ${s.glow} border ${s.border} bg-zinc-800/60 shadow-lg`
                      : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                  }`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>

          {/* Status cluster */}
          <div className="flex items-center gap-4">
            {/* WS status */}
            <div className="flex items-center gap-2.5">
              <div className={`w-2 h-2 rounded-full transition-all duration-300 ${wsColor}`} />
              <span className="text-[10px] text-zinc-500 uppercase tracking-[0.2em]">
                {wsStatus === "connected" ? "LIVE" : wsStatus === "connecting" ? "CONNECTING" : "IDLE"}
              </span>
            </div>

            {/* Model badge */}
            {latestStep?.model && (
              <div className="hidden md:flex items-center gap-1.5 bg-zinc-900/80 rounded-xl px-3 py-1.5 border border-zinc-800/50">
                <span className="text-[9px] text-violet-400 uppercase tracking-widest">🧠</span>
                <span className="text-[10px] text-violet-400 font-bold tracking-wide">{latestStep.model}</span>
              </div>
            )}

            {/* Duration */}
            {isRunning && executionTime === null && (
              <div className="flex items-center gap-2 bg-zinc-900/80 rounded-xl px-4 py-2 border border-zinc-800/50 backdrop-blur-xl">
                <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse shadow-[0_0_6px_rgba(167,139,250,0.8)]" />
                <span className="text-[10px] text-zinc-500 uppercase tracking-widest">Running</span>
              </div>
            )}

            {executionTime !== null && (
              <div className="flex items-center gap-2 bg-zinc-900/80 rounded-xl px-4 py-2 border border-zinc-800/50 backdrop-blur-xl">
                <span className="text-[10px] text-emerald-400 uppercase tracking-widest">{executionTime}s</span>
              </div>
            )}

            {/* Step counter */}
            {(isRunning || completedSteps > 0) && (
              <div className="flex items-center gap-3 bg-zinc-900/80 rounded-xl px-4 py-2 border border-zinc-800/50 backdrop-blur-xl">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-widest">Steps</span>
                  <span className="text-sm font-bold text-white tabular-nums">{completedSteps}</span>
                  <span className="text-[10px] text-zinc-600">/ {maxSteps}</span>
                </div>
                {failedSteps > 0 && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-red-400">{failedSteps}</span>
                    <span className="text-[10px] text-zinc-600">fail</span>
                  </div>
                )}
              </div>
            )}

            {/* Stop button */}
            {isRunning && (
              <button
                onClick={stopTask}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-[11px] font-bold uppercase tracking-widest hover:bg-red-500/20 hover:border-red-500/50 transition-all"
              >
                <span className="text-sm">■</span> Stop
              </button>
            )}
          </div>
        </div>

        {/* Progress bar */}
        {isRunning && (
          <div className="h-[2px] bg-zinc-900/80 w-full">
            <div
              className="h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-500 transition-all duration-500 ease-out shadow-[0_0_10px_rgba(168,85,247,0.6)]"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </header>

      <main className="relative z-10 flex-1 max-w-[1920px] mx-auto w-full p-4 grid grid-cols-1 xl:grid-cols-[420px_1fr_380px] gap-4 min-h-[calc(100vh-64px)]">

        {/* ─── LEFT PANEL — Task Input ─── */}
        <div className="space-y-4">
          {/* Main task card */}
          <div className="rounded-3xl border border-zinc-800/60 bg-zinc-950/70 backdrop-blur-2xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)]">
            <div className="px-6 py-5 border-b border-zinc-800/40 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-violet-600/30 to-cyan-600/30 border border-violet-500/30 flex items-center justify-center">
                  <span className="text-sm">🎯</span>
                </div>
                <div>
                  <span className="text-[10px] text-zinc-500 uppercase tracking-[0.25em] font-semibold">Task Input</span>
                  <div className="text-[9px] text-zinc-700 mt-0.5">MiniMax M2.7 · WebSocket streaming</div>
                </div>
              </div>
              <div className={`w-2 h-2 rounded-full ${isRunning ? "bg-violet-400 animate-pulse shadow-[0_0_8px_rgba(167,139,250,0.8)]" : "bg-zinc-700"}`} />
            </div>

            <div className="p-6 space-y-5">
              {/* URL field */}
              <div className="space-y-2">
                <label className="text-[9px] text-zinc-600 uppercase tracking-[0.3em] font-semibold">Target URL</label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={isRunning}
                  className="w-full bg-zinc-900/80 border border-zinc-800/60 rounded-2xl px-4 py-3.5 text-[13px] font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all disabled:opacity-40"
                  placeholder="https://..."
                />
              </div>

              {/* Task field */}
              <div className="space-y-2">
                <label className="text-[9px] text-zinc-600 uppercase tracking-[0.3em] font-semibold">Instructions</label>
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  disabled={isRunning}
                  rows={6}
                  className="w-full bg-zinc-900/80 border border-zinc-800/60 rounded-2xl px-4 py-3.5 text-[13px] text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all resize-none disabled:opacity-40"
                  placeholder="What should the agent do?"
                />
              </div>

              {/* Execute button */}
              <button
                onClick={runTask}
                disabled={isRunning || !url || !task}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white font-black text-sm tracking-[0.1em] uppercase hover:from-violet-500 hover:to-fuchsia-500 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 shadow-[0_0_30px_rgba(168,85,247,0.3)] hover:shadow-[0_0_40px_rgba(168,85,247,0.5)] active:scale-[0.98]"
              >
                {isRunning ? (
                  <span className="flex items-center justify-center gap-3">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Executing...
                  </span>
                ) : (
                  <span className="flex items-center justify-center gap-2">
                    <span className="text-base">▶</span> Execute Agent
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Quick test sites */}
          <div className="rounded-3xl border border-zinc-800/60 bg-zinc-950/70 backdrop-blur-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-800/40">
              <span className="text-[10px] text-zinc-500 uppercase tracking-[0.25em] font-semibold">Quick Launch</span>
            </div>
            <div className="p-4 grid grid-cols-2 gap-2.5">
              {QUICK_SITES.map((site) => (
                <button
                  key={site.name}
                  onClick={() => {
                    setUrl(site.url);
                    setTask(site.task);
                  }}
                  disabled={isRunning}
                  className="group p-4 rounded-2xl bg-zinc-900/60 border border-zinc-800/50 hover:border-violet-500/40 hover:bg-zinc-900/90 transition-all duration-200 text-left disabled:opacity-30 disabled:cursor-not-allowed active:scale-[0.97]"
                >
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <span className="text-base">{site.icon}</span>
                    <span className="text-[11px] font-bold text-zinc-300 group-hover:text-white transition-colors">{site.name}</span>
                  </div>
                  <p className="text-[9px] text-zinc-600 leading-relaxed line-clamp-2">{site.task.slice(0, 60)}...</p>
                </button>
              ))}
            </div>
          </div>

          {/* Session stats */}
          <div className="rounded-3xl border border-zinc-800/60 bg-zinc-950/70 backdrop-blur-2xl p-6">
            <div className="text-[9px] text-zinc-600 uppercase tracking-[0.3em] font-semibold mb-4">Session Stats</div>
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-2xl bg-zinc-900/80 border border-zinc-800/50 p-4 text-center">
                <div className="text-2xl font-black text-white">{completedSteps}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider mt-1">Done</div>
              </div>
              <div className="rounded-2xl bg-zinc-900/80 border border-zinc-800/50 p-4 text-center">
                <div className="text-2xl font-black text-red-400">{failedSteps}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider mt-1">Failed</div>
              </div>
              <div className="rounded-2xl bg-zinc-900/80 border border-zinc-800/50 p-4 text-center">
                <div className="text-2xl font-black text-violet-400">{steps.length}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider mt-1">Total</div>
              </div>
            </div>
          </div>
        </div>

        {/* ─── CENTER — Viewport + Thinking ─── */}
        <div className="space-y-4">
          {/* Browser viewport with filmstrip */}
          <div className="rounded-3xl border border-zinc-800/60 bg-zinc-950/70 backdrop-blur-2xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)]">
            {/* Chrome bar */}
            <div className="flex items-center gap-3 px-5 py-3.5 bg-zinc-900/90 border-b border-zinc-800/40 backdrop-blur-xl">
              <div className="flex gap-2">
                <div className="w-3.5 h-3.5 rounded-full bg-red-500/80 shadow-[0_0_6px_rgba(248,113,113,0.4)]" />
                <div className="w-3.5 h-3.5 rounded-full bg-amber-500/80 shadow-[0_0_6px_rgba(251,191,36,0.4)]" />
                <div className="w-3.5 h-3.5 rounded-full bg-emerald-500/80 shadow-[0_0_6px_rgba(52,211,153,0.4)]" />
              </div>
              <div className="flex-1 mx-3">
                <div className="bg-black/80 rounded-xl px-4 py-1.5 text-xs text-zinc-400 truncate font-mono border border-zinc-800/60 max-w-xl mx-auto backdrop-blur-xl">
                  {currentUrl || url}
                </div>
              </div>
              <div className={`px-4 py-1.5 rounded-xl text-[10px] font-black uppercase tracking-widest ${modeStyle.color} border ${modeStyle.border} ${modeStyle.glow} bg-zinc-900/80 shadow-lg`}>
                {modeStyle.label}
              </div>
            </div>

            {/* Screenshot viewport */}
            <div className="relative bg-black">
              {/* Main screenshot */}
              <div className="aspect-[16/9] relative">
                {currentScreenshot ? (
                  <img
                    src={`data:image/png;base64,${currentScreenshot}`}
                    alt="Browser view"
                    className={`w-full h-full object-contain ${isRunning ? "animate-pulse" : ""}`}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center">
                    {isRunning ? (
                      <div className="text-center space-y-5">
                        <div className="relative mx-auto w-20 h-20">
                          <div className="absolute inset-0 border-4 border-zinc-800 rounded-full" />
                          <div className="absolute inset-0 border-4 border-transparent border-t-violet-500 rounded-full animate-spin shadow-[0_0_15px_rgba(168,85,247,0.5)]" />
                        </div>
                        <p className="text-xs text-zinc-600 animate-pulse tracking-widest uppercase">Initializing browser...</p>
                      </div>
                    ) : (
                      <div className="text-center space-y-4">
                        <div className="w-20 h-20 mx-auto rounded-3xl bg-zinc-900/80 border border-zinc-800/60 flex items-center justify-center text-3xl shadow-inner">
                          🖥️
                        </div>
                        <p className="text-xs text-zinc-700 tracking-widest uppercase">Execute a task to see the browser</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Step badge overlay */}
                {isRunning && (
                  <div className="absolute top-4 right-4 bg-black/90 border border-zinc-700/60 rounded-2xl px-4 py-2.5 backdrop-blur-xl shadow-[0_0_20px_rgba(0,0,0,0.8)]">
                    <span className="text-[10px] text-zinc-500 uppercase tracking-widest">Step </span>
                    <span className="text-sm font-black text-white tabular-nums">{completedSteps}</span>
                  </div>
                )}

                {/* Live URL overlay */}
                {latestStep?.url && (
                  <div className="absolute bottom-4 left-4 bg-black/90 border border-zinc-700/40 rounded-xl px-3 py-1.5 backdrop-blur-xl">
                    <span className="text-[9px] text-zinc-500 truncate max-w-xs">{latestStep.url}</span>
                  </div>
                )}

                {/* Pulsing border when running */}
                {isRunning && (
                  <div className="absolute inset-0 rounded-b-3xl border-2 border-violet-500/30 animate-pulse shadow-[0_0_20px_rgba(168,85,247,0.15)] pointer-events-none" />
                )}
              </div>

              {/* Screenshot filmstrip */}
              {screenshotHistory.length > 1 && (
                <div className="border-t border-zinc-800/40 p-3 bg-zinc-950/50">
                  <div className="flex gap-2 overflow-x-auto pb-1">
                    {screenshotHistory.map((ss, i) => (
                      <button
                        key={i}
                        onClick={() => {
                          setCurrentScreenshot(ss);
                          setActiveScreenshotIndex(i);
                        }}
                        className={`flex-shrink-0 w-20 h-12 rounded-xl overflow-hidden border-2 transition-all ${
                          activeScreenshotIndex === i
                            ? "border-violet-500 shadow-[0_0_10px_rgba(168,85,247,0.4)]"
                            : "border-zinc-800/50 hover:border-zinc-600"
                        }`}
                      >
                        <img
                          src={`data:image/png;base64,${ss}`}
                          alt={`Step ${i + 1}`}
                          className="w-full h-full object-cover"
                        />
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* AI Thinking Panel — streaming live reasoning */}
          <div className="rounded-3xl border border-zinc-800/60 bg-zinc-950/70 backdrop-blur-2xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)]">
            <div className="px-5 py-4 border-b border-zinc-800/40 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-base">🧠</span>
                <span className="text-[10px] text-zinc-500 uppercase tracking-[0.25em] font-semibold">Live Reasoning</span>
                {latestStep?.model && (
                  <span className="text-[9px] text-violet-400/60 font-mono">{latestStep.model}</span>
                )}
                {latestStep?.duration_ms != null && (
                  <span className="text-[9px] text-zinc-600 font-mono">{latestStep.duration_ms}ms</span>
                )}
              </div>
              {latestThinking && isRunning && (
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse shadow-[0_0_6px_rgba(167,139,250,0.8)]" />
                  <span className="text-[9px] text-violet-400 uppercase tracking-widest">Thinking</span>
                </div>
              )}
            </div>

            {/* Scrolling thinking history */}
            <div
              ref={thinkingRef}
              className="h-[200px] overflow-y-auto p-4 space-y-3"
              style={{ scrollbarWidth: "thin", scrollbarColor: "#3f3f46 transparent" }}
            >
              {thinkingHistory.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-xs text-zinc-700 uppercase tracking-widest text-center">
                    {isRunning ? "Agent reasoning will appear here..." : "Execute a task to see live reasoning"}
                  </p>
                </div>
              ) : (
                thinkingHistory.map((thought, i) => {
                  const isLast = i === thinkingHistory.length - 1;
                  return (
                    <div
                      key={i}
                      className={`rounded-2xl p-4 border transition-all duration-300 ${
                        isLast && isRunning
                          ? "bg-violet-950/40 border-violet-500/30 shadow-[0_0_15px_rgba(168,85,247,0.1)]"
                          : "bg-zinc-900/50 border-zinc-800/50"
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-[9px] text-zinc-600 font-mono uppercase tracking-widest">
                          #{i + 1}
                        </span>
                        {isLast && isRunning && (
                          <div className="flex gap-1">
                            {[0, 1, 2].map((d) => (
                              <div
                                key={d}
                                className="w-1 h-1 rounded-full bg-violet-400 animate-bounce"
                                style={{ animationDelay: `${d * 0.15}s` }}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                      <pre className="text-[11px] text-zinc-300 whitespace-pre-wrap leading-relaxed font-mono">
                        {thought}
                      </pre>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Final answer */}
          {finalAnswer && (
            <div className="rounded-3xl border border-emerald-500/20 bg-gradient-to-br from-emerald-950/40 to-zinc-950/80 backdrop-blur-2xl overflow-hidden shadow-[0_0_40px_rgba(52,211,153,0.1)]">
              <div className="px-5 py-4 border-b border-emerald-500/20 flex items-center gap-3">
                <span className="text-base">✅</span>
                <span className="text-[10px] text-emerald-400 uppercase tracking-[0.25em] font-semibold">Agent Result</span>
                {executionTime !== null && (
                  <span className="text-[9px] text-zinc-600 ml-auto uppercase tracking-widest">{executionTime}s</span>
                )}
                {steps.length > 0 && (
                  <span className="text-[9px] text-zinc-600 uppercase tracking-widest">{steps.length} steps</span>
                )}
              </div>
              <div className="p-6">
                <pre className="text-[13px] text-zinc-200 whitespace-pre-wrap leading-relaxed font-mono">{finalAnswer}</pre>
              </div>
            </div>
          )}
        </div>

        {/* ─── RIGHT — Expanded Live Activity Feed ─── */}
        <div className="space-y-4">
          <div className="rounded-3xl border border-zinc-800/60 bg-zinc-950/70 backdrop-blur-2xl overflow-hidden shadow-[0_0_60px_rgba(0,0,0,0.8)]">
            <div className="px-5 py-4 border-b border-zinc-800/40 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="text-base">📡</span>
                <span className="text-[10px] text-zinc-500 uppercase tracking-[0.25em] font-semibold">Live Activity</span>
              </div>
              {isRunning && (
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
                  <span className="text-[9px] text-emerald-400 uppercase tracking-widest">Streaming</span>
                </div>
              )}
            </div>

            <div
              ref={feedRef}
              className="h-[calc(100vh-180px)] overflow-y-auto p-4 space-y-2.5"
              style={{ scrollbarWidth: "thin", scrollbarColor: "#3f3f46 transparent" }}
            >
              {steps.length === 0 ? (
                <div className="flex items-center justify-center h-48">
                  <div className="text-center space-y-3">
                    <div className="w-14 h-14 mx-auto rounded-2xl bg-zinc-900/80 border border-zinc-800/60 flex items-center justify-center text-xl shadow-inner">
                      ⚡
                    </div>
                    <p className="text-xs text-zinc-700 uppercase tracking-widest">No activity yet</p>
                  </div>
                </div>
              ) : (
                steps.map((step, i) => {
                  const isLatest = i === steps.length - 1;
                  const icon = ACTION_ICONS[step.action] || "•";
                  const isError = step.status === "retrying" || step.status === "failed";
                  const isDone = step.action === "done";
                  const isThinking = step.status === "thinking";
                  const isExpanded = expandedSteps.has(step.step);
                  const hasDetails = !!(step.observation || step.ai_reasoning || step.url || step.duration_ms != null || step.error);

                  return (
                    <div
                      key={`${step.step}-${i}`}
                      className={`rounded-2xl border p-4 transition-all duration-200 ${
                        isError
                          ? "bg-red-950/30 border-red-500/30"
                          : isDone
                          ? "bg-emerald-950/30 border-emerald-500/30"
                          : isThinking
                          ? "bg-violet-950/30 border-violet-500/40 shadow-[0_0_15px_rgba(168,85,247,0.1)] animate-pulse"
                          : isLatest && isRunning
                          ? "bg-zinc-900/80 border-zinc-700/60"
                          : "bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/60"
                      }`}
                    >
                      {/* Main row */}
                      <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-sm flex-shrink-0 ${
                          isError ? "bg-red-500/20" : isDone ? "bg-emerald-500/20" : isThinking ? "bg-violet-500/20" : "bg-zinc-800/80"
                        }`}>
                          {icon}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
                              {step.action}
                            </span>
                            {step.status === "thinking" && (
                              <span className="text-[8px] text-violet-400 uppercase tracking-widest">thinking</span>
                            )}
                            {isError && (
                              <span className="text-[8px] text-red-400 uppercase tracking-widest">error</span>
                            )}
                            {step.duration_ms != null && (
                              <span className="text-[9px] text-zinc-600 font-mono">{step.duration_ms}ms</span>
                            )}
                            {step.model && (
                              <span className="text-[9px] text-violet-400/60 font-mono">{step.model}</span>
                            )}
                          </div>

                          {step.argument && (
                            <p className="text-[11px] text-zinc-400 font-mono truncate">{step.argument}</p>
                          )}

                          {/* Observation — what the agent saw */}
                          {step.observation && (
                            <div className="mt-2 p-2 bg-cyan-950/30 rounded-xl border border-cyan-800/20">
                              <div className="text-[8px] text-cyan-500 uppercase tracking-widest mb-1">👁 Observation</div>
                              <p className="text-[10px] text-zinc-400 font-mono leading-relaxed line-clamp-2">
                                {step.observation}
                              </p>
                            </div>
                          )}

                          {/* AI Reasoning — expandable */}
                          {step.ai_reasoning && hasDetails && (
                            <button
                              onClick={() => toggleExpanded(step.step)}
                              className="mt-2 flex items-center gap-1.5 text-[9px] text-violet-400/70 hover:text-violet-400 transition-colors"
                            >
                              <span>{isExpanded ? "▼" : "▶"}</span>
                              <span>{isExpanded ? "Hide" : "Show"} reasoning</span>
                            </button>
                          )}

                          {isExpanded && step.ai_reasoning && (
                            <div className="mt-2 p-2.5 bg-zinc-900/80 rounded-xl border border-zinc-800/50">
                              <div className="text-[8px] text-violet-500 uppercase tracking-widest mb-1">💬 Reasoning</div>
                              <pre className="text-[10px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap">
                                {step.ai_reasoning}
                              </pre>
                            </div>
                          )}

                          {/* URL */}
                          {step.url && (
                            <div className="mt-1.5 flex items-center gap-1.5">
                              <span className="text-[9px] text-zinc-600">🌐</span>
                              <span className="text-[9px] text-zinc-500 font-mono truncate">{step.url}</span>
                            </div>
                          )}

                          {/* Page title */}
                          {step.page_title && (
                            <p className="text-[9px] text-zinc-600 font-mono truncate mt-0.5">{step.page_title}</p>
                          )}

                          {/* Error */}
                          {step.error && (
                            <p className="text-[10px] text-red-400 mt-1 font-mono">{step.error}</p>
                          )}
                        </div>

                        <span className="text-[9px] text-zinc-700 font-mono flex-shrink-0 mt-0.5">
                          #{step.step}
                        </span>
                      </div>

                      {/* Thumbnail if screenshot present */}
                      {step.screenshot && !isThinking && (
                        <div className="mt-3">
                          <img
                            src={`data:image/png;base64,${step.screenshot}`}
                            alt={`Step ${step.step}`}
                            className="w-full h-24 object-cover rounded-xl border border-zinc-800/50"
                          />
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
