import { apiBaseUrl } from "@/lib/config";
import {
  type ChangeDetectionRequestInput,
  type ChangeDetectionResult,
  type ChangeMethodsResponse,
  changeDetectionRequestSchema,
  changeDetectionResultSchema,
  changeMethodsResponseSchema,
} from "./change-contracts";

export class ChangeClientError extends Error {
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
    this.name = "ChangeClientError";
    this.code = options.code ?? "CHANGE_DETECTION_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/**
 * Fetch all supported change detection methods from the registry.
 */
export async function listChangeMethods(signal?: AbortSignal): Promise<ChangeMethodsResponse> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/change/methods`;
  const requestId = `chg_mth_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ChangeClientError("Unable to reach change detection service. Please try again.", {
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
      // ignore json parse error
    }

    const message =
      errorData?.error?.message ??
      `Failed to list change detection methods (HTTP ${response.status}).`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new ChangeClientError(message, {
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
    throw new ChangeClientError("Received invalid JSON from change detection service.", {
      code: "INVALID_RESPONSE",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parsed = changeMethodsResponseSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new ChangeClientError("Change methods schema validation failed.", {
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
 * Execute pixel-level change detection between two prepared raster assets.
 */
export async function calculateChangeDetection(
  request: ChangeDetectionRequestInput,
  signal?: AbortSignal,
): Promise<ChangeDetectionResult> {
  const validatedRequest = changeDetectionRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/change/calculate`;
  const requestId = `chg_calc_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new ChangeClientError("Unable to reach change detection service. Please try again.", {
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
      // ignore json parse error
    }

    const message =
      errorData?.error?.message ?? `Change detection calculation failed (HTTP ${response.status}).`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new ChangeClientError(message, {
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
    throw new ChangeClientError("Received invalid JSON from change detection service.", {
      code: "INVALID_RESPONSE",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parsed = changeDetectionResultSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new ChangeClientError("Change detection response schema validation failed.", {
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
 * Retrieve a previously calculated change detection result by ID.
 */
export async function getChangeResult(
  resultId: string,
  signal?: AbortSignal,
): Promise<ChangeDetectionResult> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/change/results/${encodeURIComponent(resultId)}`;
  const requestId = `chg_get_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ChangeClientError("Unable to reach change detection service. Please try again.", {
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
      // ignore
    }

    const message =
      errorData?.error?.message ?? `Failed to fetch change result (HTTP ${response.status}).`;
    const code = errorData?.error?.code ?? `HTTP_${response.status}`;

    throw new ChangeClientError(message, {
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
    throw new ChangeClientError("Received invalid JSON from change detection service.", {
      code: "INVALID_RESPONSE",
      status: response.status,
      requestId: responseRequestId,
      retryable: false,
      details: error,
    });
  }

  const parsed = changeDetectionResultSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new ChangeClientError("Change result schema validation failed.", {
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
 * Construct URL to retrieve continuous or discrete classified overlay PNG.
 */
export function getChangeOverlayUrl(
  resultId: string,
  options: { classified?: boolean } = {},
): string {
  const baseUrl = apiBaseUrl();
  const classifiedParam = options.classified ? "?classified=true" : "";
  return `${baseUrl}/change/results/${encodeURIComponent(resultId)}/overlay${classifiedParam}`;
}
