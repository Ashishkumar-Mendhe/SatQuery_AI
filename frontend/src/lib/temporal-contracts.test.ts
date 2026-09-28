import { describe, expect, it } from "vitest";

import {
  pairingPreferencesSchema,
  temporalPairValidationRequestSchema,
  temporalPairValidationResultSchema,
  temporalSceneCandidatesSchema,
  temporalSearchRequestSchema,
  temporalWindowSchema,
} from "./temporal-contracts";

describe("Temporal Contracts Validation", () => {
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

  it("validates valid temporal window", () => {
    const valid = temporalWindowSchema.parse({
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      label: "before",
    });
    expect(valid.start_date).toBe("2025-01-01");
    expect(valid.label).toBe("before");
  });

  it("rejects reversed temporal window", () => {
    expect(() =>
      temporalWindowSchema.parse({
        start_date: "2025-02-01",
        end_date: "2025-01-01",
      }),
    ).toThrow("start_date cannot be after end_date");
  });

  it("validates temporal search request", () => {
    const valid = temporalSearchRequestSchema.parse({
      aoi: sampleAoi,
      before_window: {
        start_date: "2025-01-01",
        end_date: "2025-01-31",
        label: "before",
      },
      after_window: {
        start_date: "2025-02-01",
        end_date: "2025-02-28",
        label: "after",
      },
      max_cloud_cover: 25,
      limit_per_window: 15,
    });
    expect(valid.limit_per_window).toBe(15);
    expect(valid.before_window.start_date).toBe("2025-01-01");
  });

  it("rejects temporal search request when before window starts after after window", () => {
    expect(() =>
      temporalSearchRequestSchema.parse({
        aoi: sampleAoi,
        before_window: {
          start_date: "2025-03-01",
          end_date: "2025-03-31",
        },
        after_window: {
          start_date: "2025-01-01",
          end_date: "2025-01-31",
        },
      }),
    ).toThrow("before_window start_date cannot be after after_window start_date");
  });

  it("validates temporal scene candidates payload", () => {
    const parsed = temporalSceneCandidatesSchema.parse({
      search_id: "test-search-123",
      before_scenes: [sampleSceneA],
      after_scenes: [sampleSceneB],
      provider_id: "earth-search",
      execution: {
        provider_id: "earth-search",
        provider_mode: "real",
        data_origin: "real",
        requested_at: "2026-09-20T00:00:00Z",
        completed_at: "2026-09-20T00:00:01Z",
        duration_milliseconds: 120,
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
        compatibility_score: 0.92,
        status: "compatible",
        reason: "Highest coverage and lowest cloud cover",
        explanation: ["Score: 0.92"],
      },
    });
    expect(parsed.before_scenes.length).toBe(1);
    expect(parsed.recommended_pair?.compatibility_score).toBe(0.92);
  });

  it("validates temporal pair validation request and response", () => {
    const request = temporalPairValidationRequestSchema.parse({
      aoi: sampleAoi,
      before_scene: sampleSceneA,
      after_scene: sampleSceneB,
      analysis_mode: "change_detection",
    });
    expect(request.before_scene.id).toBe("S2A_20250101");

    const result = temporalPairValidationResultSchema.parse({
      valid: true,
      status: "compatible",
      before_scene_id: "S2A_20250101",
      after_scene_id: "S2B_20250120",
      temporal_gap_days: 19.0,
      compatibility_score: 0.92,
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
    });
    expect(result.valid).toBe(true);
    expect(result.temporal_gap_days).toBe(19.0);
  });

  it("validates pairing preferences schema", () => {
    const prefs = pairingPreferencesSchema.parse({
      prefer_same_collection: true,
      prefer_same_platform: true,
      prefer_lowest_cloud_cover: true,
      maximum_temporal_gap_days: 60,
      min_aoi_coverage_percent: 85.0,
      required_bands: ["B04", "B08"],
    });
    expect(prefs.prefer_same_collection).toBe(true);
    expect(prefs.prefer_same_platform).toBe(true);
    expect(prefs.maximum_temporal_gap_days).toBe(60);
    expect(prefs.min_aoi_coverage_percent).toBe(85.0);
    expect(prefs.required_bands).toEqual(["B04", "B08"]);
  });
});
