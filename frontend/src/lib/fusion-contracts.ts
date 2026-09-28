import { z } from "zod";

import {
  analysisWarningSchema,
  aoiGeometrySchema,
  evidenceItemSchema,
  overlayFeatureSchema,
} from "./analysis-contracts";
import { rasterProvenanceSchema } from "./preparation-contracts";
import { dataOriginSchema } from "./provider-contracts";

export const FUSION_SCHEMA_VERSION = "1.0.0" as const;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const sarBackscatterCoefficientSchema = z.enum(["sigma0", "gamma0", "beta0", "unknown"]);
export type SARBackscatterCoefficient = z.infer<typeof sarBackscatterCoefficientSchema>;

export const sarPowerUnitSchema = z.enum(["linear_power", "decibels", "raw_dn", "unknown"]);
export type SARPowerUnit = z.infer<typeof sarPowerUnitSchema>;

export const sarPolarizationSchema = z.enum(["VV", "VH", "HH", "HV"]);
export type SARPolarization = z.infer<typeof sarPolarizationSchema>;

export const sarOrbitDirectionSchema = z.enum(["ascending", "descending", "unknown"]);
export type SAROrbitDirection = z.infer<typeof sarOrbitDirectionSchema>;

export const sarCalibrationStatusSchema = z.enum([
  "terrain_corrected",
  "calibrated_only",
  "uncalibrated",
]);
export type SARCalibrationStatus = z.infer<typeof sarCalibrationStatusSchema>;

export const fusionCompatibilityStatusSchema = z.enum([
  "valid",
  "compatible_with_warnings",
  "incompatible",
  "insufficient_evidence",
]);
export type FusionCompatibilityStatus = z.infer<typeof fusionCompatibilityStatusSchema>;

export const jointObservationStateSchema = z.enum([
  "both_detect_change",
  "optical_response_only",
  "sar_response_only",
  "neither_above_threshold",
  "uncertain",
]);
export type JointObservationState = z.infer<typeof jointObservationStateSchema>;

export const coveragePartitionCategorySchema = z.enum([
  "jointly_observable",
  "optical_only",
  "sar_only",
  "neither",
]);
export type CoveragePartitionCategory = z.infer<typeof coveragePartitionCategorySchema>;

export const fusionRuleIdSchema = z.enum(["co_observed_response_change"]);
export type FusionRuleId = z.infer<typeof fusionRuleIdSchema>;

// ---------------------------------------------------------------------------
// SAR Models
// ---------------------------------------------------------------------------

export const sarThresholdConfigSchema = z
  .object({
    increase_threshold_db: z.number().min(0.1).max(20.0).default(2.0),
    decrease_threshold_db: z.number().min(-20.0).max(-0.1).default(-2.0),
    min_cluster_size_pixels: z.number().int().min(1).max(1000).default(5),
    simplify_tolerance_meters: z.number().min(0.0).max(100.0).default(5.0),
  })
  .strict()
  .superRefine((data, context) => {
    if (data.increase_threshold_db <= data.decrease_threshold_db) {
      context.addIssue({
        code: "custom",
        message: "increase_threshold_db must be strictly greater than decrease_threshold_db",
      });
    }
  });
export type SARThresholdConfig = z.infer<typeof sarThresholdConfigSchema>;
export type SARThresholdConfigInput = z.input<typeof sarThresholdConfigSchema>;

export const DEFAULT_SAR_THRESHOLD_CONFIG: SARThresholdConfig = {
  increase_threshold_db: 2.0,
  decrease_threshold_db: -2.0,
  min_cluster_size_pixels: 5,
  simplify_tolerance_meters: 5.0,
};

export const sarChangeEvidenceSchema = z
  .object({
    evidence_id: z.string(),
    before_scene_id: z.string(),
    after_scene_id: z.string(),
    before_asset_id: z.string(),
    after_asset_id: z.string(),
    difference_asset_id: z.string(),
    polarization: sarPolarizationSchema.default("VV"),
    coefficient: sarBackscatterCoefficientSchema.default("sigma0"),
    unit: sarPowerUnitSchema.default("decibels"),
    calibration_status: sarCalibrationStatusSchema.default("terrain_corrected"),
    orbit_direction: sarOrbitDirectionSchema.default("unknown"),
    before_timestamp: z.string(),
    after_timestamp: z.string(),
    increase_threshold_db: z.number(),
    decrease_threshold_db: z.number(),
    mean_delta_db: z.number(),
    min_delta_db: z.number(),
    max_delta_db: z.number(),
    std_delta_db: z.number(),
    valid_area_km2: z.number().min(0.0),
    data_origin: dataOriginSchema.default("real"),
    warnings: z.array(z.string()).default([]),
  })
  .strict();
export type SARChangeEvidence = z.infer<typeof sarChangeEvidenceSchema>;

// ---------------------------------------------------------------------------
// Temporal Roles & Compatibility
// ---------------------------------------------------------------------------

export const temporalObservationRoleSchema = z
  .object({
    role: z.enum(["optical_before", "optical_after", "sar_before", "sar_after"]),
    scene_id: z.string(),
    acquisition_timestamp: z.string(),
    prepared_asset_id: z.string(),
    sensor: z.string(),
    data_origin: dataOriginSchema.default("real"),
  })
  .strict();
export type TemporalObservationRole = z.infer<typeof temporalObservationRoleSchema>;

export const multimodalTimingMetricsSchema = z
  .object({
    optical_before_timestamp: z.string(),
    optical_after_timestamp: z.string(),
    sar_before_timestamp: z.string(),
    sar_after_timestamp: z.string(),
    optical_duration_days: z.number().min(0.0),
    sar_duration_days: z.number().min(0.0),
    before_offset_days: z.number(),
    after_offset_days: z.number(),
    event_timestamp: z.string().nullable().optional(),
    event_bracketed_by_optical: z.boolean().nullable().optional(),
    event_bracketed_by_sar: z.boolean().nullable().optional(),
    interval_overlap_ratio: z.number().min(0.0).max(1.0),
  })
  .strict();
export type MultimodalTimingMetrics = z.infer<typeof multimodalTimingMetricsSchema>;

export const compatibilityAssessmentSchema = z
  .object({
    status: fusionCompatibilityStatusSchema,
    timing: multimodalTimingMetricsSchema.nullable().optional(),
    optical_resolution_meters: z.number().nullable().optional(),
    sar_resolution_meters: z.number().nullable().optional(),
    common_crs: z.string().nullable().optional(),
    blocking_issues: z.array(z.string()).default([]),
    warnings: z.array(analysisWarningSchema).default([]),
    method_version: z.string().default(FUSION_SCHEMA_VERSION),
  })
  .strict();
export type CompatibilityAssessment = z.infer<typeof compatibilityAssessmentSchema>;

// ---------------------------------------------------------------------------
// Coverage Partitions & Joint Metrics
// ---------------------------------------------------------------------------

export const coveragePartitionPixelCountsSchema = z
  .object({
    total_aoi_pixels: z.number().int().min(0),
    jointly_observable_pixels: z.number().int().min(0),
    optical_only_pixels: z.number().int().min(0),
    sar_only_pixels: z.number().int().min(0),
    neither_pixels: z.number().int().min(0),
  })
  .strict();
export type CoveragePartitionPixelCounts = z.infer<typeof coveragePartitionPixelCountsSchema>;

export const coveragePartitionsSchema = z
  .object({
    total_aoi_area_km2: z.number().min(0.0),
    jointly_observable_area_km2: z.number().min(0.0),
    optical_only_area_km2: z.number().min(0.0),
    sar_only_area_km2: z.number().min(0.0),
    neither_area_km2: z.number().min(0.0),
    joint_percent_of_aoi: z.number().min(0.0).max(100.0),
    optical_only_percent_of_aoi: z.number().min(0.0).max(100.0),
    sar_only_percent_of_aoi: z.number().min(0.0).max(100.0),
    neither_percent_of_aoi: z.number().min(0.0).max(100.0),
    pixel_counts: coveragePartitionPixelCountsSchema,
  })
  .strict();
export type CoveragePartitions = z.infer<typeof coveragePartitionsSchema>;

export const jointStatePixelCountsSchema = z
  .object({
    both_detect_change_pixels: z.number().int().min(0),
    optical_response_only_pixels: z.number().int().min(0),
    sar_response_only_pixels: z.number().int().min(0),
    neither_above_threshold_pixels: z.number().int().min(0),
    uncertain_pixels: z.number().int().min(0),
  })
  .strict();
export type JointStatePixelCounts = z.infer<typeof jointStatePixelCountsSchema>;

export const jointStateMetricsSchema = z
  .object({
    joint_area_km2: z.number().min(0.0),
    both_detect_change_area_km2: z.number().min(0.0),
    optical_response_only_area_km2: z.number().min(0.0),
    sar_response_only_area_km2: z.number().min(0.0),
    neither_above_threshold_area_km2: z.number().min(0.0),
    uncertain_area_km2: z.number().min(0.0),
    both_detect_change_percent: z.number().min(0.0).max(100.0).nullable().optional(),
    optical_response_only_percent: z.number().min(0.0).max(100.0).nullable().optional(),
    sar_response_only_percent: z.number().min(0.0).max(100.0).nullable().optional(),
    neither_above_threshold_percent: z.number().min(0.0).max(100.0).nullable().optional(),
    uncertain_percent: z.number().min(0.0).max(100.0).nullable().optional(),
    pixel_counts: jointStatePixelCountsSchema,
  })
  .strict();
export type JointStateMetrics = z.infer<typeof jointStateMetricsSchema>;

// ---------------------------------------------------------------------------
// Region & Quality
// ---------------------------------------------------------------------------

export const fusionRegionSchema = z
  .object({
    id: z.string().min(1).max(120),
    state: jointObservationStateSchema,
    geometry: aoiGeometrySchema,
    area_km2: z.number().min(0.0),
    pixel_count: z.number().int().min(1),
    mean_optical_difference: z.number().nullable().optional(),
    mean_sar_difference_db: z.number().nullable().optional(),
    optical_evidence_id: z.string().nullable().optional(),
    sar_evidence_id: z.string().nullable().optional(),
    rule_explanation: z.string(),
    confidence: z.number().min(0.0).max(1.0),
    warnings: z.array(z.string()).default([]),
  })
  .strict();
export type FusionRegion = z.infer<typeof fusionRegionSchema>;

export const fusionQualityBreakdownSchema = z
  .object({
    score: z.number().min(0.0).max(1.0),
    temporal_alignment_factor: z.number().min(0.0).max(1.0),
    spatial_resolution_factor: z.number().min(0.0).max(1.0),
    calibration_certainty_factor: z.number().min(0.0).max(1.0),
    valid_coverage_factor: z.number().min(0.0).max(1.0),
    factors: z.record(z.string(), z.number()).default({}),
    limitations: z.array(z.string()).default([]),
  })
  .strict();
export type FusionQualityBreakdown = z.infer<typeof fusionQualityBreakdownSchema>;

export const fusionRuleDefinitionSchema = z
  .object({
    rule_id: fusionRuleIdSchema,
    name: z.string().min(1).max(120),
    version: z.string().default(FUSION_SCHEMA_VERSION),
    description: z.string().min(1).max(500),
    supported_modalities: z.array(z.string()).default(["Optical", "SAR"]),
    disclaimer: z.string().min(1).max(500),
  })
  .strict();
export type FusionRuleDefinition = z.infer<typeof fusionRuleDefinitionSchema>;

// ---------------------------------------------------------------------------
// Requests & Results
// ---------------------------------------------------------------------------

export const fusionRequestSchema = z
  .object({
    request_id: z.string().nullable().optional(),
    optical_change_result_id: z.string().max(256).nullable().optional(),
    sar_prepared_pair_id: z.string().max(256).nullable().optional(),
    sar_before_asset_id: z.string().max(256).nullable().optional(),
    sar_after_asset_id: z.string().max(256).nullable().optional(),
    aoi: aoiGeometrySchema,
    rule_id: fusionRuleIdSchema.default("co_observed_response_change"),
    temporal_tolerance_days: z.number().min(1.0).max(365.0).default(30.0),
    sar_threshold_config: sarThresholdConfigSchema.default(DEFAULT_SAR_THRESHOLD_CONFIG),
    event_timestamp: z.string().nullable().optional(),
    allow_partial: z.boolean().default(true),
    max_regions: z.number().int().min(1).max(500).default(100),
  })
  .strict();
export type FusionRequest = z.infer<typeof fusionRequestSchema>;
export type FusionRequestInput = z.input<typeof fusionRequestSchema>;

export const fusionResultSchema = z
  .object({
    result_id: z.string().min(1).max(120),
    rule_id: fusionRuleIdSchema,
    rule_definition: fusionRuleDefinitionSchema,
    compatibility: compatibilityAssessmentSchema,
    coverage: coveragePartitionsSchema,
    joint_metrics: jointStateMetricsSchema,
    regions: z.array(fusionRegionSchema).default([]),
    observations: z.array(temporalObservationRoleSchema).default([]),
    sar_evidence: sarChangeEvidenceSchema.nullable().optional(),
    optical_change_result_id: z.string().nullable().optional(),
    difference_overlay: overlayFeatureSchema.nullable().optional(),
    classified_overlay: overlayFeatureSchema.nullable().optional(),
    evidence: z.array(evidenceItemSchema).default([]),
    quality: fusionQualityBreakdownSchema,
    warnings: z.array(analysisWarningSchema).default([]),
    blocking_issues: z.array(z.string()).default([]),
    provenance: rasterProvenanceSchema,
    data_origin: dataOriginSchema.default("real"),
    created_at: z.string(),
    interpretation_readiness: z.boolean().default(false),
  })
  .strict();
export type FusionResult = z.infer<typeof fusionResultSchema>;

export const fusionCapabilitiesResponseSchema = z
  .object({
    rules: z.array(fusionRuleDefinitionSchema),
    supported_polarizations: z.array(z.string()).default(["VV", "VH", "HH", "HV"]),
    supported_coefficients: z.array(z.string()).default(["sigma0", "gamma0", "beta0", "unknown"]),
    version: z.string().default(FUSION_SCHEMA_VERSION),
  })
  .strict();
export type FusionCapabilitiesResponse = z.infer<typeof fusionCapabilitiesResponseSchema>;
