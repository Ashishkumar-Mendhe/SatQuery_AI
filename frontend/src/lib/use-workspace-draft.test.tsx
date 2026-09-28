import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds } from "./aoi";
import { useWorkspaceDraft } from "./use-workspace-draft";
import { serializeWorkspaceDraft, WORKSPACE_DRAFT_STORAGE_KEY } from "./workspace-draft-storage";

describe("useWorkspaceDraft", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    window.localStorage.clear();
  });

  it("initializes with default clean state when no draft exists", () => {
    const { result } = renderHook(() => useWorkspaceDraft({ selectedAoi: null }));

    expect(result.current.analysisMode).toBe("visual_question_answering");
    expect(result.current.questionDraft).toBe("");
    expect(result.current.dateRange).toBeNull();
    expect(result.current.persistenceState).toBe("empty");
    expect(result.current.isRestored).toBe(false);
  });

  it("restores an existing valid workspace draft on mount", () => {
    const sampleAoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.1]);
    const stored = serializeWorkspaceDraft({
      analysisMode: "spectral_analysis",
      questionDraft: "Inspect vegetation canopy",
      aoi: sampleAoi,
      dateRange: { start_date: "2026-01-01", end_date: "2026-02-01" },
    });
    window.localStorage.setItem(WORKSPACE_DRAFT_STORAGE_KEY, stored);

    const onRestoreAoi = vi.fn();
    const { result } = renderHook(() => useWorkspaceDraft({ selectedAoi: null, onRestoreAoi }));

    expect(result.current.analysisMode).toBe("spectral_analysis");
    expect(result.current.questionDraft).toBe("Inspect vegetation canopy");
    expect(result.current.dateRange?.start_date).toBe("2026-01-01");
    expect(result.current.isRestored).toBe(true);
    expect(result.current.persistenceState).toBe("restored");
    expect(onRestoreAoi).toHaveBeenCalledWith(
      expect.objectContaining({ bounds: sampleAoi.bounds }),
    );
  });

  it("auto-saves state changes after debounce interval", () => {
    const { result } = renderHook(() => useWorkspaceDraft({ selectedAoi: null }));

    act(() => {
      result.current.setAnalysisMode("change_detection");
      result.current.setQuestionDraft("Quantify urban expansion");
    });

    // Advance timers by 300ms debounce
    act(() => {
      vi.advanceTimersByTime(350);
    });

    const stored = window.localStorage.getItem(WORKSPACE_DRAFT_STORAGE_KEY);
    expect(stored).not.toBeNull();
    expect(stored).toContain("change_detection");
    expect(stored).toContain("Quantify urban expansion");
  });

  it("resets workspace state and clears localStorage on resetWorkspace", () => {
    const { result } = renderHook(() => useWorkspaceDraft({ selectedAoi: null }));

    act(() => {
      result.current.setAnalysisMode("change_detection");
      result.current.setQuestionDraft("Some question");
    });

    act(() => {
      vi.advanceTimersByTime(350);
    });
    expect(window.localStorage.getItem(WORKSPACE_DRAFT_STORAGE_KEY)).not.toBeNull();

    act(() => {
      result.current.resetWorkspace();
    });

    expect(result.current.analysisMode).toBe("visual_question_answering");
    expect(result.current.questionDraft).toBe("");
    expect(result.current.dateRange).toBeNull();
    expect(window.localStorage.getItem(WORKSPACE_DRAFT_STORAGE_KEY)).toBeNull();
  });
});
