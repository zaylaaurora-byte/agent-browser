"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play, Square, ChevronDown, ChevronRight, Globe, Zap, Brain,
  Eye, Clock, AlertCircle, CheckCircle2, Loader2, MousePointer,
  Type, ScrollText, Timer, Camera, Rocket
} from "lucide-react";

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

const ACTION_CONFIG: Record<string, { icon: React.ElementType; color: string }> = {
  navigate: { icon: Globe, color: "text-blue-400" },
  click: { icon: MousePointer, color: "text-amber-400" },
  type: { icon: Type, color: "text-emerald-400" },
  scroll: { icon: ScrollText, color: "text-zinc-400" },
  wait: { icon: Timer, color: "text-zinc-400" },
  screenshot: { icon: Camera, color: "text-pink-400" },
  done: { icon: CheckCircle2, color: "text-emerald-400" },
  error: { icon: AlertCircle, color: "text-red-400" },
  check: { icon: CheckCircle2, color: "text-cyan-400" },
  submit: { icon: Rocket, color: "text-violet-400" },
  thinking: { icon: Brain, color: "text-violet-400" },
};

const MODE_STYLES: Record<Mode, { label: string; color: string; border: string; bg: string }> = {
  fast: { label: "Fast", color: "text-amber-400", border: "border-amber-500/40", bg: "bg-amber-500/10" },
  stealth: { label: "Stealth", color: "text-slate-300", border: "border-slate-500/40", bg: "bg-slate-500/10" },
  deep: { label: "Deep", color: "text-violet-400", border: "border-violet-500/40", bg: "bg-violet-500/10" },
};

const QUICK_SITES = [
  { name: "Pizza Form", icon: "🍕", url: "https://httpbin.org/forms/post", task: "Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page." },
  { name: "Login Flow", icon: "🔐", url: "https://httpbin.org/basic-auth/user/passwd", task: "Navigate to the page. Type user in the username field and passwd in the password field. Click the submit button. Report the result." },
  { name: "Job Board", icon: "💼", url: "https://boards.greenhouse.io/embed/job_board?for_first=True", task: "Navigate to the job board. Report all visible job listings including job title, company name, and location." },
  { name: "Travel Search", icon: "✈️", url: "https://www.booking.com", task: "Navigate to Booking.com. Report the page title and what search fields are visible. Do not fill anything in." },
];

export function AgentBrowser() {
  const [url, setUrl] = useState("https://httpbin.org/forms/post");
  const [task, setTask] = useState("Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page.");
  const [mode, setMode] = useState<Mode>("deep");
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<string | null>(null);
  const [finalAnswer, setFinalAnswer] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [currentUrl, setCurrentUrl] = useState(url);
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [latestThinking, setLatestThinking] = useState<string | null>(null);
  const [screenshotHistory, setScreenshotHistory] = useState<string[]>([]);
  const [activeScreenshotIndex, setActiveScreenshotIndex] = useState<number>(-1);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const wsRef = useRef<WebSocket | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const thinkingRef = useRef<HTMLDivElement>(null);
  const startTimeRef = useRef<number>(0);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
    if (thinkingRef.current) thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
  }, []);

  useEffect(() => { scrollToBottom(); }, [steps, latestThinking, scrollToBottom]);

  const disconnectWs = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setWsStatus("disconnected");
  }, []);

  const runTask = useCallback(async () => {
    if (!url || !task) return;
    disconnectWs();
    setIsRunning(true);
    setSteps([]);
    setCurrentScreenshot(null);
    setFinalAnswer(null);
    setLatestThinking(null);
    setCurrentUrl(url);
    setExecutionTime(null);
    setScreenshotHistory([]);
    setActiveScreenshotIndex(-1);
    setExpandedSteps(new Set());
    startTimeRef.current = Date.now();

    const ws = new WebSocket("ws://localhost:8001/ws/agent");
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

        if (data.status === "thinking") {
          setLatestThinking(data.thinking ?? data.ai_reasoning ?? null);
          if (data.screenshot) setCurrentScreenshot(data.screenshot);
        }

        if (data.status === "completed" || data.status === "snapshot") {
          setSteps((prev) => {
            const withoutDupe = prev.filter((s) => !(s.step === data.step && s.status === "thinking"));
            return [...withoutDupe, data];
          });
          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
            setScreenshotHistory((prev) => [...prev, data.screenshot!].slice(-20));
          }
          setLatestThinking(null);
        }

        if (data.action === "done") {
          setFinalAnswer(data.answer ?? null);
          if (data.screenshot) setCurrentScreenshot(data.screenshot);
          setExecutionTime(Math.round((Date.now() - startTimeRef.current) / 1000));
          setIsRunning(false);
          setWsStatus("disconnected");
          disconnectWs();
        }

        if (data.action === "error" || data.status === "failed") {
          setSteps((prev) => {
            const withoutDupe = prev.filter((s) => !(s.step === data.step && s.status === "thinking"));
            return [...withoutDupe, data];
          });
          if (data.screenshot) setCurrentScreenshot(data.screenshot);
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onerror = () => { setWsStatus("disconnected"); setIsRunning(false); };
    ws.onclose = () => { setWsStatus("disconnected"); setIsRunning(false); };
  }, [url, task, mode, disconnectWs]);

  const stopTask = useCallback(() => {
    disconnectWs();
    setIsRunning(false);
    setExecutionTime(Math.round((Date.now() - startTimeRef.current) / 1000));
  }, [disconnectWs]);

  const completedSteps = steps.filter((s) => s.status === "completed" || s.action === "done").length;
  const failedSteps = steps.filter((s) => s.status === "retrying" || s.status === "failed").length;
  const modeStyle = MODE_STYLES[mode];

  return (
    <div className="relative z-10 max-w-[1920px] mx-auto w-full px-6 pb-12">
      {/* ─── TASK INPUT BAR ─── */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="mb-6"
      >
        <div className="rounded-2xl glass overflow-hidden glow-violet">
          <div className="p-5 space-y-4">
            <div className="flex gap-3 items-start">
              {/* URL */}
              <div className="flex-1">
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={isRunning}
                  placeholder="https://target-url.com"
                  className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm font-mono text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all disabled:opacity-40"
                />
              </div>
              {/* Mode selector */}
              <div className="flex items-center gap-1 bg-black/40 rounded-xl p-1 border border-zinc-800/60">
                {(["fast", "stealth", "deep"] as Mode[]).map((m) => {
                  const s = MODE_STYLES[m];
                  return (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`px-4 py-2.5 text-[11px] font-bold tracking-wider rounded-lg transition-all duration-200 ${
                        mode === m ? `${s.color} ${s.border} border bg-zinc-800/60` : "text-zinc-500 hover:text-zinc-300 border border-transparent"
                      }`}
                    >
                      {s.label}
                    </button>
                  );
                })}
              </div>
              {/* Execute */}
              <button
                onClick={isRunning ? stopTask : runTask}
                disabled={!isRunning && (!url || !task)}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold text-sm tracking-wide transition-all duration-200 active:scale-[0.97] ${
                  isRunning
                    ? "bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20"
                    : "bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white shadow-[0_0_30px_rgba(168,85,247,0.3)] hover:shadow-[0_0_40px_rgba(168,85,247,0.5)] disabled:opacity-30 disabled:cursor-not-allowed"
                }`}
              >
                {isRunning ? <><Square className="w-4 h-4" /> Stop</> : <><Play className="w-4 h-4" /> Execute</>}
              </button>
            </div>

            {/* Task textarea */}
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              disabled={isRunning}
              rows={2}
              placeholder="What should the agent do?"
              className="w-full bg-black/40 border border-zinc-800/60 rounded-xl px-4 py-3 text-sm text-zinc-200 placeholder:text-zinc-700 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/50 transition-all resize-none disabled:opacity-40"
            />

            {/* Quick launches */}
            <div className="flex gap-2">
              {QUICK_SITES.map((site) => (
                <button
                  key={site.name}
                  onClick={() => { setUrl(site.url); setTask(site.task); }}
                  disabled={isRunning}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl bg-black/30 border border-zinc-800/50 hover:border-violet-500/30 text-left transition-all disabled:opacity-30 active:scale-[0.97] group"
                >
                  <span className="text-sm">{site.icon}</span>
                  <span className="text-[11px] font-semibold text-zinc-400 group-hover:text-zinc-200 transition-colors">{site.name}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Progress bar */}
          {isRunning && (
            <div className="h-[2px] bg-zinc-900">
              <motion.div
                className="h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-500"
                initial={{ width: "0%" }}
                animate={{ width: `${Math.min((completedSteps / 500) * 100, 100)}%` }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </div>
          )}
        </div>
      </motion.div>

      {/* ─── MAIN 3-COLUMN LAYOUT ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6">
        {/* Left: Viewport + Thinking */}
        <div className="space-y-6">
          {/* Browser Viewport */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="rounded-2xl glass overflow-hidden"
          >
            {/* Chrome bar */}
            <div className="flex items-center gap-3 px-4 py-3 bg-black/60 border-b border-zinc-800/40">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500/70" />
                <div className="w-3 h-3 rounded-full bg-amber-500/70" />
                <div className="w-3 h-3 rounded-full bg-emerald-500/70" />
              </div>
              <div className="flex-1 mx-3">
                <div className="bg-black/60 rounded-lg px-3 py-1.5 text-xs text-zinc-500 truncate font-mono border border-zinc-800/40 max-w-lg mx-auto">
                  {currentUrl || url}
                </div>
              </div>
              <div className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest ${modeStyle.color} border ${modeStyle.border} ${modeStyle.bg}`}>
                {modeStyle.label}
              </div>
              {/* Status */}
              <div className="flex items-center gap-2">
                {wsStatus === "connected" && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.8)]" />
                    <span className="text-[9px] text-emerald-400 font-bold uppercase tracking-wider">Live</span>
                  </div>
                )}
                {isRunning && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-zinc-900/60 border border-zinc-800/50">
                    <span className="text-[10px] text-zinc-400 font-mono">{completedSteps} steps</span>
                  </div>
                )}
                {executionTime !== null && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-zinc-900/60 border border-zinc-800/50">
                    <Clock className="w-3 h-3 text-emerald-400" />
                    <span className="text-[10px] text-emerald-400 font-mono">{executionTime}s</span>
                  </div>
                )}
              </div>
            </div>

            {/* Screenshot */}
            <div className="relative bg-black aspect-[16/9]">
              {currentScreenshot ? (
                <img
                  src={`data:image/png;base64,${currentScreenshot}`}
                  alt="Browser view"
                  className="w-full h-full object-contain"
                />
              ) : isRunning ? (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center space-y-4">
                    <Loader2 className="w-12 h-12 text-violet-500 animate-spin mx-auto" />
                    <p className="text-xs text-zinc-600 uppercase tracking-widest">Initializing browser...</p>
                  </div>
                </div>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center space-y-3">
                    <Globe className="w-12 h-12 text-zinc-800 mx-auto" />
                    <p className="text-xs text-zinc-700 uppercase tracking-widest">Execute a task to see the browser</p>
                  </div>
                </div>
              )}
              {isRunning && (
                <div className="absolute inset-0 border-2 border-violet-500/20 rounded-b-2xl pointer-events-none animate-pulse" />
              )}
            </div>

            {/* Screenshot filmstrip */}
            {screenshotHistory.length > 1 && (
              <div className="border-t border-zinc-800/40 p-3 bg-black/40">
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {screenshotHistory.map((ss, i) => (
                    <button
                      key={i}
                      onClick={() => { setCurrentScreenshot(ss); setActiveScreenshotIndex(i); }}
                      className={`flex-shrink-0 w-20 h-12 rounded-lg overflow-hidden border-2 transition-all ${
                        activeScreenshotIndex === i ? "border-violet-500 shadow-[0_0_10px_rgba(168,85,247,0.3)]" : "border-zinc-800/50 hover:border-zinc-600"
                      }`}
                    >
                      <img src={`data:image/png;base64,${ss}`} alt={`Step ${i + 1}`} className="w-full h-full object-cover" />
                    </button>
                  ))}
                </div>
              </div>
            )}
          </motion.div>

          {/* Thinking Panel */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="rounded-2xl glass overflow-hidden"
          >
            <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center gap-3">
              <Brain className="w-4 h-4 text-violet-400" />
              <span className="text-[11px] text-zinc-400 font-semibold tracking-wider uppercase">Live Reasoning</span>
              {steps[steps.length - 1]?.model && (
                <span className="text-[10px] text-violet-400/60 font-mono">{steps[steps.length - 1].model}</span>
              )}
              {latestThinking && isRunning && (
                <div className="ml-auto flex items-center gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
                  <span className="text-[9px] text-violet-400 uppercase tracking-widest">Thinking</span>
                </div>
              )}
            </div>
            <div ref={thinkingRef} className="h-[200px] overflow-y-auto p-4 space-y-2">
              {steps.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-xs text-zinc-700 uppercase tracking-widest">
                    {isRunning ? "Agent reasoning will appear here..." : "Execute a task to see live reasoning"}
                  </p>
                </div>
              ) : (
                steps.map((step, i) => {
                  if (!step.thinking && !step.ai_reasoning) return null;
                  const isLast = i === steps.length - 1;
                  return (
                    <div key={i} className={`rounded-xl p-3 border transition-all duration-200 ${
                      isLast && isRunning ? "bg-violet-950/30 border-violet-500/20" : "bg-black/30 border-zinc-800/40"
                    }`}>
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[9px] text-zinc-600 font-mono">#{step.step}</span>
                        {step.duration_ms != null && <span className="text-[9px] text-zinc-600 font-mono">{step.duration_ms}ms</span>}
                        {isLast && isRunning && (
                          <div className="flex gap-0.5">
                            {[0, 1, 2].map((d) => (
                              <div key={d} className="w-1 h-1 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: `${d * 0.15}s` }} />
                            ))}
                          </div>
                        )}
                      </div>
                      <pre className="text-[11px] text-zinc-300 whitespace-pre-wrap leading-relaxed font-mono">
                        {step.thinking || step.ai_reasoning}
                      </pre>
                    </div>
                  );
                })
              )}
            </div>
          </motion.div>

          {/* Final Answer */}
          <AnimatePresence>
            {finalAnswer && (
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="rounded-2xl border border-emerald-500/20 bg-gradient-to-br from-emerald-950/30 to-black/60 backdrop-blur-xl overflow-hidden glow-emerald"
              >
                <div className="px-4 py-3 border-b border-emerald-500/20 flex items-center gap-3">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-[11px] text-emerald-400 font-semibold tracking-wider uppercase">Agent Result</span>
                  {executionTime !== null && <span className="text-[10px] text-zinc-600 ml-auto">{executionTime}s</span>}
                  <span className="text-[10px] text-zinc-600">{steps.length} steps</span>
                </div>
                <div className="p-5">
                  <pre className="text-sm text-zinc-200 whitespace-pre-wrap leading-relaxed font-mono">{finalAnswer}</pre>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Right: Activity Feed */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="rounded-2xl glass overflow-hidden h-[calc(100vh-120px)] sticky top-20"
        >
          <div className="px-4 py-3 border-b border-zinc-800/40 flex items-center gap-3">
            <Zap className="w-4 h-4 text-cyan-400" />
            <span className="text-[11px] text-zinc-400 font-semibold tracking-wider uppercase">Activity</span>
            {isRunning && (
              <div className="ml-auto flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                <span className="text-[9px] text-cyan-400 uppercase tracking-widest">Live</span>
              </div>
            )}
            <div className="flex items-center gap-2 text-[10px]">
              <span className="text-emerald-400 font-mono">{completedSteps}</span>
              <span className="text-zinc-700">done</span>
              {failedSteps > 0 && (
                <>
                  <span className="text-red-400 font-mono">{failedSteps}</span>
                  <span className="text-zinc-700">fail</span>
                </>
              )}
            </div>
          </div>

          <div ref={feedRef} className="h-[calc(100%-48px)] overflow-y-auto p-3 space-y-2">
            {steps.length === 0 ? (
              <div className="flex items-center justify-center h-48">
                <div className="text-center space-y-3">
                  <Eye className="w-10 h-10 text-zinc-800 mx-auto" />
                  <p className="text-xs text-zinc-700 uppercase tracking-widest">No activity yet</p>
                </div>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {steps.map((step, i) => {
                  const config = ACTION_CONFIG[step.action] || ACTION_CONFIG.click;
                  const Icon = config.icon;
                  const isError = step.status === "retrying" || step.status === "failed";
                  const isDone = step.action === "done";
                  const isThinking = step.status === "thinking";
                  const isExpanded = expandedSteps.has(step.step);
                  const hasReasoning = !!(step.ai_reasoning || step.thinking);

                  return (
                    <motion.div
                      key={`${step.step}-${i}`}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                      className={`rounded-xl border p-3 transition-all duration-200 ${
                        isError ? "bg-red-950/20 border-red-500/20" :
                        isDone ? "bg-emerald-950/20 border-emerald-500/20" :
                        isThinking ? "bg-violet-950/20 border-violet-500/20" :
                        "bg-black/30 border-zinc-800/40 hover:border-zinc-700/50"
                      }`}
                    >
                      <div className="flex items-start gap-2.5">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          isError ? "bg-red-500/15" : isDone ? "bg-emerald-500/15" : isThinking ? "bg-violet-500/15" : "bg-zinc-800/60"
                        }`}>
                          <Icon className={`w-3.5 h-3.5 ${config.color}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-[10px] font-bold text-zinc-300 uppercase tracking-wider">{step.action}</span>
                            {step.duration_ms != null && <span className="text-[9px] text-zinc-600 font-mono">{step.duration_ms}ms</span>}
                            {step.model && <span className="text-[9px] text-violet-400/50 font-mono">{step.model}</span>}
                          </div>
                          {step.argument && (
                            <p className="text-[10px] text-zinc-500 font-mono truncate">{step.argument}</p>
                          )}
                          {step.observation && (
                            <div className="mt-1.5 p-2 bg-cyan-950/20 rounded-lg border border-cyan-800/15">
                              <div className="text-[8px] text-cyan-500 uppercase tracking-widest mb-0.5">Observation</div>
                              <p className="text-[9px] text-zinc-500 font-mono leading-relaxed line-clamp-2">{step.observation}</p>
                            </div>
                          )}
                          {hasReasoning && (
                            <button
                              onClick={() => setExpandedSteps((prev) => {
                                const next = new Set(prev);
                                next.has(step.step) ? next.delete(step.step) : next.add(step.step);
                                return next;
                              })}
                              className="mt-1.5 flex items-center gap-1 text-[9px] text-violet-400/60 hover:text-violet-400 transition-colors"
                            >
                              {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                              {isExpanded ? "Hide" : "Show"} reasoning
                            </button>
                          )}
                          {isExpanded && hasReasoning && (
                            <div className="mt-1.5 p-2 bg-zinc-900/60 rounded-lg border border-zinc-800/40">
                              <pre className="text-[9px] text-zinc-400 font-mono leading-relaxed whitespace-pre-wrap">{step.thinking || step.ai_reasoning}</pre>
                            </div>
                          )}
                          {step.error && <p className="text-[9px] text-red-400 mt-1 font-mono">{step.error}</p>}
                          {step.url && (
                            <div className="mt-1 flex items-center gap-1">
                              <Globe className="w-2.5 h-2.5 text-zinc-600" />
                              <span className="text-[9px] text-zinc-600 font-mono truncate">{step.url}</span>
                            </div>
                          )}
                        </div>
                        <span className="text-[9px] text-zinc-700 font-mono flex-shrink-0">#{step.step}</span>
                      </div>
                      {step.screenshot && !isThinking && (
                        <div className="mt-2">
                          <img
                            src={`data:image/png;base64,${step.screenshot}`}
                            alt={`Step ${step.step}`}
                            className="w-full h-20 object-cover rounded-lg border border-zinc-800/40"
                          />
                        </div>
                      )}
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}
