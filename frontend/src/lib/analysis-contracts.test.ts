import { describe, expect, it } from "vitest";
import {
  analysisRequestSchema,
  analysisResponseSchema,
  aoiGeometrySchema,
  apiErrorSchema,
  cloudCoverFilterSchema,
  dateRangeSchema,
  evidenceItemSchema,
  findingSchema,
  overlayFeatureSchema,
} from "./analysis-contracts";

describe("analysis-contracts validation suite", () => {
  const validPolygonAoi = {
    type: "Polygon" as const,
    coordinates: [
      [
        [77.58, 12.96],
        [77.62, 12.96],
        [77.62, 13.01],
        [77.58, 13.01],
        [77.58, 12.96],
      ],
    ],
    bbox: [77.58, 12.96, 77.62, 13.01] as [number, number, number, number],
    crs: "EPSG:4326",
    area_km2: 21.45,
  };

  const validSatelliteScene = {
    id: "S2B_T43PGQ_20251223T051848_L2A",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-12-23T05:25:18.674Z",
    sensor_type: "multispectral" as const,
    platform: "Sentinel-2B",
    cloud_cover: 4.3,
    geometry: validPolygonAoi,
    bbox: [77.58, 12.96, 77.62, 13.01] as [number, number, number, number],
    thumbnail_url: "https://example.com/thumb.jpg",
    preview_url: "https://example.com/preview.jpg",
    available_bands: ["B02", "B03", "B04", "B08", "B11"],
    resolution_meters: 10.0,
    quality_score: 0.95,
    metadata: { sun_elevation: 45.2 },
  };

  const validConfidence = {
    overall: 0.87,
    data_quality: 1.0,
    temporal_quality: 0.9,
    spatial_quality: 0.85,
    model_confidence: 0.8,
    evidence_agreement: 0.85,
    factors: [
      {
        code: "DATA_QUALITY",
        label: "Level-2A Surface Reflectance",
        score: 1.0,
        weight: 0.35,
        explanation: "High quality bottom-of-atmosphere reflectance data.",
        evidence_ids: ["evd_01"],
      },
    ],
    methodology: "Multi-factor weighted geometric index assessment.",
    limitations: ["Cloud shadow may affect small portions of eastern sector."],
  };

  const validEvidence = {
    id: "evd_01",
    type: "spectral_measurement" as const,
    title: "Mean NDVI in AOI",
    description: "Calculated mean NDVI over active vegetation zones.",
    source_scene_ids: ["S2B_T43PGQ_20251223T051848_L2A"],
    geometry: validPolygonAoi,
    measurement: { ndvi_mean: 0.54, valid_pixels: 45000 },
    observed_at: "2025-12-23T05:25:18.674Z",
    confidence: 0.92,
    provenance: {
      computation: "numpy_band_math",
      algorithm_name: "NDVI_B08_B04",
      version: "1.0.0",
      processed_at: "2026-09-18T13:00:00Z",
      parameters: { scale: 0.0001 },
    },
  };

  const validFinding = {
    id: "fnd_01",
    title: "Healthy Vegetation Concentration",
    description: "Dense, healthy canopy detected across 65% of the AOI.",
    severity: "informational" as const,
    category: "vegetation",
    evidence_ids: ["evd_01"],
    confidence: 0.88,
    interpretation: "Vegetation index indicates robust post-monsoon foliage.",
    limitations: ["Sensor 10m ground resolution limits individual tree detection."],
    recommended_follow_up: ["Monitor again in late dry season (March)."],
  };

  it("validates correct AOI geometry and rejects unclosed polygons", () => {
    expect(aoiGeometrySchema.safeParse(validPolygonAoi).success).toBe(true);

    const unclosed = {
      ...validPolygonAoi,
      coordinates: [
        [
          [77.58, 12.96],
          [77.62, 12.96],
          [77.62, 13.01],
          [77.58, 13.01],
          [77.59, 12.99], // Not matching first
        ],
      ],
    };
    expect(aoiGeometrySchema.safeParse(unclosed).success).toBe(false);
  });

  it("validates chronological date range and rejects inverted dates", () => {
    expect(
      dateRangeSchema.safeParse({
        start_date: "2025-01-01",
        end_date: "2025-12-31",
      }).success,
    ).toBe(true);

    expect(
      dateRangeSchema.safeParse({
        start_date: "2025-12-31",
        end_date: "2025-01-01",
      }).success,
    ).toBe(false);
  });

  it("validates cloud cover preferences", () => {
    expect(
      cloudCoverFilterSchema.safeParse({
        maximum_percent: 30,
        preferred_maximum_percent: 10,
      }).success,
    ).toBe(true);

    expect(
      cloudCoverFilterSchema.safeParse({
        maximum_percent: 20,
        preferred_maximum_percent: 40,
      }).success,
    ).toBe(false);
  });

  it("validates analysis requests with mode-aware constraints", () => {
    const validReq = analysisRequestSchema.safeParse({
      question: "What is the vegetation health in this area?",
      mode: "visual_question_answering",
      aoi: validPolygonAoi,
    });
    expect(validReq.success).toBe(true);

    const blankReq = analysisRequestSchema.safeParse({
      question: "   ",
      mode: "visual_question_answering",
      aoi: validPolygonAoi,
    });
    expect(blankReq.success).toBe(false);

    // Change detection without scenes or date_range fails
    const invalidChangeReq = analysisRequestSchema.safeParse({
      question: "What changed between these scenes?",
      mode: "change_detection",
      aoi: validPolygonAoi,
    });
    expect(invalidChangeReq.success).toBe(false);

    // Change detection with identical before/after fails
    const identicalChangeReq = analysisRequestSchema.safeParse({
      question: "What changed between these scenes?",
      mode: "change_detection",
      aoi: validPolygonAoi,
      scene_selection: {
        before_scene_id: "scene_01",
        after_scene_id: "scene_01",
      },
    });
    expect(identicalChangeReq.success).toBe(false);

    // Valid change detection request succeeds
    const validChangeReq = analysisRequestSchema.safeParse({
      question: "What changed between these scenes?",
      mode: "change_detection",
      aoi: validPolygonAoi,
      scene_selection: {
        before_scene_id: "scene_01",
        after_scene_id: "scene_02",
      },
    });
    expect(validChangeReq.success).toBe(true);
  });

  it("validates overlay requirements for vector and raster layers", () => {
    const validVector = overlayFeatureSchema.safeParse({
      id: "ovl_01",
      type: "polygon",
      title: "Vegetation Mask",
      geometry: validPolygonAoi,
      style: { fill_color: "#10b981", fill_opacity: 0.6 },
    });
    expect(validVector.success).toBe(true);

    const invalidVector = overlayFeatureSchema.safeParse({
      id: "ovl_02",
      type: "polygon",
      title: "Missing Geometry Mask",
    });
    expect(invalidVector.success).toBe(false);

    const validRaster = overlayFeatureSchema.safeParse({
      id: "ovl_03",
      type: "raster",
      title: "NDVI Heatmap",
      raster_url: "/api/v1/imagery/tiles/tile_01/{z}/{x}/{y}.png",
      bounds: [77.58, 12.96, 77.62, 13.01],
    });
    expect(validRaster.success).toBe(true);
  });

  it("validates finding and evidence linkages", () => {
    expect(findingSchema.safeParse(validFinding).success).toBe(true);
    expect(evidenceItemSchema.safeParse(validEvidence).success).toBe(true);

    const findingNoEvidence = {
      ...validFinding,
      evidence_ids: [],
    };
    expect(findingSchema.safeParse(findingNoEvidence).success).toBe(false);
  });

  it("validates complete AnalysisResponse payload", () => {
    const fullResponse = {
      request_id: "req_123456",
      job_id: "job_987654",
      status: "completed" as const,
      answer:
        "Significant vegetation increase detected in the northern sector following monsoon rains.",
      answer_type: "text_and_evidence",
      findings: [validFinding],
      evidence: [validEvidence],
      spectral_result: {
        scene_id: "S2B_T43PGQ_20251223T051848_L2A",
        indices: [
          {
            index_name: "NDVI",
            mean: 0.54,
            minimum: -0.1,
            maximum: 0.82,
            standard_deviation: 0.15,
            valid_pixel_count: 45000,
            unit: "index_value",
            scene_id: "S2B_T43PGQ_20251223T051848_L2A",
          },
        ],
        summary: "Overall healthy vegetation with high NDVI values.",
        evidence_ids: ["evd_01"],
        confidence: 0.9,
        warnings: [],
      },
      change_result: null,
      overlays: [],
      confidence: validConfidence,
      warnings: [
        {
          code: "HIGH_CLOUD_COVER",
          severity: "info" as const,
          title: "Minor Cloud Cover",
          message: "Cloud cover is 4.3%, within safe limits.",
        },
      ],
      scenes: [validSatelliteScene],
      processing_metadata: {
        processing_started_at: "2026-09-18T13:00:00Z",
        processing_completed_at: "2026-09-18T13:00:05Z",
        duration_milliseconds: 5000,
        pipeline_version: "1.0.0",
        algorithms: ["NDVI_Processor", "Gemini_VLM"],
        ai_provider: "gemini",
        ai_model: "gemini-2.0-flash",
        is_mock_data: false,
      },
    };

    const parsed = analysisResponseSchema.safeParse(fullResponse);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.request_id).toBe("req_123456");
      expect(parsed.data.confidence.overall).toBe(0.87);
    }
  });

  it("validates APIError structures", () => {
    const err = apiErrorSchema.safeParse({
      code: "INVALID_AOI",
      message: "The AOI coordinates are out of bounds.",
      status: 422,
      request_id: "req_err_01",
      field_errors: [{ field: "aoi.coordinates", message: "Longitude out of range" }],
      retryable: false,
    });
    expect(err.success).toBe(true);
  });
});
