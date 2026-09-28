import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";

const CATALOG_TIMEOUT_MS = 20_000;

const utcDateTimeSchema = z
  .string()
  .refine(
    (value) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value)),
    "Expected an ISO 8601 timestamp with a timezone offset.",
  );
const identifierSchema = z.string().min(1).max(512);
const providerSchema = z
  .object({ id: z.string().min(1).max(64), name: z.string().min(1).max(160) })
  .strict();
const acquisitionSchema = z.object({ start: utcDateTimeSchema, end: utcDateTimeSchema }).strict();
const positionSchema = z.tuple([z.number().finite(), z.number().finite()]);
const polygonSchema = z
  .object({
    type: z.literal("Polygon"),
    coordinates: z.array(z.array(positionSchema).min(4)).min(1),
  })
  .strict();
const multiPolygonSchema = z
  .object({
    type: z.literal("MultiPolygon"),
    coordinates: z.array(z.array(z.array(positionSchema).min(4)).min(1)).min(1),
  })
  .strict();
const geometrySchema = z.discriminatedUnion("type", [polygonSchema, multiPolygonSchema]);
const collectionIdentitySchema = z
  .object({ id: identifierSchema, title: z.string().min(1).max(300).nullable() })
  .strict();
const fieldProvenanceSchema = z
  .object({
    normalized_field: z.string().min(1).max(256),
    source: z.enum(["provider_record", "provider_api", "adapter_derived"]),
    source_field: z.string().min(1).max(256),
    method: z.string().min(1).max(500).nullable(),
  })
  .strict();
const sceneSchema = z
  .object({
    provider: providerSchema,
    provider_asset_id: identifierSchema,
    provider_asset_version: z.string().min(1).max(256).nullable(),
    collection: collectionIdentitySchema,
    acquisition: acquisitionSchema,
    platform: z.string().min(1).max(160).nullable(),
    instruments: z.array(z.string().min(1).max(160)).max(32),
    product_type: z.string().min(1).max(160).nullable(),
    processing_level: z.string().min(1).max(160).nullable(),
    footprint: geometrySchema,
    bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]),
    cloud_cover: z
      .object({
        percent: z.number().min(0).max(100),
        source_field: z.string().min(1).max(256),
        semantics: z.string().min(1).max(500),
      })
      .strict()
      .nullable(),
    spatial_resolution: z
      .array(
        z
          .object({
            value: z.number().positive(),
            unit: z.literal("metre"),
            axis: z.enum(["nominal", "x", "y"]),
            source_field: z.string().min(1).max(256),
          })
          .strict(),
      )
      .max(3),
    bands: z.array(z.string().min(1).max(160)).max(256),
    polarizations: z.array(z.string().min(1).max(160)).max(16),
    preview: z
      .object({
        purpose: z.enum(["thumbnail", "preview"]),
        access: z.enum(["public", "temporary", "backend_mediated", "unavailable"]),
        href: z.string().url().nullable(),
        media_type: z.string().min(1).max(160).nullable(),
        width: z.number().int().positive().max(20_000).nullable(),
        height: z.number().int().positive().max(20_000).nullable(),
        expires_at: utcDateTimeSchema.nullable(),
        attribution: z.string().min(1).max(500).nullable(),
      })
      .strict()
      .nullable(),
    license: z
      .object({
        name: z.string().min(1).max(200),
        url: z.string().url().nullable(),
        permits_analytical_use: z.boolean().nullable(),
        summary: z.string().min(1).max(1000).nullable(),
      })
      .strict()
      .nullable(),
    asset_access: z
      .object({
        state: z.enum([
          "metadata_only",
          "provider_accessible",
          "requires_authorization",
          "requires_purchase",
          "unavailable",
          "unknown",
        ]),
        method: z.enum(["none", "provider_reference", "backend_mediated"]),
        reason: z.string().min(1).max(1000).nullable(),
      })
      .strict(),
    provenance: z
      .object({
        adapter: z.string().min(1).max(128),
        adapter_version: z.string().min(1).max(128),
        retrieved_at: utcDateTimeSchema,
        source_record_id: identifierSchema,
        source_record_version: z.string().min(1).max(256).nullable(),
        metadata_digest_sha256: z.string().regex(/^[0-9a-f]{64}$/),
        fields: z.array(fieldProvenanceSchema).min(1).max(100),
      })
      .strict(),
    unavailable_fields: z
      .array(
        z
          .object({
            field: z.string().min(1).max(256),
            availability: z.literal("unavailable"),
            reason: z.string().min(1).max(500),
          })
          .strict(),
      )
      .max(100),
  })
  .strict();

const collectionSchema = z
  .object({
    id: z.string().min(1).max(160),
    title: z.string().min(1).max(300).nullable(),
    description: z.string().min(1).max(5000).nullable(),
    license_name: z.string().min(1).max(200).nullable(),
    license_url: z.string().url().nullable(),
    temporal_start: utcDateTimeSchema.nullable(),
    temporal_end: utcDateTimeSchema.nullable(),
    platforms: z.array(z.string().min(1).max(160)).max(32),
    instruments: z.array(z.string().min(1).max(160)).max(32),
    spatial_resolutions_metres: z.array(z.number().positive()).max(3),
  })
  .strict();

const collectionsResponseSchema = z
  .object({
    schema_version: z.literal("1.0"),
    provider: providerSchema,
    items: z.array(collectionSchema).max(50),
    returned_count: z.number().int().min(0).max(50),
  })
  .strict();

const searchRequestSchema = z
  .object({
    schema_version: z.literal("1.0"),
    provider: z.literal("earth-search"),
    aoi: geometrySchema,
    acquisition: acquisitionSchema,
    collections: z.array(z.string().min(1).max(160)).max(50),
    cloud_cover: z
      .object({
        max_percent: z.number().min(0).max(100),
        source: z.literal("provider_reported"),
        include_unknown: z.literal(false),
      })
      .strict()
      .nullable(),
    limit: z.number().int().min(1).max(100),
    cursor: z.string().min(1).max(2048).nullable(),
    sort: z.enum(["acquired_desc", "acquired_asc"]),
  })
  .strict();

const searchResponseSchema = z
  .object({
    schema_version: z.literal("1.0"),
    search_id: z.string().uuid(),
    status: z.enum(["succeeded", "partial"]),
    query: searchRequestSchema,
    provider: providerSchema,
    items: z.array(sceneSchema).max(100),
    returned_count: z.number().int().min(0).max(100),
    next_cursor: z.string().min(1).max(2048).nullable(),
    searched_at: utcDateTimeSchema,
    attributions: z.array(z.string().min(1).max(1000)).min(1).max(20),
    warnings: z.array(z.string().min(1).max(1000)).max(50),
  })
  .strict();

export const catalogueSceneSchema = sceneSchema;
export const catalogueSearchRequestSchema = searchRequestSchema;

const errorEnvelopeSchema = z
  .object({
    error: z
      .object({
        code: z.string().min(1),
        message: z.string().min(1),
        request_id: z.string().min(1),
        details: z.unknown().nullable(),
        retryable: z.boolean(),
      })
      .strict(),
  })
  .strict();

export type CatalogueCollection = z.infer<typeof collectionSchema>;
export type CatalogueScene = z.infer<typeof sceneSchema>;
export type CatalogueSearchRequest = z.infer<typeof searchRequestSchema>;
export type CatalogueSearchResponse = z.infer<typeof searchResponseSchema>;
export type CatalogueCollectionsResponse = z.infer<typeof collectionsResponseSchema>;
export type CatalogueErrorKind =
  | "validation"
  | "not_found"
  | "provider"
  | "rate_limit"
  | "timeout"
  | "network"
  | "cancelled"
  | "unexpected_response"
  | "configuration";

export class CatalogueClientError extends Error {
  constructor(
    readonly kind: CatalogueErrorKind,
    message: string,
    readonly requestId: string | null = null,
    readonly retryable = false,
  ) {
    super(message);
    this.name = "CatalogueClientError";
  }
}

function errorKind(status: number, code: string): CatalogueErrorKind {
  if (status === 422) return "validation";
  if (status === 404 || code === "CATALOGUE_ITEM_NOT_FOUND") return "not_found";
  if (status === 429 || code === "RATE_LIMITED") return "rate_limit";
  if (status === 504 || code === "UPSTREAM_TIMEOUT") return "timeout";
  return "provider";
}

async function requestCatalogue<T>(
  path: string,
  schema: z.ZodType<T>,
  options: { method?: "GET" | "POST"; body?: unknown; signal?: AbortSignal },
): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) abortFromCaller();
  else options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, CATALOG_TIMEOUT_MS);

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      signal: controller.signal,
    });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new CatalogueClientError(
        "unexpected_response",
        "SatQuery returned an unreadable catalogue response.",
        response.headers.get("X-Request-ID"),
      );
    }
    if (!response.ok) {
      const envelope = errorEnvelopeSchema.safeParse(body);
      if (!envelope.success) {
        throw new CatalogueClientError(
          "unexpected_response",
          "SatQuery returned an unexpected catalogue error.",
          response.headers.get("X-Request-ID"),
        );
      }
      throw new CatalogueClientError(
        errorKind(response.status, envelope.data.error.code),
        envelope.data.error.message,
        envelope.data.error.request_id,
        envelope.data.error.retryable,
      );
    }
    const parsed = schema.safeParse(body);
    if (!parsed.success) {
      throw new CatalogueClientError(
        "unexpected_response",
        "SatQuery returned catalogue data that did not match the API contract.",
        response.headers.get("X-Request-ID"),
      );
    }
    return parsed.data;
  } catch (error) {
    if (error instanceof CatalogueClientError) throw error;
    if (options.signal?.aborted) {
      throw new CatalogueClientError("cancelled", "The outdated catalogue request was cancelled.");
    }
    if (timedOut) {
      throw new CatalogueClientError("timeout", "The catalogue request timed out.", null, true);
    }
    throw new CatalogueClientError("network", "SatQuery could not be reached.", null, true);
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export function listCatalogueCollections(signal?: AbortSignal) {
  return requestCatalogue("/catalog/collections?provider=earth-search", collectionsResponseSchema, {
    signal,
  });
}

export function searchCatalogue(request: CatalogueSearchRequest, signal?: AbortSignal) {
  const validatedRequest = searchRequestSchema.parse(request);
  return requestCatalogue("/catalog/searches", searchResponseSchema, {
    method: "POST",
    body: validatedRequest,
    signal,
  });
}

export async function getCatalogueItem(
  providerId: string,
  collectionId: string,
  itemId: string,
  signal?: AbortSignal,
) {
  const provider = z.literal("earth-search").parse(providerId);
  const collection = identifierSchema.parse(collectionId);
  const item = identifierSchema.parse(itemId);
  const scene = await requestCatalogue(
    `/catalog/collections/${encodeURIComponent(collection)}/items/${encodeURIComponent(item)}?provider=${encodeURIComponent(provider)}`,
    sceneSchema,
    { signal },
  );
  if (
    scene.provider.id !== provider ||
    scene.collection.id !== collection ||
    scene.provider_asset_id !== item
  ) {
    throw new CatalogueClientError(
      "unexpected_response",
      "SatQuery returned metadata for a different catalogue scene.",
    );
  }
  return scene;
}
