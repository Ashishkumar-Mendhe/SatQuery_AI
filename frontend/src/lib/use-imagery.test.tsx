import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SelectedAoi } from "./aoi";
import * as imageryClient from "./imagery-client";
import { getCompatiblePresets, useImagery } from "./use-imagery";

describe("useImagery hook", () => {
  const sampleAoi: SelectedAoi = {
    version: 1,
    name: "Test AOI",
    source: "rectangle",
    bounds: [77.5, 12.9, 77.7, 13.1],
    areaSquareMeters: 45000000,
    feature: {
      type: "Feature",
      bbox: [77.5, 12.9, 77.7, 13.1],
      properties: { name: "Test AOI", source: "rectangle" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.5, 12.9],
            [77.7, 12.9],
            [77.7, 13.1],
            [77.5, 13.1],
            [77.5, 12.9],
          ],
        ],
      },
    },
  };

  const sampleAsset = {
    asset_id: "ast-1",
    scene_id: "S2A_20250101",
    product_type: "map_preview" as const,
    format: "png" as const,
    content_type: "image/png",
    width: 512,
    height: 512,
    resolution_meters: 10,
    bbox: [77.5, 12.9, 77.7, 13.1] as [number, number, number, number],
    crs: "EPSG:3857",
    bands: ["B04", "B03", "B02"],
    size_bytes: 45000,
    checksum: "abc123sha256",
    created_at: "2026-09-20T00:00:00Z",
    display_url: "/api/v1/imagery/assets/ast-1",
    provider_id: "earth-search",
    data_origin: "real" as const,
    warnings: [],
    processing_metadata: {},
  };

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("filters compatible presets based on sensor type", () => {
    expect(getCompatiblePresets("optical")).toContain("true_color");
    expect(getCompatiblePresets("optical")).toContain("vegetation");
    expect(getCompatiblePresets("sar")).toContain("sar_vv");
    expect(getCompatiblePresets("sar")).not.toContain("true_color");
  });

  it("initializes with default state", () => {
    const { result } = renderHook(() => useImagery());
    expect(result.current.activeAsset).toBeNull();
    expect(result.current.singleStatus).toBe("idle");
    expect(result.current.opacity).toBe(1.0);
    expect(result.current.visible).toBe(true);
    expect(result.current.comparisonMode).toBe("swipe");
  });

  it("fetches single scene imagery successfully", async () => {
    vi.spyOn(imageryClient, "requestImagery").mockResolvedValueOnce(sampleAsset);

    const { result } = renderHook(() =>
      useImagery({ selectedAoi: sampleAoi, sceneId: "S2A_20250101" }),
    );

    let asset: unknown;
    await act(async () => {
      asset = await result.current.fetchImagery("S2A_20250101", sampleAoi);
    });

    expect(asset).toEqual(sampleAsset);
    expect(result.current.activeAsset).toEqual(sampleAsset);
    expect(result.current.singleStatus).toBe("ready");
    expect(result.current.singleError).toBeNull();
  });

  it("handles fetch failure gracefully", async () => {
    vi.spyOn(imageryClient, "requestImagery").mockRejectedValueOnce(
      new Error("Provider processing failed"),
    );

    const { result } = renderHook(() =>
      useImagery({ selectedAoi: sampleAoi, sceneId: "S2A_20250101" }),
    );

    await act(async () => {
      await result.current.fetchImagery("S2A_20250101", sampleAoi);
    });

    expect(result.current.activeAsset).toBeNull();
    expect(result.current.singleStatus).toBe("error");
    expect(result.current.singleError).toBe("Provider processing failed");
  });

  it("updates opacity and visibility correctly", () => {
    const { result } = renderHook(() => useImagery());

    act(() => {
      result.current.setOpacity(0.75);
      result.current.setVisible(false);
    });

    expect(result.current.opacity).toBe(0.75);
    expect(result.current.visible).toBe(false);
  });

  it("fetches multitemporal imagery and stores alignment status", async () => {
    const temporalResponse = {
      request_id: "req-temporal-123",
      pair_id: "pair-123",
      before_asset: sampleAsset,
      after_asset: { ...sampleAsset, asset_id: "ast-2", scene_id: "S2B_20250120" },
      alignment_status: "aligned" as const,
      data_origin: "real" as const,
      warnings: [],
      processing_metadata: {},
    };

    vi.spyOn(imageryClient, "requestTemporalImagery").mockResolvedValueOnce(temporalResponse);

    const { result } = renderHook(() =>
      useImagery({
        selectedAoi: sampleAoi,
        beforeSceneId: "S2A_20250101",
        afterSceneId: "S2B_20250120",
      }),
    );

    await act(async () => {
      await result.current.fetchTemporalImagery("S2A_20250101", "S2B_20250120", sampleAoi);
    });

    expect(result.current.temporalStatus).toBe("ready");
    expect(result.current.temporalResponse).toEqual(temporalResponse);
    expect(result.current.alignmentStatus).toBe("aligned");
  });

  it("invalidates assets when AOI changes", async () => {
    vi.spyOn(imageryClient, "requestImagery").mockResolvedValueOnce(sampleAsset);

    let currentAoi: SelectedAoi = sampleAoi;
    const { result, rerender } = renderHook(() =>
      useImagery({ selectedAoi: currentAoi, sceneId: "S2A_20250101" }),
    );

    await act(async () => {
      await result.current.fetchImagery("S2A_20250101", currentAoi);
    });

    expect(result.current.activeAsset).toEqual(sampleAsset);

    // Change AOI coordinates
    currentAoi = {
      ...sampleAoi,
      feature: {
        ...sampleAoi.feature,
        geometry: {
          type: "Polygon",
          coordinates: [
            [
              [78.0, 13.0],
              [78.2, 13.0],
              [78.2, 13.2],
              [78.0, 13.2],
              [78.0, 13.0],
            ],
          ],
        },
      },
    };

    rerender();

    expect(result.current.activeAsset).toBeNull();
    expect(result.current.singleStatus).toBe("idle");
  });
});
