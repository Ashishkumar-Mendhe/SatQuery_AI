import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  calculateChangeDetection,
  ChangeClientError,
  getChangeOverlayUrl,
  getChangeResult,
  listChangeMethods,
} from "./change-client";

const mockDefinition = {
  method: "ndvi_difference",
  display_name: "NDVI Difference",
  formula: "NDVI_after - NDVI_before",
  input_type: "spectral_index",
  directionality: "bidirectional",
  expected_range: [-2.0, 2.0],
  default_threshold_config: {
    strategy: "fixed",
    positive_threshold: 0.15,
    negative_threshold: -0.15,
    std_multiplier: 1.5,
    percentile_cutoff: 95.0,
    min_cluster_size_pixels: 5,
    simplify_tolerance_meters: 5.0,
  },
  supported_sensors: ["Sentinel-2"],
  description: "Detects vegetation change.",
  limitations: "Sensitive to seasonality.",
  default_color_ramp: "RdYlGn",
  version: "1.0.0",
};

const mockResult = {
  result_id: "res-chg-101",
  pair_id: "pair-101",
  method: "ndvi_difference",
  definition: mockDefinition,
  before_scene_id: "S2A_before",
  after_scene_id: "S2A_after",
  before_asset_id: "ast-bef",
  after_asset_id: "ast-aft",
  difference_asset_id: "ast-diff",
  preview_asset_id: "ast-prev",
  classified_preview_asset_id: "ast-cls",
  metrics: {
    gain_area_km2: 0.2,
    loss_area_km2: 0.1,
    stable_area_km2: 0.7,
    net_change_area_km2: 0.1,
    shared_valid_area_km2: 1.0,
    pixel_counts: {
      total_aoi_pixels: 1000,
      shared_valid_pixels: 1000,
      gain_pixels: 200,
      loss_pixels: 100,
      stable_pixels: 700,
      uncertain_pixels: 0,
      gain_percent: 20.0,
      loss_percent: 10.0,
      stable_percent: 70.0,
      uncertain_percent: 0.0,
    },
    positive_threshold_applied: 0.15,
    negative_threshold_applied: -0.15,
    threshold_strategy: "fixed",
  },
  regions: [],
  overlay: null,
  classified_overlay: null,
  evidence: [],
  confidence_breakdown: {
    overall: 0.9,
    data_quality: 0.95,
    temporal_quality: 0.9,
    spatial_quality: 0.9,
    model_confidence: 0.85,
    evidence_agreement: 0.9,
    factors: [],
    methodology: "Multi-factor",
    limitations: [],
  },
  confidence: 0.9,
  warnings: [],
  provenance: {
    pipeline_version: "1.0",
    source_asset_ids: ["ast-bef", "ast-aft"],
    source_scene_ids: ["S2A_before", "S2A_after"],
    operations: ["spectral_differencing"],
    parameters: {},
    software: "SatQuery Change Engine v1.0",
    started_at: "2026-09-20T12:00:00Z",
    completed_at: "2026-09-20T12:00:01Z",
    duration_milliseconds: 1000,
    data_origin: "real",
  },
  data_origin: "real",
  created_at: "2026-09-20T12:00:01Z",
};

describe("change-client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("listChangeMethods fetches and validates methods response", async () => {
    const mockMethods = {
      methods: [mockDefinition],
      total_count: 1,
      version: "1.0.0",
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-req" }),
      json: async () => mockMethods,
    } as Response);

    const result = await listChangeMethods();
    expect(result.methods).toHaveLength(1);
    expect(result.methods[0].method).toBe("ndvi_difference");
  });

  it("calculateChangeDetection posts payload and returns validated result", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-calc" }),
      json: async () => mockResult,
    } as Response);

    const request = {
      prepared_pair_id: "pair-101",
      before_prepared_asset_id: "ast-bef",
      after_prepared_asset_id: "ast-aft",
      aoi: {
        type: "Polygon" as const,
        coordinates: [
          [
            [10.0, 50.0],
            [10.1, 50.0],
            [10.1, 50.1],
            [10.0, 50.1],
            [10.0, 50.0],
          ],
        ],
      },
      method: "ndvi_difference" as const,
    };

    const result = await calculateChangeDetection(request);
    expect(result.result_id).toBe("res-chg-101");
    expect(result.metrics.gain_area_km2).toBe(0.2);
  });

  it("getChangeResult retrieves result by id", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ "X-Request-ID": "test-get" }),
      json: async () => mockResult,
    } as Response);

    const result = await getChangeResult("res-chg-101");
    expect(result.result_id).toBe("res-chg-101");
  });

  it("throws ChangeClientError with server error details on HTTP failure", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: new Headers({ "X-Request-ID": "test-err" }),
      json: async () => ({
        error: {
          message: "Spatial grids do not match.",
          code: "GRID_MISMATCH",
        },
      }),
    } as unknown as Response);

    await expect(
      calculateChangeDetection({
        prepared_pair_id: "pair-101",
        before_prepared_asset_id: "ast-bef",
        after_prepared_asset_id: "ast-aft",
        aoi: {
          type: "Polygon" as const,
          coordinates: [
            [
              [10.0, 50.0],
              [10.1, 50.0],
              [10.1, 50.1],
              [10.0, 50.1],
              [10.0, 50.0],
            ],
          ],
        },
      }),
    ).rejects.toThrowError(ChangeClientError);
  });

  it("generates correct overlay URL", () => {
    const urlContinuous = getChangeOverlayUrl("res-123");
    expect(urlContinuous).toContain("/change/results/res-123/overlay");
    expect(urlContinuous).not.toContain("classified=true");

    const urlClassified = getChangeOverlayUrl("res-123", { classified: true });
    expect(urlClassified).toContain("/change/results/res-123/overlay?classified=true");
  });
});
