import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchRasterMetadata,
  getAssetDisplayUrl,
  requestImagery,
  requestTemporalImagery,
} from "./imagery-client";

describe("Imagery Client", () => {
  const samplePolygon = {
    type: "Polygon" as const,
    coordinates: [
      [
        [77.5, 12.9],
        [77.7, 12.9],
        [77.7, 13.1],
        [77.5, 13.1],
        [77.5, 12.9],
      ],
    ],
  };

  const sampleAsset = {
    asset_id: "ast-12345",
    scene_id: "S2A_20250101",
    product_type: "map_preview",
    format: "png",
    content_type: "image/png",
    width: 512,
    height: 512,
    resolution_meters: 10,
    bbox: [77.5, 12.9, 77.7, 13.1],
    crs: "EPSG:3857",
    bands: ["B04", "B03", "B02"],
    size_bytes: 45000,
    checksum: "abc123sha256",
    created_at: "2026-09-20T00:00:00Z",
    display_url: "/api/v1/imagery/assets/ast-12345",
    provider_id: "earth-search",
    data_origin: "real",
    warnings: [],
    processing_metadata: {},
  };

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("computes asset display URL correctly", () => {
    const url = getAssetDisplayUrl("ast-test-1");
    expect(url).toBe("http://localhost:8000/api/v1/imagery/assets/ast-test-1");
  });

  it("requests single scene imagery successfully", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleAsset), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await requestImagery({
      scene_id: "S2A_20250101",
      aoi: samplePolygon,
      product_type: "map_preview",
      visualization_preset: "true_color",
      output_format: "png",
    });

    expect(result.asset_id).toBe("ast-12345");
    expect(result.scene_id).toBe("S2A_20250101");
  });

  it("handles HTTP error with structured message from backend", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: "SCENE_NOT_FOUND",
            message: "Scene was not found in provider catalogue.",
          },
        }),
        {
          status: 404,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    await expect(
      requestImagery({
        scene_id: "NON_EXISTENT",
        aoi: samplePolygon,
      }),
    ).rejects.toThrow("Scene was not found in provider catalogue.");
  });

  it("handles network failure gracefully", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await expect(
      requestImagery({
        scene_id: "S2A_20250101",
        aoi: samplePolygon,
      }),
    ).rejects.toThrow("Unable to reach satellite imagery service.");
  });

  it("requests multitemporal imagery successfully", async () => {
    const temporalResponse = {
      request_id: "req-temp-1",
      pair_id: "pair-1",
      before_asset: sampleAsset,
      after_asset: { ...sampleAsset, asset_id: "ast-after-2", scene_id: "S2B_20250120" },
      alignment_status: "aligned",
      data_origin: "real",
      warnings: [],
      processing_metadata: {},
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(temporalResponse), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await requestTemporalImagery({
      before_scene_id: "S2A_20250101",
      after_scene_id: "S2B_20250120",
      aoi: samplePolygon,
    });

    expect(result.request_id).toBe("req-temp-1");
    expect(result.alignment_status).toBe("aligned");
    expect(result.before_asset.asset_id).toBe("ast-12345");
  });

  it("fetches raster metadata successfully", async () => {
    const sampleMetadata = {
      crs: "EPSG:3857",
      bbox: [77.5, 12.9, 77.7, 13.1],
      width: 512,
      height: 512,
      pixel_size_x: 10,
      pixel_size_y: 10,
      band_count: 3,
      band_names: ["Red", "Green", "Blue"],
      data_type: "uint8",
      no_data_values: [0],
      scene_id: "S2A_20250101",
      provider: "earth-search",
      collection: "sentinel-2-c1-l2a",
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(sampleMetadata), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const meta = await fetchRasterMetadata("ast-12345");
    expect(meta.crs).toBe("EPSG:3857");
    expect(meta.band_count).toBe(3);
  });
});
