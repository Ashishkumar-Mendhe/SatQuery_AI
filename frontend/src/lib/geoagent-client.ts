import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";
import { viewerSceneIdentitySchema } from "@/lib/viewer-contracts";

const uuid = z.string().uuid();
const source = z
  .object({
    source: viewerSceneIdentitySchema,
    modality: z.enum(["optical", "sar"]),
    acquired_at: z.string().nullable(),
    polarization: z.enum(["HH", "HV", "VH", "VV"]).nullable(),
  })
  .strict();
const selection = z
  .object({ aoi: z.unknown().nullable(), scenes: z.array(source).max(2) })
  .strict();
const resultReference = z
  .object({
    tool: z.enum([
      "inference_vqa",
      "inference_caption",
      "inference_grounding",
      "optical_change",
      "optical_sar_observation",
    ]),
    job_id: uuid,
    result_id: uuid,
    aoi_sha256: z.string(),
    source_scenes: z.array(viewerSceneIdentitySchema),
    verified_at: z.string(),
  })
  .strict();
const execution = z
  .object({
    request_id: uuid,
    conversation_id: uuid.nullable(),
    status: z.enum([
      "submitted",
      "result_pending",
      "completed",
      "failed",
      "unavailable",
      "clarification_required",
      "unsupported",
      "submission_unknown",
    ]),
    summary: z.object({
      intended_analysis: z.string().nullable(),
      tool: z.string().nullable(),
      input_scenes: z.array(viewerSceneIdentitySchema),
      aoi_sha256: z.string().nullable(),
      status: z.string(),
      job_id: uuid.nullable(),
      result_id: uuid.nullable(),
    }),
    job_id: uuid.nullable(),
    result_id: uuid.nullable(),
    output: z.record(z.string(), z.unknown()).nullable(),
    cancel_path: z.string().nullable(),
    error_code: z.string().nullable(),
    message: z.string(),
    retry_same_request_id: z.boolean(),
  })
  .passthrough();
export const geoAgentTurnSchema = z
  .object({
    conversation_id: uuid,
    request_id: uuid,
    status: z.enum(["clarification_required", "executed", "unavailable", "stale"]),
    message: z.string(),
    selection_revision: z.number().int().nonnegative(),
    selection,
    missing_reference: z.enum(["aoi", "earlier_scene", "change_result", "intent"]).nullable(),
    resolved_result: resultReference.nullable(),
    execution: execution.nullable(),
  })
  .strict();
const conversationSchema = z
  .object({ conversation_id: uuid, selection_revision: z.number().int().nonnegative(), selection })
  .passthrough();

export type GeoAgentTurn = z.infer<typeof geoAgentTurnSchema>;
export type GeoAgentSelection = z.infer<typeof selection>;
export type GeoAgentExecution = NonNullable<GeoAgentTurn["execution"]>;
export type GeoAgentConversation = z.infer<typeof conversationSchema>;
export type GeoAgentTurnRequest = {
  request_id: string;
  expected_selection_revision: number;
  message: string;
  selection?: GeoAgentSelection;
};

export class GeoAgentClientError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = "GeoAgentClientError";
  }
}

async function request<T>(path: string, schema: z.ZodType<T>, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json", ...init.headers },
    });
  } catch (error) {
    if (init.signal?.aborted) throw error;
    throw new GeoAgentClientError("SatQuery could not be reached.", "NETWORK_UNAVAILABLE", true);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = z
      .object({
        error: z.object({ code: z.string(), message: z.string(), retryable: z.boolean() }),
      })
      .safeParse(body);
    throw new GeoAgentClientError(
      parsed.success ? parsed.data.error.message : "SatQuery could not process the request.",
      parsed.success ? parsed.data.error.code : "REQUEST_FAILED",
      parsed.success && parsed.data.error.retryable,
    );
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success)
    throw new GeoAgentClientError(
      "SatQuery returned data outside the conversation contract.",
      "INVALID_RESPONSE",
      false,
    );
  return parsed.data;
}

export const geoAgentClient = {
  get: (conversationId: string, signal?: AbortSignal) =>
    request(`/geoagent/conversations/${conversationId}`, conversationSchema, { signal }),
  turn: (conversationId: string, body: GeoAgentTurnRequest, signal?: AbortSignal) =>
    request(`/geoagent/conversations/${conversationId}/turns`, geoAgentTurnSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    }),
};
export type GeoAgentClient = typeof geoAgentClient;
