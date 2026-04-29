"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";

interface AgentStep {
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

export default function Home() {
  const [url, setUrl] = useState("https://example.com");
  const [task, setTask] = useState("");
  const [mode, setMode] = useState<"fast" | "stealth">("fast");
  const [isExecuting, setIsExecuting] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<string | null>(null);
  const [finalAnswer, setFinalAnswer] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const executeTask = async () => {
    if (!url || !task) return;
    
    setIsExecuting(true);
    setSteps([]);
    setCurrentScreenshot(null);
    setFinalAnswer(null);
    
    try {
      const response = await fetch("/api/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, task, mode }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      
      setSteps((prev) => [
        ...prev,
        {
          step: data.steps_executed,
          action: "completed",
          status: "completed",
          answer: data.answer,
        },
      ]);
      
      setFinalAnswer(data.answer);
      if (data.screenshot) {
        setCurrentScreenshot(data.screenshot);
      }
    } catch (err) {
      console.error("Execution error:", err);
    } finally {
      setIsExecuting(false);
    }
  };

  // WebSocket version for real-time updates
  const executeWithSocket = async () => {
    if (!url || !task) return;
    
    setIsExecuting(true);
    setSteps([]);
    setCurrentScreenshot(null);
    setFinalAnswer(null);
    
    const ws = new WebSocket(`ws://${window.location.host}/ws/agent`);
    
    ws.onopen = () => {
      ws.send(JSON.stringify({ url, task, mode }));
    };
    
    ws.onmessage = (event) => {
      const data: AgentStep = JSON.parse(event.data);
      
      if (data.status === "completed") {
        setFinalAnswer(data.answer);
        setIsExecuting(false);
        ws.close();
      } else if (data.screenshot) {
        setCurrentScreenshot(data.screenshot);
      } else {
        setSteps((prev) => [...prev, data]);
      }
    };
    
    ws.onerror = () => {
      setIsExecuting(false);
    };
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      {/* Header */}
      <header className="border-b border-zinc-800 bg-zinc-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
            </div>
            <h1 className="text-xl font-bold bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
              Agent Browser
            </h1>
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant={mode === "stealth" ? "default" : "secondary"} className="cursor-pointer" onClick={() => setMode(mode === "fast" ? "stealth" : "fast")}>
              {mode === "fast" ? "⚡ Fast" : "🥷 Stealth"}
            </Badge>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-4 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left Panel - Input */}
        <Card className="lg:col-span-1 bg-zinc-900/50 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-lg font-medium text-zinc-300">Task Input</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Target URL</label>
              <Input 
                placeholder="https://example.com"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 focus:ring-violet-500"
              />
            </div>
            
            <div className="space-y-2">
              <label className="text-sm text-zinc-400">Task</label>
              <Textarea 
                placeholder="What do you want the agent to do?"
                value={task}
                onChange={(e) => setTask(e.target.value)}
                className="bg-zinc-800 border-zinc-700 text-zinc-100 placeholder:text-zinc-500 min-h-[120px]"
              />
            </div>
            
            <Button 
              onClick={executeWithSocket}
              disabled={isExecuting || !url || !task}
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white"
            >
              {isExecuting ? (
                <span className="flex items-center gap-2">
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Executing...
                </span>
              ) : "Execute Agent"}
            </Button>
          </CardContent>
        </Card>

        {/* Center - Browser View */}
        <Card className="lg:col-span-2 bg-zinc-900/50 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-medium text-zinc-300">Browser View</CardTitle>
            {currentScreenshot && (
              <Badge variant="outline" className="text-zinc-400">
                Screenshot
              </Badge>
            )}
          </CardHeader>
          <CardContent>
            <div className="aspect-video bg-zinc-950 rounded-lg overflow-hidden border border-zinc-800 relative">
              {currentScreenshot ? (
                <img 
                  src={`data:image/png;base64,${currentScreenshot}`}
                  alt="Browser screenshot"
                  className="w-full h-full object-contain"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-zinc-600">
                  <div className="text-center">
                    <svg className="w-16 h-16 mx-auto mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                    <p>No screenshot yet</p>
                  </div>
                </div>
              )}
              
              {/* Status overlay */}
              {isExecuting && (
                <div className="absolute inset-0 bg-zinc-950/50 flex items-center justify-center">
                  <div className="flex items-center gap-2 text-violet-400">
                    <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Agent running...
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Bottom - Activity Feed */}
        <Card className="lg:col-span-3 bg-zinc-900/50 border-zinc-800">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-medium text-zinc-300">Activity Feed</CardTitle>
            <Badge variant="secondary" className="text-zinc-400">
              {steps.length} steps
            </Badge>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[200px] pr-4">
              {steps.length === 0 ? (
                <div className="text-center text-zinc-500 py-8">
                  No activity yet. Execute a task to see the agent in action.
                </div>
              ) : (
                <div className="space-y-3">
                  {steps.map((step, i) => (
                    <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50">
                      <div className="w-6 h-6 rounded-full bg-violet-600/20 text-violet-400 flex items-center justify-center text-xs font-mono shrink-0">
                        {step.step}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <Badge 
                            variant={step.status === "completed" ? "default" : step.status === "error" || step.status === "retrying" ? "destructive" : "secondary"}
                            className="text-xs"
                          >
                            {step.action}
                          </Badge>
                          {step.argument && (
                            <span className="text-sm text-zinc-400 truncate font-mono">
                              {step.argument}
                            </span>
                          )}
                        </div>
                        {step.ai_reasoning && (
                          <p className="text-xs text-zinc-500 mt-1 line-clamp-2">
                            {step.ai_reasoning}
                          </p>
                        )}
                        {step.error && (
                          <p className="text-xs text-red-400 mt-1">
                            Error: {step.error}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
            
            {finalAnswer && (
              <>
                <Separator className="my-4 bg-zinc-800" />
                <div className="p-4 rounded-lg bg-gradient-to-r from-violet-900/30 to-indigo-900/30 border border-violet-700/30">
                  <h4 className="text-sm font-medium text-violet-300 mb-2">Final Answer</h4>
                  <p className="text-zinc-200">{finalAnswer}</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}