import { z } from "zod";

export const ANALYSIS_SCHEMA_VERSION = "1.0" as const;
export const MAX_QUESTION_LENGTH = 1000;
export const MIN_QUESTION_LENGTH = 3;

// ---------------------------------------------------------------------------
// Primitive Validation Helpers
// ---------------------------------------------------------------------------

const utcTimestampSchema = z
  .string()
  .refine(
    (value) => value.endsWith("Z") && Number.isFinite(Date.parse(value)),
    "Expected an ISO 8601 UTC timestamp with a Z suffix.",
  );

const isoDateOrTimestampSchema = z
  .string()
  .refine(
    (value) => Number.isFinite(Date.parse(value.endsWith("Z") ? value : `${value}T00:00:00Z`)),
    "Expected an ISO 8601 date (YYYY-MM-DD) or UTC timestamp.",
  );

const coordinateSchema = z.number().finite();

export const boundingBoxSchema = z
  .tuple([coordinateSchema, coordinateSchema, coordinateSchema, coordinateSchema])
  .superRefine(([west, south, east, north], context) => {
    if (
      !(-180 <= west && west < east && east <= 180 && -90 <= south && south < north && north <= 90)
    ) {
      context.addIssue({
        code: "custom",
        message: "Bounds must be ordered west, south, east, north within WGS84.",
      });
    }
  });

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export const analysisModeSchema = z.enum([
  "visual_question_answering",
  "spatial_grounding",
  "change_detection",
  "spectral_analysis",
  "multimodal_analysis",
  "vegetation_health",
  "water_body_monitoring",
]);
export type AnalysisMode = z.infer<typeof analysisModeSchema>;

export const analysisJobStatusSchema = z.enum([
  "queued",
  "validating",
  "discovering_imagery",
  "downloading_imagery",
  "preprocessing",
  "analyzing",
  "generating_overlays",
  "generating_report",
  "completed",
  "partially_completed",
  "failed",
  "cancelled",
  "succeeded",
]);
export type AnalysisJobStatus = z.infer<typeof analysisJobStatusSchema>;

export const imageryProviderSchema = z.enum([
  "earth-search",
  "sentinel_hub",
  "copernicus_dataspace",
  "planetary_computer",
  "local_upload",
  "mock",
]);
export type ImageryProvider = z.infer<typeof imageryProviderSchema>;

export const sensorTypeSchema = z.enum(["optical", "sar", "multispectral", "unknown"]);
export type SensorType = z.infer<typeof sensorTypeSchema>;

export const geometryTypeSchema = z.enum(["Point", "Polygon", "MultiPolygon"]);
export type GeometryType = z.infer<typeof geometryTypeSchema>;

export const overlayTypeSchema = z.enum([
  "point",
  "polygon",
  "bounding_box",
  "heatmap",
  "raster",
  "mask",
]);
export type OverlayType = z.infer<typeof overlayTypeSchema>;

export const evidenceTypeSchema = z.enum([
  "source_scene",
  "spectral_measurement",
  "change_measurement",
  "detected_region",
  "model_observation",
  "user_input",
]);
export type EvidenceType = z.infer<typeof evidenceTypeSchema>;

export const warningSeveritySchema = z.enum(["info", "low", "medium", "high", "critical"]);
export type WarningSeverity = z.infer<typeof warningSeveritySchema>;

export const findingSeveritySchema = z.enum(["informational", "low", "medium", "high", "critical"]);
export type FindingSeverity = z.infer<typeof findingSeveritySchema>;

export const reportFormatSchema = z.enum(["pdf", "json", "markdown"]);
export type ReportFormat = z.infer<typeof reportFormatSchema>;

export const apiErrorCodeSchema = z.enum([
  "INVALID_AOI",
  "INVALID_DATE_RANGE",
  "AOI_TOO_LARGE",
  "NO_SCENES_FOUND",
  "HIGH_CLOUD_COVER",
  "LOW_IMAGE_QUALITY",
  "TEMPORAL_GAP_TOO_LARGE",
  "INSUFFICIENT_EVIDENCE",
  "LOW_CONFIDENCE",
  "PROVIDER_UNAVAILABLE",
  "ANALYSIS_FAILED",
  "UNSUPPORTED_ANALYSIS_MODE",
  "INTERNAL_ERROR",
  "RESOLUTION_LIMIT_WARNING",
  "VALIDATION_FAILED",
]);
export type APIErrorCode = z.infer<typeof apiErrorCodeSchema>;

export const warningCodeSchema = z.enum([
  "HIGH_CLOUD_COVER",
  "LOW_IMAGE_QUALITY",
  "TEMPORAL_GAP_TOO_LARGE",
  "RESOLUTION_LIMIT_WARNING",
  "INSUFFICIENT_EVIDENCE",
  "UNGEIGER_REFERENCED_IMAGE",
  "MOCK_DATA_USED",
  "PARTIAL_COVERAGE",
]);
export type WarningCode = z.infer<typeof warningCodeSchema>;

// ---------------------------------------------------------------------------
// Geometric & Spatial Schemas
// ---------------------------------------------------------------------------

export const aoiGeometrySchema = z
  .object({
    type: geometryTypeSchema,
    coordinates: z.unknown(),
    bbox: boundingBoxSchema.nullable().optional(),
    crs: z.string().default("EPSG:4326"),
    area_km2: z.number().nonnegative().nullable().optional(),
  })
  .strict()
  .superRefine((data, context) => {
    const coords = data.coordinates;
    if (data.type === "Point") {
      if (!Array.isArray(coords) || coords.length < 2) {
        context.addIssue({
          code: "custom",
          message: "Point coordinates must be [longitude, latitude]",
        });
        return;
      }
      const [lon, lat] = coords as [number, number];
      if (lon < -180 || lon > 180 || lat < -90 || lat > 90) {
        context.addIssue({ code: "custom", message: "Point coordinate out of WGS84 range" });
      }
    } else if (data.type === "Polygon") {
      if (!Array.isArray(coords) || coords.length === 0) {
        context.addIssue({ code: "custom", message: "Polygon must contain linear rings" });
        return;
      }
      const rings = coords as Array<Array<[number, number]>>;
      for (const ring of rings) {
        if (!Array.isArray(ring) || ring.length < 4) {
          context.addIssue({
            code: "custom",
            message: "Linear ring must contain at least 4 positions",
          });
          return;
        }
        for (const [lon, lat] of ring) {
          if (lon < -180 || lon > 180 || lat < -90 || lat > 90) {
            context.addIssue({
              code: "custom",
              message: `Coordinate [${lon}, ${lat}] out of WGS84 bounds`,
            });
          }
        }
        const first = ring[0];
        const last = ring[ring.length - 1];
        if (first[0] !== last[0] || first[1] !== last[1]) {
          context.addIssue({
            code: "custom",
            message: "Polygon linear ring must be closed (first == last)",
          });
        }
      }
    }
  });
export type AOIGeometry = z.infer<typeof aoiGeometrySchema>;

export const dateRangeSchema = z
  .object({
    start_date: isoDateOrTimestampSchema,
    end_date: isoDateOrTimestampSchema,
  })
  .strict()
  .superRefine((data, context) => {
    const start = Date.parse(
      data.start_date.endsWith("Z") ? data.start_date : `${data.start_date}T00:00:00Z`,
    );
    const end = Date.parse(
      data.end_date.endsWith("Z") ? data.end_date : `${data.end_date}T00:00:00Z`,
    );
    if (start > end) {
      context.addIssue({ code: "custom", message: "start_date must not be after end_date" });
    }
  });
export type DateRange = z.infer<typeof dateRangeSchema>;

export const cloudCoverFilterSchema = z
  .object({
    maximum_percent: z.number().min(0).max(100).default(100),
    preferred_maximum_percent: z.number().min(0).max(100).nullable().optional(),
  })
  .strict()
  .superRefine((data, context) => {
    if (
      data.preferred_maximum_percent !== undefined &&
      data.preferred_maximum_percent !== null &&
      data.preferred_maximum_percent > data.maximum_percent
    ) {
      context.addIssue({
        code: "custom",
        message: "preferred_maximum_percent must not exceed maximum_percent",
      });
    }
  });
export type CloudCoverFilter = z.infer<typeof cloudCoverFilterSchema>;

// ---------------------------------------------------------------------------
// Satellite Scene & Selection
// ---------------------------------------------------------------------------

export const satelliteSceneSchema = z
  .object({
    id: z.string().min(1).max(512),
    provider: z.string(),
    collection: z.string(),
    acquisition_time: utcTimestampSchema,
    sensor_type: sensorTypeSchema.default("multispectral"),
    platform: z.string().max(120).nullable().optional(),
    cloud_cover: z.number().min(0).max(100).nullable().optional(),
    geometry: aoiGeometrySchema.nullable().optional(),
    bbox: boundingBoxSchema,
    thumbnail_url: z.string().nullable().optional(),
    preview_url: z.string().nullable().optional(),
    available_bands: z.array(z.string()).default([]),
    resolution_meters: z.number().positive().nullable().optional(),
    quality_score: z.number().min(0).max(1).nullable().optional(),
    metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type SatelliteScene = z.infer<typeof satelliteSceneSchema>;

export const sceneSelectionSchema = z
  .object({
    before_scene_id: z.string().min(1).max(512).nullable().optional(),
    after_scene_id: z.string().min(1).max(512).nullable().optional(),
    primary_scene_id: z.string().min(1).max(512).nullable().optional(),
    supporting_scene_ids: z.array(z.string()).default([]),
    selection_reason: z.string().max(500).nullable().optional(),
  })
  .strict();
export type SceneSelection = z.infer<typeof sceneSelectionSchema>;

export const analysisOptionsSchema = z
  .object({
    spectral_indices: z.array(z.string()).default(["NDVI", "NDWI"]),
    change_threshold: z.number().min(0).max(1).default(0.2),
    include_overlays: z.boolean().default(true),
    include_raw_measurements: z.boolean().default(true),
    generate_report: z.boolean().default(false),
    requested_report_format: reportFormatSchema.default("pdf"),
    maximum_cloud_cover: z.number().min(0).max(100).default(20),
    language: z.string().max(10).default("en"),
    output_resolution_meters: z.number().positive().nullable().optional(),
  })
  .strict();
export type AnalysisOptions = z.infer<typeof analysisOptionsSchema>;

export const defaultAnalysisOptions: AnalysisOptions = {
  spectral_indices: ["NDVI", "NDWI"],
  change_threshold: 0.2,
  include_overlays: true,
  include_raw_measurements: true,
  generate_report: false,
  requested_report_format: "pdf",
  maximum_cloud_cover: 20,
  language: "en",
};

export const clientContextSchema = z
  .object({
    locale: z.string().max(20).default("en-US").optional(),
    timezone: z.string().max(50).default("UTC").optional(),
    ui_version: z.string().max(50).default("0.1.0").optional(),
  })
  .strict();
export type ClientContext = z.infer<typeof clientContextSchema>;

// ---------------------------------------------------------------------------
// Analysis Request
// ---------------------------------------------------------------------------

export const analysisRequestSchema = z
  .object({
    request_id: z.string().max(120).nullable().optional(),
    question: z
      .string()
      .min(MIN_QUESTION_LENGTH)
      .max(MAX_QUESTION_LENGTH)
      .refine((val) => val.trim().length >= MIN_QUESTION_LENGTH, "Question must not be blank"),
    mode: analysisModeSchema,
    aoi: aoiGeometrySchema,
    date_range: dateRangeSchema.nullable().optional(),
    scene_selection: sceneSelectionSchema.nullable().optional(),
    options: analysisOptionsSchema.default(defaultAnalysisOptions),
    client_context: clientContextSchema.nullable().optional(),
  })
  .strict()
  .superRefine((data, context) => {
    if (data.mode === "change_detection") {
      if (!data.scene_selection && !data.date_range) {
        context.addIssue({
          code: "custom",
          message: "Change detection requires either scene_selection or date_range",
        });
      }
      if (data.scene_selection) {
        if (!data.scene_selection.before_scene_id || !data.scene_selection.after_scene_id) {
          context.addIssue({
            code: "custom",
            message:
              "Change detection with scene_selection requires both before_scene_id and after_scene_id",
          });
        }
        if (data.scene_selection.before_scene_id === data.scene_selection.after_scene_id) {
          context.addIssue({
            code: "custom",
            message: "before_scene_id and after_scene_id must be distinct",
          });
        }
      }
    }
  });
export type AnalysisRequest = z.infer<typeof analysisRequestSchema>;

// ---------------------------------------------------------------------------
// Error & Job Status
// ---------------------------------------------------------------------------

export const apiFieldErrorSchema = z
  .object({
    field: z.string(),
    message: z.string(),
    code: z.string().nullable().optional(),
  })
  .strict();
export type APIFieldError = z.infer<typeof apiFieldErrorSchema>;

export const apiErrorSchema = z
  .object({
    code: z.string(),
    message: z.string(),
    status: z.number().int(),
    request_id: z.string().nullable().optional(),
    field_errors: z.array(apiFieldErrorSchema).default([]),
    retryable: z.boolean().default(false),
    suggested_action: z.string().nullable().optional(),
    details: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type APIError = z.infer<typeof apiErrorSchema>;

export const analysisJobSchema = z
  .object({
    job_id: z.string().min(1).max(120),
    request_id: z.string().min(1).max(120),
    status: analysisJobStatusSchema,
    progress: z.number().min(0).max(1).default(0),
    current_stage: z.string().nullable().optional(),
    created_at: utcTimestampSchema,
    started_at: utcTimestampSchema.nullable().optional(),
    completed_at: utcTimestampSchema.nullable().optional(),
    estimated_completion_seconds: z.number().nonnegative().nullable().optional(),
    error: apiErrorSchema.nullable().optional(),
  })
  .strict();
export type AnalysisJob = z.infer<typeof analysisJobSchema>;

// ---------------------------------------------------------------------------
// Spectral & Change Results
// ---------------------------------------------------------------------------

export const spectralMeasurementSchema = z
  .object({
    index_name: z.string().min(1).max(50),
    value: z.number().nullable().optional(),
    minimum: z.number().nullable().optional(),
    maximum: z.number().nullable().optional(),
    mean: z.number().nullable().optional(),
    median: z.number().nullable().optional(),
    standard_deviation: z.number().nonnegative().nullable().optional(),
    valid_pixel_count: z.number().int().nonnegative().nullable().optional(),
    unit: z.string().default("index_value"),
    scene_id: z.string().min(1).max(512),
    geometry: aoiGeometrySchema.nullable().optional(),
    region_id: z.string().nullable().optional(),
    confidence: z.number().min(0).max(1).nullable().optional(),
  })
  .strict();
export type SpectralMeasurement = z.infer<typeof spectralMeasurementSchema>;

export const overlayStyleSchema = z
  .object({
    stroke_color: z.string().default("#ef4444"),
    stroke_width: z.number().nonnegative().default(2.0),
    fill_color: z.string().nullable().default("#ef4444"),
    fill_opacity: z.number().min(0).max(1).default(0.5),
    radius: z.number().nonnegative().nullable().optional(),
    icon: z.string().nullable().optional(),
    color_ramp: z.array(z.string()).nullable().optional(),
    min_value: z.number().nullable().optional(),
    max_value: z.number().nullable().optional(),
  })
  .strict();
export type OverlayStyle = z.infer<typeof overlayStyleSchema>;

export const defaultOverlayStyle: OverlayStyle = {
  stroke_color: "#ef4444",
  stroke_width: 2.0,
  fill_color: "#ef4444",
  fill_opacity: 0.5,
};

export const overlayFeatureSchema = z
  .object({
    id: z.string().min(1).max(120),
    type: overlayTypeSchema,
    title: z.string().min(1).max(120),
    description: z.string().nullable().optional(),
    geometry: aoiGeometrySchema.nullable().optional(),
    raster_url: z.string().nullable().optional(),
    mask_url: z.string().nullable().optional(),
    bounds: boundingBoxSchema.nullable().optional(),
    style: overlayStyleSchema.default(defaultOverlayStyle),
    visible_by_default: z.boolean().default(true),
    evidence_ids: z.array(z.string()).default([]),
    metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict()
  .superRefine((data, context) => {
    if (["point", "polygon", "bounding_box"].includes(data.type)) {
      if (!data.geometry) {
        context.addIssue({
          code: "custom",
          message: `Vector overlay '${data.type}' requires geometry`,
        });
      }
    } else if (["raster", "mask", "heatmap"].includes(data.type)) {
      if (!data.raster_url && !data.mask_url && !data.geometry) {
        context.addIssue({
          code: "custom",
          message: `Raster overlay '${data.type}' requires url or geometry`,
        });
      }
    }
  });
export type OverlayFeature = z.infer<typeof overlayFeatureSchema>;

export const analysisWarningSchema = z
  .object({
    code: z.string(),
    severity: warningSeveritySchema,
    title: z.string().min(1).max(120),
    message: z.string().min(5).max(500),
    affected_evidence_ids: z.array(z.string()).default([]),
    suggested_action: z.string().nullable().optional(),
    details: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type AnalysisWarning = z.infer<typeof analysisWarningSchema>;

export const spectralIndexResultSchema = z
  .object({
    scene_id: z.string().min(1).max(512),
    indices: z.array(spectralMeasurementSchema).default([]),
    summary: z.string(),
    evidence_ids: z.array(z.string()).min(1),
    overlays: z.array(overlayFeatureSchema).default([]),
    confidence: z.number().min(0).max(1),
    warnings: z.array(analysisWarningSchema).default([]),
  })
  .strict();
export type SpectralIndexResult = z.infer<typeof spectralIndexResultSchema>;

export const changeMetricsSchema = z
  .object({
    changed_area_square_km: z.number().nonnegative(),
    changed_area_percent: z.number().min(0).max(100),
    gained_area_square_km: z.number().nonnegative(),
    lost_area_square_km: z.number().nonnegative(),
    unchanged_area_square_km: z.number().nonnegative(),
    pixel_count: z.number().int().nonnegative().nullable().optional(),
    threshold_used: z.number().default(0.2),
  })
  .strict();
export type ChangeMetrics = z.infer<typeof changeMetricsSchema>;

export const changeDetectionResultSchema = z
  .object({
    before_scene_id: z.string().min(1).max(512),
    after_scene_id: z.string().min(1).max(512),
    metrics: changeMetricsSchema,
    detected_regions: z.array(aoiGeometrySchema).default([]),
    summary: z.string(),
    evidence_ids: z.array(z.string()).min(1),
    overlays: z.array(overlayFeatureSchema).default([]),
    confidence: z.number().min(0).max(1),
    warnings: z.array(analysisWarningSchema).default([]),
  })
  .strict();
export type ChangeDetectionResult = z.infer<typeof changeDetectionResultSchema>;

// ---------------------------------------------------------------------------
// Evidence & Findings
// ---------------------------------------------------------------------------

export const evidenceProvenanceSchema = z
  .object({
    computation: z.string(),
    algorithm_name: z.string().nullable().optional(),
    version: z.string().nullable().optional(),
    processed_at: utcTimestampSchema,
    parameters: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type EvidenceProvenance = z.infer<typeof evidenceProvenanceSchema>;

export const evidenceItemSchema = z
  .object({
    id: z.string().min(1).max(120),
    type: evidenceTypeSchema,
    title: z.string().min(1).max(120),
    description: z.string(),
    source_scene_ids: z.array(z.string()).min(1),
    geometry: aoiGeometrySchema.nullable().optional(),
    measurement: z.record(z.string(), z.unknown()).nullable().optional(),
    observed_at: utcTimestampSchema.nullable().optional(),
    confidence: z.number().min(0).max(1),
    provenance: evidenceProvenanceSchema,
    metadata: z.record(z.string(), z.unknown()).nullable().optional(),
  })
  .strict();
export type EvidenceItem = z.infer<typeof evidenceItemSchema>;

export const findingSchema = z
  .object({
    id: z.string().min(1).max(120),
    title: z.string().min(3).max(120),
    description: z.string(),
    severity: findingSeveritySchema.default("informational"),
    category: z.string().default("general"),
    evidence_ids: z.array(z.string()).min(1),
    geometry: aoiGeometrySchema.nullable().optional(),
    confidence: z.number().min(0).max(1),
    interpretation: z.string(),
    limitations: z.array(z.string()).nullable().optional(),
    recommended_follow_up: z.array(z.string()).nullable().optional(),
  })
  .strict();
export type Finding = z.infer<typeof findingSchema>;

// ---------------------------------------------------------------------------
// Confidence Breakdown
// ---------------------------------------------------------------------------

export const confidenceFactorSchema = z
  .object({
    code: z.string(),
    label: z.string(),
    score: z.number().min(0).max(1),
    weight: z.number().min(0).max(1),
    explanation: z.string(),
    evidence_ids: z.array(z.string()).default([]),
  })
  .strict();
export type ConfidenceFactor = z.infer<typeof confidenceFactorSchema>;

export const confidenceBreakdownSchema = z
  .object({
    overall: z.number().min(0).max(1),
    data_quality: z.number().min(0).max(1),
    temporal_quality: z.number().min(0).max(1),
    spatial_quality: z.number().min(0).max(1),
    model_confidence: z.number().min(0).max(1),
    evidence_agreement: z.number().min(0).max(1),
    factors: z.array(confidenceFactorSchema).default([]),
    methodology: z.string(),
    limitations: z.array(z.string()).default([]),
  })
  .strict();
export type ConfidenceBreakdown = z.infer<typeof confidenceBreakdownSchema>;

// ---------------------------------------------------------------------------
// Processing Metadata & Complete Analysis Response
// ---------------------------------------------------------------------------

export const processingMetadataSchema = z
  .object({
    processing_started_at: utcTimestampSchema,
    processing_completed_at: utcTimestampSchema,
    duration_milliseconds: z.number().int().nonnegative(),
    pipeline_version: z.string().default("1.0.0"),
    algorithms: z.array(z.string()).default([]),
    ai_provider: z.string().nullable().optional(),
    ai_model: z.string().nullable().optional(),
    is_mock_data: z.boolean().default(false),
  })
  .strict();
export type ProcessingMetadata = z.infer<typeof processingMetadataSchema>;

export const analysisResponseSchema = z
  .object({
    request_id: z.string().min(1).max(120),
    job_id: z.string().min(1).max(120),
    status: analysisJobStatusSchema.default("completed"),
    answer: z.string(),
    answer_type: z.string().default("text_and_evidence"),
    findings: z.array(findingSchema).default([]),
    evidence: z.array(evidenceItemSchema).default([]),
    spectral_result: spectralIndexResultSchema.nullable().optional(),
    change_result: changeDetectionResultSchema.nullable().optional(),
    overlays: z.array(overlayFeatureSchema).default([]),
    confidence: confidenceBreakdownSchema,
    warnings: z.array(analysisWarningSchema).default([]),
    scenes: z.array(satelliteSceneSchema).default([]),
    processing_metadata: processingMetadataSchema,
  })
  .strict();
export type AnalysisResponse = z.infer<typeof analysisResponseSchema>;
