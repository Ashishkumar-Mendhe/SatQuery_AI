import { apiBaseUrl } from "@/lib/config";
import {
  type ImageryAsset,
  type ImageryRequestInput,
  type RasterMetadata,
  type TemporalImageryRequestInput,
  type TemporalImageryResponse,
  imageryAssetSchema,
  imageryRequestSchema,
  rasterMetadataSchema,
  temporalImageryRequestSchema,
  temporalImageryResponseSchema,
} from "./imagery-contracts";

export class ImageryClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly requestId: string | null;
  readonly retryable: boolean;
  readonly details: unknown;

  constructor(
    message: string,
    options: {
      code?: string;
      status?: number;
      requestId?: string | null;
      retryable?: boolean;
      details?: unknown;
    } = {},
  ) {
    super(message);
    this.name = "ImageryClientError";
    this.code = options.code ?? "IMAGERY_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

export function getAssetDisplayUrl(assetId: string): string {
  const baseUrl = apiBaseUrl();
  return `${baseUrl}/imagery/assets/${encodeURIComponent(assetId)}`;
}

export async function requestImagery(
  request: ImageryRequestInput,
  signal?: AbortSignal,
): Promise<ImageryAsset> {
  const validatedRequest = imageryRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/imagery/request`;
  const requestId = `img_req_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(validatedRequest),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ImageryClientError("Unable to reach satellite imagery service. Please try again.", {
      code: "NETWORK_ERROR",
      status: 0,
      requestId,
      retryable: true,
      details: error,
    });
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;

  if (!response.ok) {
    let errorData: { error?: { message?: string; code?: string; details?: unknown } } | null = null;
    try {
      errorData = await response.json();
    } catch {
      // JSON parse failure
    }

    const message =
      errorData?.error?.message ??
      `Satellite imagery retrieval failed with HTTP ${response.status}.`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new ImageryClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable: response.status >= 500 || response.status === 429,
      details: errorData?.error?.details,
    });
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch (error) {
    throw new ImageryClientError("Invalid response received from imagery service.", {
      code: "PARSE_ERROR",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parseResult = imageryAssetSchema.safeParse(json);
  if (!parseResult.success) {
    throw new ImageryClientError("Imagery response contract validation failed.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: parseResult.error.issues,
    });
  }

  return parseResult.data;
}

export async function requestTemporalImagery(
  request: TemporalImageryRequestInput,
  signal?: AbortSignal,
): Promise<TemporalImageryResponse> {
  const validatedRequest = temporalImageryRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/imagery/temporal-request`;
  const requestId = `temporal_img_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(validatedRequest),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ImageryClientError(
      "Unable to reach multitemporal imagery service. Please try again.",
      {
        code: "NETWORK_ERROR",
        status: 0,
        requestId,
        retryable: true,
        details: error,
      },
    );
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;

  if (!response.ok) {
    let errorData: { error?: { message?: string; code?: string; details?: unknown } } | null = null;
    try {
      errorData = await response.json();
    } catch {
      // JSON parse failure
    }

    const message =
      errorData?.error?.message ??
      `Multitemporal imagery retrieval failed with HTTP ${response.status}.`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new ImageryClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable: response.status >= 500 || response.status === 429,
      details: errorData?.error?.details,
    });
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch (error) {
    throw new ImageryClientError("Invalid response received from multitemporal imagery service.", {
      code: "PARSE_ERROR",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parseResult = temporalImageryResponseSchema.safeParse(json);
  if (!parseResult.success) {
    throw new ImageryClientError("Temporal imagery contract validation failed.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: parseResult.error.issues,
    });
  }

  return parseResult.data;
}

export async function fetchRasterMetadata(
  assetId: string,
  signal?: AbortSignal,
): Promise<RasterMetadata> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/imagery/assets/${encodeURIComponent(assetId)}/metadata`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ImageryClientError("Unable to fetch raster metadata.", {
      code: "NETWORK_ERROR",
      status: 0,
      retryable: true,
      details: error,
    });
  }

  if (!response.ok) {
    throw new ImageryClientError(`Raster metadata fetch failed with HTTP ${response.status}.`, {
      code: `HTTP_${response.status}`,
      status: response.status,
    });
  }

  const json = await response.json();
  return rasterMetadataSchema.parse(json);
}
