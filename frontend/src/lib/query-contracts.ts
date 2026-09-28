import { z } from "zod";

import {
  analysisModeSchema,
  analysisWarningSchema,
  aoiGeometrySchema,
  confidenceFactorSchema,
} from "./analysis-contracts";
import { dataOriginSchema, providerExecutionMetadataSchema } from "./provider-contracts";

export const QUERY_SCHEMA_VERSION = "1.0.0" as const;

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const queryIntentSchema = z.enum([
  "evidence_summary",
  "spectral_summary",
  "change_summary",
  "multimodal_summary",
  "locate_evidence",
  "explain_quality",
  "needs_processing",
  "clarification_required",
  "unsupported",
]);
export type QueryIntent = z.infer<typeof queryIntentSchema>;

export const sufficiencyStatusSchema = z.enum([
  "answerable",
  "partially_answerable",
  "clarification_required",
  "needs_processing",
  "insufficient_evidence",
  "unsupported",
]);
export type SufficiencyStatus = z.infer<typeof sufficiencyStatusSchema>;

export const generationModeSchema = z.enum([
  "llm_explanation",
  "deterministic_summary",
  "mock_demo",
]);
export type GenerationMode = z.infer<typeof generationModeSchema>;

export const claimKindSchema = z.enum([
  "measurement",
  "interpretation",
  "background",
  "limitation",
]);
export type ClaimKind = z.infer<typeof claimKindSchema>;

export const claimValidationStatusSchema = z.enum(["valid", "unverified", "rejected"]);
export type ClaimValidationStatus = z.infer<typeof claimValidationStatusSchema>;

// ---------------------------------------------------------------------------
// Context Snapshot & Plan Models
// ---------------------------------------------------------------------------

export const workspaceContextSnapshotSchema = z.object({
  snapshot_id: z.string(),
  fingerprint: z.string(),
  aoi_geometry: aoiGeometrySchema.nullable().optional(),
  aoi_id: z.string().nullable().optional(),
  location_label: z.string().nullable().optional(),
  scene_ids: z.array(z.string()).default([]),
  active_mode: analysisModeSchema.nullable().optional(),
  active_spectral_result_id: z.string().nullable().optional(),
  active_change_result_id: z.string().nullable().optional(),
  active_fusion_result_id: z.string().nullable().optional(),
  created_at: z.string().optional(),
});
export type WorkspaceContextSnapshotInput = z.input<typeof workspaceContextSnapshotSchema>;
export type WorkspaceContextSnapshot = z.infer<typeof workspaceContextSnapshotSchema>;

export const queryPlanSchema = z.object({
  intent: queryIntentSchema,
  scope: z.string(),
  required_evidence: z.array(z.string()).default([]),
  missing_inputs: z.array(z.string()).default([]),
  approved_operations: z.array(z.string()).default([]),
  routing_reason: z.string(),
  context_fingerprint: z.string(),
});
export type QueryPlan = z.infer<typeof queryPlanSchema>;

// ---------------------------------------------------------------------------
// Answer Components & Actions
// ---------------------------------------------------------------------------

export const answerClaimSchema = z.object({
  claim_id: z.string(),
  kind: claimKindSchema,
  evidence_ids: z.array(z.string()).default([]),
  metric_references: z.array(z.string()).default([]),
  resolved_measurement: z.record(z.string(), z.unknown()).nullable().optional(),
  region_ids: z.array(z.string()).default([]),
  display_text: z.string(),
  validation_status: claimValidationStatusSchema.default("valid"),
});
export type AnswerClaim = z.infer<typeof answerClaimSchema>;

export const suggestedNextActionSchema = z.object({
  action_id: z.string(),
  label: z.string(),
  description: z.string(),
  workflow_target: z.string(),
  parameters: z.record(z.string(), z.unknown()).nullable().optional(),
});
export type SuggestedNextAction = z.infer<typeof suggestedNextActionSchema>;

export const processingTraceStepSchema = z.object({
  stage: z.string(),
  status: z.string(),
  duration_ms: z.number().int().nonnegative(),
  description: z.string(),
  timestamp: z.string().optional(),
});
export type ProcessingTraceStep = z.infer<typeof processingTraceStepSchema>;

// ---------------------------------------------------------------------------
// Query Request & Answer Envelope
// ---------------------------------------------------------------------------

export const queryRequestSchema = z.object({
  question: z.string().min(3).max(1000),
  workspace_id: z.string().nullable().optional(),
  context_snapshot: workspaceContextSnapshotSchema,
  conversation_id: z.string().nullable().optional(),
  reply_to_answer_id: z.string().nullable().optional(),
  locale: z.string().nullable().optional().default("en"),
  request_id: z.string().nullable().optional(),
});
export type QueryRequestInput = z.input<typeof queryRequestSchema>;
export type QueryRequest = z.infer<typeof queryRequestSchema>;

export const queryAnswerSchema = z.object({
  answer_id: z.string(),
  request_id: z.string(),
  context_fingerprint: z.string(),
  answer_status: sufficiencyStatusSchema,
  generation_mode: generationModeSchema,
  plan: queryPlanSchema,
  summary: z.string(),
  claims: z.array(answerClaimSchema).default([]),
  evidence_references: z.array(z.string()).default([]),
  spatial_references: z.array(z.string()).default([]),
  quality_factors: z.array(confidenceFactorSchema).default([]),
  warnings: z.array(analysisWarningSchema).default([]),
  limitations: z.array(z.string()).default([]),
  suggested_actions: z.array(suggestedNextActionSchema).default([]),
  processing_trace: z.array(processingTraceStepSchema).default([]),
  data_origin: dataOriginSchema.default("real"),
  created_at: z.string(),
  provider_execution: providerExecutionMetadataSchema.nullable().optional(),
});
export type QueryAnswer = z.infer<typeof queryAnswerSchema>;

export const queryCapabilitiesResponseSchema = z.object({
  supported_intents: z.array(queryIntentSchema),
  supported_generation_modes: z.array(generationModeSchema),
  example_questions: z.array(z.string()),
});
export type QueryCapabilitiesResponse = z.infer<typeof queryCapabilitiesResponseSchema>;
