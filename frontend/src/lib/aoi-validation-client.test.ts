import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createSelectedAoi } from "./aoi";
import { AoiClientError, validateAoiWithBackend } from "./aoi-validation-client";

const validPolygon = {
  type: "Polygon",
  coordinates: [
    [
      [77.55, 12.9],
      [77.65, 12.9],
      [77.65, 13.0],
      [77.55, 13.0],
      [77.55, 12.9],
    ],
  ],
};

describe("AOI validation client", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("submits AOI to backend and parses successful validation response", async () => {
    const mockResponse = {
      valid: true,
      normalized_geometry: {
        type: "Polygon",
        coordinates: validPolygon.coordinates,
        bbox: [77.55, 12.9, 77.65, 13.0],
        crs: "EPSG:4326",
        area_km2: 120.5,
      },
      bbox: [77.55, 12.9, 77.65, 13.0],
      area_km2: 120.5,
      geometry_type: "Polygon",
      coordinate_count: 5,
      warnings: [],
      errors: [],
      validation_version: "1.0",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    });

    const aoi = createSelectedAoi(validPolygon, "polygon");
    const result = await validateAoiWithBackend(aoi);

    expect(result.valid).toBe(true);
    expect(result.bbox).toEqual([77.55, 12.9, 77.65, 13.0]);
    expect(result.area_km2).toBe(120.5);
    expect(global.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/aoi/validate",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("throws AoiClientError when backend returns structured error", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: () =>
        Promise.resolve(JSON.stringify({ error: { message: "Invalid polygon geometry" } })),
    });

    const aoi = createSelectedAoi(validPolygon, "polygon");
    await expect(validateAoiWithBackend(aoi)).rejects.toThrow(AoiClientError);
  });

  it("falls back gracefully when backend is unreachable", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Network connection refused"));

    const aoi = createSelectedAoi(validPolygon, "polygon");
    const result = await validateAoiWithBackend(aoi);

    expect(result.valid).toBe(true);
    expect(result.warnings[0].message).toMatch(/unreachable/);
  });
});
