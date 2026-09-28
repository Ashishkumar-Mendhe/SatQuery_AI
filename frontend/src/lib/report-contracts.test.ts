import { describe, expect, it } from "vitest";
import {
  REPORT_SCHEMA_VERSION,
  reportFigureSchema,
  reportGenerationRequestSchema,
  reportResponseSchema,
  reportSnapshotSchema,
} from "./report-contracts";

describe("report-contracts validation suite", () => {
  it("validates valid ReportGenerationRequest and ReportResponse payloads", () => {
    const validReq = {
      result_id: "res-test-001",
      workspace_id: "ws-test",
      title: "Comprehensive Land Analysis Report",
      format: "pdf" as const,
      formats: ["pdf" as const, "json" as const],
      included_sections: ["summary" as const, "scenes" as const, "quantitative_findings" as const],
      locale: "en",
    };
    expect(reportGenerationRequestSchema.safeParse(validReq).success).toBe(true);

    const validRes = {
      report_id: "rep-112233",
      workspace_id: "ws-test",
      result_id: "res-test-001",
      title: "Comprehensive Land Analysis Report",
      status: "completed" as const,
      formats: ["pdf" as const, "json" as const],
      format_statuses: {
        pdf: {
          format: "pdf" as const,
          status: "completed" as const,
          download_url: "/api/v1/reports/rep-112233/download/pdf",
          file_size_bytes: 1048576,
        },
      },
      download_urls: {
        pdf: "/api/v1/reports/rep-112233/download/pdf",
        json: "/api/v1/reports/rep-112233/download/json",
      },
      created_at: "2026-09-18T13:05:00Z",
      is_mock_data: false,
    };
    expect(reportResponseSchema.safeParse(validRes).success).toBe(true);
  });

  it("validates valid ReportFigure payload", () => {
    const validFigure = {
      figure_id: "fig-001",
      figure_type: "change_map" as const,
      title: "NDVI Difference Map",
      description: "Bi-temporal difference classified",
      role: "composite" as const,
      caption: "Gain in green, loss in magenta",
      legend_labels: ["Gain", "Loss", "Stable"],
      orientation_label: "North Up (WGS84 / EPSG:4326)",
      is_mock_data: false,
    };
    expect(reportFigureSchema.safeParse(validFigure).success).toBe(true);
  });

  it("validates comprehensive ReportSnapshot with mathematical accounting", () => {
    const validSnapshot = {
      schema_version: REPORT_SCHEMA_VERSION,
      report_id: "rep-snap-001",
      workspace_id: "ws-test",
      result_id: "res-test-001",
      title: "Immutable Dossier Snapshot",
      analysis_timestamp: "2026-09-18T13:00:00Z",
      created_at: "2026-09-18T13:05:00Z",
      aoi: {
        type: "Polygon" as const,
        coordinates: [
          [
            [77.58, 12.96],
            [77.6, 12.96],
            [77.6, 12.98],
            [77.58, 12.98],
            [77.58, 12.96],
          ],
        ],
        area_km2: 2.0,
      },
      scenes: [],
      figures: [],
      claims: [],
      observations: [],
      warnings: [],
      limitations: [],
      methodology_notes: [],
      included_sections: ["summary" as const, "quantitative_findings" as const],
      quantitative_summary: {
        aoi_total_area_km2: 2.0,
        valid_comparison_area_km2: 1.0,
        gain_area_km2: 0.2,
        loss_area_km2: 0.1,
        stable_area_km2: 0.65,
        uncertain_area_km2: 0.05,
      },
      data_origin: "real" as const,
      is_mock_data: false,
      is_fallback_data: false,
      checksum_sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    };
    expect(reportSnapshotSchema.safeParse(validSnapshot).success).toBe(true);
  });
});
