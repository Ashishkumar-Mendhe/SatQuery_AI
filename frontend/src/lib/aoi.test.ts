import { describe, expect, it } from "vitest";

import {
  AoiValidationError,
  createAoiFromBounds,
  createSelectedAoi,
  formatAoiArea,
  getMapDisplayIssue,
  parseGeoJsonText,
  serializeAoi,
} from "./aoi";

// Synthetic geometry fixtures; these are not measured real-world findings.
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

describe("AOI geometry contract", () => {
  it.each([
    [
      [
        [0, 0],
        [3, 0],
        [1, 0],
        [1, 1],
        [0, 0],
      ],
    ],
    [
      [
        [0, 0],
        [1, 1],
        [2, 2],
        [0, 0],
      ],
    ],
    [
      [
        [0, 0],
        [1, 0],
        [1, 1],
        [1, 0],
        [0, 0],
      ],
    ],
    [
      [
        [0, 0],
        [Infinity, 0],
        [1, 1],
        [0, 0],
      ],
    ],
    [
      [
        [0, 0],
        [181, 0],
        [1, 1],
        [0, 0],
      ],
    ],
  ])("rejects synthetic degenerate or out-of-range ring %j", (ring) => {
    expect(() => createSelectedAoi({ type: "Polygon", coordinates: [ring] }, "geojson")).toThrow();
  });

  it("enforces file and vertex limits and rejects legacy CRS metadata", () => {
    expect(() => parseGeoJsonText(" ".repeat(1_000_001))).toThrow(/1 MB/);
    expect(() =>
      createSelectedAoi({ ...validPolygon, coordinates: [Array(501).fill([0, 0])] }, "geojson"),
    ).toThrow(/500/);
    expect(() => createSelectedAoi({ ...validPolygon, crs: {} }, "geojson")).toThrow(/CRS/);
    expect(formatAoiArea(0.2)).toBe("<1 m²");
    expect(formatAoiArea(10_000)).toBe("1.00 ha");
  });
  it("keeps longitude-latitude order and recomputes bounds and geodesic area", () => {
    const aoi = createSelectedAoi(validPolygon, "polygon");

    expect(aoi.bounds).toEqual([77.55, 12.9, 77.65, 13]);
    expect(aoi.feature.geometry.coordinates[0][0]).toEqual([77.55, 12.9]);
    expect(aoi.areaSquareMeters).toBeGreaterThan(100_000_000);
    expect(formatAoiArea(aoi.areaSquareMeters)).toMatch(/km²$/);
  });

  it.each([
    [
      "unclosed ring",
      { ...validPolygon, coordinates: [[...validPolygon.coordinates[0].slice(0, -1)]] },
    ],
    [
      "self intersection",
      {
        type: "Polygon",
        coordinates: [
          [
            [0, 0],
            [1, 1],
            [1, 0],
            [0, 1],
            [0, 0],
          ],
        ],
      },
    ],
    [
      "polygon hole",
      { ...validPolygon, coordinates: [validPolygon.coordinates[0], validPolygon.coordinates[0]] },
    ],
    ["multipolygon", { type: "MultiPolygon", coordinates: [[validPolygon.coordinates]] }],
    [
      "antimeridian crossing",
      {
        type: "Polygon",
        coordinates: [
          [
            [170, 10],
            [-170, 10],
            [-170, 20],
            [170, 20],
            [170, 10],
          ],
        ],
      },
    ],
  ])("rejects %s without changing it", (_label, geometry) => {
    expect(() => createSelectedAoi(geometry, "geojson")).toThrow(AoiValidationError);
  });

  it("validates bbox ordering and creates a closed rectangle", () => {
    const aoi = createAoiFromBounds([-1, 50, 1, 51]);
    const ring = aoi.feature.geometry.coordinates[0];

    expect(ring[0]).toEqual(ring[ring.length - 1]);
    expect(aoi.bounds).toEqual([-1, 50, 1, 51]);
    expect(() => createAoiFromBounds([170, -10, -170, 10])).toThrow(/Antimeridian/);
  });

  it("keeps geographic validity separate from the Web Mercator display limit", () => {
    const polarAoi = createAoiFromBounds([10, 86, 11, 87]);

    expect(polarAoi.bounds[1]).toBe(86);
    expect(getMapDisplayIssue(polarAoi)).toMatch(/valid WGS84/);
  });

  it("round-trips exported GeoJSON and ignores untrusted bbox metadata", () => {
    const original = createSelectedAoi(validPolygon, "polygon", "Bengaluru sample");
    const exported = JSON.parse(serializeAoi(original));
    exported.bbox = [-180, -90, 180, 90];
    const restored = parseGeoJsonText(JSON.stringify(exported));

    expect(restored.bounds).toEqual(original.bounds);
    expect(restored.name).toBe("Bengaluru sample");
    expect(restored.feature.geometry.coordinates).toEqual(original.feature.geometry.coordinates);
  });
});
