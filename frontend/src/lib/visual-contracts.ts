import { z } from "zod";

import { analysisWarningSchema, aoiGeometrySchema } from "./analysis-contracts";
import { dataOriginSchema, providerExecutionMetadataSchema } from "./provider-contracts";
import { generationModeSchema, workspaceContextSnapshotSchema } from "./query-contracts";

export const VISUAL_SCHEMA_VERSION = "1.0.0" as const;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const imageInputRoleSchema = z.enum(["single", "before", "after", "composite"]);
export type ImageInputRole = z.infer<typeof imageInputRoleSchema>;

export const observationSourceSchema = z.enum(["model_prediction", "computed_evidence"]);
export type ObservationSource = z.infer<typeof observationSourceSchema>;

export const coordinateStatusSchema = z.enum([
  "valid",
  "invalid_padding_only",
  "partial_clamped",
  "out_of_bounds",
  "unavailable",
]);
export type CoordinateStatus = z.infer<typeof coordinateStatusSchema>;

export const semanticStatusSchema = z.enum([
  "unverified",
  "evidence_supported",
  "independently_reviewed",
]);
export type SemanticStatus = z.infer<typeof semanticStatusSchema>;

export const mapGroundingStatusSchema = z.enum([
  "available",
  "image_only_no_georeference",
  "unavailable_out_of_bounds",
  "unavailable_transform_error",
]);
export type MapGroundingStatus = z.infer<typeof mapGroundingStatusSchema>;

export const visualOperationSchema = z.enum(["describe", "locate", "compare"]);
export type VisualOperation = z.infer<typeof visualOperationSchema>;

// ---------------------------------------------------------------------------
// Image Manifest Schema
// ---------------------------------------------------------------------------

export const imageManifestSchema = z.object({
  manifest_id: z.string(),
  input_image_id: z.string(),
  source_scene_id: z.string(),
  source_asset_id: z.string(),
  role: imageInputRoleSchema.default("single"),
  content_hash: z.string(),
  submitted_width: z.number().int().positive(),
  submitted_height: z.number().int().positive(),
  content_rectangle: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  rendering_type: z.string().default("true_color"),
  crs: z.string().nullable().optional(),
  affine_transform: z.array(z.number()).length(6).nullable().optional(),
  crop_window: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable().optional(),
  resize_dimensions: z.tuple([z.number(), z.number()]).nullable().optional(),
  padding: z.tuple([z.number(), z.number(), z.number(), z.number()]).default([0, 0, 0, 0]),
  data_origin: dataOriginSchema.default("real"),
  acquisition_time: z.string().optional(),
  aoi_fingerprint: z.string().nullable().optional(),
  created_at: z.string().optional(),
});
export type ImageManifest = z.infer<typeof imageManifestSchema>;

// ---------------------------------------------------------------------------
// Grounded Region & Observation Schemas
// ---------------------------------------------------------------------------

export const groundedVisualRegionSchema = z.object({
  region_id: z.string(),
  observation_id: z.string(),
  manifest_id: z.string(),
  canonical_box: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  pixel_box: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  wgs84_geometry: aoiGeometrySchema.nullable().optional(),
  clipping_status: coordinateStatusSchema.default("valid"),
  transform_provenance: z.record(z.string(), z.unknown()).default({}),
  matched_evidence_ids: z.array(z.string()).default([]),
  overlap_area_km2: z.number().nullable().optional(),
  limitations: z.array(z.string()).default([]),
});
export type GroundedVisualRegion = z.infer<typeof groundedVisualRegionSchema>;

export const visualObservationSchema = z.object({
  observation_id: z.string(),
  input_image_id: z.string(),
  label: z.string(),
  description: z.string(),
  visibility: z.string().default("visible"),
  canonical_box: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable().optional(),
  observation_source: observationSourceSchema.default("model_prediction"),
  coordinate_status: coordinateStatusSchema.default("valid"),
  semantic_status: semanticStatusSchema.default("unverified"),
  map_grounding_status: mapGroundingStatusSchema.default("available"),
  model_confidence: z.number().min(0).max(1).nullable().optional(),
  associated_evidence_ids: z.array(z.string()).default([]),
  warnings: z.array(z.string()).default([]),
});
export type VisualObservation = z.infer<typeof visualObservationSchema>;

// ---------------------------------------------------------------------------
// Visual Query Request & Response Schemas
// ---------------------------------------------------------------------------

export const visualQueryRequestSchema = z.object({
  question: z.string().min(3).max(1000),
  workspace_id: z.string().nullable().optional(),
  context_snapshot: workspaceContextSnapshotSchema,
  selected_image_asset_ids: z.array(z.string()).min(1).max(2),
  operation: visualOperationSchema.default("describe"),
  existing_evidence_ids: z.array(z.string()).default([]),
  locale: z.string().nullable().optional().default("en"),
  request_id: z.string().nullable().optional(),
});
export type VisualQueryRequestInput = z.input<typeof visualQueryRequestSchema>;
export type VisualQueryRequest = z.infer<typeof visualQueryRequestSchema>;

export const visualQueryResponseSchema = z.object({
  answer_id: z.string(),
  request_id: z.string(),
  context_fingerprint: z.string(),
  answer: z.string(),
  observations: z.array(visualObservationSchema).default([]),
  manifests: z.array(imageManifestSchema).default([]),
  grounded_regions: z.array(groundedVisualRegionSchema).default([]),
  evidence_references: z.array(z.string()).default([]),
  generation_mode: generationModeSchema.default("llm_explanation"),
  data_origin: dataOriginSchema.default("real"),
  warnings: z.array(analysisWarningSchema).default([]),
  limitations: z.array(z.string()).default([]),
  provider_execution: providerExecutionMetadataSchema.nullable().optional(),
  created_at: z.string(),
});
export type VisualQueryResponse = z.infer<typeof visualQueryResponseSchema>;

export const visualCapabilitiesResponseSchema = z.object({
  supported_operations: z.array(visualOperationSchema),
  supports_bounding_boxes: z.boolean(),
  supports_temporal_comparison: z.boolean(),
  max_images_per_query: z.number().int().positive(),
  example_questions: z.array(z.string()),
});
export type VisualCapabilitiesResponse = z.infer<typeof visualCapabilitiesResponseSchema>;
