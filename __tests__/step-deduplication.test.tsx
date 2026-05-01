import { describe, it, expect, vi } from "vitest";
// ─── Helper: unit-test the deduplication logic directly ─────────────────────
// This extracts the step-processing logic from AgentBrowser.onmessage so we can
// test it without React/WebSocket complexity.

// Minimal Step type matching the agent types
interface Step {
  step: number;
  status: string;
  action?: string;
  observation?: string;
  thinking?: string;
  ai_reasoning?: string;
  answer?: string;
  screenshot?: string;
  timestamp?: number;
}

// Re-implements the deduplication logic from index.tsx onmessage handler
// Returns { latestThinking, steps } (matching the React state shape)
function applyStepDeduplication(
  prevSteps: Step[],
  newStep: Step
): { latestThinking: string | null; steps: Step[]; finalAnswer: string | null } {
  const latestThinking = newStep.status === "thinking"
    ? (newStep.thinking ?? newStep.ai_reasoning ?? null)
    : null;

  let steps = [...prevSteps];
  let finalAnswer: string | null = null;

  if (newStep.status === "thinking") {
    // Remove any existing thinking entry for this step# (replace-in-place)
    steps = steps.filter((s) => !(s.step === newStep.step && s.status === "thinking"));
    steps.push(newStep);
  } else if (newStep.status === "completed" || newStep.status === "snapshot") {
    // Remove thinking entry for this step, then add the completed one
    steps = steps.filter((s) => !(s.step === newStep.step && s.status === "thinking"));
    steps.push(newStep);
  } else if (newStep.action === "done") {
    finalAnswer = newStep.answer ?? null;
  } else if (newStep.action === "error" || newStep.status === "failed") {
    steps = steps.filter((s) => !(s.step === newStep.step && s.status === "thinking"));
    steps.push(newStep);
  }

  return { latestThinking, steps, finalAnswer };
}

// ─── BUG-03: Step deduplication ─────────────────────────────────────────────
// The bug: thinking + completed messages for the same step# were both added
// to the steps array, showing duplicate "#1" entries in the activity feed.
describe("BUG-03: Step deduplication logic", () => {
  it("thinking message adds to steps array (bug behavior — thinking IS in steps)", () => {
    const result = applyStepDeduplication([], {
      step: 1, status: "thinking", thinking: "planning...", action: "navigate",
    });
    // The thinking message IS added to steps (per the code — it's the completed
    // filtering that removes the thinking, not the thinking addition itself)
    expect(result.steps).toHaveLength(1);
    expect(result.steps[0].status).toBe("thinking");
  });

  it("completed message REMOVES thinking entry for same step# and adds completed entry", () => {
    // Start with thinking already in steps
    const withThinking: Step[] = [
      { step: 1, status: "thinking", thinking: "planning...", action: "navigate" },
    ];

    const result = applyStepDeduplication(withThinking, {
      step: 1, status: "completed", action: "navigate", observation: "navigated to form",
    });

    // Thinking should be gone
    const thinkingEntries = result.steps.filter(
      (s) => s.step === 1 && s.status === "thinking"
    );
    expect(thinkingEntries).toHaveLength(0);

    // Completed should be present
    const completedEntries = result.steps.filter(
      (s) => s.step === 1 && s.status === "completed"
    );
    expect(completedEntries).toHaveLength(1);
    expect(completedEntries[0].observation).toBe("navigated to form");

    // Total entries for step 1 should be exactly 1 (not 2 — that's the bug)
    const step1Entries = result.steps.filter((s) => s.step === 1);
    expect(step1Entries).toHaveLength(1);
  });

  it("separate step numbers produce separate entries", () => {
    const after1 = applyStepDeduplication([], {
      step: 1, status: "completed", action: "navigate", observation: "done",
    });
    const after2 = applyStepDeduplication(after1.steps, {
      step: 2, status: "completed", action: "click", observation: "clicked",
    });

    expect(after2.steps).toHaveLength(2);
    expect(after2.steps.map((s) => s.step)).toEqual([1, 2]);
  });

  it("done action sets finalAnswer and does not add to steps", () => {
    const result = applyStepDeduplication([], {
      step: 1, action: "done", answer: "All tasks completed!",
    });

    expect(result.finalAnswer).toBe("All tasks completed!");
    expect(result.steps).toHaveLength(0);
  });

  it("failed status removes thinking and adds failed entry", () => {
    const withThinking: Step[] = [
      { step: 1, status: "thinking", thinking: "trying...", action: "click" },
    ];

    const result = applyStepDeduplication(withThinking, {
      step: 1, status: "failed", action: "click", observation: "element not found",
    });

    // Thinking removed
    expect(result.steps.filter((s) => s.status === "thinking")).toHaveLength(0);
    // Failed added
    const failed = result.steps.find((s) => s.status === "failed");
    expect(failed?.observation).toBe("element not found");
    // Only 1 entry for step 1
    expect(result.steps.filter((s) => s.step === 1)).toHaveLength(1);
  });

  it("BUG-03 regression: thinking+completed for same step# does NOT produce 2 entries", () => {
    // Simulate the exact sequence that triggered the bug:
    // step 1 thinking arrives → step 1 completed arrives
    const afterThinking = applyStepDeduplication([], {
      step: 1, status: "thinking", thinking: "planning...", action: "navigate",
    });
    const afterCompleted = applyStepDeduplication(afterThinking.steps, {
      step: 1, status: "completed", action: "navigate", observation: "done",
    });

    // The bug produced 2 entries for step 1. After fix: only 1.
    const step1Entries = afterCompleted.steps.filter((s) => s.step === 1);
    expect(step1Entries).toHaveLength(1);
    expect(step1Entries[0].status).toBe("completed");
  });

  it("thinking updates latestThinking state field", () => {
    const result = applyStepDeduplication([], {
      step: 1, status: "thinking", thinking: "analyzing page...",
    });
    expect(result.latestThinking).toBe("analyzing page...");
  });

  it("completed clears latestThinking", () => {
    const result = applyStepDeduplication([], {
      step: 1, status: "completed", action: "navigate", observation: "ok",
    });
    expect(result.latestThinking).toBeNull();
  });

  it("snapshot message removes thinking and adds snapshot entry", () => {
    const withThinking: Step[] = [
      { step: 1, status: "thinking", thinking: "waiting...", action: "wait" },
    ];
    const result = applyStepDeduplication(withThinking, {
      step: 1, status: "snapshot", action: "wait", observation: "waited 5s",
    });

    expect(result.steps.filter((s) => s.step === 1 && s.status === "thinking")).toHaveLength(0);
    expect(result.steps.find((s) => s.step === 1 && s.status === "snapshot")).toBeDefined();
    expect(result.steps.filter((s) => s.step === 1)).toHaveLength(1);
  });
});
