import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  exportSnapshotDirect,
  getReportDownloadUrl,
  getReportStatus,
  ReportClientError,
  requestReportGeneration,
} from "./report-client";

describe("report-client suite", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("requestReportGeneration posts valid request and parses response", async () => {
    const mockReportResponse = {
      report_id: "rep-001",
      workspace_id: "ws-default",
      result_id: "res-001",
      title: "Test Report",
      status: "completed",
      formats: ["pdf", "json"],
      format_statuses: {
        pdf: {
          format: "pdf",
          status: "completed",
          download_url: "/api/v1/reports/rep-001/download/pdf",
        },
      },
      download_urls: {
        pdf: "/api/v1/reports/rep-001/download/pdf",
      },
      created_at: "2026-09-20T12:00:00Z",
      is_mock_data: false,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-req-rep" }),
      json: async () => mockReportResponse,
    });

    const res = await requestReportGeneration({
      result_id: "res-001",
      title: "Test Report",
      formats: ["pdf", "json"],
      included_sections: ["summary", "quantitative_findings"],
    });

    expect(res.report_id).toBe("rep-001");
    expect(res.status).toBe("completed");
    expect(res.formats).toContain("pdf");
  });

  it("exportSnapshotDirect posts snapshot payload and returns response", async () => {
    const mockSnapshot = {
      schema_version: "1.0.0",
      report_id: "rep-snap-001",
      workspace_id: "ws-default",
      result_id: "res-001",
      title: "Snapshot Direct",
      analysis_timestamp: "2026-09-20T12:00:00Z",
      created_at: "2026-09-20T12:00:00Z",
      aoi: {
        type: "Polygon" as const,
        coordinates: [
          [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
            [0, 0],
          ],
        ],
        crs: "EPSG:4326",
        area_km2: 1.0,
      },
      scenes: [],
      figures: [],
      claims: [],
      observations: [],
      warnings: [],
      limitations: [],
      methodology_notes: [],
      included_sections: ["summary" as const],
      quantitative_summary: {},
      data_origin: "real" as const,
      is_mock_data: false,
      is_fallback_data: false,
    };

    const mockResponse = {
      report_id: "rep-snap-001",
      workspace_id: "ws-default",
      result_id: "res-001",
      title: "Snapshot Direct",
      status: "completed",
      formats: ["pdf", "json"],
      format_statuses: {},
      download_urls: {},
      created_at: "2026-09-20T12:00:00Z",
      is_mock_data: false,
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const res = await exportSnapshotDirect(mockSnapshot);
    expect(res.report_id).toBe("rep-snap-001");
  });

  it("getReportStatus handles 404 cleanly with ReportClientError", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { message: "Report not found", code: "not_found" } }),
    });

    await expect(getReportStatus("rep-nonexistent")).rejects.toThrow(ReportClientError);
  });

  it("getReportDownloadUrl formats URL correctly", () => {
    const url = getReportDownloadUrl("rep-abc-123", "pdf");
    expect(url).toContain("/reports/rep-abc-123/download/pdf");
  });
});
