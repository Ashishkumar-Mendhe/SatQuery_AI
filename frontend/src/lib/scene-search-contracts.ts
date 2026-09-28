import { z } from "zod";

import {
  analysisWarningSchema,
  aoiGeometrySchema,
  dateRangeSchema,
  satelliteSceneSchema,
  sensorTypeSchema,
} from "./analysis-contracts";
import { dataOriginSchema, providerExecutionMetadataSchema } from "./provider-contracts";

// ---------------------------------------------------------------------------
// Scene Search Request & Response Contracts
// ---------------------------------------------------------------------------

export const sceneSearchRequestSchema = z
  .object({
    aoi: aoiGeometrySchema,
    date_range: dateRangeSchema.nullable().optional(),
    collections: z.array(z.string()).default([]),
    sensor_types: z.array(sensorTypeSchema).default([]),
    max_cloud_cover: z.number().min(0).max(100).default(20),
    limit: z.number().int().min(1).max(200).default(50),
    sort_order: z.enum(["asc", "desc"]).default("desc"),
    required_bands: z.array(z.string()).default([]),
    include_preview: z.boolean().default(true),
    cursor: z.string().nullable().optional(),
  })
  .strict();
export type SceneSearchRequest = z.infer<typeof sceneSearchRequestSchema>;

export const sceneSearchResponseSchema = z
  .object({
    request_id: z.string(),
    scenes: z.array(satelliteSceneSchema),
    total_matched: z.number().int().nullable().optional(),
    returned_count: z.number().int().nonnegative(),
    next_cursor: z.string().nullable().optional(),
    provider_id: z.string(),
    execution: providerExecutionMetadataSchema,
    warnings: z.array(analysisWarningSchema).default([]),
    data_origin: dataOriginSchema,
  })
  .strict();
export type SceneSearchResponse = z.infer<typeof sceneSearchResponseSchema>;
