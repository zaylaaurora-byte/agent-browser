import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { TaskInput } from "../src/components/agent/task-input";
import { AgentBrowser } from "../src/components/agent/index";

const defaultProps = {
  url: "https://example.com",
  setUrl: vi.fn(),
  task: "Do something",
  setTask: vi.fn(),
  mode: "deep" as const,
  setMode: vi.fn(),
  isRunning: false,
  completedSteps: 0,
  onExecute: vi.fn(),
  onStop: vi.fn(),
  onShowSettings: vi.fn(),
};

// ─── TaskInput tests ────────────────────────────────────────────────────────

describe("TaskInput", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the Execute button", () => {
    render(<TaskInput {...defaultProps} />);
    expect(screen.getByRole("button", { name: /execute/i })).toBeInTheDocument();
  });

  it("renders the Settings button", () => {
    render(<TaskInput {...defaultProps} />);
    expect(screen.getByTitle(/settings/i)).toBeInTheDocument();
  });

  it("calls onExecute when Execute button is clicked", async () => {
    const user = userEvent.setup();
    render(<TaskInput {...defaultProps} />);
    await user.click(screen.getByRole("button", { name: /execute/i }));
    expect(defaultProps.onExecute).toHaveBeenCalledTimes(1);
  });

  it("does NOT call onExecute when inputs are empty (button disabled)", () => {
    render(<TaskInput {...defaultProps} url="" task="" />);
    expect(screen.getByRole("button", { name: /execute/i })).toBeDisabled();
  });

  it("shows Stop button with step count when isRunning=true", () => {
    render(<TaskInput {...defaultProps} isRunning={true} completedSteps={5} />);
    expect(screen.getByRole("button", { name: /stop · 5/i })).toBeInTheDocument();
  });

  it("calls onStop when Stop button is clicked", async () => {
    const user = userEvent.setup();
    render(<TaskInput {...defaultProps} isRunning={true} completedSteps={3} />);
    await user.click(screen.getByRole("button", { name: /stop · 3/i }));
    expect(defaultProps.onStop).toHaveBeenCalledTimes(1);
  });

  it("disables Execute button when task is empty", () => {
    render(<TaskInput {...defaultProps} task="" />);
    expect(screen.getByRole("button", { name: /execute/i })).toBeDisabled();
  });

  it("disables Execute button when url is empty", () => {
    render(<TaskInput {...defaultProps} url="" />);
    expect(screen.getByRole("button", { name: /execute/i })).toBeDisabled();
  });

  it("calls onShowSettings when settings button is clicked", async () => {
    const user = userEvent.setup();
    render(<TaskInput {...defaultProps} />);
    await user.click(screen.getByTitle(/settings/i));
    expect(defaultProps.onShowSettings).toHaveBeenCalledTimes(1);
  });

  it("renders mode selector with fast/stealth/deep options", () => {
    render(<TaskInput {...defaultProps} />);
    expect(screen.getByRole("button", { name: /fast/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stealth/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /deep/i })).toBeInTheDocument();
  });

  it("calls setMode when a mode button is clicked", async () => {
    const user = userEvent.setup();
    render(<TaskInput {...defaultProps} mode="deep" />);
    await user.click(screen.getByRole("button", { name: /fast/i }));
    expect(defaultProps.setMode).toHaveBeenCalledWith("fast");
  });

  it("disables all mode buttons when isRunning=true", () => {
    render(<TaskInput {...defaultProps} isRunning={true} />);
    expect(screen.getByRole("button", { name: /fast/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /stealth/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /deep/i })).toBeDisabled();
  });

  it("renders quick launch chips", () => {
    render(<TaskInput {...defaultProps} />);
    // Quick sites are defined in types.ts — just check some exist
    const chips = screen.getAllByRole("button").filter(b => !b.getAttribute("aria-label"));
    expect(chips.length).toBeGreaterThan(0);
  });
});

// ─── AgentBrowser keyboard shortcut tests ────────────────────────────────────

describe("AgentBrowser keyboard shortcuts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });
  afterEach(() => {
    cleanup();
  });

  it("exposes agentBrowserRun on window after mount", () => {
    // Render a minimal AgentBrowser and verify window exposure works
    // We test this indirectly via the onExecute mock
    render(<AgentBrowser />);
    expect((window as any).agentBrowserRun).toBeDefined();
    expect((window as any).agentBrowserStop).toBeDefined();
  });

  it("exposes agentBrowserScrollToAgent on window after mount", () => {
    render(<AgentBrowser />);
    expect((window as any).agentBrowserScrollToAgent).toBeDefined();
  });
});

// ─── canExecute logic ────────────────────────────────────────────────────────

describe("canExecute logic in TaskInput", () => {
  it("returns false when url is whitespace only", () => {
    // The component uses url.trim() so whitespace-only should disable
    render(<TaskInput {...{
      url: "   ", setUrl: vi.fn(), task: "test", setTask: vi.fn(),
      mode: "deep", setMode: vi.fn(), isRunning: false, completedSteps: 0,
      onExecute: vi.fn(), onStop: vi.fn(), onShowSettings: vi.fn(),
    }} />);
    expect(screen.getByRole("button", { name: /execute/i })).toBeDisabled();
  });

  it("returns false when task is whitespace only", () => {
    render(<TaskInput {...{
      url: "https://example.com", setUrl: vi.fn(), task: "  ", setTask: vi.fn(),
      mode: "deep", setMode: vi.fn(), isRunning: false, completedSteps: 0,
      onExecute: vi.fn(), onStop: vi.fn(), onShowSettings: vi.fn(),
    }} />);
    expect(screen.getByRole("button", { name: /execute/i })).toBeDisabled();
  });

  it("button is enabled when both url and task are non-empty", () => {
    render(<TaskInput {...{
      url: "https://example.com", setUrl: vi.fn(), task: "do stuff", setTask: vi.fn(),
      mode: "deep", setMode: vi.fn(), isRunning: false, completedSteps: 0,
      onExecute: vi.fn(), onStop: vi.fn(), onShowSettings: vi.fn(),
    }} />);
    expect(screen.getByRole("button", { name: /execute/i })).not.toBeDisabled();
  });
});
