import { describe, expect, it } from "vitest";

import {
  imageManifestSchema,
  visualObservationSchema,
  groundedVisualRegionSchema,
  visualQueryRequestSchema,
  visualQueryResponseSchema,
  visualCapabilitiesResponseSchema,
} from "./visual-contracts";

describe("visual-contracts", () => {
  it("parses a valid image manifest", () => {
    const raw = {
      manifest_id: "mf-1234",
      input_image_id: "img-single-5678",
      source_scene_id: "S2A_MSIL2A_20260920",
      source_asset_id: "ast-preview-1",
      role: "single",
      content_hash: "sha256:abcdef123456",
      submitted_width: 800,
      submitted_height: 600,
      content_rectangle: [0, 0, 800, 600],
      rendering_type: "true_color",
      crs: "EPSG:32644",
      affine_transform: [10, 0, 500000, 0, -10, 2400000],
      padding: [0, 0, 0, 0],
      data_origin: "real",
    };

    const parsed = imageManifestSchema.parse(raw);
    expect(parsed.manifest_id).toBe("mf-1234");
    expect(parsed.submitted_width).toBe(800);
    expect(parsed.role).toBe("single");
  });

  it("parses visual observations with canonical bounding boxes", () => {
    const raw = {
      observation_id: "obs-1",
      input_image_id: "img-single-1",
      label: "Water Body",
      description: "Dark spectral depression characteristic of deep open water",
      canonical_box: [0.1, 0.2, 0.4, 0.5],
      observation_source: "model_prediction",
      coordinate_status: "valid",
      semantic_status: "unverified",
      map_grounding_status: "available",
      model_confidence: 0.88,
      associated_evidence_ids: ["ev-water-1"],
    };

    const parsed = visualObservationSchema.parse(raw);
    expect(parsed.label).toBe("Water Body");
    expect(parsed.canonical_box).toEqual([0.1, 0.2, 0.4, 0.5]);
    expect(parsed.observation_source).toBe("model_prediction");
  });

  it("parses grounded visual region with polygon geometry", () => {
    const raw = {
      region_id: "greg-1",
      observation_id: "obs-1",
      manifest_id: "mf-1",
      canonical_box: [0.1, 0.2, 0.4, 0.5],
      pixel_box: [80, 120, 320, 300],
      wgs84_geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.1, 28.5],
            [77.2, 28.5],
            [77.2, 28.6],
            [77.1, 28.6],
            [77.1, 28.5],
          ],
        ],
      },
      clipping_status: "valid",
      matched_evidence_ids: ["ev-chg-1"],
      overlap_area_km2: 1.45,
    };

    const parsed = groundedVisualRegionSchema.parse(raw);
    expect(parsed.region_id).toBe("greg-1");
    expect(parsed.overlap_area_km2).toBe(1.45);
    expect(parsed.matched_evidence_ids).toContain("ev-chg-1");
  });

  it("parses visual query request and response envelope", () => {
    const req = {
      question: "Highlight the large water body in this image",
      context_snapshot: {
        snapshot_id: "snap-1",
        fingerprint: "fp-abc",
        scene_ids: ["S2A_20260920"],
      },
      selected_image_asset_ids: ["ast-1"],
      operation: "locate",
    };

    const parsedReq = visualQueryRequestSchema.parse(req);
    expect(parsedReq.operation).toBe("locate");
    expect(parsedReq.selected_image_asset_ids).toEqual(["ast-1"]);

    const resp = {
      answer_id: "vans-1",
      request_id: "vreq-1",
      context_fingerprint: "fp-abc",
      answer: "A prominent water body is visible in the northwest quadrant.",
      observations: [
        {
          observation_id: "obs-1",
          input_image_id: "img-1",
          label: "Water Body",
          description: "Clear low-albedo surface",
          canonical_box: [0.1, 0.1, 0.3, 0.3],
        },
      ],
      manifests: [],
      grounded_regions: [],
      evidence_references: [],
      generation_mode: "llm_explanation",
      data_origin: "real",
      warnings: [],
      limitations: ["Model prediction only"],
      created_at: new Date().toISOString(),
    };

    const parsedResp = visualQueryResponseSchema.parse(resp);
    expect(parsedResp.answer_id).toBe("vans-1");
    expect(parsedResp.observations.length).toBe(1);
  });

  it("parses visual capabilities", () => {
    const cap = {
      supported_operations: ["describe", "locate", "compare"],
      supports_bounding_boxes: true,
      supports_temporal_comparison: true,
      max_images_per_query: 2,
      example_questions: ["Highlight the water body"],
    };

    const parsed = visualCapabilitiesResponseSchema.parse(cap);
    expect(parsed.supports_bounding_boxes).toBe(true);
    expect(parsed.max_images_per_query).toBe(2);
  });
});
