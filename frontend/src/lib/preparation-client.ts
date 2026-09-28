import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";
import { viewerSceneIdentitySchema } from "@/lib/viewer-contracts";

const TIMEOUT_MS = 35_000;
const uuid = z.string().uuid();
const artifactSchema = z
  .object({
    artifact_id: uuid,
    kind: z.enum(["prepared_raster", "validity_mask", "quality_mask", "provenance_manifest"]),
    media_type: z.enum(["image/tiff", "application/json"]),
    checksum_sha256: z.string().regex(/^[0-9a-f]{64}$/),
    byte_size: z.number().int().nonnegative(),
    access: z
      .object({
        state: z.enum(["available", "expired", "denied", "unavailable"]),
        reason: z.string().nullable(),
      })
      .strict(),
  })
  .strict();

export const processingJobStatusSchema = z
  .object({
    schema_version: z.literal("1.0"),
    job_id: uuid,
    state: z.enum(["queued", "running", "cancelling", "succeeded", "failed", "cancelled"]),
    submitted_at: z.string(),
    started_at: z.string().nullable(),
    finished_at: z.string().nullable(),
    attempt: z.number().int().nonnegative(),
    current_stage: z.string().nullable(),
    progress: z
      .object({
        completed_units: z.number().int(),
        total_units: z.number().int(),
        units: z.string(),
      })
      .strict()
      .nullable(),
    artifacts: z.array(artifactSchema),
    error_code: z.string().nullable(),
    safe_error_message: z.string().nullable(),
  })
  .strict();

const checkSchema = z
  .object({
    check_id: z.string(),
    category: z.string(),
    outcome: z.enum(["pass", "warning", "fail", "unknown", "not_applicable"]),
    required: z.boolean(),
    measured_value: z.number().nullable(),
    measured_text: z.string().nullable(),
    units: z.string().nullable(),
    denominator_name: z.string().nullable(),
    denominator_value: z.number().nullable(),
    threshold_description: z.string(),
    reason: z.string(),
    corrective_action: z.string().nullable(),
    evidence_source: z.string(),
    provisional_threshold: z.boolean(),
  })
  .strict();

export const qualityReportSchema = z
  .object({
    profile: z
      .object({
        profile_id: z.string(),
        version: z.string(),
        intended_task: z.string(),
        processing_profile: z.string(),
        required_bands: z.array(z.string()),
        required_capabilities: z.array(z.string()),
        requires_registration: z.boolean(),
      })
      .strict(),
    threshold_version: z.string(),
    thresholds_are_provisional_engineering_limits: z.boolean(),
    readiness: z.enum(["ready", "limited", "not_ready", "unknown", "unsupported"]),
    readiness_reason: z.string(),
    blocking_check_ids: z.array(z.string()),
    warning_check_ids: z.array(z.string()),
    minimum_supported_spatial_scale_metres: z.number().nullable(),
    requested_spatial_scale_metres: z.number().nullable(),
    map_viewing_affected: z.boolean(),
    catalogue_search_affected: z.boolean(),
    checks: z.array(checkSchema),
  })
  .strict();

const coverageSchema = z
  .object({
    name: z.string(),
    pixel_count: z.number(),
    denominator_name: z.string(),
    denominator_pixels: z.number(),
    percent: z.number(),
    area_square_metres: z.number(),
  })
  .strict();
export const preparationManifestSchema = z
  .object({
    schema_version: z.string(),
    job_id: uuid,
    code_version: z.string(),
    configuration_version: z.string(),
    request: z
      .object({
        scenes: z.array(viewerSceneIdentitySchema),
        intended_task: z.string(),
        processing_profile: z.string(),
      })
      .passthrough(),
    grid: z
      .object({
        crs: z.string(),
        width: z.number(),
        height: z.number(),
        resolution_metres: z.array(z.number()),
        bounds: z.array(z.number()),
      })
      .passthrough(),
    registration: z.record(z.string(), z.unknown()),
    pair_coverage: z.array(coverageSchema),
    scenes: z.array(
      z
        .object({
          scene: viewerSceneIdentitySchema,
          quality_information: z.string(),
          native_resolutions_metres: z.array(z.number()),
          output_resolution_metres: z.number(),
          upsampled: z.boolean(),
          upsampling_explanation: z.string().nullable(),
          coverage: z.array(coverageSchema),
          quality_artifact_id: uuid,
        })
        .passthrough(),
    ),
    completed_at: z.string(),
    manifest_artifact_id: uuid,
  })
  .passthrough();

export type ProcessingJobStatus = z.infer<typeof processingJobStatusSchema>;
export type QualityReport = z.infer<typeof qualityReportSchema>;
export type PreparationManifest = z.infer<typeof preparationManifestSchema>;
export type PreparationArtifact = z.infer<typeof artifactSchema>;
export type PreparationRequest = {
  schema_version: "1.0";
  scenes: Array<z.infer<typeof viewerSceneIdentitySchema>>;
  aoi: unknown;
  required_bands: Array<{ role: string; common_name: "red" | "green" | "blue" | "nir" }>;
  intended_task: "optical_single_scene" | "optical_pair";
  processing_profile: "sentinel-2-l2a-surface-reflectance-v1";
  options: {
    grid_policy: "common_utm";
    target_resolution_metres: number;
    continuous_resampling: "bilinear";
    mask_resampling: "nearest";
    calibration: "source_metadata";
    clip_to_aoi: true;
    preserve_originals: true;
    max_output_pixels: number;
  };
};

const errorSchema = z
  .object({
    error: z
      .object({
        code: z.string(),
        message: z.string(),
        request_id: z.string(),
        retryable: z.boolean(),
      })
      .passthrough(),
  })
  .passthrough();
export class PreparationClientError extends Error {
  constructor(
    readonly kind: "cancelled" | "blocked" | "failure" | "network" | "unexpected_response",
    message: string,
    readonly retryable = false,
  ) {
    super(message);
    this.name = "PreparationClientError";
  }
}

async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  const callerSignal = init.signal;
  const controller = new AbortController();
  const abort = () => controller.abort(callerSignal?.reason);
  if (callerSignal?.aborted) abort();
  else callerSignal?.addEventListener("abort", abort, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      signal: controller.signal,
      cache: "no-store",
      headers: { Accept: "application/json", ...init.headers },
    });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new PreparationClientError(
        "unexpected_response",
        "SatQuery returned an unreadable preparation response.",
      );
    }
    if (!response.ok) {
      const parsed = errorSchema.safeParse(body);
      const message = parsed.success
        ? parsed.data.error.message
        : "Preparation could not be completed.";
      const blocked = response.status === 401 || response.status === 403 || response.status === 503;
      throw new PreparationClientError(
        blocked ? "blocked" : "failure",
        message,
        parsed.success && parsed.data.error.retryable,
      );
    }
    const parsed = schema.safeParse(body);
    if (!parsed.success)
      throw new PreparationClientError(
        "unexpected_response",
        "SatQuery returned preparation data outside the recorded contract.",
      );
    return parsed.data;
  } catch (error) {
    if (error instanceof PreparationClientError) throw error;
    if (callerSignal?.aborted)
      throw new PreparationClientError(
        "cancelled",
        "The outdated preparation request was cancelled.",
      );
    throw new PreparationClientError(
      "network",
      "SatQuery could not be reached for preparation.",
      true,
    );
  } finally {
    window.clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abort);
  }
}

export const preparationClient = {
  start: (body: PreparationRequest, idempotencyKey: string, signal?: AbortSignal) =>
    requestJson("/processing/preparations", processingJobStatusSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
      signal,
    }),
  status: (jobId: string, signal?: AbortSignal) =>
    requestJson(`/processing/jobs/${jobId}`, processingJobStatusSchema, { signal }),
  report: (jobId: string, signal?: AbortSignal) =>
    requestJson(`/processing/jobs/${jobId}/quality-report`, qualityReportSchema, { signal }),
  manifest: (artifactId: string, signal?: AbortSignal) =>
    requestJson(`/processing/artifacts/${artifactId}`, preparationManifestSchema, { signal }),
};

export type PreparationClient = typeof preparationClient;
export function preparationArtifactUrl(id: string): string {
  return `${apiBaseUrl()}/processing/artifacts/${id}`;
}
export function preparationQualityReportUrl(jobId: string): string {
  return `${apiBaseUrl()}/processing/jobs/${jobId}/quality-report`;
}
export function preparationMaskTileTemplate(id: string, mask: "usable" | "exclusions"): string {
  return `${apiBaseUrl()}/processing/artifacts/${id}/tiles/${mask}/{z}/{x}/{y}.png`;
}
