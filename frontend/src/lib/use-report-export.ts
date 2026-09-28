"use client";

import { useCallback, useState } from "react";
import type {
  AOIGeometry,
  DateRange,
  ReportFormat,
  SatelliteScene,
  SensorType,
} from "./analysis-contracts";
import type { ChangeDetectionResult } from "./change-contracts";
import type { QueryAnswer } from "./query-contracts";
import {
  downloadReportFile,
  exportSnapshotDirect,
  ReportClientError,
  requestReportGeneration,
} from "./report-client";
import {
  REPORT_SCHEMA_VERSION,
  type ReportResponse,
  type ReportSection,
  type ReportSnapshot,
} from "./report-contracts";
import type { VisualQueryResponse } from "./visual-contracts";

export interface ExportReportContext {
  resultId?: string | null;
  workspaceId?: string;
  title?: string;
  query?: string | null;
  aoi?: AOIGeometry | null;
  dateRange?: DateRange | null;
  scenes?: unknown[];
  selectedScene?: unknown;
  answer?: QueryAnswer | null;
  visualResponse?: VisualQueryResponse | null;
  changeResult?: ChangeDetectionResult | null;
  snapshot?: ReportSnapshot | null;
}

const DEFAULT_SECTIONS: ReportSection[] = [
  "summary",
  "scenes",
  "quantitative_findings",
  "visual_evidence",
  "ai_interpretation",
  "confidence_limitations",
  "provenance_methods",
];

export function normalizeToSatelliteScene(scene: unknown): SatelliteScene {
  if (!scene || typeof scene !== "object") {
    return {
      id: "scene-1",
      provider: "earth-search",
      collection: "sentinel-2-c1-l2a",
      acquisition_time: new Date().toISOString(),
      sensor_type: "multispectral",
      bbox: [0, 0, 0, 0],
      available_bands: [],
    };
  }
  const s = scene as Record<string, unknown>;
  if (
    typeof s.provider === "string" &&
    typeof s.collection === "string" &&
    typeof s.id === "string"
  ) {
    return scene as SatelliteScene;
  }
  const id = String(s.id || s.provider_asset_id || s.scene_id || "scene-1");
  const provider =
    typeof s.provider === "string"
      ? s.provider
      : ((s.provider as Record<string, unknown> | undefined)?.id as string) || "earth-search";
  const collection =
    typeof s.collection === "string"
      ? s.collection
      : ((s.collection as Record<string, unknown> | undefined)?.id as string) ||
        "sentinel-2-c1-l2a";
  const acquisition_time =
    (s.acquisition_time as string) ||
    ((s.acquisition as Record<string, unknown> | undefined)?.timestamp as string) ||
    new Date().toISOString();
  const cloud_cover =
    typeof s.cloud_cover === "number"
      ? s.cloud_cover
      : (((s.cloud_cover as Record<string, unknown> | undefined)?.value_percent as number) ?? null);
  const bbox = (s.bbox as [number, number, number, number]) || [0, 0, 0, 0];
  const geometry: AOIGeometry | undefined =
    (s.geometry as AOIGeometry | undefined) ||
    (s.footprint
      ? {
          type: "Polygon",
          coordinates: (s.footprint as { coordinates: number[][][] }).coordinates,
          crs: "EPSG:4326",
        }
      : undefined);
  const available_bands =
    (s.available_bands as string[]) ||
    (s.bands ? Object.keys(s.bands as Record<string, unknown>) : []);
  const platform =
    (s.platform as string) ||
    ((s.sensor as Record<string, unknown> | undefined)?.platform as string) ||
    undefined;
  const sensor_type = (s.sensor_type as SensorType) || "multispectral";
  const thumbnail_url = (s.thumbnail_url as string) || (s.preview_url as string) || undefined;
  const resolution_meters =
    (s.resolution_meters as number) ||
    ((s.sensor as Record<string, unknown> | undefined)?.resolution_meters as number) ||
    undefined;

  return {
    id,
    provider,
    collection,
    acquisition_time,
    sensor_type,
    platform,
    cloud_cover,
    geometry,
    bbox,
    thumbnail_url,
    available_bands,
    resolution_meters,
  };
}

export function buildClientReportSnapshot(
  context: ExportReportContext,
  title: string,
  includedSections: ReportSection[],
): ReportSnapshot {
  const now = new Date().toISOString();
  const reportId = `rep-${Math.random().toString(36).slice(2, 10)}`;
  const isMock = Boolean(
    context.snapshot?.is_mock_data ||
      context.answer?.data_origin === "mock" ||
      context.visualResponse?.data_origin === "mock" ||
      context.changeResult?.data_origin === "mock",
  );

  const rawScenes = context.scenes ?? (context.selectedScene ? [context.selectedScene] : []);
  const normalizedScenes = rawScenes.map(normalizeToSatelliteScene);

  return {
    schema_version: REPORT_SCHEMA_VERSION,
    report_id: reportId,
    workspace_id: context.workspaceId ?? "ws-default",
    result_id: context.resultId ?? reportId,
    title: title.trim() || "SatQuery Geospatial Analysis Dossier",
    analysis_timestamp: now,
    created_at: now,
    query: context.query ?? null,
    aoi: context.aoi ?? {
      type: "Polygon",
      coordinates: [
        [
          [77.5, 12.9],
          [77.7, 12.9],
          [77.7, 13.1],
          [77.5, 13.1],
          [77.5, 12.9],
        ],
      ],
      crs: "EPSG:4326",
    },
    requested_date_range: context.dateRange ?? null,
    scenes: normalizedScenes,
    answer: context.answer ?? null,
    visual_response: context.visualResponse ?? null,
    change_result: context.changeResult ?? null,
    spectral_result: null,
    fusion_result: null,
    figures: [],
    claims: context.answer?.claims ?? [],
    observations: context.visualResponse?.observations ?? [],
    confidence_breakdown: null,
    warnings: [...(context.answer?.warnings ?? []), ...(context.changeResult?.warnings ?? [])],
    limitations: context.answer?.limitations ?? [],
    methodology_notes: [],
    included_sections: includedSections,
    quantitative_summary: {},
    data_origin: isMock ? "mock" : "real",
    is_mock_data: isMock,
    is_fallback_data: false,
    checksum_sha256: null,
  };
}

export function useReportExport() {
  const [isOpen, setIsOpen] = useState(false);
  const [title, setTitle] = useState("SatQuery Analysis Report");
  const [selectedFormats, setSelectedFormats] = useState<ReportFormat[]>(["pdf", "json"]);
  const [includedSections, setIncludedSections] = useState<ReportSection[]>(DEFAULT_SECTIONS);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState<string | null>(null);
  const [reportResponse, setReportResponse] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const openDialog = useCallback(() => {
    setIsOpen(true);
    setError(null);
  }, []);

  const closeDialog = useCallback(() => {
    setIsOpen(false);
  }, []);

  const toggleFormat = useCallback((format: ReportFormat) => {
    setSelectedFormats((prev) => {
      if (prev.includes(format)) {
        if (prev.length === 1) return prev; // Keep at least one format
        return prev.filter((f) => f !== format);
      }
      return [...prev, format];
    });
  }, []);

  const toggleSection = useCallback((section: ReportSection) => {
    setIncludedSections((prev) => {
      if (prev.includes(section)) {
        return prev.filter((s) => s !== section);
      }
      return [...prev, section];
    });
  }, []);

  const reset = useCallback(() => {
    setReportResponse(null);
    setError(null);
    setIsGenerating(false);
    setGenerationStage(null);
  }, []);

  const generateReport = useCallback(
    async (context: ExportReportContext) => {
      setIsGenerating(true);
      setError(null);
      setGenerationStage("Capturing immutable analysis snapshot...");

      try {
        let response: ReportResponse;

        if (context.snapshot) {
          // If caller has pre-constructed or cached snapshot, export directly
          setGenerationStage("Rendering PDF & serializing JSON...");
          response = await exportSnapshotDirect(context.snapshot);
        } else if (context.aoi) {
          // Assemble snapshot from active context and export directly
          setGenerationStage("Assembling snapshot & rendering report...");
          const clientSnapshot = buildClientReportSnapshot(context, title, includedSections);
          response = await exportSnapshotDirect(clientSnapshot);
        } else {
          // Send request to server to build snapshot and generate
          const targetResultId =
            context.resultId ||
            context.changeResult?.result_id ||
            context.answer?.answer_id ||
            context.visualResponse?.answer_id ||
            `res-${Date.now()}`;

          setGenerationStage("Resolving evidence & rendering report...");
          response = await requestReportGeneration({
            result_id: targetResultId,
            workspace_id: context.workspaceId ?? "ws-default",
            title: title.trim() || "SatQuery Analysis Report",
            formats: selectedFormats,
            included_sections: includedSections,
            locale: "en",
          });
        }

        setReportResponse(response);
        setGenerationStage(null);
      } catch (err: unknown) {
        setGenerationStage(null);
        if (err instanceof ReportClientError) {
          setError(err.message);
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("An unexpected error occurred while generating the report.");
        }
      } finally {
        setIsGenerating(false);
      }
    },
    [title, selectedFormats, includedSections],
  );

  const downloadFile = useCallback(
    async (format: ReportFormat) => {
      if (!reportResponse) return;
      try {
        const safeTitle = (reportResponse.title || "satquery_report")
          .toLowerCase()
          .replace(/[^a-z0-9_-]/g, "_")
          .slice(0, 50);
        await downloadReportFile(
          reportResponse.report_id,
          format as "pdf" | "json",
          `${safeTitle}_${reportResponse.report_id}.${format}`,
        );
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : `Failed to download ${format.toUpperCase()}`);
      }
    },
    [reportResponse],
  );

  return {
    isOpen,
    openDialog,
    closeDialog,
    title,
    setTitle,
    selectedFormats,
    setSelectedFormats,
    toggleFormat,
    includedSections,
    setIncludedSections,
    toggleSection,
    isGenerating,
    generationStage,
    reportResponse,
    error,
    generateReport,
    downloadFile,
    reset,
  };
}
