import { afterEach, describe, expect, it, vi } from "vitest";

import { apiBaseUrl, inspectBackendHealth } from "./health-client";

const liveBody = { status: "live", service: "satquery-api", version: "0.1.0" };
const readyBody = {
  status: "ready",
  service: "satquery-api",
  version: "0.1.0",
  request_id: "ready-body-id",
  checks: {
    database: {
      status: "up",
      postgis: "available",
      migration: "current",
      server_version: "18.synthetic",
      postgis_version: "3.6.synthetic",
      migration_revision: "20260907_0001",
    },
  },
};

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: init?.status ?? 200,
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": "header-request-id",
    },
  });
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("inspectBackendHealth", () => {
  it("rejects a public API URL without the versioned prefix", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000");

    expect(() => apiBaseUrl()).toThrow("public API base URL is invalid");
  });

  it("validates live and ready responses", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(liveBody))
        .mockResolvedValueOnce(jsonResponse(readyBody)),
    );

    const result = await inspectBackendHealth();

    expect(result.state).toBe("ready");
    expect(result.requestId).toBe("header-request-id");
  });

  it("reports a database dependency failure as reachable but unavailable", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(liveBody))
        .mockResolvedValueOnce(
          jsonResponse(
            {
              error: {
                code: "DEPENDENCY_UNAVAILABLE",
                message: "A required service dependency is unavailable.",
                request_id: "failure-id",
                details: { dependency: "database" },
                retryable: true,
              },
            },
            { status: 503 },
          ),
        ),
    );

    await expect(inspectBackendHealth()).resolves.toMatchObject({
      state: "database_unavailable",
      requestId: "header-request-id",
    });
  });

  it("does not accept an unknown success response", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ status: "probably" })));

    await expect(inspectBackendHealth()).rejects.toMatchObject({
      kind: "unexpected_response",
    });
  });

  it("distinguishes a network failure", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network details")));

    await expect(inspectBackendHealth()).rejects.toMatchObject({
      kind: "network",
    });
  });

  it("honors caller cancellation", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        });
      }),
    );
    const controller = new AbortController();
    const pending = inspectBackendHealth({ signal: controller.signal });

    controller.abort();

    await expect(pending).rejects.toMatchObject({
      kind: "cancelled",
    });
  });

  it("classifies its own deadline as a timeout", async () => {
    vi.useFakeTimers();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        });
      }),
    );

    const assertion = expect(inspectBackendHealth({ timeoutMs: 100 })).rejects.toMatchObject({
      kind: "timeout",
    });
    await vi.advanceTimersByTimeAsync(100);
    await assertion;
  });
});
