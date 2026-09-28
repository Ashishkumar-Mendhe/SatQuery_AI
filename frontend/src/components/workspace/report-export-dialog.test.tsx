import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReportFormat } from "@/lib/analysis-contracts";
import type { ReportSection } from "@/lib/report-contracts";
import type { useReportExport } from "@/lib/use-report-export";
import { ReportExportDialog } from "./report-export-dialog";

describe("ReportExportDialog", () => {
  const baseExportState: ReturnType<typeof useReportExport> = {
    isOpen: true,
    openDialog: vi.fn(),
    closeDialog: vi.fn(),
    title: "SatQuery Analysis Dossier",
    setTitle: vi.fn(),
    selectedFormats: ["pdf", "json"] as ReportFormat[],
    setSelectedFormats: vi.fn(),
    toggleFormat: vi.fn(),
    includedSections: ["summary", "quantitative_findings"] as ReportSection[],
    setIncludedSections: vi.fn(),
    toggleSection: vi.fn(),
    isGenerating: false,
    generationStage: null,
    reportResponse: null,
    error: null,
    generateReport: vi.fn(),
    downloadFile: vi.fn(),
    reset: vi.fn(),
  };

  const baseContext = {
    resultId: "res-test-001",
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
      crs: "EPSG:4326",
      area_km2: 2.0,
    },
    scenes: [
      {
        id: "S2A_20260101",
        provider: "earth-search",
        collection: "sentinel-2-c1-l2a",
        acquisition_time: "2026-01-01T05:20:00Z",
        sensor_type: "optical" as const,
        platform: "Sentinel-2A",
        cloud_cover: 2.5,
        resolution_meters: 10.0,
      },
    ],
  };

  it("renders configuration view when open", () => {
    render(<ReportExportDialog exportState={baseExportState} context={baseContext} />);

    expect(screen.getByRole("heading", { name: "Export Evidence Dossier" })).toBeInTheDocument();
    expect(screen.getByLabelText("Report Title")).toHaveValue("SatQuery Analysis Dossier");
    expect(screen.getByTestId("format-pdf-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("format-json-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("generate-report-submit")).toBeInTheDocument();
    expect(screen.getByText("2.00 km²")).toBeInTheDocument();
  });

  it("displays prominent synthetic banner when mock data is present", () => {
    const mockContext = {
      ...baseContext,
      snapshot: {
        schema_version: "1.0.0",
        report_id: "rep-mock-001",
        workspace_id: "ws-default",
        result_id: "res-test-001",
        title: "Mock Dossier",
        analysis_timestamp: "2026-09-20T12:00:00Z",
        created_at: "2026-09-20T12:00:00Z",
        aoi: baseContext.aoi,
        scenes: [],
        figures: [],
        claims: [],
        observations: [],
        warnings: [],
        limitations: [],
        methodology_notes: [],
        included_sections: ["summary" as const],
        quantitative_summary: {},
        data_origin: "mock" as const,
        is_mock_data: true,
        is_fallback_data: false,
      },
    };

    render(<ReportExportDialog exportState={baseExportState} context={mockContext} />);
    expect(screen.getByText(/Synthetic Demo Data/)).toBeInTheDocument();
  });

  it("triggers generateReport when submit button is clicked", () => {
    const generateReportMock = vi.fn();
    const exportState = {
      ...baseExportState,
      generateReport: generateReportMock,
    };

    render(<ReportExportDialog exportState={exportState} context={baseContext} />);
    fireEvent.click(screen.getByTestId("generate-report-submit"));

    expect(generateReportMock).toHaveBeenCalledWith(baseContext);
  });

  it("renders download buttons when report generation is completed", () => {
    const completedState: ReturnType<typeof useReportExport> = {
      ...baseExportState,
      reportResponse: {
        report_id: "rep-comp-001",
        workspace_id: "ws-default",
        result_id: "res-test-001",
        title: "SatQuery Analysis Dossier",
        status: "completed",
        formats: ["pdf", "json"] as ReportFormat[],
        format_statuses: {},
        download_urls: {},
        snapshot: {
          schema_version: "1.0.0",
          report_id: "rep-comp-001",
          workspace_id: "ws-default",
          result_id: "res-test-001",
          title: "SatQuery Analysis Dossier",
          analysis_timestamp: "2026-09-20T12:00:00Z",
          created_at: "2026-09-20T12:00:00Z",
          aoi: baseContext.aoi,
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
          checksum_sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        },
        created_at: "2026-09-20T12:00:00Z",
        is_mock_data: false,
      },
    };

    render(<ReportExportDialog exportState={completedState} context={baseContext} />);

    expect(screen.getByTestId("report-success-panel")).toBeInTheDocument();
    expect(screen.getByTestId("download-pdf-button")).toBeInTheDocument();
    expect(screen.getByTestId("download-json-button")).toBeInTheDocument();
    expect(
      screen.getByText("9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"),
    ).toBeInTheDocument();
  });
});
