import { apiBaseUrl } from "@/lib/config";
import {
  type FusionCapabilitiesResponse,
  type FusionRequestInput,
  type FusionResult,
  fusionCapabilitiesResponseSchema,
  fusionRequestSchema,
  fusionResultSchema,
} from "./fusion-contracts";

export class FusionClientError extends Error {
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
    this.name = "FusionClientError";
    this.code = options.code ?? "FUSION_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/**
 * Fetch supported evidence fusion capabilities and rules.
 */
export async function getFusionCapabilities(
  signal?: AbortSignal,
): Promise<FusionCapabilitiesResponse> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/fusion/capabilities`;
  const requestId = `fus_cap_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new FusionClientError("Unable to reach evidence fusion service. Please try again.", {
      code: "NETWORK_ERROR",
      status: 0,
      requestId,
      retryable: true,
      details: error,
    });
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    const errObj =
      errorData && typeof errorData === "object" && "error" in errorData
        ? (errorData as { error: { message?: string; code?: string; details?: unknown } }).error
        : null;

    throw new FusionClientError(
      errObj?.message || `Failed to fetch fusion capabilities (${response.status})`,
      {
        code: errObj?.code || "FUSION_CAPABILITIES_FAILED",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = fusionCapabilitiesResponseSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new FusionClientError("Fusion capabilities response failed client schema validation.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      details: parsed.error.issues,
    });
  }

  return parsed.data;
}

/**
 * Trigger deterministic optical and SAR evidence fusion calculation.
 */
export async function analyzeFusion(
  requestInput: FusionRequestInput,
  signal?: AbortSignal,
): Promise<FusionResult> {
  const validatedRequest = fusionRequestSchema.parse(requestInput);
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/fusion/analyze`;
  const requestId =
    validatedRequest.request_id || `fus_req_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new FusionClientError("Unable to execute evidence fusion. Please try again.", {
      code: "NETWORK_ERROR",
      status: 0,
      requestId,
      retryable: true,
      details: error,
    });
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    const errObj =
      errorData && typeof errorData === "object" && "error" in errorData
        ? (errorData as { error: { message?: string; code?: string; details?: unknown } }).error
        : null;

    throw new FusionClientError(
      errObj?.message || `Fusion calculation failed (${response.status})`,
      {
        code: errObj?.code || "FUSION_CALCULATION_FAILED",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = fusionResultSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new FusionClientError("Fusion result failed client schema validation.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      details: parsed.error.issues,
    });
  }

  return parsed.data;
}

/**
 * Fetch a cached fusion result by result ID.
 */
export async function getFusionResult(
  resultId: string,
  signal?: AbortSignal,
): Promise<FusionResult> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/fusion/results/${encodeURIComponent(resultId)}`;
  const requestId = `fus_res_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new FusionClientError("Unable to retrieve fusion result. Please try again.", {
      code: "NETWORK_ERROR",
      status: 0,
      requestId,
      retryable: true,
      details: error,
    });
  }

  const responseRequestId = response.headers.get("X-Request-ID") ?? requestId;

  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = null;
    }
    const errObj =
      errorData && typeof errorData === "object" && "error" in errorData
        ? (errorData as { error: { message?: string; code?: string; details?: unknown } }).error
        : null;

    throw new FusionClientError(
      errObj?.message || `Failed to retrieve fusion result (${response.status})`,
      {
        code: errObj?.code || "FUSION_RESULT_FETCH_FAILED",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = fusionResultSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new FusionClientError("Retrieved fusion result failed schema validation.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      details: parsed.error.issues,
    });
  }

  return parsed.data;
}

/**
 * Generate full API URL for streaming the classified 5-state fusion overlay PNG.
 */
export function getFusionOverlayUrl(resultId: string): string {
  const baseUrl = apiBaseUrl();
  return `${baseUrl}/fusion/results/${encodeURIComponent(resultId)}/overlay`;
}
