import { describe, expect, it } from "vitest";

import {
  changeDetectionDefinitionSchema,
  changeDetectionMethodSchema,
  changeDetectionRequestSchema,
  changeDetectionResultSchema,
  changeMethodsResponseSchema,
  changeMetricsSchema,
  changePixelCountsSchema,
  changeRegionSchema,
  changeThresholdConfigSchema,
  maskOptionsSchema,
  thresholdStrategySchema,
} from "./change-contracts";

describe("change-contracts", () => {
  it("validates change detection methods enum", () => {
    expect(changeDetectionMethodSchema.parse("ndvi_difference")).toBe("ndvi_difference");
    expect(changeDetectionMethodSchema.parse("ndwi_difference")).toBe("ndwi_difference");
    expect(changeDetectionMethodSchema.parse("ndbi_difference")).toBe("ndbi_difference");
    expect(changeDetectionMethodSchema.parse("absolute_index_difference")).toBe(
      "absolute_index_difference",
    );
    expect(changeDetectionMethodSchema.parse("multiband_change_magnitude")).toBe(
      "multiband_change_magnitude",
    );
    expect(() => changeDetectionMethodSchema.parse("unsupported_method")).toThrow();
  });

  it("validates threshold strategies enum", () => {
    expect(thresholdStrategySchema.parse("fixed")).toBe("fixed");
    expect(thresholdStrategySchema.parse("standard_deviation")).toBe("standard_deviation");
    expect(thresholdStrategySchema.parse("percentile")).toBe("percentile");
    expect(thresholdStrategySchema.parse("otsu")).toBe("otsu");
    expect(thresholdStrategySchema.parse("manual")).toBe("manual");
    expect(() => thresholdStrategySchema.parse("random")).toThrow();
  });

  it("validates changeThresholdConfigSchema with valid and default values", () => {
    const parsed = changeThresholdConfigSchema.parse({});
    expect(parsed.strategy).toBe("fixed");
    expect(parsed.positive_threshold).toBe(0.15);
    expect(parsed.negative_threshold).toBe(-0.15);
    expect(parsed.min_cluster_size_pixels).toBe(5);
  });

  it("rejects changeThresholdConfigSchema when positive threshold < negative threshold in fixed mode", () => {
    expect(() =>
      changeThresholdConfigSchema.parse({
        strategy: "fixed",
        positive_threshold: -0.2,
        negative_threshold: 0.1,
      }),
    ).toThrow();
  });

  it("validates maskOptionsSchema with defaults", () => {
    const parsed = maskOptionsSchema.parse({});
    expect(parsed.apply_no_data_mask).toBe(true);
    expect(parsed.apply_cloud_mask).toBe(true);
    expect(parsed.minimum_valid_data_percent).toBe(1.0);
  });

  it("validates changePixelCountsSchema and enforces boundaries", () => {
    const valid = {
      total_aoi_pixels: 1000,
      shared_valid_pixels: 800,
      gain_pixels: 160,
      loss_pixels: 80,
      stable_pixels: 560,
      uncertain_pixels: 0,
      gain_percent: 20.0,
      loss_percent: 10.0,
      stable_percent: 70.0,
      uncertain_percent: 0.0,
    };
    expect(changePixelCountsSchema.parse(valid)).toEqual(valid);

    expect(() =>
      changePixelCountsSchema.parse({
        ...valid,
        gain_percent: 150.0,
      }),
    ).toThrow();
  });

  it("validates changeMetricsSchema", () => {
    const valid = {
      gain_area_km2: 0.16,
      loss_area_km2: 0.08,
      stable_area_km2: 0.56,
      net_change_area_km2: 0.08,
      shared_valid_area_km2: 0.8,
      pixel_counts: {
        total_aoi_pixels: 1000,
        shared_valid_pixels: 800,
        gain_pixels: 160,
        loss_pixels: 80,
        stable_pixels: 560,
        uncertain_pixels: 0,
        gain_percent: 20.0,
        loss_percent: 10.0,
        stable_percent: 70.0,
        uncertain_percent: 0.0,
      },
      positive_threshold_applied: 0.15,
      negative_threshold_applied: -0.15,
      threshold_strategy: "fixed",
    };
    expect(changeMetricsSchema.parse(valid)).toEqual(valid);
  });

  it("validates changeRegionSchema", () => {
    const region = {
      id: "reg-001",
      category: "spectral_gain",
      geometry: {
        type: "Polygon" as const,
        coordinates: [
          [
            [10.0, 50.0],
            [10.1, 50.0],
            [10.1, 50.1],
            [10.0, 50.1],
            [10.0, 50.0],
          ],
        ],
        crs: "EPSG:4326",
      },
      area_km2: 0.05,
      pixel_count: 50,
      mean_magnitude: 0.28,
      min_magnitude: 0.16,
      max_magnitude: 0.42,
      threshold_rule: "delta > 0.15",
      evidence_id: "evi-001",
      confidence: 0.92,
      warnings: [],
    };
    expect(changeRegionSchema.parse(region)).toEqual(region);
  });

  it("validates changeDetectionDefinitionSchema directly", () => {
    const def = {
      method: "ndvi_difference" as const,
      display_name: "NDVI Difference",
      formula: "NDVI_after - NDVI_before",
      input_type: "spectral_index",
      directionality: "bidirectional" as const,
      expected_range: [-2.0, 2.0] as [number, number],
      default_threshold_config: {
        strategy: "fixed" as const,
        positive_threshold: 0.15,
        negative_threshold: -0.15,
        std_multiplier: 1.5,
        percentile_cutoff: 95.0,
        min_cluster_size_pixels: 5,
        simplify_tolerance_meters: 5.0,
      },
      supported_sensors: ["Sentinel-2"],
      description: "Detects vegetation change.",
      limitations: "Phenology effects.",
      default_color_ramp: "RdYlGn",
      version: "1.0.0",
    };
    expect(changeDetectionDefinitionSchema.parse(def)).toEqual(def);
  });

  it("validates changeDetectionRequestSchema with valid input", () => {
    const request = {
      prepared_pair_id: "pair-123",
      before_prepared_asset_id: "ast-bef-1",
      after_prepared_asset_id: "ast-aft-2",
      aoi: {
        type: "Polygon" as const,
        coordinates: [
          [
            [10.0, 50.0],
            [10.1, 50.0],
            [10.1, 50.1],
            [10.0, 50.1],
            [10.0, 50.0],
          ],
        ],
        crs: "EPSG:4326",
      },
      method: "ndvi_difference" as const,
    };
    const parsed = changeDetectionRequestSchema.parse(request);
    expect(parsed.prepared_pair_id).toBe("pair-123");
    expect(parsed.method).toBe("ndvi_difference");
    expect(parsed.generate_overlay).toBe(true);
  });

  it("validates changeMethodsResponseSchema and definitions", () => {
    const response = {
      methods: [
        {
          method: "ndvi_difference" as const,
          display_name: "NDVI Difference",
          formula: "NDVI_after - NDVI_before",
          input_type: "spectral_index",
          directionality: "bidirectional" as const,
          expected_range: [-2.0, 2.0] as [number, number],
          default_threshold_config: {
            strategy: "fixed" as const,
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
      ],
      total_count: 1,
      version: "1.0.0",
    };
    const parsed = changeMethodsResponseSchema.parse(response);
    expect(parsed.methods).toHaveLength(1);
    expect(parsed.methods[0].method).toBe("ndvi_difference");
  });

  it("validates complete changeDetectionResultSchema envelope", () => {
    const result = {
      result_id: "res-chg-123",
      pair_id: "pair-123",
      method: "ndvi_difference" as const,
      definition: {
        method: "ndvi_difference" as const,
        display_name: "NDVI Difference",
        formula: "NDVI_after - NDVI_before",
        input_type: "spectral_index",
        directionality: "bidirectional" as const,
        expected_range: [-2.0, 2.0] as [number, number],
        default_threshold_config: {
          strategy: "fixed" as const,
          positive_threshold: 0.15,
          negative_threshold: -0.15,
          std_multiplier: 1.5,
          percentile_cutoff: 95.0,
          min_cluster_size_pixels: 5,
          simplify_tolerance_meters: 5.0,
        },
        supported_sensors: ["Sentinel-2"],
        description: "Detects vegetation changes.",
        limitations: "Phenological differences.",
        default_color_ramp: "RdYlGn",
        version: "1.0.0",
      },
      before_scene_id: "S2A_20230101",
      after_scene_id: "S2A_20230201",
      before_asset_id: "ast-bef",
      after_asset_id: "ast-aft",
      difference_asset_id: "ast-diff",
      preview_asset_id: "ast-prev",
      classified_preview_asset_id: "ast-cls",
      metrics: {
        gain_area_km2: 0.1,
        loss_area_km2: 0.05,
        stable_area_km2: 0.85,
        net_change_area_km2: 0.05,
        shared_valid_area_km2: 1.0,
        pixel_counts: {
          total_aoi_pixels: 1000,
          shared_valid_pixels: 1000,
          gain_pixels: 100,
          loss_pixels: 50,
          stable_pixels: 850,
          uncertain_pixels: 0,
          gain_percent: 10.0,
          loss_percent: 5.0,
          stable_percent: 85.0,
          uncertain_percent: 0.0,
        },
        positive_threshold_applied: 0.15,
        negative_threshold_applied: -0.15,
        threshold_strategy: "fixed" as const,
      },
      regions: [],
      overlay: null,
      classified_overlay: null,
      evidence: [],
      confidence_breakdown: {
        overall: 0.9,
        data_quality: 0.95,
        temporal_quality: 0.9,
        spatial_quality: 0.9,
        model_confidence: 0.85,
        evidence_agreement: 0.9,
        factors: [],
        methodology: "Multi-factor spectral change confidence",
        limitations: [],
      },
      confidence: 0.9,
      warnings: [],
      provenance: {
        pipeline_version: "1.0",
        source_asset_ids: ["ast-bef", "ast-aft"],
        source_scene_ids: ["S2A_20230101", "S2A_20230201"],
        operations: ["spectral_differencing"],
        parameters: {},
        software: "SatQuery Change Engine v1.0",
        started_at: "2026-09-20T12:00:00Z",
        completed_at: "2026-09-20T12:00:01Z",
        duration_milliseconds: 1000,
        data_origin: "real" as const,
      },
      data_origin: "real" as const,
      created_at: "2026-09-20T12:00:01Z",
    };
    const parsed = changeDetectionResultSchema.parse(result);
    expect(parsed.result_id).toBe("res-chg-123");
    expect(parsed.confidence).toBe(0.9);
  });
});
