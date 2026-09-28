import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SatelliteScene } from "./analysis-contracts";
import { createAoiFromBounds } from "./aoi";
import * as temporalClient from "./temporal-client";
import type { TemporalPairValidationResult, TemporalSceneCandidates } from "./temporal-contracts";
import { useTemporalPairing } from "./use-temporal-pairing";

describe("useTemporalPairing hook", () => {
  const sampleAoi = createAoiFromBounds([77.58, 12.95, 77.62, 12.99]);

  const sampleBeforeScene: SatelliteScene = {
    id: "S2A_20250101",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-01T05:20:00Z",
    sensor_type: "multispectral",
    platform: "Sentinel-2A",
    cloud_cover: 2.5,
    bbox: [77.5, 12.8, 77.7, 13.1],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleAfterScene: SatelliteScene = {
    id: "S2B_20250120",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-20T05:20:00Z",
    sensor_type: "multispectral",
    platform: "Sentinel-2B",
    cloud_cover: 3.5,
    bbox: [77.5, 12.8, 77.7, 13.1],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleCandidates: TemporalSceneCandidates = {
    search_id: "search-123",
    before_scenes: [sampleBeforeScene],
    after_scenes: [sampleAfterScene],
    provider_id: "earth-search",
    execution: {
      provider_id: "earth-search",
      provider_mode: "real",
      data_origin: "real",
      requested_at: "2026-09-20T00:00:00Z",
      completed_at: "2026-09-20T00:00:01Z",
      duration_milliseconds: 100,
      attempt_count: 1,
      fallback_used: false,
      cached: false,
      limitations: [],
    },
    warnings: [],
    data_origin: "real",
    generated_at: "2026-09-20T00:00:00Z",
    recommended_pair: {
      before_scene_id: "S2A_20250101",
      after_scene_id: "S2B_20250120",
      compatibility_score: 0.95,
      status: "compatible",
      reason: "High spatial overlap and matching sensor",
      explanation: [],
    },
  };

  const sampleValidationResult: TemporalPairValidationResult = {
    valid: true,
    status: "compatible",
    before_scene_id: "S2A_20250101",
    after_scene_id: "S2B_20250120",
    temporal_gap_days: 19.0,
    compatibility_score: 0.95,
    factors: [
      {
        name: "collection_platform",
        score: 1.0,
        weight: 0.25,
        weighted_score: 0.25,
        status: "optimal",
        details: "Identical collection",
      },
    ],
    issues: [],
    warnings: [],
    spatial_metrics: {
      before_aoi_coverage_percent: 100,
      after_aoi_coverage_percent: 100,
      mutual_aoi_coverage_percent: 100,
      scene_overlap_percent: 100,
    },
    data_origin_status: "real",
    validation_version: "1.0",
  };

  beforeEach(() => {
    vi.spyOn(temporalClient, "searchTemporalCandidates").mockResolvedValue(sampleCandidates);
    vi.spyOn(temporalClient, "validateTemporalPair").mockResolvedValue(sampleValidationResult);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("initializes with empty candidate state and selections", () => {
    const { result } = renderHook(() =>
      useTemporalPairing({
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2025-02-01", end_date: "2025-02-28" },
        sceneFilters: { maxCloudCover: 20, sensorType: "optical", limit: 12 },
      }),
    );

    expect(result.current.candidates).toBeNull();
    expect(result.current.selectedBeforeScene).toBeNull();
    expect(result.current.selectedAfterScene).toBeNull();
    expect(result.current.validationResult).toBeNull();
    expect(result.current.searchState).toBe("idle");
  });

  it("searches candidates and auto-stages recommended pair", async () => {
    const { result } = renderHook(() =>
      useTemporalPairing({
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2025-02-01", end_date: "2025-02-28" },
        sceneFilters: { maxCloudCover: 20, sensorType: "optical", limit: 12 },
      }),
    );

    await act(async () => {
      await result.current.searchCandidates();
    });

    expect(temporalClient.searchTemporalCandidates).toHaveBeenCalledTimes(1);
    expect(result.current.candidates).toEqual(sampleCandidates);
    expect(result.current.selectedBeforeScene).toEqual(sampleBeforeScene);
    expect(result.current.selectedAfterScene).toEqual(sampleAfterScene);
  });

  it("auto-validates when before and after scenes are selected", async () => {
    const { result } = renderHook(() =>
      useTemporalPairing({
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2025-02-01", end_date: "2025-02-28" },
        sceneFilters: { maxCloudCover: 20, sensorType: "optical", limit: 12 },
      }),
    );

    await act(async () => {
      result.current.selectBeforeScene(sampleBeforeScene);
      result.current.selectAfterScene(sampleAfterScene);
    });

    expect(temporalClient.validateTemporalPair).toHaveBeenCalledWith(
      expect.objectContaining({
        before_scene: sampleBeforeScene,
        after_scene: sampleAfterScene,
      }),
      expect.any(AbortSignal),
    );
    expect(result.current.validationResult).toEqual(sampleValidationResult);
  });

  it("clears validation result when selection is cleared", async () => {
    const { result } = renderHook(() =>
      useTemporalPairing({
        selectedAoi: sampleAoi,
        beforeWindow: { start_date: "2025-01-01", end_date: "2025-01-31" },
        afterWindow: { start_date: "2025-02-01", end_date: "2025-02-28" },
        sceneFilters: { maxCloudCover: 20, sensorType: "optical", limit: 12 },
      }),
    );

    await act(async () => {
      result.current.selectBeforeScene(sampleBeforeScene);
      result.current.selectAfterScene(sampleAfterScene);
    });

    expect(result.current.validationResult).not.toBeNull();

    act(() => {
      result.current.clearSelection();
    });

    expect(result.current.selectedBeforeScene).toBeNull();
    expect(result.current.selectedAfterScene).toBeNull();
    expect(result.current.validationResult).toBeNull();
  });
});
