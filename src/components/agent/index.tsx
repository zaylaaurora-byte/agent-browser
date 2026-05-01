"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Globe, Brain, Zap } from "lucide-react";
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

type MobileTab = "browser" | "thinking" | "activity";

const TABS: { id: MobileTab; label: string; Icon: React.ElementType }[] = [
  { id: "browser",  label: "Browser",  Icon: Globe  },
  { id: "thinking", label: "Thinking", Icon: Brain  },
  { id: "activity", label: "Activity", Icon: Zap    },
];

export function AgentBrowser() {
  const [url, setUrl]     = useState("https://httpbin.org/forms/post");
  const [task, setTask]   = useState("Go to the page and describe what you see — identify any forms, buttons, and interactive elements.");
  const [mode, setMode]   = useState<Mode>("deep");

  const [isRunning, setIsRunning]                           = useState(false);
  const [steps, setSteps]                                   = useState<Step[]>([]);
  const [currentScreenshot, setCurrentScreenshot]           = useState<string | null>(null);
  const [finalAnswer, setFinalAnswer]                       = useState<string | null>(null);
  const [wsStatus, setWsStatus]                             = useState<"disconnected"|"connecting"|"connected">("disconnected");
  const [currentUrl, setCurrentUrl]                         = useState(url);
  const [executionTime, setExecutionTime]                   = useState<number | null>(null);
  const [latestThinking, setLatestThinking]                 = useState<string | null>(null);
  const [screenshotHistory, setScreenshotHistory]           = useState<string[]>([]);
  const [activeScreenshotIndex, setActiveScreenshotIndex]   = useState(-1);
  const [expandedSteps, setExpandedSteps]                   = useState<Set<number>>(new Set());
  const [lightboxOpen, setLightboxOpen]                     = useState(false);
  const [showShortcuts, setShowShortcuts]                   = useState(false);
  const [showSettings, setShowSettings]                     = useState(false);
  const [mobileTab, setMobileTab]                           = useState<MobileTab>("browser");

  const wsRef        = useRef<WebSocket | null>(null);
  const feedRef      = useRef<HTMLDivElement>(null);
  const thinkingRef  = useRef<HTMLDivElement>(null);
  const startRef     = useRef(0);
  const lastTaskRef  = useRef("");

  const scrollBottom = useCallback(() => {
    feedRef.current    && (feedRef.current.scrollTop    = feedRef.current.scrollHeight);
    thinkingRef.current && (thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight);
  }, []);

  useEffect(() => { scrollBottom(); }, [steps, latestThinking, scrollBottom]);
  useEffect(() => { if (isRunning) setMobileTab("browser"); }, [isRunning]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const ctrl = e.ctrlKey || e.metaKey;
      if (ctrl && e.key === "Enter") { e.preventDefault(); if (!isRunning && url && task) run(); }
      if (e.key === "Escape" && isRunning) { e.preventDefault(); stop(); }
      if (e.key === "?" && !isRunning) { e.preventDefault(); setShowShortcuts((v) => !v); }
      if (e.key === "r" && !isRunning && !ctrl) {
        const s = localStorage.getItem("ab-last-task");
        if (s) { try { const { url: u, task: t, mode: m } = JSON.parse(s); setUrl(u); setTask(t); setMode(m as Mode); } catch { /* ignore */ } }
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [isRunning, url, task]);

  const disconnect = useCallback(() => {
    wsRef.current?.close(); wsRef.current = null;
    setWsStatus("disconnected");
  }, []);

  const run = useCallback(() => {
    if (!url || !task) return;
    localStorage.setItem("ab-last-task", JSON.stringify({ url, task, mode }));
    lastTaskRef.current = task;
    disconnect();
    setIsRunning(true); setSteps([]); setCurrentScreenshot(null);
    setFinalAnswer(null); setLatestThinking(null); setCurrentUrl(url);
    setExecutionTime(null); setScreenshotHistory([]); setActiveScreenshotIndex(-1);
    setExpandedSteps(new Set());
    startRef.current = Date.now();

    const cfg = (() => {
      try { return JSON.parse(localStorage.getItem("agent-browser-settings") || "{}"); } catch { return {}; }
    })();
    const wsUrl     = cfg.backendUrl || "ws://localhost:8001/ws/agent";
    const apiKey    = cfg.apiKey    || "";
    const modelName = cfg.model     || "MiniMax-M2.7";

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    setWsStatus("connecting");

    ws.onopen = () => {
      setWsStatus("connected");
      ws.send(JSON.stringify({ url, task, mode, api_key: apiKey, model_name: modelName }));
    };
    ws.onmessage = (e) => {
      try {
        const d: Step = JSON.parse(e.data);
        d.timestamp = Date.now();
        if (d.status === "thinking") {
          setLatestThinking(d.thinking ?? d.ai_reasoning ?? null);
          if (d.screenshot) setCurrentScreenshot(d.screenshot);
        }
        if (d.status === "completed" || d.status === "snapshot") {
          setSteps((p) => [...p.filter((s) => !(s.step === d.step && s.status === "thinking")), d]);
          if (d.screenshot) { setCurrentScreenshot(d.screenshot); setScreenshotHistory((p) => [...p, d.screenshot!].slice(-20)); }
          setLatestThinking(null);
        }
        if (d.action === "done") {
          setFinalAnswer(d.answer ?? null);
          if (d.screenshot) setCurrentScreenshot(d.screenshot);
          setExecutionTime(Math.round((Date.now() - startRef.current) / 1000));
          setIsRunning(false); disconnect();
        }
        if (d.action === "error" || d.status === "failed") {
          setSteps((p) => [...p.filter((s) => !(s.step === d.step && s.status === "thinking")), d]);
          if (d.screenshot) setCurrentScreenshot(d.screenshot);
          setIsRunning(false);
          setExecutionTime(Math.round((Date.now() - startRef.current) / 1000));
        }
      } catch { /* ignore */ }
    };
    ws.onerror = ws.onclose = () => { setWsStatus("disconnected"); setIsRunning(false); };
  }, [url, task, mode, disconnect]);

  const stop = useCallback(() => {
    disconnect(); setIsRunning(false);
    setExecutionTime(Math.round((Date.now() - startRef.current) / 1000));
  }, [disconnect]);

  const completedSteps = steps.filter((s) => s.status === "completed" || s.action === "done").length;
  const failedSteps    = steps.filter((s) => s.status === "retrying" || s.status === "failed").length;

  return (
    <>
      <div className="relative z-10 max-w-screen-2xl mx-auto w-full px-3 sm:px-5 lg:px-6 pb-10">

        <TaskInput
          url={url} setUrl={setUrl} task={task} setTask={setTask}
          mode={mode} setMode={setMode} isRunning={isRunning}
          completedSteps={completedSteps} onExecute={run} onStop={stop}
          onShowSettings={() => setShowSettings(true)}
        />

        {/* Mobile tab bar */}
        <div className="tab-bar xl:hidden mb-4">
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setMobileTab(id)}
              className={`tab-btn ${mobileTab === id ? "active" : ""}`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{label}</span>
            </button>
          ))}
        </div>

        {/* Main grid */}
        <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-4 lg:gap-5">

          {/* Left */}
          <div className={`space-y-4 ${mobileTab === "activity" ? "hidden xl:block" : ""}`}>
            <div className={mobileTab === "thinking" ? "hidden xl:block" : ""}>
              <BrowserViewport
                currentScreenshot={currentScreenshot} currentUrl={currentUrl}
                mode={mode} isRunning={isRunning} wsStatus={wsStatus}
                completedSteps={completedSteps} executionTime={executionTime}
                screenshotHistory={screenshotHistory} activeScreenshotIndex={activeScreenshotIndex}
                onScreenshotClick={() => currentScreenshot && setLightboxOpen(true)}
                onThumbnailClick={(ss, i) => { setCurrentScreenshot(ss); setActiveScreenshotIndex(i); }}
              />
            </div>
            <div className={mobileTab === "browser" ? "hidden xl:block" : ""}>
              <ThinkingPanel steps={steps} latestThinking={latestThinking} isRunning={isRunning} thinkingRef={thinkingRef} />
            </div>
            <AnimatePresence>
              {finalAnswer && (
                <ResultPanel finalAnswer={finalAnswer} executionTime={executionTime} stepsCount={steps.length} />
              )}
            </AnimatePresence>
          </div>

          {/* Right */}
          <div className={mobileTab !== "activity" ? "hidden xl:block" : ""}>
            <ActivityFeed
              steps={steps} isRunning={isRunning}
              completedSteps={completedSteps} failedSteps={failedSteps}
              expandedSteps={expandedSteps} setExpandedSteps={setExpandedSteps}
              feedRef={feedRef}
            />
          </div>
        </div>
      </div>

      <AnimatePresence>
        {lightboxOpen && currentScreenshot && (
          <Lightbox screenshot={currentScreenshot} onClose={() => setLightboxOpen(false)} />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {showShortcuts && <KeyboardShortcutsOverlay onClose={() => setShowShortcuts(false)} />}
      </AnimatePresence>
      <AnimatePresence>
        {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
      </AnimatePresence>
    </>
  );
}
