"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { TaskInput, type Mode } from "./task-input";
import { BrowserViewport } from "./browser-viewport";
import { ActivityFeed } from "./activity-feed";
import { ThinkingPanel } from "./thinking-panel";

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

export function AgentBrowser() {
  const [url, setUrl] = useState("https://httpbin.org/forms/post");
  const [task, setTask] = useState(
    "Fill and submit the pizza order form: Type John Connor in name, 07123456789 in phone, john@example.com in email. Select Large pizza size. Check Bacon topping. Click Submit. Report the result page."
  );
  const [mode, setMode] = useState<Mode>("deep");
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<string | null>(null);
  const [finalAnswer, setFinalAnswer] = useState<string | null>(null);
  const [maxSteps] = useState(500);
  const [wsStatus, setWsStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [currentUrl, setCurrentUrl] = useState("https://httpbin.org/forms/post");
  const [executionTime, setExecutionTime] = useState<number | null>(null);
  const [latestThinking, setLatestThinking] = useState<string | null>(null);
  const [thinkingHistory, setThinkingHistory] = useState<string[]>([]);
  const [screenshotHistory, setScreenshotHistory] = useState<string[]>([]);
  const [activeScreenshotIndex, setActiveScreenshotIndex] = useState<number>(-1);
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());
  const [latestStepUrl, setLatestStepUrl] = useState<string | undefined>(undefined);
  const [latestModel, setLatestModel] = useState<string | undefined>(undefined);
  const [latestDuration, setLatestDuration] = useState<number | undefined>(undefined);

  const wsRef = useRef<WebSocket | null>(null);
  const startTimeRef = useRef<number>(0);

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
    setCurrentUrl(url);
    setExecutionTime(null);
    setLatestThinking(null);
    setThinkingHistory([]);
    setScreenshotHistory([]);
    setActiveScreenshotIndex(-1);
    setExpandedSteps(new Set());
    setLatestStepUrl(undefined);
    setLatestModel(undefined);
    setLatestDuration(undefined);
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

        if (data.model) setLatestModel(data.model);
        if (data.duration_ms != null) setLatestDuration(data.duration_ms);
        if (data.url) setLatestStepUrl(data.url);

        // Handle thinking step
        if (data.status === "thinking") {
          setLatestThinking(data.thinking ?? data.ai_reasoning ?? null);
          if (data.thinking) {
            setThinkingHistory((prev) => {
              const updated = [...prev, data.thinking!];
              return updated.slice(-30);
            });
          }
          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
          }
        }

        // Handle completed action
        if (data.status === "completed" || data.status === "snapshot") {
          setSteps((prev) => {
            const withoutDupe = prev.filter(
              (s) => !(s.step === data.step && s.status === "thinking")
            );
            return [...withoutDupe, data];
          });

          if (data.screenshot) {
            setCurrentScreenshot(data.screenshot);
            setScreenshotHistory((prev) => {
              const updated = [...prev, data.screenshot!];
              return updated.slice(-20);
            });
            setActiveScreenshotIndex(-1); // will be set by length
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
            const withoutDupe = prev.filter(
              (s) => !(s.step === data.step && s.status === "thinking")
            );
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
  }, [url, task, mode, disconnectWs]);

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

  const handleScreenshotSelect = (ss: string, index: number) => {
    setCurrentScreenshot(ss);
    setActiveScreenshotIndex(index);
  };

  // Computed stats
  const completedSteps = steps.filter(
    (s) => s.status === "completed" || s.action === "done"
  ).length;
  const failedSteps = steps.filter(
    (s) => s.status === "retrying" || s.status === "failed"
  ).length;
  const latestStep = steps[steps.length - 1];

  // Update active screenshot index based on history
  const effectiveScreenshotIndex =
    activeScreenshotIndex === -1 ? screenshotHistory.length - 1 : activeScreenshotIndex;

  return (
    <div className="relative z-10 max-w-[1920px] mx-auto w-full px-4 pb-8">
      {/* ─── Status Bar ─── */}
      {(isRunning || completedSteps > 0) && (
        <div className="flex items-center justify-center gap-4 mb-4">
          {/* WS Status */}
          <div className="flex items-center gap-2 glass-card-sm px-3 py-1.5">
            <div
              className={`w-1.5 h-1.5 rounded-full transition-colors duration-300 ${
                wsStatus === "connected"
                  ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                  : wsStatus === "connecting"
                  ? "bg-amber-400 animate-pulse"
                  : "bg-zinc-600"
              }`}
            />
            <span className="text-[9px] text-zinc-500 uppercase tracking-widest">
              {wsStatus === "connected" ? "LIVE" : wsStatus === "connecting" ? "CONNECTING" : "IDLE"}
            </span>
          </div>

          {/* Model */}
          {latestModel && (
            <div className="flex items-center gap-1.5 glass-card-sm px-3 py-1.5">
              <span className="text-[9px] text-violet-400/60">🧠</span>
              <span className="text-[9px] text-violet-400 font-bold tracking-wide">
                {latestModel}
              </span>
            </div>
          )}

          {/* Timer */}
          {isRunning && executionTime === null && (
            <div className="flex items-center gap-1.5 glass-card-sm px-3 py-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
              <span className="text-[9px] text-zinc-500 uppercase tracking-widest">Running</span>
            </div>
          )}

          {executionTime !== null && (
            <div className="glass-card-sm px-3 py-1.5">
              <span className="text-[9px] text-emerald-400 uppercase tracking-widest">
                {executionTime}s
              </span>
            </div>
          )}

          {/* Step counter */}
          {(isRunning || completedSteps > 0) && (
            <div className="flex items-center gap-2 glass-card-sm px-3 py-1.5">
              <span className="text-[9px] text-zinc-500 uppercase tracking-widest">Steps</span>
              <span className="text-sm font-bold text-white tabular-nums">{completedSteps}</span>
              <span className="text-[9px] text-zinc-600">/ {maxSteps}</span>
              {failedSteps > 0 && (
                <>
                  <span className="text-[9px] text-red-400">{failedSteps}</span>
                  <span className="text-[8px] text-zinc-600">fail</span>
                </>
              )}
            </div>
          )}

          {/* Progress bar */}
          {isRunning && (
            <div className="flex-1 max-w-xs h-[2px] bg-white/[0.04] rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-violet-600 via-fuchsia-500 to-cyan-500"
                initial={{ width: "0%" }}
                animate={{
                  width: `${Math.min((completedSteps / maxSteps) * 100, 100)}%`,
                }}
                transition={{ duration: 0.5, ease: "easeOut" }}
              />
            </div>
          )}
        </div>
      )}

      {/* ─── 3-Column Layout ─── */}
      <div className="grid grid-cols-1 xl:grid-cols-[380px_1fr_360px] gap-4 min-h-[calc(100vh-200px)]">
        {/* LEFT — Task Input */}
        <TaskInput
          url={url}
          setUrl={setUrl}
          task={task}
          setTask={setTask}
          mode={mode}
          setMode={setMode}
          isRunning={isRunning}
          onExecute={runTask}
          onStop={stopTask}
        />

        {/* CENTER — Viewport + Thinking + Answer */}
        <div className="space-y-4">
          <BrowserViewport
            currentScreenshot={currentScreenshot}
            currentUrl={currentUrl}
            targetUrl={url}
            isRunning={isRunning}
            mode={mode}
            completedSteps={completedSteps}
            screenshotHistory={screenshotHistory}
            activeScreenshotIndex={effectiveScreenshotIndex}
            onScreenshotSelect={handleScreenshotSelect}
            latestStepUrl={latestStepUrl}
          />

          <ThinkingPanel
            thinkingHistory={thinkingHistory}
            isRunning={isRunning}
            latestThinking={latestThinking}
            model={latestModel}
            durationMs={latestDuration}
          />

          {/* Final Answer */}
          <AnimatePresence>
            {finalAnswer && (
              <motion.div
                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="glass-card overflow-hidden border-emerald-500/20 glow-emerald"
              >
                <div className="px-4 py-3 border-b border-emerald-500/10 flex items-center gap-2">
                  <span className="text-sm">✅</span>
                  <span className="text-[10px] text-emerald-400 uppercase tracking-[0.2em] font-semibold">
                    Agent Result
                  </span>
                  {executionTime !== null && (
                    <span className="text-[9px] text-zinc-600 ml-auto uppercase tracking-widest">
                      {executionTime}s
                    </span>
                  )}
                  {steps.length > 0 && (
                    <span className="text-[9px] text-zinc-600 uppercase tracking-widest">
                      {steps.length} steps
                    </span>
                  )}
                </div>
                <div className="p-5">
                  <pre className="text-[13px] text-zinc-200 whitespace-pre-wrap leading-relaxed font-mono">
                    {finalAnswer}
                  </pre>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* RIGHT — Activity Feed */}
        <ActivityFeed
          steps={steps}
          isRunning={isRunning}
          expandedSteps={expandedSteps}
          onToggleExpanded={toggleExpanded}
        />
      </div>
    </div>
  );
}
