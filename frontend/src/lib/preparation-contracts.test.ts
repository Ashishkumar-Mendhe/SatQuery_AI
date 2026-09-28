import { describe, expect, it } from "vitest";

import {
  preparedRasterAssetSchema,
  preparedTemporalPairSchema,
  rasterPreparationRequestSchema,
  temporalRasterPreparationRequestSchema,
} from "./preparation-contracts";

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
  bbox: [77.58, 12.96, 77.62, 13.0] as [number, number, number, number],
};

describe("preparation-contracts", () => {
  it("validates single-scene raster preparation request", () => {
    const parsed = rasterPreparationRequestSchema.parse({
      source_asset_id: "ast-123",
      scene_id: "S2A_20250101",
      aoi: sampleAoi,
      target_crs: "EPSG:32643",
      target_resolution_meters: 10.0,
      resampling_method: "bilinear",
      clip_to_aoi: true,
      output_format: "geotiff",
    });

    expect(parsed.source_asset_id).toBe("ast-123");
    expect(parsed.target_crs).toBe("EPSG:32643");
    expect(parsed.resampling_method).toBe("bilinear");
  });

  it("rejects PNG output format for analysis preparation request", () => {
    expect(() =>
      rasterPreparationRequestSchema.parse({
        source_asset_id: "ast-123",
        scene_id: "S2A_20250101",
        aoi: sampleAoi,
        output_format: "png",
      }),
    ).toThrow();
  });

  it("validates temporal raster preparation request", () => {
    const parsed = temporalRasterPreparationRequestSchema.parse({
      pair_id: "pair-1",
      before_asset_id: "ast-b",
      after_asset_id: "ast-a",
      aoi: sampleAoi,
      strategy: "common_intersection",
      target_crs: "EPSG:32643",
      optical_resampling_method: "bilinear",
    });

    expect(parsed.pair_id).toBe("pair-1");
    expect(parsed.strategy).toBe("common_intersection");
  });

  it("rejects temporal raster preparation request with identical before and after assets", () => {
    expect(() =>
      temporalRasterPreparationRequestSchema.parse({
        pair_id: "pair-1",
        before_asset_id: "ast-same",
        after_asset_id: "ast-same",
        aoi: sampleAoi,
      }),
    ).toThrow();
  });

  it("validates prepared raster asset schema", () => {
    const now = new Date().toISOString();
    const parsed = preparedRasterAssetSchema.parse({
      asset_id: "ast-prep-1",
      source_asset_ids: ["ast-src"],
      scene_ids: ["S2A_20250101"],
      role: "single",
      format: "geotiff",
      crs: "EPSG:32643",
      bbox: [77.58, 12.96, 77.62, 13.0],
      width: 256,
      height: 256,
      pixel_size_x: 10.0,
      pixel_size_y: 10.0,
      transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
      band_count: 4,
      band_names: ["B02", "B03", "B04", "B08"],
      data_type: "float32",
      no_data_values: [-9999.0],
      valid_pixel_count: 50000,
      invalid_pixel_count: 15536,
      valid_data_percent: 76.3,
      resolution_meters: 10.0,
      resampling_method: "bilinear",
      clip_applied: true,
      mask_applied: true,
      created_at: now,
      data_origin: "real",
      provenance: {
        pipeline_version: "1.0",
        source_asset_ids: ["ast-src"],
        source_scene_ids: ["S2A_20250101"],
        operations: ["reproject", "clip"],
        parameters: { target_crs: "EPSG:32643" },
        software: "SatQuery Harmonizer",
        started_at: now,
        completed_at: now,
        duration_milliseconds: 85.0,
        data_origin: "real",
      },
      warnings: [],
      preview_url: "/api/v1/imagery/assets/prev-1",
    });

    expect(parsed.asset_id).toBe("ast-prep-1");
    expect(parsed.valid_data_percent).toBe(76.3);
  });

  it("validates prepared temporal pair schema", () => {
    const now = new Date().toISOString();
    const mockAsset = {
      asset_id: "ast-prep-1",
      source_asset_ids: ["ast-src"],
      scene_ids: ["S2A_20250101"],
      role: "before",
      format: "geotiff" as const,
      crs: "EPSG:32643",
      bbox: [77.58, 12.96, 77.62, 13.0] as [number, number, number, number],
      width: 256,
      height: 256,
      pixel_size_x: 10.0,
      pixel_size_y: 10.0,
      transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
      band_count: 4,
      band_names: ["B02", "B03", "B04", "B08"],
      data_type: "float32",
      no_data_values: [-9999.0],
      valid_pixel_count: 50000,
      invalid_pixel_count: 15536,
      valid_data_percent: 76.3,
      resolution_meters: 10.0,
      resampling_method: "bilinear" as const,
      clip_applied: true,
      mask_applied: true,
      created_at: now,
      data_origin: "real" as const,
      provenance: {
        pipeline_version: "1.0",
        source_asset_ids: ["ast-src"],
        source_scene_ids: ["S2A_20250101"],
        operations: ["reproject", "clip"],
        parameters: { target_crs: "EPSG:32643" },
        software: "SatQuery Harmonizer",
        started_at: now,
        completed_at: now,
        duration_milliseconds: 85.0,
        data_origin: "real" as const,
      },
      warnings: [],
      preview_url: "/api/v1/imagery/assets/prev-1",
    };

    const pair = preparedTemporalPairSchema.parse({
      preparation_id: "prep-pair-1",
      pair_id: "pair-1",
      before_asset: mockAsset,
      after_asset: { ...mockAsset, asset_id: "ast-prep-2", role: "after" },
      common_crs: "EPSG:32643",
      common_bbox: [77.58, 12.96, 77.62, 13.0],
      common_width: 256,
      common_height: 256,
      common_transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
      common_resolution_meters: 10.0,
      shared_valid_pixel_count: 48000,
      shared_valid_percent: 73.2,
      alignment_status: "aligned",
      quality: {
        valid_data_percent: 76.3,
        no_data_percent: 23.7,
        aoi_coverage_percent: 73.2,
        resolution_consistency: 1.0,
        grid_alignment_score: 1.0,
        metadata_completeness: 1.0,
        quality_score: 0.95,
        factors: {},
        limitations: [],
      },
      warnings: [],
      blocking_issues: [],
      ready_for_analysis: true,
      created_at: now,
    });

    expect(pair.preparation_id).toBe("prep-pair-1");
    expect(pair.alignment_status).toBe("aligned");
  });
});
