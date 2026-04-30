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
  check: "✓",
  submit: "🚀",
  thinking: "🧠",
};

const MODE_COLORS: Record<Mode, { bg: string; border: string; text: string; glow: string }> = {
  fast: { bg: "bg-amber-500/20", border: "border-amber-500/40", text: "text-amber-300", glow: "shadow-amber-500/20" },
  stealth: { bg: "bg-slate-500/20", border: "border-slate-500/40", text: "text-slate-300", glow: "shadow-slate-500/20" },
  deep: { bg: "bg-violet-500/20", border: "border-violet-500/40", text: "text-violet-300", glow: "shadow-violet-500/20" },
};

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
  const [currentUrl, setCurrentUrl] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [steps, latestAiReasoning, scrollToBottom]);

  const disconnectWs = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setWsStatus("disconnected");
  };

  const runTask = useCallback(async () => {
    if (!url || !task) return;

    // Disconnect any existing connection
    disconnectWs();

    setIsRunning(true);
    setSteps([]);
    setCurrentScreenshot(null);
    setFinalAnswer(null);
    setLatestAiReasoning(null);
    setCurrentUrl(url);

    const wsUrl = `ws://${backendUrl.replace("http://", "").replace("https://", "")}/ws/agent`;
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

        // Handle screenshot steps — update the viewport
        if (data.screenshot && data.action !== "done") {
          setCurrentScreenshot(data.screenshot);
        }

        // Handle AI reasoning — show in the thinking panel
        if (data.ai_reasoning) {
          setLatestAiReasoning(data.ai_reasoning);
        }

        // Handle final answer
        if (data.action === "done") {
          setFinalAnswer(data.answer ?? null);
          if (data.screenshot) setCurrentScreenshot(data.screenshot);
          setIsRunning(false);
          setWsStatus("disconnected");
          ws.close();
        }

        // Handle errors
        if (data.action === "error") {
          setSteps((prev) => [...prev, data]);
        } else {
          setSteps((prev) => {
            // Avoid duplicates
            if (prev.length > 0 && prev[prev.length - 1].step === data.step && data.status !== "snapshot") {
              return prev;
            }
            return [...prev, data];
          });
        }
      } catch (e) {
        console.error("WS parse error", e);
      }
    };

    ws.onerror = () => {
      setWsStatus("disconnected");
      setIsRunning(false);
    };

    ws.onclose = () => {
      setWsStatus("disconnected");
      if (isRunning) setIsRunning(false);
    };
  }, [url, task, mode, backendUrl, isRunning]);

  const stopTask = () => {
    disconnectWs();
    setIsRunning(false);
  };

  const latestStep = steps[steps.length - 1];
  const completedSteps = steps.filter((s) => s.status === "completed" || s.status === "snapshot" || s.action === "done").length;
  const failedSteps = steps.filter((s) => s.status === "retrying" || s.status === "failed").length;
  const progress = maxSteps > 0 ? Math.min((completedSteps / maxSteps) * 100, 100) : 0;

  const modeStyle = MODE_COLORS[mode];

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-zinc-100 flex flex-col font-mono">
      {/* Header */}
      <header className="border-b border-zinc-800/50 bg-[#0a0a0f]/95 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-[1920px] mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3.5">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-600 to-fuchsia-600 flex items-center justify-center shadow-lg shadow-violet-500/25">
                <span className="text-white text-lg">🤖</span>
              </div>
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-400 border-2 border-[#0a0a0f]" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-widest text-white">
                AGENT<span className="text-violet-400">BROWSER</span>
              </h1>
              <p className="text-[9px] text-zinc-600 tracking-[0.2em] uppercase">Autonomous Web Agent</p>
            </div>
          </div>

          {/* Mode Selector */}
          <div className="flex items-center gap-1 bg-zinc-900/80 rounded-xl p-1.5 border border-zinc-800/50">
            {(["fast", "deep", "stealth"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-4 py-1.5 text-xs rounded-lg capitalize tracking-wider transition-all duration-200 ${
                  mode === m
                    ? `${modeStyle.bg} ${modeStyle.border} ${modeStyle.text} font-bold shadow-sm ${modeStyle.glow}`
                    : "text-zinc-500 hover:text-zinc-300"
                }`}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Status */}
          <div className="flex items-center gap-4">
            {/* WS Status */}
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full transition-colors ${
                  wsStatus === "connected"
                    ? "bg-emerald-400 shadow-sm shadow-emerald-400/50"
                    : wsStatus === "connecting"
                    ? "bg-amber-400 animate-pulse"
                    : "bg-zinc-700"
                }`}
              />
              <span className="text-[10px] text-zinc-500 uppercase tracking-widest">
                {wsStatus === "connected" ? "Live" : wsStatus === "connecting" ? "Connecting" : "Idle"}
              </span>
            </div>

            {/* Step Counter */}
            {isRunning && (
              <div className="flex items-center gap-2 bg-zinc-900/80 rounded-lg px-3 py-1.5 border border-zinc-800/50">
                <span className="text-[10px] text-zinc-500 uppercase tracking-widest">Step</span>
                <span className="text-sm font-bold text-white tabular-nums">{completedSteps}</span>
                <span className="text-[10px] text-zinc-600">/ {maxSteps}</span>
              </div>
            )}

            {/* Stop Button */}
            {isRunning && (
              <button
                onClick={stopTask}
                className="px-3 py-1.5 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 text-xs hover:bg-red-500/30 transition-colors"
              >
                ■ Stop
              </button>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        {isRunning && (
          <div className="h-0.5 bg-zinc-900 w-full">
            <div
              className="h-full bg-gradient-to-r from-violet-600 to-fuchsia-600 transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}
      </header>

      <main className="flex-1 max-w-[1920px] mx-auto w-full p-4 grid grid-cols-1 xl:grid-cols-[420px_1fr_380px] gap-4">
        {/* LEFT — Task Input */}
        <div className="space-y-4">
          <div className="bg-zinc-950/80 rounded-2xl border border-zinc-800/50 overflow-hidden">
            <div className="px-5 py-4 border-b border-zinc-800/40 flex items-center justify-between">
              <span className="text-[10px] text-zinc-600 uppercase tracking-[0.2em] font-semibold">Task Input</span>
              <div className={`w-2 h-2 rounded-full ${isRunning ? "bg-violet-400 animate-pulse shadow-sm shadow-violet-400/50" : "bg-zinc-700"}`} />
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2 block">Target URL</label>
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={isRunning}
                  className="w-full bg-zinc-900/80 border border-zinc-800/50 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/50 transition-all disabled:opacity-50"
                  placeholder="https://..."
                />
              </div>
              <div>
                <label className="text-[10px] text-zinc-600 uppercase tracking-widest mb-2 block">Instructions</label>
                <textarea
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  disabled={isRunning}
                  rows={6}
                  className="w-full bg-zinc-900/80 border border-zinc-800/50 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/30 focus:border-violet-500/50 transition-all resize-none disabled:opacity-50"
                  placeholder="What should the agent do?"
                />
              </div>
              <button
                onClick={runTask}
                disabled={isRunning || !url || !task}
                className="w-full py-3.5 rounded-xl bg-white text-black font-bold text-sm hover:bg-zinc-200 disabled:opacity-30 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2.5 shadow-lg shadow-white/10"
              >
                {isRunning ? (
                  <>
                    <div className="w-4 h-4 border-2 border-zinc-400 border-t-transparent rounded-full animate-spin" />
                    Agent Running...
                  </>
                ) : (
                  <>
                    <span className="text-base">▶</span>
                    Execute Agent
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick Test Sites */}
          <div className="bg-zinc-950/80 rounded-2xl border border-zinc-800/50 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800/40">
              <span className="text-[10px] text-zinc-600 uppercase tracking-[0.2em] font-semibold">Quick Test Sites</span>
            </div>
            <div className="p-4 grid grid-cols-2 gap-2">
              {[
                { name: "🍕 Pizza Form", url: "https://httpbin.org/forms/post" },
                { name: "🔐 Login Form", url: "https://httpbin.org/forms/post" },
                { name: "🌐 Google", url: "https://google.com" },
                { name: "📰 BBC News", url: "https://bbc.com/news" },
              ].map((site) => (
                <button
                  key={site.name}
                  onClick={() => {
                    setUrl(site.url);
                    setTask("Explore this page. Take a screenshot and report what you find.");
                  }}
                  disabled={isRunning}
                  className="p-3 rounded-xl bg-zinc-900/60 border border-zinc-800/40 text-xs text-zinc-400 hover:bg-zinc-800/60 hover:text-white hover:border-zinc-700/60 transition-all text-left disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  {site.name}
                </button>
              ))}
            </div>
          </div>

          {/* Stats */}
          <div className="bg-zinc-950/80 rounded-2xl border border-zinc-800/50 overflow-hidden p-5">
            <div className="text-[10px] text-zinc-600 uppercase tracking-[0.2em] font-semibold mb-3">Session Stats</div>
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-zinc-900/60 rounded-xl p-3 text-center border border-zinc-800/30">
                <div className="text-xl font-bold text-white">{completedSteps}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider">Done</div>
              </div>
              <div className="bg-zinc-900/60 rounded-xl p-3 text-center border border-zinc-800/30">
                <div className="text-xl font-bold text-red-400">{failedSteps}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider">Failed</div>
              </div>
              <div className="bg-zinc-900/60 rounded-xl p-3 text-center border border-zinc-800/30">
                <div className="text-xl font-bold text-violet-400">{steps.length}</div>
                <div className="text-[9px] text-zinc-600 uppercase tracking-wider">Total</div>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER — Browser Viewport + AI Brain */}
        <div className="space-y-4">
          {/* Browser Viewport */}
          <div className="bg-zinc-950/80 rounded-2xl border border-zinc-800/50 overflow-hidden">
            {/* Chrome bar */}
            <div className="flex items-center gap-3 px-4 py-3 bg-zinc-900/90 border-b border-zinc-800/40">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-500/70" />
                <div className="w-3 h-3 rounded-full bg-amber-500/70" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
              </div>
              <div className="flex-1 mx-2">
                <div className="bg-black rounded-lg px-3 py-1 text-xs text-zinc-400 truncate font-mono border border-zinc-800/50 max-w-md mx-auto">
                  {currentUrl || url}
                </div>
              </div>
              <div className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest ${modeStyle.bg} ${modeStyle.border} ${modeStyle.text}`}>
                {mode}
              </div>
            </div>

            {/* Viewport */}
            <div className="aspect-[16/10] bg-black relative">
              {currentScreenshot ? (
                <img
                  src={`data:image/png;base64,${currentScreenshot}`}
                  alt="Browser view"
                  className="w-full h-full object-contain transition-opacity duration-300"
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center space-y-4">
                    {isRunning ? (
                      <>
                        <div className="relative mx-auto w-16 h-16">
                          <div className="absolute inset-0 border-4 border-zinc-800 rounded-full" />
                          <div className="absolute inset-0 border-4 border-transparent border-t-violet-500 rounded-full animate-spin" />
                        </div>
                        <p className="text-xs text-zinc-600 animate-pulse">Loading browser...</p>
                      </>
                    ) : (
                      <>
                        <div className="w-16 h-16 mx-auto rounded-2xl bg-zinc-900/80 border border-zinc-800/50 flex items-center justify-center text-3xl opacity-30">
                          🖥️
                        </div>
                        <p className="text-xs text-zinc-700">Execute a task to see the browser</p>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Step counter overlay */}
              {isRunning && (
                <div className="absolute top-3 right-3 bg-black/90 border border-zinc-700/50 rounded-xl px-3 py-2 backdrop-blur-sm">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-widest">Step </span>
                  <span className="text-sm font-bold text-white tabular-nums">{completedSteps}</span>
                </div>
              )}
            </div>
          </div>

          {/* AI Brain — Live Reasoning */}
          <div className="bg-zinc-950/80 rounded-2xl border border-zinc-800/50 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-base">🧠</span>
                <span className="text-[10px] text-zinc-600 uppercase tracking-[0.2em] font-semibold">Agent Brain</span>
              </div>
              {latestAiReasoning && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                  <span className="text-[9px] text-violet-400 uppercase tracking-widest">Thinking</span>
                </div>
              )}
            </div>
            <div className="p-5 min-h-[120px]">
              {latestAiReasoning ? (
                <div className="bg-zinc-900/60 rounded-xl p-4 border border-zinc-800/40">
                  <pre className="text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed font-mono">
                    {latestAiReasoning}
                  </pre>
                </div>
              ) : isRunning ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <div
                          key={i}
                          className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"
                          style={{ animationDelay: `${i * 0.15}s` }}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-zinc-600">Agent is thinking...</span>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-zinc-700 text-center py-4">Agent reasoning will appear here during execution</p>
              )}
            </div>
          </div>

          {/* Final Answer */}
          {finalAnswer && (
            <div className="bg-gradient-to-br from-emerald-950/60 to-zinc-950/80 rounded-2xl border border-emerald-500/20 overflow-hidden">
              <div className="px-5 py-3 border-b border-emerald-500/20 flex items-center gap-2">
                <span className="text-base">✅</span>
                <span className="text-[10px] text-emerald-400 uppercase tracking-[0.2em] font-semibold">Agent Result</span>
              </div>
              <div className="p-5">
                <pre className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed font-mono">{finalAnswer}</pre>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT — Live Activity Feed */}
        <div className="space-y-4">
          {/* Activity Feed */}
          <div className="bg-zinc-950/80 rounded-2xl border border-zinc-800/50 overflow-hidden">
            <div className="px-5 py-3 border-b border-zinc-800/40 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-base">📡</span>
                <span className="text-[10px] text-zinc-600 uppercase tracking-[0.2em] font-semibold">Live Activity</span>
              </div>
              {isRunning && (
                <div className="flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-sm shadow-emerald-400/50" />
                  <span className="text-[9px] text-emerald-400 uppercase tracking-widest">Streaming</span>
                </div>
              )}
            </div>
            <div ref={feedRef} className="h-[520px] overflow-y-auto p-4 space-y-2">
              {steps.length === 0 ? (
                <div className="h-full flex items-center justify-center">
                  <div className="text-center space-y-3 py-12">
                    <div className="w-12 h-12 rounded-xl bg-zinc-900/80 border border-zinc-800/50 flex items-center justify-center mx-auto text-xl">
                      ⚡
                    </div>
                    <p className="text-xs text-zinc-700">Execute a task to see live agent steps</p>
                  </div>
                </div>
              ) : (
                steps.map((step, i) => {
                  const isActive = i === steps.length - 1 && isRunning;
                  const icon = ACTION_ICONS[step.action] || "•";
                  const isError = step.status === "failed" || step.status === "retrying";
                  const isDone = step.action === "done";

                  return (
                    <div
                      key={i}
                      className={`rounded-xl border p-3 transition-all duration-300 ${
                        isDone
                          ? "bg-emerald-950/30 border-emerald-500/30"
                          : isError
                          ? "bg-red-950/30 border-red-500/30"
                          : isActive
                          ? "bg-violet-950/30 border-violet-500/40 shadow-sm shadow-violet-500/10"
                          : "bg-zinc-900/40 border-zinc-800/40"
                      }`}
                    >
                      <div className="flex items-center gap-2.5">
                        <span className={`text-base transition-transform ${isActive ? "scale-125" : ""}`}>
                          {icon}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span
                              className={`text-xs font-semibold capitalize ${
                                isDone
                                  ? "text-emerald-400"
                                  : isError
                                  ? "text-red-400"
                                  : isActive
                                  ? "text-violet-300"
                                  : "text-zinc-400"
                              }`}
                            >
                              {step.action}
                            </span>
                            {isActive && (
                              <div className="flex gap-0.5">
                                {[0, 1, 2].map((d) => (
                                  <div
                                    key={d}
                                    className="w-1 h-1 rounded-full bg-violet-400 animate-pulse"
                                    style={{ animationDelay: `${d * 0.2}s` }}
                                  />
                                ))}
                              </div>
                            )}
                          </div>
                          {step.argument && (
                            <p className="text-[10px] text-zinc-600 truncate mt-0.5 font-mono">{step.argument}</p>
                          )}
                          {step.error && (
                            <p className="text-[10px] text-red-400/70 mt-1 font-mono">⚠ {step.error}</p>
                          )}
                          {step.ai_reasoning && isActive && (
                            <p className="text-[9px] text-zinc-600 mt-1 leading-relaxed line-clamp-2 italic">
                              → {step.ai_reasoning.slice(0, 100)}...
                            </p>
                          )}
                        </div>
                        <span className="text-[9px] text-zinc-700 font-mono shrink-0">#{step.step}</span>
                      </div>
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
