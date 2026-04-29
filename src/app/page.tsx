"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

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
}

type Mode = "fast" | "stealth";

export default function Home() {
  const [url, setUrl] = useState("https://example.com");
  const [task, setTask] = useState("What text is visible on this page?");
  const [mode, setMode] = useState<Mode>("fast");
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [currentUrl, setCurrentUrl] = useState("");
  const feedRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [steps, scrollToBottom]);

  const runTask = async () => {
    if (!url || !task || isRunning) return;

    setIsRunning(true);
    setSteps([]);
    setScreenshot(null);
    setAnswer(null);
    setCurrentUrl(url);

    // Connect directly to backend WebSocket (Next.js can't proxy WS)
    const wsUrl = `ws://localhost:8001/ws/agent`;

    try {
      const ws = new WebSocket(wsUrl);

      const wsTimeout = setTimeout(() => {
        ws.close();
        // Fallback to REST
        runRestTask();
      }, 3000);

      ws.onopen = () => {
        clearTimeout(wsTimeout);
        setConnected(true);
        ws.send(JSON.stringify({ url, task, mode }));
      };

      ws.onmessage = (event) => {
        const data: Step = JSON.parse(event.data);

        if (data.status === "completed") {
          setAnswer(data.answer ?? null);
          if (data.screenshot) setScreenshot(data.screenshot);
          setIsRunning(false);
          setConnected(false);
          ws.close();
          return;
        }

        if (data.screenshot) {
          setScreenshot(data.screenshot);
        } else if (data.status === "snapshot") {
          if (data.screenshot) setScreenshot(data.screenshot);
          if (data.url) setCurrentUrl(data.url);
        } else {
          setSteps((prev) => [...prev, data]);
        }
      };

      ws.onerror = () => {
        clearTimeout(wsTimeout);
        setConnected(false);
        ws.close();
        runRestTask();
      };

      ws.onclose = () => {
        setConnected(false);
      };
    } catch {
      runRestTask();
    }
  };

  const runRestTask = async () => {
    try {
      const res = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, task, mode }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      setSteps((prev) => [
        ...prev,
        {
          step: data.steps_executed,
          action: "completed",
          status: data.status,
          answer: data.answer,
        },
      ]);

      setAnswer(data.answer);
      if (data.screenshot) setScreenshot(data.screenshot);
    } catch (err) {
      setSteps((prev) => [
        ...prev,
        { step: 0, action: "error", status: "failed", error: String(err) },
      ]);
    } finally {
      setIsRunning(false);
    }
  };

  const actionIcons: Record<string, string> = {
    navigate: "🌐",
    click: "👆",
    type: "⌨️",
    scroll: "📜",
    wait: "⏳",
    screenshot: "📸",
    done: "✅",
    error: "❌",
    thinking: "🧠",
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800/50 bg-zinc-900/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center text-sm font-bold">
              A
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight">Agent Browser</h1>
              <p className="text-[10px] text-zinc-500 leading-none">AI-Powered Automation</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {connected && (
              <Badge variant="outline" className="text-emerald-400 border-emerald-400/30 text-xs animate-pulse">
                ● Live
              </Badge>
            )}
            <button
              onClick={() => setMode(mode === "fast" ? "stealth" : "fast")}
              className="px-3 py-1.5 text-xs rounded-full border border-zinc-700 bg-zinc-800/50 hover:bg-zinc-700/50 transition-colors"
            >
              {mode === "fast" ? "⚡ Fast" : "🥷 Stealth"}
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[1600px] mx-auto w-full p-4 grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
        {/* Sidebar */}
        <div className="space-y-4">
          <Card className="bg-zinc-900/50 border-zinc-800/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-zinc-400">Task</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <label className="text-xs text-zinc-500 mb-1 block">URL</label>
                <Input
                  placeholder="https://example.com"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="bg-zinc-800/50 border-zinc-700/50 text-sm h-9 focus:ring-violet-500/50"
                />
              </div>

              <div>
                <label className="text-xs text-zinc-500 mb-1 block">Instructions</label>
                <Textarea
                  placeholder="What should the agent do?"
                  value={task}
                  onChange={(e) => setTask(e.target.value)}
                  className="bg-zinc-800/50 border-zinc-700/50 text-sm min-h-[100px] resize-none focus:ring-violet-500/50"
                />
              </div>

              <Button
                onClick={runTask}
                disabled={isRunning || !url || !task}
                className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-40 h-10 text-sm font-medium"
              >
                {isRunning ? (
                  <span className="flex items-center gap-2">
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Running...
                  </span>
                ) : (
                  "Execute Agent"
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Activity Feed */}
          <Card className="bg-zinc-900/50 border-zinc-800/50">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-medium text-zinc-400">Activity</CardTitle>
                <Badge variant="secondary" className="text-[10px] bg-zinc-800">{steps.length} steps</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div ref={feedRef} className="h-[300px] overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                {steps.length === 0 ? (
                  <p className="text-xs text-zinc-600 text-center py-8">
                    Execute a task to see agent activity
                  </p>
                ) : (
                  steps.map((step, i) => (
                    <div
                      key={i}
                      className={`p-2 rounded-md border text-xs ${
                        step.status === "failed" || step.status === "retrying"
                          ? "bg-red-950/20 border-red-900/30"
                          : step.status === "completed"
                          ? "bg-emerald-950/20 border-emerald-900/30"
                          : "bg-zinc-800/30 border-zinc-700/30"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{actionIcons[step.action] || "•"}</span>
                        <span className="font-mono text-zinc-300">{step.action}</span>
                        {step.argument && (
                          <span className="text-zinc-500 truncate">{step.argument}</span>
                        )}
                      </div>
                      {step.error && (
                        <p className="text-red-400 mt-1 pl-6">{step.error}</p>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content — Browser View */}
        <div className="space-y-4">
          {/* Browser chrome */}
          <Card className="bg-zinc-900/50 border-zinc-800/50 overflow-hidden">
            <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900 border-b border-zinc-800/50">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-zinc-700" />
                <div className="w-3 h-3 rounded-full bg-zinc-700" />
                <div className="w-3 h-3 rounded-full bg-zinc-700" />
              </div>
              <div className="flex-1 mx-2">
                <div className="bg-zinc-800 rounded-md px-3 py-1 text-xs text-zinc-400 truncate font-mono">
                  {isRunning ? currentUrl || url : url}
                </div>
              </div>
              {isRunning && (
                <Badge variant="outline" className="text-violet-400 border-violet-400/30 text-[10px] animate-pulse">
                  Agent Active
                </Badge>
              )}
            </div>

            {/* Screenshot viewport */}
            <div className="aspect-video bg-zinc-950 relative">
              {screenshot ? (
                <img
                  src={`data:image/png;base64,${screenshot}`}
                  alt="Browser"
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="text-center space-y-3">
                    <div className="w-16 h-16 mx-auto rounded-2xl bg-zinc-800/50 flex items-center justify-center">
                      <svg className="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <p className="text-xs text-zinc-600">Browser view will appear here</p>
                  </div>
                </div>
              )}

              {/* Running overlay */}
              {isRunning && !screenshot && (
                <div className="absolute inset-0 bg-zinc-950/80 flex items-center justify-center">
                  <div className="flex items-center gap-3 text-violet-400">
                    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <span className="text-sm">Starting browser...</span>
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Answer */}
          {answer && (
            <Card className="bg-gradient-to-r from-violet-950/30 to-indigo-950/30 border-violet-800/30">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-violet-600/20 flex items-center justify-center text-violet-400 text-xs shrink-0 mt-0.5">
                    ✦
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-violet-300 mb-1">Answer</h3>
                    <p className="text-sm text-zinc-200 leading-relaxed">{answer}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}