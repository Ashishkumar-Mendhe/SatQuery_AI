import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";
import { viewerSceneIdentitySchema } from "@/lib/viewer-contracts";

const TIMEOUT_MS = 40_000;
const uuid = z.string().uuid();
const artifactSchema = z
  .object({
    artifact_id: uuid,
    kind: z.enum(["inference_chip", "inference_evidence"]),
    media_type: z.enum(["image/png", "application/json"]),
    checksum_sha256: z.string().regex(/^[0-9a-f]{64}$/),
    byte_size: z.number().int().nonnegative(),
    access: z.object({ state: z.literal("available"), reason: z.null() }).strict(),
  })
  .strict();

const modelSchema = z
  .object({
    provider: z.string(),
    model: z.string(),
    version: z.string(),
    adapter_version: z.string(),
    runtime: z.enum(["hosted_api", "local"]),
    weights: z.enum(["hosted_not_disclosed", "public_checkpoint"]),
    licence_basis: z.string(),
    execution_hardware: z.string(),
  })
  .strict();

const qualityCheckSchema = z
  .object({
    check_id: z.string(),
    scope: z.enum(["source", "prepared_scene", "prepared_pair"]),
    metric: z.string(),
    measured_value: z.number().nullable(),
    units: z.string().nullable(),
    threshold: z
      .object({ operator: z.string(), value: z.number(), units: z.string() })
      .strict()
      .nullable(),
    outcome: z.enum(["passed", "failed", "unresolved", "not_applicable"]),
    explanation: z.string(),
  })
  .strict();

const sourceChipSchema = z
  .object({
    chip_id: uuid,
    scene: viewerSceneIdentitySchema,
    acquired_at: z.string(),
    checksum_sha256: z.string(),
    media_type: z.enum(["image/png", "image/jpeg"]),
    byte_size: z.number(),
    width: z.number().int().positive(),
    height: z.number().int().positive(),
    band_order: z.tuple([z.literal("red"), z.literal("green"), z.literal("blue")]),
    rendering: z
      .object({ method: z.literal("fixed_linear"), per_image_normalization: z.literal(false) })
      .passthrough(),
    pixel_to_map: z
      .object({
        crs: z.string(),
        affine: z.tuple([z.number(), z.number(), z.number(), z.number(), z.number(), z.number()]),
      })
      .passthrough(),
    footprint_wgs84: z
      .object({ type: z.string(), coordinates: z.array(z.unknown()) })
      .passthrough(),
    phase6_quality: z
      .object({
        readiness: z
          .object({
            state: z.enum(["ready", "limited", "not_ready", "unresolved", "unsupported"]),
            explanation: z.string(),
          })
          .passthrough(),
        quality_checks: z.array(qualityCheckSchema),
      })
      .passthrough(),
  })
  .passthrough();

const pixelBoxSchema = z
  .object({
    coordinate_space: z.literal("image_pixel"),
    source_chip_id: uuid,
    image_width: z.number().int().positive(),
    image_height: z.number().int().positive(),
    x_min: z.number(),
    y_min: z.number(),
    x_max: z.number(),
    y_max: z.number(),
  })
  .passthrough();

const mapPolygonSchema = z
  .object({
    coordinate_space: z.literal("projected_map"),
    source_chip_id: uuid,
    crs: z.string(),
    rings: z.array(z.array(z.tuple([z.number(), z.number()]))),
  })
  .strict();

const groundingSchema = z
  .object({
    source_chip_id: uuid,
    status: z.enum([
      "detected",
      "no_detection",
      "ambiguous_detection",
      "unsupported_geometry",
      "unavailable",
      "failed_inference",
    ]),
    model: modelSchema,
    candidates: z.array(
      z
        .object({
          candidate_index: z.number().int(),
          label: z.string(),
          model_score: z.number(),
          score_meaning: z.literal("uncalibrated_model_relevance"),
          image_chip_box: pixelBoxSchema,
          map_footprint: mapPolygonSchema,
        })
        .passthrough(),
    ),
    reason: z.string().nullable(),
  })
  .passthrough();

const answerSchema = z
  .object({
    task: z.enum(["visual_question_answering", "image_captioning"]),
    source_chip_id: uuid,
    availability: z.enum(["available", "unavailable", "unknown"]),
    answer: z.string().nullable(),
    reason: z.string().nullable(),
    model: modelSchema,
    quality_warnings: z.array(
      z
        .object({
          code: z.string(),
          severity: z.string(),
          message: z.string(),
          corrective_action: z.string().nullable(),
        })
        .passthrough(),
    ),
    calibrated_confidence: z.null(),
  })
  .passthrough();

export const inferenceEvidenceSchema = z
  .object({
    request: z
      .object({ request_id: uuid, operation: z.string(), scene: viewerSceneIdentitySchema })
      .passthrough(),
    source_chip: sourceChipSchema,
    input_chip_artifact: artifactSchema,
    quality_decision: z
      .object({
        state: z.enum(["proceed", "proceed_with_warning", "blocked", "unknown"]),
        reason: z.string(),
        required_check_ids: z.array(z.string()),
      })
      .strict(),
    execution_state: z.enum(["completed", "unavailable", "blocked", "unknown"]),
    execution_reason: z.string().nullable(),
    answer: answerSchema.nullable(),
    grounding: groundingSchema.nullable(),
    interpretation_disclaimer: z.literal("evidence_not_validation"),
    interpretation_notice: z.string(),
  })
  .strict();

export const inferenceJobStatusSchema = z
  .object({
    schema_version: z.literal("1.0"),
    job_id: uuid,
    request_id: uuid,
    operation: z.enum(["visual_question_answering", "image_captioning", "referring_grounding"]),
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
    result: inferenceEvidenceSchema.nullable(),
    error_code: z.string().nullable(),
    safe_error_message: z.string().nullable(),
  })
  .strict();

export type InferenceOperation =
  | "visual_question_answering"
  | "image_captioning"
  | "referring_grounding";
export type InferenceEvidence = z.infer<typeof inferenceEvidenceSchema>;
export type InferenceJobStatus = z.infer<typeof inferenceJobStatusSchema>;
export type InferenceSubmission = {
  schema_version: "1.0";
  request_id: string;
  operation: InferenceOperation;
  scene: z.infer<typeof viewerSceneIdentitySchema>;
  aoi: unknown;
  text: string | null;
  requested_geometry: "bounding_box";
};

const errorSchema = z
  .object({ error: z.object({ message: z.string(), retryable: z.boolean() }).passthrough() })
  .passthrough();

export class InferenceClientError extends Error {
  constructor(
    readonly kind: "cancelled" | "blocked" | "failure" | "network" | "unexpected_response",
    message: string,
    readonly retryable = false,
  ) {
    super(message);
    this.name = "InferenceClientError";
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
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const parsed = errorSchema.safeParse(body);
      throw new InferenceClientError(
        response.status === 401 || response.status === 403 || response.status === 503
          ? "blocked"
          : "failure",
        parsed.success ? parsed.data.error.message : "Inference could not be completed.",
        parsed.success && parsed.data.error.retryable,
      );
    }
    const parsed = schema.safeParse(body);
    if (!parsed.success)
      throw new InferenceClientError(
        "unexpected_response",
        "SatQuery returned inference data outside the recorded contract.",
      );
    return parsed.data;
  } catch (error) {
    if (error instanceof InferenceClientError) throw error;
    if (callerSignal?.aborted)
      throw new InferenceClientError("cancelled", "The outdated inference request was cancelled.");
    throw new InferenceClientError("network", "SatQuery could not be reached for inference.", true);
  } finally {
    window.clearTimeout(timeout);
    callerSignal?.removeEventListener("abort", abort);
  }
}

export const inferenceClient = {
  start: (body: InferenceSubmission, idempotencyKey: string, signal?: AbortSignal) =>
    requestJson("/inference/jobs", inferenceJobStatusSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(body),
      signal,
    }),
  status: (jobId: string, signal?: AbortSignal) =>
    requestJson(`/inference/jobs/${jobId}`, inferenceJobStatusSchema, { signal }),
};

export type InferenceClient = typeof inferenceClient;
export function inferenceArtifactUrl(id: string): string {
  return `${apiBaseUrl()}/inference/artifacts/${id}`;
}
