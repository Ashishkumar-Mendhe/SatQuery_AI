import { apiBaseUrl } from "@/lib/config";
import {
  type ReportGenerationRequestInput,
  type ReportResponse,
  type ReportSnapshot,
  reportGenerationRequestSchema,
  reportResponseSchema,
  reportSnapshotSchema,
} from "./report-contracts";

export class ReportClientError extends Error {
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
    this.name = "ReportClientError";
    this.code = options.code ?? "REPORT_ERROR";
    this.status = options.status ?? 500;
    this.requestId = options.requestId ?? null;
    this.retryable = options.retryable ?? false;
    this.details = options.details;
  }
}

/**
 * Request server to build a snapshot and generate requested report formats.
 */
export async function requestReportGeneration(
  input: ReportGenerationRequestInput,
  signal?: AbortSignal,
): Promise<ReportResponse> {
  const parsed = reportGenerationRequestSchema.parse(input);
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/reports/request`;
  const requestId = `rep_req_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(parsed),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ReportClientError(
      `Network failure requesting report generation: ${error instanceof Error ? error.message : "Unknown error"}`,
      { code: "NETWORK_ERROR", retryable: true, details: error },
    );
  }

  if (!response.ok) {
    let errorMessage = `Report generation failed (HTTP ${response.status})`;
    let errorCode = "REPORT_GEN_FAILED";
    try {
      const errorBody = (await response.json()) as Record<string, unknown>;
      if (errorBody.error && typeof errorBody.error === "object") {
        const nested = errorBody.error as Record<string, unknown>;
        errorMessage = (nested.message as string) || errorMessage;
        errorCode = (nested.code as string) || errorCode;
      } else if (typeof errorBody.detail === "string") {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Use fallback
    }
    throw new ReportClientError(errorMessage, {
      code: errorCode,
      status: response.status,
      retryable: response.status >= 500,
    });
  }

  const rawJson = await response.json();
  return reportResponseSchema.parse(rawJson);
}

/**
 * Direct export from an existing client-side or cached ReportSnapshot.
 */
export async function exportSnapshotDirect(
  snapshot: ReportSnapshot,
  signal?: AbortSignal,
): Promise<ReportResponse> {
  const parsed = reportSnapshotSchema.parse(snapshot);
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/reports/snapshot-export`;
  const requestId = `rep_snap_${Math.random().toString(36).slice(2, 11)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
      },
      body: JSON.stringify(parsed),
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ReportClientError(
      `Network failure during snapshot export: ${error instanceof Error ? error.message : "Unknown error"}`,
      { code: "NETWORK_ERROR", retryable: true, details: error },
    );
  }

  if (!response.ok) {
    let errorMessage = `Snapshot export failed (HTTP ${response.status})`;
    let errorCode = "EXPORT_FAILED";
    try {
      const errorBody = (await response.json()) as Record<string, unknown>;
      if (errorBody.error && typeof errorBody.error === "object") {
        const nested = errorBody.error as Record<string, unknown>;
        errorMessage = (nested.message as string) || errorMessage;
        errorCode = (nested.code as string) || errorCode;
      } else if (typeof errorBody.detail === "string") {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Use fallback
    }
    throw new ReportClientError(errorMessage, {
      code: errorCode,
      status: response.status,
      retryable: response.status >= 500,
    });
  }

  const rawJson = await response.json();
  return reportResponseSchema.parse(rawJson);
}

/**
 * Poll or check report generation status and download URLs.
 */
export async function getReportStatus(
  reportId: string,
  signal?: AbortSignal,
): Promise<ReportResponse> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/reports/${encodeURIComponent(reportId)}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ReportClientError(
      `Network failure checking report status: ${error instanceof Error ? error.message : "Unknown error"}`,
      { code: "NETWORK_ERROR", retryable: true },
    );
  }

  if (!response.ok) {
    throw new ReportClientError(`Report ${reportId} not found or unavailable`, {
      code: "REPORT_NOT_FOUND",
      status: response.status,
    });
  }

  const rawJson = await response.json();
  return reportResponseSchema.parse(rawJson);
}

/**
 * Fetch raw snapshot data for audit or client verification.
 */
export async function getReportSnapshot(
  reportId: string,
  signal?: AbortSignal,
): Promise<ReportSnapshot> {
  const baseUrl = apiBaseUrl();
  const url = `${baseUrl}/reports/${encodeURIComponent(reportId)}/snapshot`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      signal,
    });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ReportClientError(
      `Network failure fetching snapshot: ${error instanceof Error ? error.message : "Unknown error"}`,
      { code: "NETWORK_ERROR", retryable: true },
    );
  }

  if (!response.ok) {
    throw new ReportClientError(`Report snapshot ${reportId} not found`, {
      code: "SNAPSHOT_NOT_FOUND",
      status: response.status,
    });
  }

  const rawJson = await response.json();
  return reportSnapshotSchema.parse(rawJson);
}

/**
 * Get direct download URL for a generated PDF or JSON export.
 */
export function getReportDownloadUrl(reportId: string, format: "pdf" | "json"): string {
  const baseUrl = apiBaseUrl();
  return `${baseUrl}/reports/${encodeURIComponent(reportId)}/download/${encodeURIComponent(format)}`;
}

/**
 * Trigger file download directly in browser.
 */
export async function downloadReportFile(
  reportId: string,
  format: "pdf" | "json",
  defaultFilename?: string,
): Promise<void> {
  const downloadUrl = getReportDownloadUrl(reportId, format);
  const response = await fetch(downloadUrl);

  if (!response.ok) {
    throw new ReportClientError(`Failed to download report file: HTTP ${response.status}`, {
      status: response.status,
    });
  }

  const blob = await response.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = blobUrl;

  const contentDisposition = response.headers.get("Content-Disposition");
  let filename = defaultFilename ?? `satquery_report_${reportId}.${format}`;
  if (contentDisposition?.includes("filename=")) {
    const match = contentDisposition.match(/filename="?([^";]+)"?/);
    if (match?.[1]) {
      filename = match[1];
    }
  }

  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(blobUrl);
}
