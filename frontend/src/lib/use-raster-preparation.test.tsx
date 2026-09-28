import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as prepClient from "./preparation-client";
import type { PreparedRasterAsset } from "./preparation-contracts";
import { useRasterPreparation } from "./use-raster-preparation";

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

describe("useRasterPreparation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("handles successful single-scene preparation workflow", async () => {
    const mockPreparedAsset: PreparedRasterAsset = {
      asset_id: "ast-prep-1",
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
      created_at: new Date().toISOString(),
      data_origin: "real",
      provenance: {
        pipeline_version: "1.0",
        source_asset_ids: ["ast-src-1"],
        source_scene_ids: ["S2A_20250101"],
        operations: ["reproject", "clip"],
        parameters: { target_crs: "EPSG:32643" },
        software: "SatQuery Harmonizer",
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        duration_milliseconds: 40.0,
        data_origin: "real",
      },
      warnings: [],
      preview_url: "/api/v1/imagery/assets/prev-1",
    };

    vi.spyOn(prepClient, "prepareRaster").mockResolvedValueOnce(mockPreparedAsset);

    const { result } = renderHook(() =>
      useRasterPreparation({
        aoi: sampleAoi,
        mode: "single",
        singleAssetId: "ast-src-1",
        singleSceneId: "S2A_20250101",
      }),
    );

    expect(result.current.isReadyForAnalysis).toBe(false);

    await act(async () => {
      await result.current.startPreparation();
    });

    expect(result.current.isReadyForAnalysis).toBe(true);
    expect(result.current.status).toBe("ready");
    expect(result.current.preparedSingleAsset?.asset_id).toBe("ast-prep-1");
  });

  it("invalidates prepared output when input scene or asset changes", async () => {
    const mockPreparedAsset: PreparedRasterAsset = {
      asset_id: "ast-prep-1",
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
      created_at: new Date().toISOString(),
      data_origin: "real",
      provenance: {
        pipeline_version: "1.0",
        source_asset_ids: ["ast-src-1"],
        source_scene_ids: ["S2A_20250101"],
        operations: ["reproject", "clip"],
        parameters: { target_crs: "EPSG:32643" },
        software: "SatQuery Harmonizer",
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        duration_milliseconds: 40.0,
        data_origin: "real",
      },
      warnings: [],
      preview_url: "/api/v1/imagery/assets/prev-1",
    };

    vi.spyOn(prepClient, "prepareRaster").mockResolvedValue(mockPreparedAsset);

    const { result, rerender } = renderHook(
      (props) =>
        useRasterPreparation({
          aoi: sampleAoi,
          mode: "single",
          singleAssetId: props.singleAssetId,
          singleSceneId: "S2A_20250101",
        }),
      {
        initialProps: { singleAssetId: "ast-src-1" },
      },
    );

    await act(async () => {
      await result.current.startPreparation();
    });

    expect(result.current.preparedSingleAsset).not.toBeNull();

    // Rerender with changed asset ID
    rerender({ singleAssetId: "ast-src-2" });

    expect(result.current.preparedSingleAsset).toBeNull();
    expect(result.current.isReadyForAnalysis).toBe(false);
  });
});
