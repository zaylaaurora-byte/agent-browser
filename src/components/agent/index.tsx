"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Square } from "lucide-react";
import { TaskInput } from "./task-input";
import { BrowserViewport } from "./browser-viewport";
import { ThinkingPanel } from "./thinking-panel";
import { ActivityFeed } from "./activity-feed";
import { ResultPanel } from "./result-panel";
import { Lightbox } from "./lightbox";
import { KeyboardShortcutsOverlay } from "./keyboard-shortcuts";
import { SettingsModal } from "./settings-modal";
import type { Step, Mode } from "./types";

export { QUICK_SITES } from "./types";

export function AgentBrowser() {
  const [url, setUrl]           = useState("https://httpbin.org/forms/post");
  const [task, setTask]         = useState(
    "Go to the page and describe what you see — identify any forms, buttons, and interactive elements."
  );
  const [mode, setMode]         = useState<Mode>("deep");
  const [isRunning, setIsRunning]         = useState(false);
  const [steps, setSteps]                   = useState<Step[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<string | null>(null);
  const [finalAnswer, setFinalAnswer]       = useState<string | null>(null);
  const [wsStatus, setWsStatus]             = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const [currentUrl, setCurrentUrl]         = useState(url);
  const [executionTime, setExecutionTime]  = useState<number | null>(null);
  const [latestThinking, setLatestThinking] = useState<string | null>(null);
  const [screenshotHistory, setScreenshotHistory] = useState<string[]>([]);
  const [activeScreenshotIndex, setActiveScreenshotIndex] = useState<number>(-1);
  const [expandedSteps, setExpandedSteps]   = useState<Set<number>>(new Set());
  const [lightboxOpen, setLightboxOpen]     = useState(false);
  const [showShortcuts, setShowShortcuts]   = useState(false);
  const [showSettings, setShowSettings]     = useState(false);

  const wsRef               = useRef<WebSocket | null>(null);
  const feedRef             = useRef<HTMLDivElement>(null);
  const thinkingRef          = useRef<HTMLDivElement>(null);
  const startTimeRef         = useRef<number>(0);
  const lastTaskRef          = useRef<string>("");

  const scrollToBottom = useCallback(() => {
    if (feedRef.current)     feedRef.current.scrollTop     = feedRef.current.scrollHeight;
    if (thinkingRef.current) thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
  }, []);

  useEffect(() => { scrollToBottom(); }, [steps, latestThinking, scrollToBottom]);

  // ─── Keyboard shortcuts ───────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;

      // Cmd/Ctrl + Enter → execute
      if (ctrl && e.key === "Enter") {
        e.preventDefault();
        if (!isRunning && url && task) runTask();
      }
      // Escape → stop
      if (e.key === "Escape" && isRunning) {
        e.preventDefault();
        stopTask();
      }
      // ? → shortcuts overlay
      if (e.key === "?" && !isRunning) {
        e.preventDefault();
        setShowShortcuts((v) => !v);
      }
      // r → replay last task
      if (e.key === "r" && !isRunning && !e.ctrlKey && !e.metaKey && lastTaskRef.current) {
        const stored = localStorage.getItem("agent-browser-last-task");
        if (stored) {
          try {
            const { url: lu, task: lt, mode: lm } = JSON.parse(stored);
            setUrl(lu); setTask(lt); setMode(lm as Mode);
          } catch { /* ignore */ }
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isRunning, url, task]);

  const disconnectWs = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    setWsStatus("disconnected");
  }, []);

  const runTask = useCallback(async () => {
    if (!url || !task) return;
    // Persist last task for replay
    localStorage.setItem("agent-browser-last-task", JSON.stringify({ url, task, mode }));
    lastTaskRef.current = task;

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

    // Read backendUrl + credentials from settings
    const defaultWsUrl = "ws://localhost:8001/ws/agent";
    const stored = localStorage.getItem("agent-browser-settings");
    let wsUrl = defaultWsUrl;
    let apiKey = "";
    let modelName = "MiniMax-M2.7";
    if (stored) {
      try {
        const cfg = JSON.parse(stored);
        wsUrl = cfg.backendUrl || defaultWsUrl;
        apiKey = cfg.apiKey || "";
        modelName = cfg.model || "MiniMax-M2.7";
      } catch { /* ignore */ }
    }

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      setWsStatus("connected");
      ws.send(JSON.stringify({ url, task, mode, api_key: apiKey, model_name: modelName }));
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
          setIsRunning(false);
          setExecutionTime(Math.round((Date.now() - startTimeRef.current) / 1000));
        }
      } catch { /* ignore */ }
    };

    ws.onerror = () => { setWsStatus("disconnected"); setIsRunning(false); };
    ws.onclose = () => { setWsStatus("disconnected"); setIsRunning(false); };
  }, [url, task, mode, disconnectWs]);

  const stopTask = useCallback(() => {
    disconnectWs();
    setIsRunning(false);
    setExecutionTime(Math.round((Date.now() - startTimeRef.current) / 1000));
  }, [disconnectWs]);

  const replayLast = useCallback(() => {
    const stored = localStorage.getItem("agent-browser-last-task");
    if (!stored) return;
    try {
      const { url: lu, task: lt, mode: lm } = JSON.parse(stored);
      setUrl(lu); setTask(lt); setMode(lm as Mode);
    } catch { /* ignore */ }
  }, []);

  const openLightbox = useCallback(() => {
    if (currentScreenshot) setLightboxOpen(true);
  }, [currentScreenshot]);

  const completedSteps = steps.filter((s) => s.status === "completed" || s.action === "done").length;
  const failedSteps     = steps.filter((s) => s.status === "retrying" || s.status === "failed").length;

  return (
    <>
      <div className="relative z-10 max-w-[1920px] mx-auto w-full px-6 pb-12">

        {/* Task Input Bar */}
        <TaskInput
          url={url} setUrl={setUrl}
          task={task} setTask={setTask}
          mode={mode} setMode={setMode}
          isRunning={isRunning}
          completedSteps={completedSteps}
          onExecute={runTask}
          onStop={stopTask}
          onShowSettings={() => setShowSettings(true)}
        />

        {/* Main 3-column layout */}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-6">
          {/* Left column */}
          <div className="space-y-6">
            <BrowserViewport
              currentScreenshot={currentScreenshot}
              currentUrl={currentUrl}
              mode={mode}
              isRunning={isRunning}
              wsStatus={wsStatus}
              completedSteps={completedSteps}
              executionTime={executionTime}
              screenshotHistory={screenshotHistory}
              activeScreenshotIndex={activeScreenshotIndex}
              onScreenshotClick={openLightbox}
              onThumbnailClick={(ss, i) => { setCurrentScreenshot(ss); setActiveScreenshotIndex(i); }}
            />

            <ThinkingPanel
              steps={steps}
              latestThinking={latestThinking}
              isRunning={isRunning}
              thinkingRef={thinkingRef}
            />

            <AnimatePresence>
              {finalAnswer && (
                <ResultPanel
                  finalAnswer={finalAnswer}
                  executionTime={executionTime}
                  stepsCount={steps.length}
                />
              )}
            </AnimatePresence>
          </div>

          {/* Right column */}
          <ActivityFeed
            steps={steps}
            isRunning={isRunning}
            completedSteps={completedSteps}
            failedSteps={failedSteps}
            expandedSteps={expandedSteps}
            setExpandedSteps={setExpandedSteps}
            feedRef={feedRef}
          />
        </div>
      </div>

      {/* Modals */}
      <AnimatePresence>
        {lightboxOpen && currentScreenshot && (
          <Lightbox
            screenshot={currentScreenshot}
            onClose={() => setLightboxOpen(false)}
          />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showShortcuts && (
          <KeyboardShortcutsOverlay onClose={() => setShowShortcuts(false)} />
        )}
      </AnimatePresence>

      <AnimatePresence>
        {showSettings && (
          <SettingsModal onClose={() => setShowSettings(false)} />
        )}
      </AnimatePresence>
    </>
  );
}
