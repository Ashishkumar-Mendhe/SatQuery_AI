import { z } from "zod";

import { analysisWarningSchema, aoiGeometrySchema, boundingBoxSchema } from "./analysis-contracts";
import { dataOriginSchema } from "./provider-contracts";

export const IMAGERY_CONTRACT_VERSION = "1.0" as const;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const imageryProductTypeSchema = z.enum([
  "catalogue_thumbnail",
  "map_preview",
  "analysis_raster",
]);
export type ImageryProductType = z.infer<typeof imageryProductTypeSchema>;

export const visualizationPresetSchema = z.enum([
  "true_color",
  "false_color",
  "vegetation",
  "water",
  "urban",
  "sar_grayscale",
  "sar_vv",
  "sar_vh",
]);
export type VisualizationPreset = z.infer<typeof visualizationPresetSchema>;

export const imageryFormatSchema = z.enum(["png", "jpeg", "geotiff", "cog"]);
export type ImageryFormat = z.infer<typeof imageryFormatSchema>;

export const imageryJobStatusSchema = z.enum([
  "queued",
  "validating",
  "authenticating",
  "requesting_provider",
  "downloading",
  "validating_raster",
  "preparing_preview",
  "ready",
  "partially_ready",
  "failed",
  "cancelled",
  "expired",
]);
export type ImageryJobStatus = z.infer<typeof imageryJobStatusSchema>;

export const alignmentStatusSchema = z.enum([
  "aligned",
  "approximately_aligned",
  "requires_alignment",
  "incompatible",
  "unknown",
]);
export type AlignmentStatus = z.infer<typeof alignmentStatusSchema>;

// ---------------------------------------------------------------------------
// Metadata & Requests
// ---------------------------------------------------------------------------

export const rasterMetadataSchema = z
  .object({
    crs: z.string().min(1).max(64),
    bbox: boundingBoxSchema,
    width: z.number().int().positive().max(8192),
    height: z.number().int().positive().max(8192),
    pixel_size_x: z.number().positive(),
    pixel_size_y: z.number().positive(),
    band_count: z.number().int().positive().max(32),
    band_names: z.array(z.string()).default([]),
    data_type: z.string().min(1).max(32),
    no_data_values: z.array(z.number().nullable()).default([]),
    acquisition_time: z.string().datetime({ offset: true }).nullable().optional(),
    scene_id: z.string().min(1),
    provider: z.string().min(1),
    collection: z.string().min(1),
    processing_level: z.string().nullable().optional(),
    transform: z.array(z.number()).nullable().optional(),
    statistics: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type RasterMetadata = z.infer<typeof rasterMetadataSchema>;

export const imageryRequestSchema = z
  .object({
    scene_id: z.string().min(1).max(256),
    aoi: aoiGeometrySchema,
    product_type: imageryProductTypeSchema.default("map_preview"),
    visualization_preset: visualizationPresetSchema.default("true_color"),
    output_format: imageryFormatSchema.default("png"),
    width: z.number().int().positive().max(4096).nullable().optional(),
    height: z.number().int().positive().max(4096).nullable().optional(),
    resolution_meters: z.number().min(1.0).max(1000.0).nullable().optional(),
    bands: z.array(z.string()).nullable().optional(),
    polarizations: z.array(z.string()).nullable().optional(),
    resampling_method: z.enum(["nearest", "bilinear", "cubic", "lanczos"]).default("bilinear"),
    map_projection: z.string().default("EPSG:3857"),
    include_metadata: z.boolean().default(true),
    request_id: z.string().nullable().optional(),
  })
  .strict()
  .refine(
    (data) => {
      if (data.product_type === "analysis_raster") {
        return data.output_format === "geotiff" || data.output_format === "cog";
      }
      return true;
    },
    { message: "analysis_raster product type requires geotiff or cog format" },
  );
export type ImageryRequest = z.infer<typeof imageryRequestSchema>;
export type ImageryRequestInput = z.input<typeof imageryRequestSchema>;

export const temporalImageryRequestSchema = z
  .object({
    before_scene_id: z.string().min(1).max(256),
    after_scene_id: z.string().min(1).max(256),
    aoi: aoiGeometrySchema,
    product_type: imageryProductTypeSchema.default("map_preview"),
    before_preset: visualizationPresetSchema.default("true_color"),
    after_preset: visualizationPresetSchema.default("true_color"),
    output_format: imageryFormatSchema.default("png"),
    width: z.number().int().positive().max(4096).nullable().optional(),
    height: z.number().int().positive().max(4096).nullable().optional(),
    resolution_meters: z.number().min(1.0).max(1000.0).nullable().optional(),
    align_outputs: z.boolean().default(true),
    include_metadata: z.boolean().default(true),
    request_id: z.string().nullable().optional(),
  })
  .strict()
  .refine((data) => data.before_scene_id !== data.after_scene_id, {
    message: "before_scene_id and after_scene_id must be distinct",
  });
export type TemporalImageryRequest = z.infer<typeof temporalImageryRequestSchema>;
export type TemporalImageryRequestInput = z.input<typeof temporalImageryRequestSchema>;

export const imageryAssetSchema = z
  .object({
    asset_id: z.string().min(1).max(256),
    scene_id: z.string().min(1).max(256),
    product_type: imageryProductTypeSchema,
    format: imageryFormatSchema,
    content_type: z.string().min(1).max(64),
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    resolution_meters: z.number().positive(),
    bbox: boundingBoxSchema,
    geometry: aoiGeometrySchema.nullable().optional(),
    crs: z.string().min(1).max(64),
    bands: z.array(z.string()).default([]),
    size_bytes: z.number().int().nonnegative(),
    checksum: z.string().min(1).max(128),
    created_at: z.string().datetime({ offset: true }),
    expires_at: z.string().datetime({ offset: true }).nullable().optional(),
    data_origin: dataOriginSchema.default("real"),
    provider_id: z.string().min(1),
    visualization_preset: visualizationPresetSchema.nullable().optional(),
    display_url: z.string().min(1),
    metadata_url: z.string().nullable().optional(),
    download_url: z.string().nullable().optional(),
    warnings: z.array(analysisWarningSchema).default([]),
    processing_metadata: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();
export type ImageryAsset = z.infer<typeof imageryAssetSchema>;

export const temporalImageryResponseSchema = z
  .object({
    request_id: z.string().min(1),
    pair_id: z.string().min(1),
    before_asset: imageryAssetSchema,
    after_asset: imageryAssetSchema,
    alignment_status: alignmentStatusSchema,
    data_origin: dataOriginSchema.default("real"),
    warnings: z.array(analysisWarningSchema).default([]),
    processing_metadata: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();
export type TemporalImageryResponse = z.infer<typeof temporalImageryResponseSchema>;
