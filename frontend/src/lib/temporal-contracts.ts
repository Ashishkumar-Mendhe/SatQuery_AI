import { z } from "zod";

import {
  analysisModeSchema,
  analysisWarningSchema,
  aoiGeometrySchema,
  boundingBoxSchema,
  satelliteSceneSchema,
  sceneSelectionSchema,
  sensorTypeSchema,
  warningSeveritySchema,
} from "./analysis-contracts";
import { dataOriginSchema, providerExecutionMetadataSchema } from "./provider-contracts";

export const TEMPORAL_PAIRING_SCHEMA_VERSION = "1.0" as const;

// ---------------------------------------------------------------------------
// Enums & Status
// ---------------------------------------------------------------------------

export const pairCompatibilityStatusSchema = z.enum([
  "compatible",
  "compatible_with_warnings",
  "incompatible",
  "unknown",
]);
export type PairCompatibilityStatus = z.infer<typeof pairCompatibilityStatusSchema>;

// ---------------------------------------------------------------------------
// Temporal Window & Search Contracts
// ---------------------------------------------------------------------------

export const temporalWindowSchema = z
  .object({
    start_date: z.string().min(1),
    end_date: z.string().min(1),
    label: z.string().default("period"),
    target_date: z.string().nullable().optional(),
  })
  .strict()
  .refine(
    (data) => {
      const s = Date.parse(data.start_date);
      const e = Date.parse(data.end_date);
      if (Number.isFinite(s) && Number.isFinite(e)) {
        return s <= e;
      }
      return data.start_date <= data.end_date;
    },
    { message: "start_date cannot be after end_date" },
  );
export type TemporalWindow = z.infer<typeof temporalWindowSchema>;

export const pairingPreferencesSchema = z
  .object({
    prefer_same_collection: z.boolean().default(true),
    prefer_same_platform: z.boolean().default(true),
    prefer_same_sensor: z.boolean().default(true),
    prefer_lowest_cloud_cover: z.boolean().default(true),
    prefer_closest_season: z.boolean().default(false),
    maximum_temporal_gap_days: z.number().int().min(1).max(3650).nullable().optional(),
    maximum_acquisition_time_difference_minutes: z.number().nonnegative().nullable().optional(),
    required_polarizations: z.array(z.string()).nullable().optional(),
    required_bands: z.array(z.string()).nullable().optional(),
    min_aoi_coverage_percent: z.number().min(0).max(100).default(10),
  })
  .strict();
export type PairingPreferences = z.infer<typeof pairingPreferencesSchema>;

export const temporalSearchRequestSchema = z
  .object({
    aoi: aoiGeometrySchema,
    before_window: temporalWindowSchema,
    after_window: temporalWindowSchema,
    collections: z.array(z.string()).default([]),
    sensor_types: z.array(sensorTypeSchema).default([]),
    max_cloud_cover: z.number().min(0).max(100).default(20),
    required_bands: z.array(z.string()).default([]),
    limit_per_window: z.number().int().min(1).max(100).default(20),
    sort_order: z.enum(["asc", "desc"]).default("desc"),
    include_preview: z.boolean().default(true),
    pairing_preferences: pairingPreferencesSchema.nullable().optional(),
  })
  .strict()
  .refine(
    (data) => {
      const bStart = Date.parse(data.before_window.start_date);
      const aStart = Date.parse(data.after_window.start_date);
      if (Number.isFinite(bStart) && Number.isFinite(aStart)) {
        return bStart <= aStart;
      }
      return data.before_window.start_date <= data.after_window.start_date;
    },
    { message: "before_window start_date cannot be after after_window start_date" },
  );
export type TemporalSearchRequest = z.infer<typeof temporalSearchRequestSchema>;
export type TemporalSearchRequestInput = z.input<typeof temporalSearchRequestSchema>;

// ---------------------------------------------------------------------------
// Compatibility & Factor Breakdown Contracts
// ---------------------------------------------------------------------------

export const pairCompatibilityIssueSchema = z
  .object({
    code: z.string().min(1),
    severity: warningSeveritySchema,
    title: z.string().min(1),
    message: z.string().min(1),
    field: z.string().nullable().optional(),
    suggested_action: z.string().nullable().optional(),
    blocking: z.boolean().default(false),
    metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type PairCompatibilityIssue = z.infer<typeof pairCompatibilityIssueSchema>;

export const compatibilityFactorScoreSchema = z
  .object({
    name: z.string().min(1),
    score: z.number().min(0).max(1),
    weight: z.number().min(0).max(1),
    weighted_score: z.number().min(0).max(1),
    status: z.enum(["optimal", "acceptable", "suboptimal", "incompatible", "unknown"]),
    details: z.string(),
  })
  .strict();
export type CompatibilityFactorScore = z.infer<typeof compatibilityFactorScoreSchema>;

export const spatialOverlapMetricsSchema = z
  .object({
    before_aoi_coverage_percent: z.number().min(0).max(100),
    after_aoi_coverage_percent: z.number().min(0).max(100),
    mutual_aoi_coverage_percent: z.number().min(0).max(100),
    scene_overlap_percent: z.number().min(0).max(100),
    shared_bbox: boundingBoxSchema.nullable().optional(),
  })
  .strict();
export type SpatialOverlapMetrics = z.infer<typeof spatialOverlapMetricsSchema>;

export const recommendedPairSchema = z
  .object({
    before_scene_id: z.string().min(1),
    after_scene_id: z.string().min(1),
    compatibility_score: z.number().min(0).max(1),
    status: pairCompatibilityStatusSchema,
    reason: z.string(),
    explanation: z.array(z.string()).default([]),
  })
  .strict();
export type RecommendedPair = z.infer<typeof recommendedPairSchema>;

export const temporalSceneCandidatesSchema = z
  .object({
    search_id: z.string(),
    before_scenes: z.array(satelliteSceneSchema).default([]),
    after_scenes: z.array(satelliteSceneSchema).default([]),
    provider_id: z.string(),
    execution: providerExecutionMetadataSchema,
    warnings: z.array(analysisWarningSchema).default([]),
    data_origin: dataOriginSchema,
    generated_at: z.string(),
    recommended_pair: recommendedPairSchema.nullable().optional(),
  })
  .strict();
export type TemporalSceneCandidates = z.infer<typeof temporalSceneCandidatesSchema>;

// ---------------------------------------------------------------------------
// Validation API Contracts
// ---------------------------------------------------------------------------

export const temporalPairValidationRequestSchema = z
  .object({
    aoi: aoiGeometrySchema,
    before_scene: satelliteSceneSchema,
    after_scene: satelliteSceneSchema,
    analysis_mode: analysisModeSchema.default("change_detection"),
    pairing_preferences: pairingPreferencesSchema.nullable().optional(),
  })
  .strict();
export type TemporalPairValidationRequest = z.infer<typeof temporalPairValidationRequestSchema>;
export type TemporalPairValidationRequestInput = z.input<
  typeof temporalPairValidationRequestSchema
>;

export const temporalPairValidationResultSchema = z
  .object({
    valid: z.boolean(),
    status: pairCompatibilityStatusSchema,
    before_scene_id: z.string().min(1),
    after_scene_id: z.string().min(1),
    temporal_gap_days: z.number(),
    temporal_gap_hours: z.number().nullable().optional(),
    compatibility_score: z.number().min(0).max(1),
    factors: z.array(compatibilityFactorScoreSchema).default([]),
    issues: z.array(pairCompatibilityIssueSchema).default([]),
    warnings: z.array(analysisWarningSchema).default([]),
    spatial_metrics: spatialOverlapMetricsSchema.nullable().optional(),
    normalized_selection: sceneSelectionSchema.nullable().optional(),
    data_origin_status: z.string().default("real"),
    validation_version: z.string().default(TEMPORAL_PAIRING_SCHEMA_VERSION),
  })
  .strict();
export type TemporalPairValidationResult = z.infer<typeof temporalPairValidationResultSchema>;
