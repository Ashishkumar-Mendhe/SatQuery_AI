import { apiBaseUrl } from "@/lib/config";
import {
  type TemporalPairValidationRequestInput,
  type TemporalPairValidationResult,
  type TemporalSceneCandidates,
  type TemporalSearchRequestInput,
  temporalPairValidationRequestSchema,
  temporalPairValidationResultSchema,
  temporalSceneCandidatesSchema,
  temporalSearchRequestSchema,
} from "./temporal-contracts";

export class TemporalClientError extends Error {
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
    this.name = "TemporalClientError";
    this.code = options.code ?? "TEMPORAL_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

export async function searchTemporalCandidates(
  request: TemporalSearchRequestInput,
  signal?: AbortSignal,
): Promise<TemporalSceneCandidates> {
  const validatedRequest = temporalSearchRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/scenes/temporal-search`;
  const requestId = `temporal_req_${Math.random().toString(36).slice(2, 11)}`;

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
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new TemporalClientError(
      `Network error contacting temporal search service: ${err instanceof Error ? err.message : String(err)}`,
      { code: "NETWORK_ERROR", status: 0, requestId, retryable: true },
    );
  }

  const responseRequestId = response.headers.get("X-Request-ID") || requestId;

  if (!response.ok) {
    let errorData: {
      error?: { code?: string; message?: string; retryable?: boolean; details?: unknown };
      detail?: string | unknown[];
    } | null = null;
    try {
      errorData = await response.json();
    } catch {
      // Ignored
    }

    const code = errorData?.error?.code ?? `HTTP_${response.status}`;
    const message =
      errorData?.error?.message ??
      (typeof errorData?.detail === "string"
        ? errorData.detail
        : `Temporal search returned HTTP ${response.status} (${response.statusText})`);
    const retryable = errorData?.error?.retryable ?? [429, 502, 503, 504].includes(response.status);

    throw new TemporalClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable,
      details: errorData?.error?.details ?? errorData?.detail,
    });
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch (err) {
    throw new TemporalClientError(
      `Invalid JSON received from temporal search endpoint: ${err instanceof Error ? err.message : String(err)}`,
      { code: "MALFORMED_RESPONSE", status: response.status, requestId: responseRequestId },
    );
  }

  try {
    return temporalSceneCandidatesSchema.parse(json);
  } catch (err) {
    throw new TemporalClientError(
      `Contract mismatch in temporal scene candidates response: ${err instanceof Error ? err.message : String(err)}`,
      {
        code: "CONTRACT_VALIDATION_ERROR",
        status: response.status,
        requestId: responseRequestId,
        details: err,
      },
    );
  }
}

export async function validateTemporalPair(
  request: TemporalPairValidationRequestInput,
  signal?: AbortSignal,
): Promise<TemporalPairValidationResult> {
  const validatedRequest = temporalPairValidationRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/scenes/validate-pair`;
  const requestId = `val_req_${Math.random().toString(36).slice(2, 11)}`;

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
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw err;
    }
    throw new TemporalClientError(
      `Network error contacting pair validation service: ${err instanceof Error ? err.message : String(err)}`,
      { code: "NETWORK_ERROR", status: 0, requestId, retryable: true },
    );
  }

  const responseRequestId = response.headers.get("X-Request-ID") || requestId;

  if (!response.ok) {
    let errorData: {
      error?: { code?: string; message?: string; retryable?: boolean; details?: unknown };
      detail?: string | unknown[];
    } | null = null;
    try {
      errorData = await response.json();
    } catch {
      // Ignored
    }

    const code = errorData?.error?.code ?? `HTTP_${response.status}`;
    const message =
      errorData?.error?.message ??
      (typeof errorData?.detail === "string"
        ? errorData.detail
        : `Pair validation returned HTTP ${response.status} (${response.statusText})`);
    const retryable = errorData?.error?.retryable ?? [429, 502, 503, 504].includes(response.status);

    throw new TemporalClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable,
      details: errorData?.error?.details ?? errorData?.detail,
    });
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch (err) {
    throw new TemporalClientError(
      `Invalid JSON received from pair validation endpoint: ${err instanceof Error ? err.message : String(err)}`,
      { code: "MALFORMED_RESPONSE", status: response.status, requestId: responseRequestId },
    );
  }

  try {
    return temporalPairValidationResultSchema.parse(json);
  } catch (err) {
    throw new TemporalClientError(
      `Contract mismatch in temporal pair validation response: ${err instanceof Error ? err.message : String(err)}`,
      {
        code: "CONTRACT_VALIDATION_ERROR",
        status: response.status,
        requestId: responseRequestId,
        details: err,
      },
    );
  }
}
