import { z } from "zod";

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const providerModeSchema = z.enum(["mock", "real", "disabled"]);
export type ProviderMode = z.infer<typeof providerModeSchema>;

export const providerStatusSchema = z.enum([
  "ready",
  "not_configured",
  "unavailable",
  "degraded",
  "disabled",
  "unknown",
]);
export type ProviderStatus = z.infer<typeof providerStatusSchema>;

export const dataOriginSchema = z.enum(["real", "mock", "fallback", "uploaded", "cached"]);
export type DataOrigin = z.infer<typeof dataOriginSchema>;

export const providerCapabilitySchema = z.enum([
  "scene_search",
  "scene_metadata",
  "scene_preview",
  "imagery_download",
  "optical_imagery",
  "sar_imagery",
  "spectral_processing",
  "change_detection",
  "visual_question_answering",
  "spatial_grounding",
  "report_generation",
]);
export type ProviderCapability = z.infer<typeof providerCapabilitySchema>;

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export const providerInfoSchema = z
  .object({
    provider_id: z.string().min(1).max(120),
    display_name: z.string().min(1).max(120),
    provider_type: z.enum(["satellite", "ai", "processing"]),
    mode: providerModeSchema,
    status: providerStatusSchema,
    capabilities: z.array(providerCapabilitySchema).default([]),
    configured: z.boolean(),
    healthy: z.boolean(),
    data_origin: dataOriginSchema,
    last_checked_at: z.string().datetime().nullable().optional(),
    message: z.string().nullable().optional(),
    limitations: z.array(z.string()).default([]),
    metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type ProviderInfo = z.infer<typeof providerInfoSchema>;

export const providerExecutionMetadataSchema = z
  .object({
    provider_id: z.string().min(1).max(120),
    provider_mode: providerModeSchema,
    data_origin: dataOriginSchema,
    requested_at: z.string().datetime(),
    completed_at: z.string().datetime().nullable().optional(),
    duration_milliseconds: z.number().nonnegative().nullable().optional(),
    attempt_count: z.number().int().positive().default(1),
    fallback_used: z.boolean().default(false),
    fallback_reason: z.string().nullable().optional(),
    cached: z.boolean().default(false),
    provider_request_id: z.string().nullable().optional(),
    limitations: z.array(z.string()).default([]),
  })
  .strict();
export type ProviderExecutionMetadata = z.infer<typeof providerExecutionMetadataSchema>;

export const providersStatusResponseSchema = z
  .object({
    environment: z.string(),
    contract_version: z.string().default("1.0"),
    satellite_provider: providerInfoSchema,
    ai_provider: providerInfoSchema,
    processing_mode: z.string(),
    mock_fallback_enabled: z.boolean(),
    overall_readiness: z.boolean(),
    timestamp: z.string().datetime(),
  })
  .strict();
export type ProvidersStatusResponse = z.infer<typeof providersStatusResponseSchema>;
