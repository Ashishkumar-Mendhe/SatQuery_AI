import { afterEach, describe, expect, it, vi } from "vitest";

import {
  searchTemporalCandidates,
  TemporalClientError,
  validateTemporalPair,
} from "./temporal-client";

describe("Temporal Client", () => {
  const sampleAoi = {
    type: "Polygon" as const,
    coordinates: [
      [
        [77.58, 12.95],
        [77.62, 12.95],
        [77.62, 12.99],
        [77.58, 12.99],
        [77.58, 12.95],
      ],
    ],
    bbox: [77.58, 12.95, 77.62, 12.99] as [number, number, number, number],
    crs: "EPSG:4326",
  };

  const sampleSceneA = {
    id: "S2A_20250101",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-01T05:20:00Z",
    sensor_type: "multispectral" as const,
    platform: "Sentinel-2A",
    cloud_cover: 2.5,
    bbox: [77.5, 12.8, 77.7, 13.1] as [number, number, number, number],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleSceneB = {
    id: "S2B_20250120",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-20T05:20:00Z",
    sensor_type: "multispectral" as const,
    platform: "Sentinel-2B",
    cloud_cover: 3.5,
    bbox: [77.5, 12.8, 77.7, 13.1] as [number, number, number, number],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("successfully searches temporal candidates", async () => {
    const mockResponse = {
      search_id: "search-abc",
      before_scenes: [sampleSceneA],
      after_scenes: [sampleSceneB],
      provider_id: "earth-search",
      execution: {
        provider_id: "earth-search",
        provider_mode: "real",
        data_origin: "real",
        requested_at: "2026-09-20T00:00:00Z",
        completed_at: "2026-09-20T00:00:01Z",
        duration_milliseconds: 150,
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
        reason: "Best match",
        explanation: [],
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-req-123" }),
      json: async () => mockResponse,
    });

    const result = await searchTemporalCandidates({
      aoi: sampleAoi,
      before_window: { start_date: "2025-01-01", end_date: "2025-01-10" },
      after_window: { start_date: "2025-01-15", end_date: "2025-01-25" },
    });

    expect(result.search_id).toBe("search-abc");
    expect(result.before_scenes.length).toBe(1);
    expect(result.after_scenes.length).toBe(1);
    expect(result.recommended_pair?.compatibility_score).toBe(0.95);
  });

  it("handles structured API error from pair validation", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers(),
      json: async () => ({
        error: {
          code: "TEMPORAL_ORDER_REVERSED",
          message: "Before acquisition cannot precede after acquisition",
          retryable: false,
        },
      }),
    });

    await expect(
      validateTemporalPair({
        aoi: sampleAoi,
        before_scene: sampleSceneB,
        after_scene: sampleSceneA,
      }),
    ).rejects.toThrow(TemporalClientError);
  });
});
