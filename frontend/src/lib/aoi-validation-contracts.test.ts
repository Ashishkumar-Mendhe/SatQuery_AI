import { describe, expect, it } from "vitest";
import {
  aoiValidationCodeSchema,
  aoiValidationIssueSchema,
  aoiValidationRequestSchema,
  aoiValidationResponseSchema,
} from "./aoi-validation-contracts";

describe("AOI validation contracts", () => {
  it("validates valid AOI validation codes", () => {
    expect(aoiValidationCodeSchema.parse("AOI_REQUIRED")).toBe("AOI_REQUIRED");
    expect(aoiValidationCodeSchema.parse("AOI_SELF_INTERSECTION")).toBe("AOI_SELF_INTERSECTION");
    expect(() => aoiValidationCodeSchema.parse("UNKNOWN_CODE")).toThrow();
  });

  it("validates structured validation issue schema", () => {
    const issue = {
      code: "AOI_TOO_LARGE",
      message: "The AOI exceeds 10,000 km².",
      severity: "error",
      field: "coordinates[0]",
    };
    const parsed = aoiValidationIssueSchema.parse(issue);
    expect(parsed.code).toBe("AOI_TOO_LARGE");
    expect(parsed.severity).toBe("error");
  });

  it("validates request payload schema", () => {
    const request = {
      geometry: {
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
        bbox: [77.55, 12.9, 77.65, 13.0],
        crs: "EPSG:4326",
        area_km2: 120.5,
      },
      client_area_km2: 120.5,
      intended_mode: "change_detection",
    };
    const parsed = aoiValidationRequestSchema.parse(request);
    expect(parsed.geometry.type).toBe("Polygon");
    expect(parsed.client_area_km2).toBe(120.5);
  });

  it("validates response payload schema", () => {
    const response = {
      valid: true,
      normalized_geometry: {
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
    const parsed = aoiValidationResponseSchema.parse(response);
    expect(parsed.valid).toBe(true);
    expect(parsed.area_km2).toBe(120.5);
  });
});
