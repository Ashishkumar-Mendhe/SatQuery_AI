import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";
import { processingJobStatusSchema, type PreparationRequest } from "@/lib/preparation-client";
import { viewerSceneIdentitySchema } from "@/lib/viewer-contracts";

const source = z
  .object({
    temporal_role: z.enum(["before", "after"]),
    scene: viewerSceneIdentitySchema,
    acquired_at: z.string(),
  })
  .strict();
const area = z
  .object({
    changed_area_square_metres: z.number(),
    changed_percent_of_joint_valid_observed_area: z.number(),
    joint_valid_observed_area_square_metres: z.number(),
    observed_coverage_percent_of_aoi: z.number(),
    unknown_area_square_metres: z.number(),
    unknown_percent_of_aoi: z.number(),
  })
  .passthrough();
export const changeResultSchema = z
  .object({
    schema_version: z.literal("1.0"),
    job_id: z.string().uuid(),
    sources: z.array(source).length(2),
    aoi: z.unknown(),
    grid: z.object({ bounds: z.array(z.number()).length(4) }).passthrough(),
    method: z.string(),
    method_version: z.string(),
    threshold: z.number(),
    threshold_units: z.string(),
    area,
    alignment_statement: z.string(),
    warnings: z.array(z.object({ code: z.string(), statement: z.string() }).strict()),
    statements: z.array(z.string()),
    cause_or_land_cover_category: z.literal("not_determined"),
    classification_artifact_id: z.string().uuid(),
    processing_version: z.string(),
  })
  .strict();
export type ChangeResult = z.infer<typeof changeResultSchema>;

async function json<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    cache: "no-store",
    headers: { Accept: "application/json", ...init.headers },
  });
  const body: unknown = await response.json();
  if (!response.ok) {
    const message =
      typeof body === "object" && body && "error" in body
        ? (body as { error?: { message?: string } }).error?.message
        : null;
    throw new Error(message ?? "Change analysis could not be completed.");
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success)
    throw new Error("SatQuery returned change data outside the recorded contract.");
  return parsed.data;
}
export const changeClient = {
  start: (body: PreparationRequest, key: string, signal?: AbortSignal) =>
    json("/processing/changes", processingJobStatusSchema, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify(body),
      signal,
    }),
  status: (id: string, signal?: AbortSignal) =>
    json(`/processing/change-jobs/${id}`, processingJobStatusSchema, { signal }),
  result: (id: string, signal?: AbortSignal) =>
    json(`/processing/change-jobs/${id}/result`, changeResultSchema, { signal }),
};
export type ChangeClient = typeof changeClient;
export const changeTileTemplate = (id: string) =>
  `${apiBaseUrl()}/processing/artifacts/${id}/tiles/change/{z}/{x}/{y}.png`;
