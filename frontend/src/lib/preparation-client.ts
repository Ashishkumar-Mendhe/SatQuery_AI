import { apiBaseUrl } from "@/lib/config";
import {
  type PreparedRasterAsset,
  type PreparedTemporalPair,
  type RasterPreparationRequestInput,
  type TemporalRasterPreparationRequestInput,
  preparedRasterAssetSchema,
  preparedTemporalPairSchema,
  rasterPreparationRequestSchema,
  temporalRasterPreparationRequestSchema,
} from "./preparation-contracts";

export class PreparationClientError extends Error {
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
    this.name = "PreparationClientError";
    this.code = options.code ?? "PREPARATION_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/**
 * Send request to harmonise, reproject to metric grid, and clip a single analysis raster.
 */
export async function prepareRaster(
  request: RasterPreparationRequestInput,
  signal?: AbortSignal,
): Promise<PreparedRasterAsset> {
  const validatedRequest = rasterPreparationRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/processing/prepare-raster`;
  const requestId = `prep_req_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new PreparationClientError(
      "Unable to reach raster preparation service. Please try again.",
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
      errorData?.error?.message ?? `Raster preparation failed with HTTP ${response.status}.`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new PreparationClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable: response.status >= 500 && response.status !== 501,
      details: errorData?.error?.details,
    });
  }

  let rawJson: unknown;
  try {
    rawJson = await response.json();
  } catch (error: unknown) {
    throw new PreparationClientError("Received invalid JSON response from preparation service.", {
      code: "INVALID_RESPONSE",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parsed = preparedRasterAssetSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new PreparationClientError("Preparation response schema validation failed.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: parsed.error.format(),
    });
  }

  return parsed.data;
}

/**
 * Send request to harmonise, reproject, and strictly align a multitemporal pair.
 */
export async function prepareTemporalPair(
  request: TemporalRasterPreparationRequestInput,
  signal?: AbortSignal,
): Promise<PreparedTemporalPair> {
  const validatedRequest = temporalRasterPreparationRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/processing/prepare-temporal-pair`;
  const requestId = `prep_pair_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new PreparationClientError(
      "Unable to reach temporal preparation service. Please try again.",
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
      errorData?.error?.message ?? `Temporal pair preparation failed with HTTP ${response.status}.`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new PreparationClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable: response.status >= 500 && response.status !== 501,
      details: errorData?.error?.details,
    });
  }

  let rawJson: unknown;
  try {
    rawJson = await response.json();
  } catch (error: unknown) {
    throw new PreparationClientError("Received invalid JSON response from preparation service.", {
      code: "INVALID_RESPONSE",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parsed = preparedTemporalPairSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new PreparationClientError("Temporal preparation response schema validation failed.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: parsed.error.format(),
    });
  }

  return parsed.data;
}
