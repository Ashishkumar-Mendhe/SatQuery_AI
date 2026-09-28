import { z } from "zod";
import { aoiGeometrySchema } from "./analysis-contracts";

export const AOI_VALIDATION_SCHEMA_VERSION = "1.0" as const;

export const aoiValidationCodeSchema = z.enum([
  "AOI_REQUIRED",
  "AOI_EMPTY",
  "INVALID_COORDINATE",
  "LONGITUDE_OUT_OF_RANGE",
  "LATITUDE_OUT_OF_RANGE",
  "POLYGON_NOT_CLOSED",
  "INSUFFICIENT_VERTICES",
  "AOI_SELF_INTERSECTION",
  "AOI_TOO_SMALL",
  "AOI_TOO_LARGE",
  "TOO_MANY_COORDINATES",
  "UNSUPPORTED_GEOMETRY",
  "UNSUPPORTED_ANTIMERIDIAN_CROSSING",
  "POLYGON_HOLES_UNSUPPORTED",
]);
export type AoiValidationCode = z.infer<typeof aoiValidationCodeSchema>;

export const aoiIssueSeveritySchema = z.enum(["info", "warning", "error"]);
export type AoiIssueSeverity = z.infer<typeof aoiIssueSeveritySchema>;

export const aoiValidationIssueSchema = z.object({
  code: aoiValidationCodeSchema,
  message: z.string().min(1),
  severity: aoiIssueSeveritySchema,
  field: z.string().nullable().optional(),
});
export type AoiValidationIssue = z.infer<typeof aoiValidationIssueSchema>;

export const aoiValidationRequestSchema = z.object({
  geometry: aoiGeometrySchema,
  client_area_km2: z.number().nonnegative().nullable().optional(),
  intended_mode: z.string().nullable().optional(),
});
export type AoiValidationRequest = z.infer<typeof aoiValidationRequestSchema>;

export const aoiValidationResponseSchema = z.object({
  valid: z.boolean(),
  normalized_geometry: aoiGeometrySchema.nullable().optional(),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable().optional(),
  area_km2: z.number().nonnegative().nullable().optional(),
  geometry_type: z.enum(["Point", "Polygon", "MultiPolygon"]).nullable().optional(),
  coordinate_count: z.number().int().nonnegative().default(0),
  warnings: z.array(aoiValidationIssueSchema).default([]),
  errors: z.array(aoiValidationIssueSchema).default([]),
  validation_version: z.literal("1.0").default("1.0"),
});
export type AoiValidationResponse = z.infer<typeof aoiValidationResponseSchema>;
