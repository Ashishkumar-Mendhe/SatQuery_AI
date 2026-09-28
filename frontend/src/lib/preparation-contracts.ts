import { z } from "zod";

import { analysisWarningSchema, aoiGeometrySchema, boundingBoxSchema } from "./analysis-contracts";
import { imageryFormatSchema } from "./imagery-contracts";
import { dataOriginSchema } from "./provider-contracts";

export const PREPARATION_CONTRACT_VERSION = "1.0" as const;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const rasterPreparationModeSchema = z.enum([
  "single_scene",
  "temporal_pair",
  "optical_pair",
  "sar_pair",
  "multimodal_inputs",
]);
export type RasterPreparationMode = z.infer<typeof rasterPreparationModeSchema>;

export const targetGridStrategySchema = z.enum([
  "reference_before",
  "reference_after",
  "highest_resolution",
  "lowest_resolution",
  "configured_resolution",
  "common_intersection",
]);
export type TargetGridStrategy = z.infer<typeof targetGridStrategySchema>;

export const resamplingMethodSchema = z.enum(["nearest", "bilinear", "cubic", "average"]);
export type ResamplingMethod = z.infer<typeof resamplingMethodSchema>;

export const preparationStatusSchema = z.enum([
  "queued",
  "inspecting_inputs",
  "validating_inputs",
  "clipping",
  "reprojecting",
  "resampling",
  "aligning",
  "applying_masks",
  "validating_outputs",
  "generating_previews",
  "ready",
  "ready_with_warnings",
  "failed",
  "cancelled",
  "expired",
]);
export type PreparationStatus = z.infer<typeof preparationStatusSchema>;

// ---------------------------------------------------------------------------
// Metrics & Provenance
// ---------------------------------------------------------------------------

export const rasterQualityMetricsSchema = z
  .object({
    valid_data_percent: z.number().min(0).max(100),
    no_data_percent: z.number().min(0).max(100),
    aoi_coverage_percent: z.number().min(0).max(100),
    shared_coverage_percent: z.number().min(0).max(100).nullable().optional(),
    resolution_consistency: z.number().min(0).max(1),
    grid_alignment_score: z.number().min(0).max(1),
    metadata_completeness: z.number().min(0).max(1),
    quality_score: z.number().min(0).max(1),
    factors: z.record(z.string(), z.number()).default({}),
    limitations: z.array(z.string()).default([]),
  })
  .strict();
export type RasterQualityMetrics = z.infer<typeof rasterQualityMetricsSchema>;

export const rasterProvenanceSchema = z
  .object({
    pipeline_version: z.string().default("1.0"),
    source_asset_ids: z.array(z.string()).min(1),
    source_scene_ids: z.array(z.string()).min(1),
    operations: z.array(z.string()).default([]),
    parameters: z.record(z.string(), z.unknown()).default({}),
    software: z.string().default("SatQuery Raster Harmonizer Engine v1.0"),
    started_at: z.string().datetime({ offset: true }),
    completed_at: z.string().datetime({ offset: true }),
    duration_milliseconds: z.number().nonnegative(),
    data_origin: dataOriginSchema.default("real"),
  })
  .strict();
export type RasterProvenance = z.infer<typeof rasterProvenanceSchema>;

// ---------------------------------------------------------------------------
// Request Schemas
// ---------------------------------------------------------------------------

export const rasterPreparationRequestSchema = z
  .object({
    request_id: z.string().nullable().optional(),
    source_asset_id: z.string().min(1).max(256),
    scene_id: z.string().min(1).max(256),
    aoi: aoiGeometrySchema,
    target_crs: z.string().nullable().optional(),
    target_resolution_meters: z.number().min(0.1).max(1000.0).nullable().optional(),
    resampling_method: resamplingMethodSchema.default("bilinear"),
    selected_bands: z.array(z.string()).nullable().optional(),
    clip_to_aoi: z.boolean().default(true),
    mask_no_data: z.boolean().default(true),
    generate_preview: z.boolean().default(true),
    output_format: imageryFormatSchema.default("geotiff"),
    options: z.record(z.string(), z.unknown()).default({}),
  })
  .strict()
  .refine((data) => data.output_format === "geotiff" || data.output_format === "cog", {
    message: "Prepared rasters must be saved in geotiff or cog format.",
  });
export type RasterPreparationRequest = z.infer<typeof rasterPreparationRequestSchema>;
export type RasterPreparationRequestInput = z.input<typeof rasterPreparationRequestSchema>;

export const temporalRasterPreparationRequestSchema = z
  .object({
    request_id: z.string().nullable().optional(),
    pair_id: z.string().min(1).max(256),
    before_asset_id: z.string().min(1).max(256),
    after_asset_id: z.string().min(1).max(256),
    aoi: aoiGeometrySchema,
    strategy: targetGridStrategySchema.default("common_intersection"),
    target_crs: z.string().nullable().optional(),
    target_resolution_meters: z.number().min(0.1).max(1000.0).nullable().optional(),
    optical_resampling_method: resamplingMethodSchema.default("bilinear"),
    sar_resampling_method: resamplingMethodSchema.default("bilinear"),
    mask_resampling_method: resamplingMethodSchema.default("nearest"),
    use_common_intersection: z.boolean().default(true),
    selected_bands: z.array(z.string()).nullable().optional(),
    required_polarizations: z.array(z.string()).nullable().optional(),
    generate_previews: z.boolean().default(true),
    options: z.record(z.string(), z.unknown()).default({}),
  })
  .strict()
  .refine((data) => data.before_asset_id !== data.after_asset_id, {
    message: "before_asset_id and after_asset_id must be distinct assets.",
  });
export type TemporalRasterPreparationRequest = z.infer<
  typeof temporalRasterPreparationRequestSchema
>;
export type TemporalRasterPreparationRequestInput = z.input<
  typeof temporalRasterPreparationRequestSchema
>;

// ---------------------------------------------------------------------------
// Response / Asset Schemas
// ---------------------------------------------------------------------------

export const preparedRasterAssetSchema = z
  .object({
    asset_id: z.string().min(1).max(256),
    source_asset_ids: z.array(z.string()).min(1),
    scene_ids: z.array(z.string()).min(1),
    role: z.string().default("single"),
    format: imageryFormatSchema.default("geotiff"),
    crs: z.string().min(1).max(64),
    bbox: boundingBoxSchema,
    geometry: aoiGeometrySchema.nullable().optional(),
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    pixel_size_x: z.number().positive(),
    pixel_size_y: z.number().positive(),
    transform: z.array(z.number()),
    band_count: z.number().int().positive(),
    band_names: z.array(z.string()).default([]),
    data_type: z.string().min(1).max(32),
    no_data_values: z.array(z.number().nullable()).default([]),
    valid_pixel_count: z.number().int().nonnegative(),
    invalid_pixel_count: z.number().int().nonnegative(),
    valid_data_percent: z.number().min(0.0).max(100.0),
    resolution_meters: z.number().positive(),
    resampling_method: resamplingMethodSchema,
    clip_applied: z.boolean().default(true),
    mask_applied: z.boolean().default(true),
    created_at: z.string().datetime({ offset: true }),
    expires_at: z.string().datetime({ offset: true }).nullable().optional(),
    data_origin: dataOriginSchema.default("real"),
    provenance: rasterProvenanceSchema,
    warnings: z.array(analysisWarningSchema).default([]),
    preview_url: z.string().nullable().optional(),
    metadata_url: z.string().nullable().optional(),
  })
  .strict();
export type PreparedRasterAsset = z.infer<typeof preparedRasterAssetSchema>;

export const preparedTemporalPairSchema = z
  .object({
    preparation_id: z.string().min(1).max(256),
    pair_id: z.string().min(1).max(256),
    before_asset: preparedRasterAssetSchema,
    after_asset: preparedRasterAssetSchema,
    common_crs: z.string().min(1).max(64),
    common_bbox: boundingBoxSchema,
    common_width: z.number().int().positive(),
    common_height: z.number().int().positive(),
    common_transform: z.array(z.number()),
    common_resolution_meters: z.number().positive(),
    shared_valid_pixel_count: z.number().int().nonnegative(),
    shared_valid_percent: z.number().min(0.0).max(100.0),
    alignment_status: z.enum([
      "aligned",
      "approximately_aligned",
      "requires_alignment",
      "incompatible",
      "unknown",
    ]),
    quality: rasterQualityMetricsSchema,
    warnings: z.array(analysisWarningSchema).default([]),
    blocking_issues: z.array(z.string()).default([]),
    ready_for_analysis: z.boolean(),
    created_at: z.string().datetime({ offset: true }),
    expires_at: z.string().datetime({ offset: true }).nullable().optional(),
    processing_metadata: z.record(z.string(), z.unknown()).default({}),
  })
  .strict();
export type PreparedTemporalPair = z.infer<typeof preparedTemporalPairSchema>;
