import { apiBaseUrl } from "@/lib/config";
import {
  type ImageManifest,
  type VisualCapabilitiesResponse,
  type VisualQueryRequestInput,
  type VisualQueryResponse,
  imageManifestSchema,
  visualCapabilitiesResponseSchema,
  visualQueryRequestSchema,
  visualQueryResponseSchema,
} from "./visual-contracts";

export class VisualClientError extends Error {
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
    this.name = "VisualClientError";
    this.code = options.code ?? "VISUAL_QUERY_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/**
 * Fetch supported visual VQA operations and model capability flags.
 */
export async function getVisualCapabilities(
  signal?: AbortSignal,
): Promise<VisualCapabilitiesResponse> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/query/visual/capabilities`;
  const requestId = `vcap_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new VisualClientError("Unable to reach visual capabilities service. Please try again.", {
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

    throw new VisualClientError(
      errObj?.message || `Failed to fetch visual capabilities (${response.status})`,
      {
        code: errObj?.code || "VISUAL_CAPABILITIES_FAILED",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = visualCapabilitiesResponseSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new VisualClientError("Visual capabilities response failed client schema validation.", {
      code: "VALIDATION_FAILED",
      status: 200,
      requestId: responseRequestId,
      details: parsed.error.format(),
    });
  }

  return parsed.data;
}

/**
 * Submit a natural-language visual query about selected optical or bitemporal satellite images.
 */
export async function askVisualQuery(
  input: VisualQueryRequestInput,
  signal?: AbortSignal,
): Promise<VisualQueryResponse> {
  const parsedInput = visualQueryRequestSchema.safeParse(input);
  if (!parsedInput.success) {
    throw new VisualClientError("Visual query input failed client schema validation.", {
      code: "CLIENT_VALIDATION_FAILED",
      status: 400,
      details: parsedInput.error.format(),
    });
  }

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/query/visual`;
  const requestId = input.request_id ?? `vqa_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(parsedInput.data),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new VisualClientError("Unable to reach visual query service. Please try again.", {
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

    throw new VisualClientError(
      errObj?.message || `Visual query request failed with status ${response.status}`,
      {
        code: errObj?.code || "VISUAL_QUERY_FAILED",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = visualQueryResponseSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new VisualClientError("Visual query response failed client schema validation.", {
      code: "VALIDATION_FAILED",
      status: 200,
      requestId: responseRequestId,
      details: parsed.error.format(),
    });
  }

  return parsed.data;
}

/**
 * Retrieve an immutable ImageManifest by ID.
 */
export async function getImageManifest(
  manifestId: string,
  signal?: AbortSignal,
): Promise<ImageManifest> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/query/manifests/${encodeURIComponent(manifestId)}`;
  const requestId = `vman_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new VisualClientError("Unable to reach manifest service. Please try again.", {
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

    throw new VisualClientError(
      errObj?.message || `Failed to fetch image manifest (${response.status})`,
      {
        code: errObj?.code || "MANIFEST_NOT_FOUND",
        status: response.status,
        requestId: responseRequestId,
        retryable: response.status >= 500,
        details: errObj?.details || errorData,
      },
    );
  }

  const rawJson = await response.json();
  const parsed = imageManifestSchema.safeParse(rawJson);
  if (!parsed.success) {
    throw new VisualClientError("Image manifest failed client schema validation.", {
      code: "VALIDATION_FAILED",
      status: 200,
      requestId: responseRequestId,
      details: parsed.error.format(),
    });
  }

  return parsed.data;
}
