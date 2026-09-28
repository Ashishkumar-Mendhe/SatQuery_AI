import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { prepareRaster, PreparationClientError } from "./preparation-client";

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

describe("preparation-client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("successfully prepares a single raster asset", async () => {
    const now = new Date().toISOString();
    const mockPreparedAsset = {
      asset_id: "ast-prep-123",
      source_asset_ids: ["ast-src-1"],
      scene_ids: ["S2A_20250101"],
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
      valid_pixel_count: 9000,
      invalid_pixel_count: 1000,
      valid_data_percent: 90.0,
      resolution_meters: 10.0,
      resampling_method: "bilinear",
      clip_applied: true,
      mask_applied: true,
      created_at: now,
      data_origin: "real",
      provenance: {
        pipeline_version: "1.0",
        source_asset_ids: ["ast-src-1"],
        source_scene_ids: ["S2A_20250101"],
        operations: ["reproject", "clip"],
        parameters: { target_crs: "EPSG:32643" },
        software: "SatQuery Harmonizer",
        started_at: now,
        completed_at: now,
        duration_milliseconds: 50.0,
        data_origin: "real",
      },
      warnings: [],
      preview_url: "/api/v1/imagery/assets/ast-prev-1",
    };

    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      status: 200,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => mockPreparedAsset,
    });

    const res = await prepareRaster({
      source_asset_id: "ast-src-1",
      scene_id: "S2A_20250101",
      aoi: sampleAoi,
      target_crs: "EPSG:32643",
      target_resolution_meters: 10.0,
    });

    expect(res.asset_id).toBe("ast-prep-123");
    expect(res.crs).toBe("EPSG:32643");
    expect(res.valid_data_percent).toBe(90.0);
  });

  it("throws PreparationClientError on backend 404 or 400 response", async () => {
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: false,
      status: 404,
      headers: new Headers({ "Content-Type": "application/json" }),
      json: async () => ({
        error: {
          code: "IMAGERY_ASSET_NOT_FOUND",
          message: "Asset 'ast-nonexistent' not found.",
        },
      }),
    });

    await expect(
      prepareRaster({
        source_asset_id: "ast-nonexistent",
        scene_id: "S2A_20250101",
        aoi: sampleAoi,
      }),
    ).rejects.toThrow(PreparationClientError);
  });
});
