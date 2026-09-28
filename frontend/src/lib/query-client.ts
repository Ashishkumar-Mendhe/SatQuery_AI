import { apiBaseUrl } from "@/lib/config";
import {
  type QueryAnswer,
  type QueryCapabilitiesResponse,
  type QueryRequestInput,
  queryAnswerSchema,
  queryCapabilitiesResponseSchema,
  queryRequestSchema,
} from "./query-contracts";

export class QueryClientError extends Error {
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
    this.name = "QueryClientError";
    this.code = options.code ?? "QUERY_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/**
 * Fetch supported question intents and engine capabilities.
 */
export async function getQueryCapabilities(
  signal?: AbortSignal,
): Promise<QueryCapabilitiesResponse> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/query/capabilities`;
  const requestId = `qry_cap_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new QueryClientError("Unable to reach query capabilities service. Please try again.", {
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

    throw new QueryClientError(
      errObj?.message || `Failed to fetch query capabilities (${response.status})`,
      {
        code: errObj?.code || "QUERY_CAPABILITIES_FAILED",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = queryCapabilitiesResponseSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new QueryClientError("Query capabilities response failed client schema validation.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      details: parsed.error.issues,
    });
  }

  return parsed.data;
}

/**
 * Ask a natural-language question grounded in the active workspace context snapshot.
 */
export async function askQuery(
  requestInput: QueryRequestInput,
  signal?: AbortSignal,
): Promise<QueryAnswer> {
  const validatedRequest = queryRequestSchema.parse(requestInput);
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/query/ask`;
  const requestId =
    validatedRequest.request_id || `qry_req_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new QueryClientError("Unable to execute query. Please try again.", {
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

    throw new QueryClientError(errObj?.message || `Query answering failed (${response.status})`, {
      code: errObj?.code || "QUERY_EXECUTION_FAILED",
      status: response.status,
      requestId: responseRequestId,
      retryable: response.status >= 500,
      details: errObj?.details || errorData,
    });
  }

  const rawJson = await response.json();
  const parsed = queryAnswerSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new QueryClientError("Query answer response failed client schema validation.", {
      code: "SCHEMA_VALIDATION_ERROR",
      status: response.status,
      requestId: responseRequestId,
      details: parsed.error.issues,
    });
  }

  return parsed.data;
}
