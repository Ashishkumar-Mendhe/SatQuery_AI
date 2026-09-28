import { apiBaseUrl } from "@/lib/config";
import {
  type SceneSearchRequest,
  type SceneSearchResponse,
  sceneSearchRequestSchema,
  sceneSearchResponseSchema,
} from "./scene-search-contracts";

export class SceneSearchClientError extends Error {
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
    this.name = "SceneSearchClientError";
    this.code = options.code ?? "SCENE_SEARCH_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

export async function searchScenes(
  request: SceneSearchRequest,
  signal?: AbortSignal,
): Promise<SceneSearchResponse> {
  // Validate outbound request against Zod schema
  const validatedRequest = sceneSearchRequestSchema.parse(request);

  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/scenes/search`;
  const requestId = `client_req_${Math.random().toString(36).slice(2, 11)}`;

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
    throw new SceneSearchClientError(
      `Network error contacting satellite scenes search service: ${err instanceof Error ? err.message : String(err)}`,
      { code: "NETWORK_ERROR", status: 0, requestId, retryable: true },
    );
  }

  const responseRequestId = response.headers.get("X-Request-ID") || requestId;

  if (!response.ok) {
    let errorData: {
      error?: { code?: string; message?: string; retryable?: boolean; details?: unknown };
    } | null = null;
    try {
      errorData = await response.json();
    } catch {
      // Ignored if response is not JSON
    }

    const code = errorData?.error?.code ?? `HTTP_${response.status}`;
    const message =
      errorData?.error?.message ??
      `Satellite scenes search returned HTTP ${response.status} (${response.statusText})`;
    const retryable = errorData?.error?.retryable ?? [429, 502, 503, 504].includes(response.status);

    throw new SceneSearchClientError(message, {
      code,
      status: response.status,
      requestId: responseRequestId,
      retryable,
      details: errorData?.error?.details,
    });
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch (err) {
    throw new SceneSearchClientError(
      `Failed to parse JSON response from satellite scenes search: ${err instanceof Error ? err.message : String(err)}`,
      { code: "INVALID_JSON_RESPONSE", status: response.status, requestId: responseRequestId },
    );
  }

  const parsed = sceneSearchResponseSchema.safeParse(json);
  if (!parsed.success) {
    throw new SceneSearchClientError(
      `Satellite scenes response failed schema validation: ${parsed.error.message}`,
      {
        code: "RESPONSE_VALIDATION_FAILED",
        status: response.status,
        requestId: responseRequestId,
        details: parsed.error.issues,
      },
    );
  }

  return parsed.data;
}
