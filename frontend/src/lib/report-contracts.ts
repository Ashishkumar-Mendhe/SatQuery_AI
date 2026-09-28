import { z } from "zod";
import {
  analysisWarningSchema,
  aoiGeometrySchema,
  confidenceBreakdownSchema,
  dateRangeSchema,
  reportFormatSchema,
  satelliteSceneSchema,
} from "./analysis-contracts";
import { changeDetectionResultSchema } from "./change-contracts";
import { fusionResultSchema } from "./fusion-contracts";
import { dataOriginSchema } from "./provider-contracts";
import { answerClaimSchema, queryAnswerSchema } from "./query-contracts";
import { visualObservationSchema, visualQueryResponseSchema } from "./visual-contracts";

export const REPORT_SCHEMA_VERSION = "1.0.0";

export const reportStatusSchema = z.enum([
  "pending",
  "generating",
  "completed",
  "partially_completed",
  "partial",
  "failed",
  "generated",
]);
export type ReportStatus = z.infer<typeof reportStatusSchema>;

export const reportSectionSchema = z.enum([
  "summary",
  "scenes",
  "quantitative_findings",
  "visual_evidence",
  "ai_interpretation",
  "confidence_limitations",
  "provenance_methods",
]);
export type ReportSection = z.infer<typeof reportSectionSchema>;

export const reportFigureTypeSchema = z.enum([
  "aoi_overview",
  "true_color_single",
  "true_color_before",
  "true_color_after",
  "spectral_index",
  "change_map",
  "fusion_overlay",
  "vqa_observation",
]);
export type ReportFigureType = z.infer<typeof reportFigureTypeSchema>;

export const reportFigureSchema = z
  .object({
    figure_id: z.string().min(1).max(120),
    figure_type: reportFigureTypeSchema,
    title: z.string().min(1).max(200),
    description: z.string().max(1000).default(""),
    source_asset_id: z.string().max(120).nullable().optional(),
    role: z.enum(["single", "before", "after", "composite"]).default("single"),
    caption: z.string().max(500).default(""),
    legend_labels: z.array(z.string()).default([]),
    scale_bar_label: z.string().max(100).nullable().optional(),
    orientation_label: z.string().max(50).default("North Up (WGS84 / EPSG:4326)"),
    resolution_meters: z.number().positive().nullable().optional(),
    is_mock_data: z.boolean().default(false),
    checksum_sha256: z.string().max(64).nullable().optional(),
  })
  .strict();
export type ReportFigure = z.infer<typeof reportFigureSchema>;

export const reportSnapshotSchema = z
  .object({
    schema_version: z.string().default(REPORT_SCHEMA_VERSION),
    report_id: z.string().min(1).max(120),
    workspace_id: z.string().max(120).default("ws-default"),
    result_id: z.string().min(1).max(120),
    title: z.string().min(1).max(200),
    analysis_timestamp: z.string(),
    created_at: z.string(),
    query: z.string().max(1000).nullable().optional(),
    aoi: aoiGeometrySchema,
    requested_date_range: dateRangeSchema.nullable().optional(),
    scenes: z.array(satelliteSceneSchema).default([]),
    answer: queryAnswerSchema.nullable().optional(),
    visual_response: visualQueryResponseSchema.nullable().optional(),
    change_result: changeDetectionResultSchema.nullable().optional(),
    spectral_result: z.record(z.string(), z.unknown()).nullable().optional(),
    fusion_result: fusionResultSchema.nullable().optional(),
    figures: z.array(reportFigureSchema).default([]),
    claims: z.array(answerClaimSchema).default([]),
    observations: z.array(visualObservationSchema).default([]),
    confidence_breakdown: confidenceBreakdownSchema.nullable().optional(),
    warnings: z.array(analysisWarningSchema).default([]),
    limitations: z.array(z.string()).default([]),
    methodology_notes: z.array(z.string()).default([]),
    included_sections: z
      .array(reportSectionSchema)
      .default([
        "summary",
        "scenes",
        "quantitative_findings",
        "visual_evidence",
        "ai_interpretation",
        "confidence_limitations",
        "provenance_methods",
      ]),
    quantitative_summary: z.record(z.string(), z.unknown()).default({}),
    data_origin: dataOriginSchema.default("real"),
    is_mock_data: z.boolean().default(false),
    is_fallback_data: z.boolean().default(false),
    checksum_sha256: z.string().max(64).nullable().optional(),
  })
  .strict();
export type ReportSnapshot = z.infer<typeof reportSnapshotSchema>;

export const reportFormatStatusSchema = z
  .object({
    format: reportFormatSchema,
    status: reportStatusSchema,
    download_url: z.string().max(512).nullable().optional(),
    file_size_bytes: z.number().int().nonnegative().nullable().optional(),
    error_message: z.string().nullable().optional(),
    error: z.record(z.string(), z.unknown()).nullable().optional(),
    generated_at: z.string().nullable().optional(),
    checksum_sha256: z.string().max(64).nullable().optional(),
  })
  .strict();
export type ReportFormatStatus = z.infer<typeof reportFormatStatusSchema>;

export const reportGenerationRequestSchema = z
  .object({
    result_id: z.string().min(1).max(120),
    workspace_id: z.string().max(120).default("ws-default").optional(),
    title: z.string().max(200).nullable().optional(),
    format: reportFormatSchema.default("pdf").optional(),
    formats: z.array(reportFormatSchema).default(["pdf", "json"]).optional(),
    included_sections: z
      .array(reportSectionSchema)
      .default([
        "summary",
        "scenes",
        "quantitative_findings",
        "visual_evidence",
        "ai_interpretation",
        "confidence_limitations",
        "provenance_methods",
      ])
      .optional(),
    locale: z.string().max(20).default("en").optional(),
    override_snapshot: reportSnapshotSchema.nullable().optional(),
  })
  .strict();
export type ReportGenerationRequest = z.infer<typeof reportGenerationRequestSchema>;
export type ReportGenerationRequestInput = z.input<typeof reportGenerationRequestSchema>;

// Backward compatibility alias
export const reportRequestSchema = reportGenerationRequestSchema;
export type ReportRequest = ReportGenerationRequest;

export const reportResponseSchema = z
  .object({
    report_id: z.string().min(1).max(120),
    analysis_job_id: z.string().max(120).nullable().optional(),
    workspace_id: z.string().max(120).default("ws-default").optional(),
    result_id: z.string().min(1).max(120).optional(),
    title: z.string().default("SatQuery Analysis Report"),
    status: reportStatusSchema.default("completed"),
    format: reportFormatSchema.default("pdf").optional(),
    formats: z
      .union([z.array(reportFormatSchema), z.record(z.string(), reportFormatStatusSchema)])
      .default(["pdf", "json"]),
    format_statuses: z.record(z.string(), reportFormatStatusSchema).default({}),
    download_url: z.string().max(512).nullable().optional(),
    download_urls: z.record(z.string(), z.string()).default({}),
    snapshot: reportSnapshotSchema.nullable().optional(),
    snapshot_checksum: z.string().max(64).nullable().optional(),
    created_at: z.string(),
    completed_at: z.string().nullable().optional(),
    expires_at: z.string().nullable().optional(),
    file_size_bytes: z.number().int().nonnegative().nullable().optional(),
    error_message: z.string().nullable().optional(),
    error: z.record(z.string(), z.unknown()).nullable().optional(),
    data_origin: dataOriginSchema.default("real").optional(),
    is_mock_data: z.boolean().default(false),
  })
  .strict();
export type ReportResponse = z.infer<typeof reportResponseSchema>;
