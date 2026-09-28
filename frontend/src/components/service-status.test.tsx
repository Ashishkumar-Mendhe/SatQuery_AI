import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { ServiceStatus } from "./service-status";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

it("shows backend failure honestly and retries", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  const fetchMock = vi
    .fn()
    .mockRejectedValueOnce(new TypeError("network details"))
    .mockRejectedValueOnce(new TypeError("network details"));
  vi.stubGlobal("fetch", fetchMock);
  const user = userEvent.setup();

  render(<ServiceStatus />);

  expect(await screen.findByText("Backend unreachable")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Retry status check" }));
  expect(await screen.findByText("Backend unreachable")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("shows a reachable backend with an unavailable database", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ status: "live", service: "satquery-api", version: "0.1.0" }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: {
              code: "DEPENDENCY_UNAVAILABLE",
              message: "A required service dependency is unavailable.",
              request_id: "req_synthetic",
              details: { dependency: "database" },
              retryable: true,
            },
          }),
          { status: 503 },
        ),
      ),
  );

  render(<ServiceStatus />);

  expect(await screen.findByText("Backend reachable; database unavailable")).toBeInTheDocument();
});

it("shows an unexpected-response state for malformed backend JSON", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "unknown" }), {
        status: 200,
      }),
    ),
  );

  render(<ServiceStatus />);

  expect(await screen.findByText("Unexpected response or request failure")).toBeInTheDocument();
});

it("shows the compact ready state only after both health checks succeed", async () => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ status: "live", service: "satquery-api", version: "0.1.0" }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "ready",
            service: "satquery-api",
            version: "0.1.0",
            request_id: "synthetic-ready-id",
            checks: {
              database: {
                status: "up",
                postgis: "available",
                migration: "current",
                server_version: "synthetic-test-version",
                postgis_version: "synthetic-test-version",
                migration_revision: "20260907_0001",
              },
            },
          }),
          { status: 200 },
        ),
      ),
  );

  render(<ServiceStatus compact />);

  expect(await screen.findByText("Backend ready")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
});
