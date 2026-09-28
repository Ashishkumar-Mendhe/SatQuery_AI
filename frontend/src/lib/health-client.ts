import { z } from "zod";

const livenessSchema = z
  .object({
    status: z.literal("live"),
    service: z.literal("satquery-api"),
    version: z.string().min(1),
  })
  .strict();

const readinessSchema = z
  .object({
    status: z.literal("ready"),
    service: z.literal("satquery-api"),
    version: z.string().min(1),
    request_id: z.string().min(1),
    checks: z
      .object({
        database: z
          .object({
            status: z.literal("up"),
            postgis: z.literal("available"),
            migration: z.literal("current"),
            server_version: z.string().min(1),
            postgis_version: z.string().min(1),
            migration_revision: z.string().min(1),
          })
          .strict(),
      })
      .strict(),
  })
  .strict();

const errorSchema = z
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

export type LivenessResponse = z.infer<typeof livenessSchema>;
export type ReadinessResponse = z.infer<typeof readinessSchema>;

export type BackendHealth =
  | {
      state: "ready";
      live: LivenessResponse;
      ready: ReadinessResponse;
      requestId: string | null;
    }
  | {
      state: "database_unavailable";
      live: LivenessResponse;
      requestId: string | null;
      message: string;
    };

export type ApiClientErrorKind =
  | "configuration"
  | "network"
  | "timeout"
  | "cancelled"
  | "unexpected_response";

export class ApiClientError extends Error {
  constructor(
    readonly kind: ApiClientErrorKind,
    message: string,
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function apiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!configured) {
    throw new ApiClientError("configuration", "NEXT_PUBLIC_API_BASE_URL is not configured.");
  }
  try {
    const parsed = new URL(configured);
    const path = parsed.pathname.replace(/\/+$/, "");
    if (
      !["http:", "https:"].includes(parsed.protocol) ||
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash ||
      path !== "/api/v1"
    ) {
      throw new Error("unsafe URL");
    }
  } catch {
    throw new ApiClientError("configuration", "The public API base URL is invalid.");
  }
  return configured.replace(/\/+$/, "");
}

type JsonResponse = {
  status: number;
  ok: boolean;
  body: unknown;
  requestId: string | null;
};

async function requestJson(
  path: string,
  options: { signal?: AbortSignal; timeoutMs: number },
): Promise<JsonResponse> {
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) {
    abortFromCaller();
  } else {
    options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  }
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs);

  try {
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new ApiClientError(
        "unexpected_response",
        "The backend returned a non-JSON response.",
        response.headers.get("X-Request-ID"),
      );
    }
    return {
      status: response.status,
      ok: response.ok,
      body,
      requestId: response.headers.get("X-Request-ID"),
    };
  } catch (error) {
    if (error instanceof ApiClientError) throw error;
    if (options.signal?.aborted) {
      throw new ApiClientError("cancelled", "The health request was cancelled.");
    }
    if (timedOut) {
      throw new ApiClientError("timeout", "The backend health request timed out.");
    }
    throw new ApiClientError("network", "The backend could not be reached.");
  } finally {
    window.clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function inspectBackendHealth(options?: {
  signal?: AbortSignal;
  timeoutMs?: number;
}): Promise<BackendHealth> {
  const requestOptions = {
    signal: options?.signal,
    timeoutMs: options?.timeoutMs ?? 5000,
  };
  const liveResponse = await requestJson("/health/live", requestOptions);
  const live = livenessSchema.safeParse(liveResponse.body);
  if (!liveResponse.ok || !live.success) {
    throw new ApiClientError(
      "unexpected_response",
      "The backend liveness response did not match the contract.",
      liveResponse.requestId,
    );
  }

  const readyResponse = await requestJson("/health/ready", requestOptions);
  if (readyResponse.ok) {
    const ready = readinessSchema.safeParse(readyResponse.body);
    if (!ready.success) {
      throw new ApiClientError(
        "unexpected_response",
        "The backend readiness response did not match the contract.",
        readyResponse.requestId,
      );
    }
    return {
      state: "ready",
      live: live.data,
      ready: ready.data,
      requestId: readyResponse.requestId,
    };
  }

  const error = errorSchema.safeParse(readyResponse.body);
  if (
    readyResponse.status === 503 &&
    error.success &&
    error.data.error.code === "DEPENDENCY_UNAVAILABLE"
  ) {
    return {
      state: "database_unavailable",
      live: live.data,
      requestId: readyResponse.requestId,
      message: error.data.error.message,
    };
  }

  throw new ApiClientError(
    "unexpected_response",
    "The backend readiness request failed unexpectedly.",
    readyResponse.requestId,
  );
}
