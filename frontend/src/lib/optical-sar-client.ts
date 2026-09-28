import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";
import { processingJobStatusSchema } from "@/lib/preparation-client";
import { viewerSceneIdentitySchema } from "@/lib/viewer-contracts";

const scene = z
  .object({
    source: viewerSceneIdentitySchema,
    acquisition: z.object({ start: z.string(), end: z.string() }),
    polarizations: z.array(z.enum(["HH", "HV", "VH", "VV"])).min(1),
    native_resolution_metres: z.number(),
  })
  .passthrough();
const preparation = z
  .object({
    preparation_id: z.string().uuid(),
    source: viewerSceneIdentitySchema,
    acquisition_time: z.string(),
    polarization: z.enum(["HH", "HV", "VH", "VV"]),
    bounds: z.tuple([z.number(), z.number(), z.number(), z.number()]),
    preview_url: z.string().startsWith("/api/v1/sar/preparations/"),
    display_scaling: z.string(),
    warnings: z.array(z.string()),
  })
  .passthrough();
const observation = z
  .object({
    modality: z.enum(["optical", "sar"]),
    source: viewerSceneIdentitySchema,
    acquired_at: z.string(),
    layer: z.string(),
    measured_value: z.number().nullable(),
    units: z.string(),
    valid_pixels: z.number(),
    denominator_pixels: z.number(),
    evidence_bounds: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable(),
    evidence_crs: z.string().nullable(),
    statement: z.string(),
  })
  .passthrough();
export const opticalSarResultSchema = z
  .object({
    request_id: z.string().uuid(),
    job_id: z.string().uuid(),
    state: z.enum(["limited", "insufficient_evidence"]),
    answer_kind: z.literal("computed_observation_summary"),
    answer: z.string(),
    optical: observation,
    sar: observation,
    source_evidence: z
      .array(
        z
          .object({
            source: viewerSceneIdentitySchema,
            acquired_at: z.string(),
            source_version: z.string().nullable(),
            preparation_version: z.string().nullable(),
            checksum: z.string().nullable(),
            polarization: z.enum(["HH", "HV", "VH", "VV"]).nullable(),
          })
          .strict(),
      )
      .length(2),
    joint_usable_pixels: z.number(),
    aoi_pixels: z.number(),
    joint_usable_percent_of_aoi: z.number(),
    joint_usable_area_square_metres: z.number(),
    time_gap_hours: z.number(),
    alignment_state: z.enum(["verified", "inconclusive", "unavailable"]),
    limitations: z.array(z.string()),
    processing_version: z.string(),
    evidence_artifact_id: z.string().uuid(),
  })
  .passthrough();
export type OpticalSarResult = z.infer<typeof opticalSarResultSchema>;
export type SarScene = z.infer<typeof scene>;
export type SarPreparation = z.infer<typeof preparation>;

async function json<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: { Accept: "application/json", ...init.headers },
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    const error =
      typeof body === "object" && body && "error" in body
        ? (body as { error?: { message?: string } }).error?.message
        : null;
    throw new Error(error ?? `Request failed (${response.status}).`);
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new Error("SatQuery returned data outside the optical/SAR contract.");
  return parsed.data;
}

export const opticalSarClient = {
  search: (aoi: unknown, start: string, end: string, signal?: AbortSignal) =>
    json("/sar/search", z.object({ scenes: z.array(scene) }).passthrough(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
      body: JSON.stringify({ provider: "inpe-bdc", aoi, acquisition: { start, end }, limit: 10 }),
    }),
  prepare: (source: SarScene["source"], aoi: unknown, polarization: string, signal?: AbortSignal) =>
    json("/sar/preparations", preparation, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal,
      body: JSON.stringify({ scene: source, aoi, polarization, max_pixels: 1_000_000 }),
    }),
  start: (body: object, key: string, signal?: AbortSignal) =>
    json("/optical-sar/jobs", processingJobStatusSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify(body),
      signal,
    }),
  status: (id: string, signal?: AbortSignal) =>
    json(`/optical-sar/jobs/${id}`, processingJobStatusSchema, { signal }),
  result: (id: string, signal?: AbortSignal) =>
    json(`/optical-sar/jobs/${id}/result`, opticalSarResultSchema, { signal }),
};

export type OpticalSarClient = typeof opticalSarClient;
