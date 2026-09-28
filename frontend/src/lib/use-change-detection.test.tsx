import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as changeClient from "./change-client";
import type { ChangeDetectionResult, ChangeMethodsResponse } from "./change-contracts";
import type { PreparedTemporalPair } from "./preparation-contracts";
import { useChangeDetection } from "./use-change-detection";

const sampleAoi = {
  type: "Polygon" as const,
  coordinates: [
    [
      [77.58, 12.96],
      [77.62, 12.96],
      [77.62, 13.0],
      [77.58, 13.0],
      [77.58, 12.96],
    ],
  ],
  crs: "EPSG:4326",
  bbox: [77.58, 12.96, 77.62, 13.0] as [number, number, number, number],
};

const samplePreparedPair: PreparedTemporalPair = {
  preparation_id: "prep-pair-1",
  pair_id: "pair-1",
  before_asset: {
    asset_id: "ast-bef",
    source_asset_ids: ["src-1"],
    scene_ids: ["S2A_before"],
    role: "single",
    format: "geotiff",
    crs: "EPSG:32643",
    bbox: [77.58, 12.96, 77.62, 13.0],
    width: 100,
    height: 100,
    pixel_size_x: 10.0,
    pixel_size_y: 10.0,
    transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
    band_count: 4,
    band_names: ["B02", "B03", "B04", "B08"],
    data_type: "float32",
    no_data_values: [-9999.0],
    valid_pixel_count: 10000,
    invalid_pixel_count: 0,
    valid_data_percent: 100.0,
    resolution_meters: 10.0,
    resampling_method: "bilinear",
    clip_applied: true,
    mask_applied: true,
    created_at: new Date().toISOString(),
    data_origin: "real",
    provenance: {
      pipeline_version: "1.0",
      source_asset_ids: ["src-1"],
      source_scene_ids: ["S2A_before"],
      operations: ["reproject"],
      parameters: {},
      software: "SatQuery Raster Harmonizer Engine v1.0",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_milliseconds: 500,
      data_origin: "real",
    },
    warnings: [],
  },
  after_asset: {
    asset_id: "ast-aft",
    source_asset_ids: ["src-2"],
    scene_ids: ["S2A_after"],
    role: "single",
    format: "geotiff",
    crs: "EPSG:32643",
    bbox: [77.58, 12.96, 77.62, 13.0],
    width: 100,
    height: 100,
    pixel_size_x: 10.0,
    pixel_size_y: 10.0,
    transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
    band_count: 4,
    band_names: ["B02", "B03", "B04", "B08"],
    data_type: "float32",
    no_data_values: [-9999.0],
    valid_pixel_count: 10000,
    invalid_pixel_count: 0,
    valid_data_percent: 100.0,
    resolution_meters: 10.0,
    resampling_method: "bilinear",
    clip_applied: true,
    mask_applied: true,
    created_at: new Date().toISOString(),
    data_origin: "real",
    provenance: {
      pipeline_version: "1.0",
      source_asset_ids: ["src-2"],
      source_scene_ids: ["S2A_after"],
      operations: ["reproject"],
      parameters: {},
      software: "SatQuery Raster Harmonizer Engine v1.0",
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      duration_milliseconds: 500,
      data_origin: "real",
    },
    warnings: [],
  },
  common_crs: "EPSG:32643",
  common_bbox: [77.58, 12.96, 77.62, 13.0],
  common_width: 100,
  common_height: 100,
  common_transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
  common_resolution_meters: 10.0,
  shared_valid_pixel_count: 10000,
  shared_valid_percent: 100.0,
  alignment_status: "aligned",
  quality: {
    valid_data_percent: 100.0,
    no_data_percent: 0.0,
    aoi_coverage_percent: 100.0,
    shared_coverage_percent: 100.0,
    resolution_consistency: 1.0,
    grid_alignment_score: 1.0,
    metadata_completeness: 1.0,
    quality_score: 1.0,
    factors: {},
    limitations: [],
  },
  warnings: [],
  blocking_issues: [],
  ready_for_analysis: true,
  created_at: new Date().toISOString(),
  processing_metadata: {},
};

const mockMethodsResponse: ChangeMethodsResponse = {
  methods: [
    {
      method: "ndvi_difference",
      display_name: "NDVI Difference",
      formula: "NDVI_after - NDVI_before",
      input_type: "spectral_index",
      directionality: "bidirectional",
      expected_range: [-2.0, 2.0],
      default_threshold_config: {
        strategy: "fixed",
        positive_threshold: 0.15,
        negative_threshold: -0.15,
        std_multiplier: 1.5,
        percentile_cutoff: 95.0,
        min_cluster_size_pixels: 5,
        simplify_tolerance_meters: 5.0,
      },
      supported_sensors: ["Sentinel-2"],
      description: "Detects vegetation changes.",
      limitations: "Phenology effects.",
      default_color_ramp: "RdYlGn",
      version: "1.0.0",
    },
    {
      method: "ndwi_difference",
      display_name: "NDWI Difference",
      formula: "NDWI_after - NDWI_before",
      input_type: "spectral_index",
      directionality: "bidirectional",
      expected_range: [-2.0, 2.0],
      default_threshold_config: {
        strategy: "fixed",
        positive_threshold: 0.2,
        negative_threshold: -0.2,
        std_multiplier: 1.5,
        percentile_cutoff: 95.0,
        min_cluster_size_pixels: 5,
        simplify_tolerance_meters: 5.0,
      },
      supported_sensors: ["Sentinel-2"],
      description: "Detects water surface changes.",
      limitations: "Shadow contamination.",
      default_color_ramp: "RdBu_r",
      version: "1.0.0",
    },
  ],
  total_count: 2,
  version: "1.0.0",
};

const mockCalculationResult: ChangeDetectionResult = {
  result_id: "res-chg-99",
  pair_id: "pair-1",
  method: "ndvi_difference",
  definition: mockMethodsResponse.methods[0],
  before_scene_id: "S2A_before",
  after_scene_id: "S2A_after",
  before_asset_id: "ast-bef",
  after_asset_id: "ast-aft",
  difference_asset_id: "ast-diff",
  preview_asset_id: "ast-prev",
  classified_preview_asset_id: "ast-cls",
  metrics: {
    gain_area_km2: 0.2,
    loss_area_km2: 0.1,
    stable_area_km2: 0.7,
    net_change_area_km2: 0.1,
    shared_valid_area_km2: 1.0,
    pixel_counts: {
      total_aoi_pixels: 10000,
      shared_valid_pixels: 10000,
      gain_pixels: 2000,
      loss_pixels: 1000,
      stable_pixels: 7000,
      uncertain_pixels: 0,
      gain_percent: 20.0,
      loss_percent: 10.0,
      stable_percent: 70.0,
      uncertain_percent: 0.0,
    },
    positive_threshold_applied: 0.15,
    negative_threshold_applied: -0.15,
    threshold_strategy: "fixed",
  },
  regions: [],
  overlay: null,
  classified_overlay: null,
  evidence: [],
  confidence_breakdown: {
    overall: 0.95,
    data_quality: 0.95,
    temporal_quality: 0.95,
    spatial_quality: 0.95,
    model_confidence: 0.9,
    evidence_agreement: 0.95,
    factors: [],
    methodology: "Multi-factor",
    limitations: [],
  },
  confidence: 0.95,
  warnings: [],
  provenance: {
    pipeline_version: "1.0",
    source_asset_ids: ["ast-bef", "ast-aft"],
    source_scene_ids: ["S2A_before", "S2A_after"],
    operations: ["spectral_differencing"],
    parameters: {},
    software: "SatQuery Change Engine v1.0",
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    duration_milliseconds: 800,
    data_origin: "real",
  },
  data_origin: "real",
  created_at: new Date().toISOString(),
};

describe("useChangeDetection", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(changeClient, "listChangeMethods").mockResolvedValue(mockMethodsResponse);
  });

  it("loads methods on mount and selects default method", async () => {
    const { result } = renderHook(() =>
      useChangeDetection({
        aoi: sampleAoi,
        preparedPair: samplePreparedPair,
      }),
    );

    expect(result.current.selectedMethod).toBe("ndvi_difference");
  });

  it("handles successful change calculation workflow", async () => {
    const calcSpy = vi
      .spyOn(changeClient, "calculateChangeDetection")
      .mockResolvedValue(mockCalculationResult);

    const { result } = renderHook(() =>
      useChangeDetection({
        aoi: sampleAoi,
        preparedPair: samplePreparedPair,
      }),
    );

    await act(async () => {
      await result.current.calculateChange();
    });

    expect(calcSpy).toHaveBeenCalledTimes(1);
    expect(result.current.result?.result_id).toBe("res-chg-99");
    expect(result.current.result?.metrics.gain_area_km2).toBe(0.2);
    expect(result.current.error).toBeNull();
  });

  it("sets error when AOI or prepared temporal pair is missing", async () => {
    const { result } = renderHook(() =>
      useChangeDetection({
        aoi: null,
        preparedPair: null,
      }),
    );

    await act(async () => {
      await result.current.calculateChange();
    });

    expect(result.current.error).toContain("AOI");
    expect(result.current.result).toBeNull();
  });

  it("resets state when reset is called", async () => {
    vi.spyOn(changeClient, "calculateChangeDetection").mockResolvedValue(mockCalculationResult);

    const { result } = renderHook(() =>
      useChangeDetection({
        aoi: sampleAoi,
        preparedPair: samplePreparedPair,
      }),
    );

    await act(async () => {
      await result.current.calculateChange();
    });

    expect(result.current.result).not.toBeNull();

    act(() => {
      result.current.reset();
    });

    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("allows setting threshold configuration and overlay display options", async () => {
    const { result } = renderHook(() =>
      useChangeDetection({
        aoi: sampleAoi,
        preparedPair: samplePreparedPair,
      }),
    );

    act(() => {
      result.current.setPositiveThreshold(0.25);
      result.current.setNegativeThreshold(-0.25);
      result.current.setThresholdStrategy("standard_deviation");
      result.current.setOverlayMode("classified");
      result.current.setOverlayOpacity(0.5);
    });

    expect(result.current.thresholdConfig.positive_threshold).toBe(0.25);
    expect(result.current.thresholdConfig.negative_threshold).toBe(-0.25);
    expect(result.current.thresholdConfig.strategy).toBe("standard_deviation");
    expect(result.current.overlayMode).toBe("classified");
    expect(result.current.overlayOpacity).toBe(0.5);
  });
});
