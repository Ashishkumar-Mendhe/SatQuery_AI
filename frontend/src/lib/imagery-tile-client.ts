import { z } from "zod";

import { apiBaseUrl } from "@/lib/health-client";
import {
  type TileMetadata,
  tileMetadataSchema,
  type ViewerSceneIdentity,
  viewerSceneIdentitySchema,
} from "@/lib/viewer-contracts";

const TILE_METADATA_TIMEOUT_MS = 35_000;

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

export type ImageryTileErrorKind =
  | "cancelled"
  | "expired"
  | "restricted"
  | "unavailable"
  | "timeout"
  | "network"
  | "unexpected_response";

export class ImageryTileClientError extends Error {
  constructor(
    readonly kind: ImageryTileErrorKind,
    message: string,
    readonly requestId: string | null = null,
    readonly retryable = false,
  ) {
    super(message);
    this.name = "ImageryTileClientError";
  }
}

function errorKind(status: number, code: string): ImageryTileErrorKind {
  if (status === 410 || code.includes("EXPIRED")) return "expired";
  if (status === 401 || status === 403 || code.includes("ACCESS")) return "restricted";
  if (status === 504 || code.includes("TIMEOUT")) return "timeout";
  return "unavailable";
}

export async function createImageryTileSet(
  scene: ViewerSceneIdentity,
  signal?: AbortSignal,
): Promise<TileMetadata> {
  const validatedScene = viewerSceneIdentitySchema.parse(scene);
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(signal?.reason);
  if (signal?.aborted) abortFromCaller();
  else signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, TILE_METADATA_TIMEOUT_MS);

  try {
    const response = await fetch(`${apiBaseUrl()}/imagery/tile-sets`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        schema_version: "1.0",
        scene: validatedScene,
        render_preset: "natural-color",
        tile_size: 256,
      }),
      cache: "no-store",
      signal: controller.signal,
    });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new ImageryTileClientError(
        "unexpected_response",
        "SatQuery returned unreadable imagery metadata.",
        response.headers.get("X-Request-ID"),
      );
    }
    if (!response.ok) {
      const envelope = errorEnvelopeSchema.safeParse(body);
      if (!envelope.success) {
        throw new ImageryTileClientError(
          "unexpected_response",
          "SatQuery returned an unexpected imagery error.",
          response.headers.get("X-Request-ID"),
        );
      }
      throw new ImageryTileClientError(
        errorKind(response.status, envelope.data.error.code),
        envelope.data.error.message,
        envelope.data.error.request_id,
        envelope.data.error.retryable,
      );
    }
    const parsed = tileMetadataSchema.safeParse(body);
    if (!parsed.success) {
      throw new ImageryTileClientError(
        "unexpected_response",
        "SatQuery returned imagery metadata that did not match the viewer contract.",
        response.headers.get("X-Request-ID"),
      );
    }
    if (JSON.stringify(parsed.data.asset.scene) !== JSON.stringify(validatedScene)) {
      throw new ImageryTileClientError(
        "unexpected_response",
        "SatQuery returned imagery metadata for a different scene.",
        response.headers.get("X-Request-ID"),
      );
    }
    return parsed.data;
  } catch (error) {
    if (error instanceof ImageryTileClientError) throw error;
    if (signal?.aborted) {
      throw new ImageryTileClientError("cancelled", "The outdated imagery request was cancelled.");
    }
    if (timedOut) {
      throw new ImageryTileClientError(
        "timeout",
        "Imagery metadata took too long to resolve.",
        null,
        true,
      );
    }
    throw new ImageryTileClientError(
      "network",
      "SatQuery could not be reached for imagery metadata.",
      null,
      true,
    );
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}

export function absoluteTileTemplate(metadata: TileMetadata): string {
  if (metadata.access.state !== "available" || !metadata.url_template) {
    throw new ImageryTileClientError("unavailable", "Imagery tile access is unavailable.");
  }
  const base = new URL(apiBaseUrl());
  const resolved = new URL(metadata.url_template, base.origin);
  if (
    resolved.origin !== base.origin ||
    resolved.username ||
    resolved.password ||
    resolved.search ||
    resolved.hash ||
    !resolved.pathname.startsWith("/api/v1/imagery/tiles/")
  ) {
    throw new ImageryTileClientError(
      "unexpected_response",
      "SatQuery returned an unsafe imagery tile template.",
    );
  }
  // URL serialisation percent-encodes MapLibre's required template markers.
  return `${base.origin}${metadata.url_template}`;
}
