import { afterEach, describe, expect, it, vi } from "vitest";
import { SAR_IMAGE_LAYER_ID, SAR_IMAGE_SOURCE_ID, syncSarLayer } from "./sar-map-layer";

afterEach(() => vi.unstubAllEnvs());

describe("SAR map preview", () => {
  it("places a trusted preview at its actual WGS84 bounds and adjusts opacity", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    const map = {
      getLayer: vi.fn().mockReturnValue(null),
      getSource: vi.fn().mockReturnValue(null),
      removeLayer: vi.fn(),
      removeSource: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
    };
    syncSarLayer(map as never, {
      previewUrl: "/api/v1/sar/preparations/00000000-0000-4000-8000-000000000001/preview.png",
      preparationId: "00000000-0000-4000-8000-000000000001",
      bounds: [77.5, 12.9, 77.51, 12.91],
      opacity: 0.35,
      visible: true,
    });
    expect(map.addSource).toHaveBeenCalledWith(
      SAR_IMAGE_SOURCE_ID,
      expect.objectContaining({
        type: "image",
        coordinates: [
          [77.5, 12.91],
          [77.51, 12.91],
          [77.51, 12.9],
          [77.5, 12.9],
        ],
      }),
    );
    expect(map.addLayer).toHaveBeenCalledWith(
      expect.objectContaining({
        id: SAR_IMAGE_LAYER_ID,
        paint: { "raster-opacity": 0.35 },
      }),
    );
  });

  it("rejects client URLs outside the trusted SAR preview route", () => {
    const map = {
      getLayer: vi.fn().mockReturnValue(null),
      getSource: vi.fn().mockReturnValue(null),
      removeLayer: vi.fn(),
      removeSource: vi.fn(),
      addSource: vi.fn(),
      addLayer: vi.fn(),
    };
    syncSarLayer(map as never, {
      previewUrl: "https://untrusted.invalid/raster.png",
      preparationId: "x",
      bounds: [77.5, 12.9, 77.51, 12.91],
      opacity: 1,
      visible: true,
    });
    expect(map.addSource).not.toHaveBeenCalled();
  });
});
