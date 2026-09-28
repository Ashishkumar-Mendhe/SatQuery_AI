import { z } from "zod";

import {
  analysisWarningSchema,
  aoiGeometrySchema,
  confidenceBreakdownSchema,
  evidenceItemSchema,
  overlayFeatureSchema,
} from "./analysis-contracts";
import { rasterProvenanceSchema } from "./preparation-contracts";
import { dataOriginSchema } from "./provider-contracts";

export const CHANGE_SCHEMA_VERSION = "1.0.0" as const;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const changeDetectionMethodSchema = z.enum([
  "ndvi_difference",
  "ndwi_difference",
  "ndbi_difference",
  "absolute_index_difference",
  "multiband_change_magnitude",
]);
export type ChangeDetectionMethod = z.infer<typeof changeDetectionMethodSchema>;

export const thresholdStrategySchema = z.enum([
  "fixed",
  "standard_deviation",
  "percentile",
  "otsu",
  "manual",
]);
export type ThresholdStrategy = z.infer<typeof thresholdStrategySchema>;

export const changeDirectionalitySchema = z.enum(["bidirectional", "magnitude_only"]);
export type ChangeDirectionality = z.infer<typeof changeDirectionalitySchema>;

// ---------------------------------------------------------------------------
// Threshold Configuration & Options
// ---------------------------------------------------------------------------

export const changeThresholdConfigSchema = z
  .object({
    strategy: thresholdStrategySchema.default("fixed"),
    positive_threshold: z.number().default(0.15),
    negative_threshold: z.number().default(-0.15),
    std_multiplier: z.number().min(0.5).max(5.0).default(1.5),
    percentile_cutoff: z.number().min(50.0).max(99.9).default(95.0),
    min_cluster_size_pixels: z.number().int().min(1).max(1000).default(5),
    simplify_tolerance_meters: z.number().min(0.0).max(100.0).default(5.0),
  })
  .strict()
  .superRefine((data, context) => {
    if (data.strategy === "fixed" || data.strategy === "manual") {
      if (data.positive_threshold < data.negative_threshold) {
        context.addIssue({
          code: "custom",
          message: "positive_threshold must be greater than or equal to negative_threshold",
        });
      }
    }
  });
export type ChangeThresholdConfig = z.infer<typeof changeThresholdConfigSchema>;
export type ChangeThresholdConfigInput = z.input<typeof changeThresholdConfigSchema>;

export const DEFAULT_THRESHOLD_CONFIG: ChangeThresholdConfig = {
  strategy: "fixed",
  positive_threshold: 0.15,
  negative_threshold: -0.15,
  std_multiplier: 1.5,
  percentile_cutoff: 95.0,
  min_cluster_size_pixels: 5,
  simplify_tolerance_meters: 5.0,
};

export const maskOptionsSchema = z
  .object({
    apply_no_data_mask: z.boolean().default(true),
    apply_cloud_mask: z.boolean().default(true),
    apply_quality_mask: z.boolean().default(true),
    include_shadow_mask: z.boolean().default(false),
    minimum_valid_data_percent: z.number().min(0.0).max(100.0).default(1.0),
    custom_mask_asset_id: z.string().max(120).nullable().optional().default(null),
  })
  .strict();
export type MaskOptions = z.infer<typeof maskOptionsSchema>;
export type MaskOptionsInput = z.input<typeof maskOptionsSchema>;

export const DEFAULT_MASK_OPTIONS: MaskOptions = {
  apply_no_data_mask: true,
  apply_cloud_mask: true,
  apply_quality_mask: true,
  include_shadow_mask: false,
  minimum_valid_data_percent: 1.0,
  custom_mask_asset_id: null,
};

// ---------------------------------------------------------------------------
// Method Definition & Registry Response
// ---------------------------------------------------------------------------

export const changeDetectionDefinitionSchema = z
  .object({
    method: changeDetectionMethodSchema,
    display_name: z.string().min(1).max(120),
    formula: z.string().min(1).max(256),
    input_type: z.string(),
    directionality: changeDirectionalitySchema,
    expected_range: z.tuple([z.number(), z.number()]),
    default_threshold_config: changeThresholdConfigSchema,
    supported_sensors: z.array(z.string()).default(["Sentinel-2", "Landsat-8", "Landsat-9"]),
    description: z.string().min(1).max(500),
    limitations: z.string().min(1).max(500),
    default_color_ramp: z.string().default("RdYlGn"),
    version: z.string().default(CHANGE_SCHEMA_VERSION),
  })
  .strict();
export type ChangeDetectionDefinition = z.infer<typeof changeDetectionDefinitionSchema>;

export const changeMethodsResponseSchema = z
  .object({
    methods: z.array(changeDetectionDefinitionSchema),
    total_count: z.number().int().nonnegative(),
    version: z.string().default(CHANGE_SCHEMA_VERSION),
  })
  .strict();
export type ChangeMethodsResponse = z.infer<typeof changeMethodsResponseSchema>;

// ---------------------------------------------------------------------------
// Metrics, Pixel Counts & Regions
// ---------------------------------------------------------------------------

export const changePixelCountsSchema = z
  .object({
    total_aoi_pixels: z.number().int().nonnegative(),
    shared_valid_pixels: z.number().int().nonnegative(),
    gain_pixels: z.number().int().nonnegative(),
    loss_pixels: z.number().int().nonnegative(),
    stable_pixels: z.number().int().nonnegative(),
    uncertain_pixels: z.number().int().nonnegative(),
    gain_percent: z.number().min(0.0).max(100.0),
    loss_percent: z.number().min(0.0).max(100.0),
    stable_percent: z.number().min(0.0).max(100.0),
    uncertain_percent: z.number().min(0.0).max(100.0),
  })
  .strict();
export type ChangePixelCounts = z.infer<typeof changePixelCountsSchema>;

export const changeMetricsSchema = z
  .object({
    gain_area_km2: z.number().nonnegative(),
    loss_area_km2: z.number().nonnegative(),
    stable_area_km2: z.number().nonnegative(),
    net_change_area_km2: z.number(),
    shared_valid_area_km2: z.number().nonnegative(),
    pixel_counts: changePixelCountsSchema,
    positive_threshold_applied: z.number(),
    negative_threshold_applied: z.number(),
    threshold_strategy: thresholdStrategySchema,
  })
  .strict();
export type ChangeMetrics = z.infer<typeof changeMetricsSchema>;

export const changeRegionSchema = z
  .object({
    id: z.string().min(1).max(120),
    category: z.string(),
    geometry: aoiGeometrySchema,
    area_km2: z.number().nonnegative(),
    pixel_count: z.number().int().positive(),
    mean_magnitude: z.number(),
    min_magnitude: z.number(),
    max_magnitude: z.number(),
    threshold_rule: z.string(),
    evidence_id: z.string(),
    confidence: z.number().min(0.0).max(1.0),
    warnings: z.array(z.string()).default([]),
  })
  .strict();
export type ChangeRegion = z.infer<typeof changeRegionSchema>;

// ---------------------------------------------------------------------------
// Request & Response
// ---------------------------------------------------------------------------

export const changeDetectionRequestSchema = z
  .object({
    request_id: z.string().nullable().optional(),
    prepared_pair_id: z.string().min(1).max(256),
    before_prepared_asset_id: z.string().min(1).max(256),
    after_prepared_asset_id: z.string().min(1).max(256),
    aoi: aoiGeometrySchema,
    method: changeDetectionMethodSchema.default("ndvi_difference"),
    threshold_config: changeThresholdConfigSchema.default(DEFAULT_THRESHOLD_CONFIG),
    mask_options: maskOptionsSchema.default(DEFAULT_MASK_OPTIONS),
    generate_overlay: z.boolean().default(true),
    generate_evidence: z.boolean().default(true),
    generate_regions: z.boolean().default(true),
    max_regions: z.number().int().min(1).max(500).default(100),
  })
  .strict();
export type ChangeDetectionRequest = z.infer<typeof changeDetectionRequestSchema>;
export type ChangeDetectionRequestInput = z.input<typeof changeDetectionRequestSchema>;

export const changeDetectionResultSchema = z
  .object({
    result_id: z.string().min(1).max(120),
    pair_id: z.string().min(1).max(256),
    method: changeDetectionMethodSchema,
    definition: changeDetectionDefinitionSchema,
    before_scene_id: z.string().min(1).max(256),
    after_scene_id: z.string().min(1).max(256),
    before_asset_id: z.string().min(1).max(256),
    after_asset_id: z.string().min(1).max(256),
    difference_asset_id: z.string().min(1).max(256),
    preview_asset_id: z.string().nullable().optional(),
    classified_preview_asset_id: z.string().nullable().optional(),
    metrics: changeMetricsSchema,
    regions: z.array(changeRegionSchema).default([]),
    overlay: overlayFeatureSchema.nullable().optional(),
    classified_overlay: overlayFeatureSchema.nullable().optional(),
    evidence: z.array(evidenceItemSchema).default([]),
    confidence_breakdown: confidenceBreakdownSchema,
    confidence: z.number().min(0.0).max(1.0),
    warnings: z.array(analysisWarningSchema).default([]),
    provenance: rasterProvenanceSchema,
    data_origin: dataOriginSchema.default("real"),
    created_at: z.string().datetime({ offset: true }),
  })
  .strict();
export type ChangeDetectionResult = z.infer<typeof changeDetectionResultSchema>;
