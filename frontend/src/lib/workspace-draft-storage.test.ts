import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds } from "./aoi";
import {
  clearWorkspaceDraftFromStorage,
  isDraftExpired,
  parseWorkspaceDraft,
  saveWorkspaceDraftToStorage,
  serializeWorkspaceDraft,
  WORKSPACE_DRAFT_STORAGE_KEY,
  WORKSPACE_DRAFT_TTL_MS,
} from "./workspace-draft-storage";

describe("workspace-draft-storage", () => {
  const sampleAoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.1]);

  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("serializes and parses a complete valid workspace draft", () => {
    const raw = serializeWorkspaceDraft({
      analysisMode: "change_detection",
      questionDraft: "Assess vegetation differences between these two dates.",
      aoi: sampleAoi,
      dateRange: { start_date: "2026-01-01", end_date: "2026-02-01" },
      sceneFilters: { maxCloudCover: 15, sensorType: "optical", limit: 8 },
      activeTab: "evidence",
      mapCamera: { center: [77.6, 13.0], zoom: 11 },
    });

    const restored = parseWorkspaceDraft(raw);
    expect(restored.analysisMode).toBe("change_detection");
    expect(restored.questionDraft).toBe("Assess vegetation differences between these two dates.");
    expect(restored.aoi).not.toBeNull();
    expect(restored.aoi?.bounds).toEqual(sampleAoi.bounds);
    expect(restored.dateRange?.start_date).toBe("2026-01-01");
    expect(restored.sceneFilters.maxCloudCover).toBe(15);
    expect(restored.activeTab).toBe("evidence");
    expect(restored.mapCamera?.zoom).toBe(11);
  });

  it("rejects corrupted JSON string", () => {
    expect(() => parseWorkspaceDraft("not valid json")).toThrow(/corrupted JSON/);
  });

  it("rejects unsupported schema version or missing version", () => {
    const invalid = JSON.stringify({ version: 2, savedAt: new Date().toISOString() });
    expect(() => parseWorkspaceDraft(invalid)).toThrow(/invalid or unsupported/);
  });

  it("rejects drafts older than 7 days TTL", () => {
    const eightDaysAgo = new Date(Date.now() - (WORKSPACE_DRAFT_TTL_MS + 10000)).toISOString();
    const expiredRaw = serializeWorkspaceDraft(
      {
        analysisMode: "visual_question_answering",
        questionDraft: "Old question",
        aoi: null,
        dateRange: null,
      },
      eightDaysAgo,
    );

    expect(() => parseWorkspaceDraft(expiredRaw)).toThrow(/expired/);
  });

  it("evaluates draft expiration correctly", () => {
    const now = new Date().toISOString();
    expect(isDraftExpired(now)).toBe(false);

    const old = new Date(Date.now() - (WORKSPACE_DRAFT_TTL_MS + 5000)).toISOString();
    expect(isDraftExpired(old)).toBe(true);

    expect(isDraftExpired("invalid-date")).toBe(true);
  });

  it("handles storage write, retrieval, and clear operations safely", () => {
    const raw = serializeWorkspaceDraft({
      analysisMode: "spectral_analysis",
      questionDraft: "Calculate NDVI",
      aoi: sampleAoi,
      dateRange: null,
    });

    const writeResult = saveWorkspaceDraftToStorage(raw);
    expect(writeResult.success).toBe(true);
    expect(window.localStorage.getItem(WORKSPACE_DRAFT_STORAGE_KEY)).toBe(raw);

    clearWorkspaceDraftFromStorage();
    expect(window.localStorage.getItem(WORKSPACE_DRAFT_STORAGE_KEY)).toBeNull();
  });

  it("handles storage write error gracefully if quota is exceeded", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("QuotaExceededError");
    });

    const result = saveWorkspaceDraftToStorage("test-payload");
    expect(result.success).toBe(false);
    expect(result.error).toBe("QuotaExceededError");
  });
});
