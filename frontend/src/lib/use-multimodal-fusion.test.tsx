import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as fusionClient from "./fusion-client";
import type { FusionResult } from "./fusion-contracts";
import { useMultimodalFusion } from "./use-multimodal-fusion";

describe("useMultimodalFusion", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("initializes with default values", () => {
    const { result } = renderHook(() => useMultimodalFusion());

    expect(result.current.opticalResultId).toBeNull();
    expect(result.current.sarBeforeAssetId).toBeNull();
    expect(result.current.sarAfterAssetId).toBeNull();
    expect(result.current.temporalToleranceDays).toBe(30.0);
    expect(result.current.isExecuting).toBe(false);
    expect(result.current.result).toBeNull();
    expect(result.current.canExecute).toBe(false);
  });

  it("updates parameters and triggers fusion successfully", async () => {
    const mockFusionResult: FusionResult = {
      result_id: "fusion-123",
      rule_id: "co_observed_response_change",
      rule_definition: {
        rule_id: "co_observed_response_change",
        name: "Co-Observed Response Change",
        version: "1.0.0",
        description: "Test description",
        supported_modalities: ["Optical", "SAR"],
        disclaimer: "Evidence only",
      },
      compatibility: {
        status: "valid",
        blocking_issues: [],
        warnings: [],
        method_version: "1.0.0",
      },
      coverage: {
        total_aoi_area_km2: 1.6,
        jointly_observable_area_km2: 1.0,
        optical_only_area_km2: 0.2,
        sar_only_area_km2: 0.1,
        neither_area_km2: 0.3,
        joint_percent_of_aoi: 62.5,
        optical_only_percent_of_aoi: 12.5,
        sar_only_percent_of_aoi: 6.25,
        neither_percent_of_aoi: 18.75,
        pixel_counts: {
          total_aoi_pixels: 16,
          jointly_observable_pixels: 10,
          optical_only_pixels: 2,
          sar_only_pixels: 1,
          neither_pixels: 3,
        },
      },
      joint_metrics: {
        joint_area_km2: 1.0,
        both_detect_change_area_km2: 0.2,
        optical_response_only_area_km2: 0.3,
        sar_response_only_area_km2: 0.1,
        neither_above_threshold_area_km2: 0.3,
        uncertain_area_km2: 0.1,
        both_detect_change_percent: 20.0,
        optical_response_only_percent: 30.0,
        sar_response_only_percent: 10.0,
        neither_above_threshold_percent: 30.0,
        uncertain_percent: 10.0,
        pixel_counts: {
          both_detect_change_pixels: 2,
          optical_response_only_pixels: 3,
          sar_response_only_pixels: 1,
          neither_above_threshold_pixels: 3,
          uncertain_pixels: 1,
        },
      },
      regions: [],
      observations: [],
      evidence: [],
      quality: {
        score: 0.85,
        temporal_alignment_factor: 1.0,
        spatial_resolution_factor: 1.0,
        calibration_certainty_factor: 1.0,
        valid_coverage_factor: 0.625,
        factors: {},
        limitations: [],
      },
      warnings: [],
      blocking_issues: [],
      provenance: {
        pipeline_version: "1.0.0",
        source_asset_ids: ["opt-1", "sar-b", "sar-a"],
        source_scene_ids: ["S2", "S1"],
        operations: [],
        parameters: {},
        software: "SatQuery",
        started_at: "2026-09-20T10:00:00Z",
        completed_at: "2026-09-20T10:00:01Z",
        duration_milliseconds: 100.0,
        data_origin: "real",
      },
      data_origin: "real",
      created_at: "2026-09-20T10:00:01Z",
      interpretation_readiness: true,
    };

    vi.spyOn(fusionClient, "analyzeFusion").mockResolvedValue(mockFusionResult);

    const aoi = {
      type: "Polygon" as const,
      coordinates: [
        [
          [0, 0],
          [1, 0],
          [1, 1],
          [0, 1],
          [0, 0],
        ],
      ],
      crs: "EPSG:4326",
    };

    const { result } = renderHook(() =>
      useMultimodalFusion({
        initialOpticalResultId: "opt-result-1",
        initialSarBeforeAssetId: "sar-b",
        initialSarAfterAssetId: "sar-a",
        aoi,
      }),
    );

    expect(result.current.canExecute).toBe(true);

    let res: FusionResult | null = null;
    await act(async () => {
      res = await result.current.executeFusion();
    });

    expect(res).not.toBeNull();
    expect(result.current.result?.result_id).toBe("fusion-123");
    expect(result.current.result?.coverage.jointly_observable_area_km2).toBe(1.0);
  });
});
