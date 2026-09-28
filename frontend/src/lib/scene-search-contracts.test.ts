import { describe, expect, it } from "vitest";

import {
  type SceneSearchRequest,
  type SceneSearchResponse,
  sceneSearchRequestSchema,
  sceneSearchResponseSchema,
} from "./scene-search-contracts";

describe("sceneSearchContracts", () => {
  const validAoi = {
    type: "Polygon" as const,
    coordinates: [
      [
        [77.45, 12.85],
        [77.75, 12.85],
        [77.75, 13.15],
        [77.45, 13.15],
        [77.45, 12.85],
      ],
    ],
    crs: "EPSG:4326",
  };

  it("validates a minimal valid SceneSearchRequest", () => {
    const raw: SceneSearchRequest = {
      aoi: validAoi,
      max_cloud_cover: 20,
      limit: 50,
      sort_order: "desc",
      collections: [],
      sensor_types: [],
      required_bands: [],
      include_preview: true,
    };

    const parsed = sceneSearchRequestSchema.parse(raw);
    expect(parsed.aoi.type).toBe("Polygon");
    expect(parsed.limit).toBe(50);
    expect(parsed.sort_order).toBe("desc");
  });

  it("validates a full SceneSearchRequest with date range", () => {
    const raw = {
      aoi: validAoi,
      date_range: {
        start_date: "2025-01-01",
        end_date: "2025-12-31",
      },
      collections: ["sentinel-2-c1-l2a"],
      sensor_types: ["multispectral" as const],
      max_cloud_cover: 15.5,
      limit: 25,
      sort_order: "asc" as const,
      required_bands: ["B04", "B08"],
      include_preview: true,
      cursor: "token_abc123",
    };

    const parsed = sceneSearchRequestSchema.parse(raw);
    expect(parsed.date_range?.start_date).toBe("2025-01-01");
    expect(parsed.collections).toContain("sentinel-2-c1-l2a");
    expect(parsed.max_cloud_cover).toBe(15.5);
  });

  it("rejects invalid cloud cover range", () => {
    const invalid = {
      aoi: validAoi,
      max_cloud_cover: 150, // exceeds 100
    };

    expect(() => sceneSearchRequestSchema.parse(invalid)).toThrow();
  });

  it("validates a standard SceneSearchResponse with real scenes and execution metadata", () => {
    const sampleResponse: SceneSearchResponse = {
      request_id: "search_req_123",
      scenes: [
        {
          id: "S2B_T43PGQ_20251223T051848_L2A",
          provider: "earth-search",
          collection: "sentinel-2-c1-l2a",
          acquisition_time: "2025-12-23T05:25:18.674Z",
          sensor_type: "multispectral",
          platform: "Sentinel-2B",
          cloud_cover: 4.3,
          geometry: validAoi,
          bbox: [77.45, 12.85, 77.75, 13.15],
          thumbnail_url:
            "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/thumbnail.jpg",
          preview_url: null,
          available_bands: ["B02", "B03", "B04", "B08"],
          resolution_meters: 10,
          quality_score: 0.95,
          metadata: { processing_level: "Level-2A" },
        },
      ],
      total_matched: 1,
      returned_count: 1,
      next_cursor: null,
      provider_id: "earth-search",
      execution: {
        provider_id: "earth-search",
        provider_mode: "real",
        data_origin: "real",
        requested_at: "2026-09-18T12:00:00.000Z",
        completed_at: "2026-09-18T12:00:00.500Z",
        duration_milliseconds: 500,
        attempt_count: 1,
        fallback_used: false,
        cached: false,
        limitations: [],
      },
      warnings: [],
      data_origin: "real",
    };

    const parsed = sceneSearchResponseSchema.parse(sampleResponse);
    expect(parsed.returned_count).toBe(1);
    expect(parsed.data_origin).toBe("real");
    expect(parsed.scenes[0].id).toBe("S2B_T43PGQ_20251223T051848_L2A");
  });

  it("validates fallback SceneSearchResponse with fallback warning", () => {
    const fallbackResponse: SceneSearchResponse = {
      request_id: "search_req_fallback",
      scenes: [
        {
          id: "mock-scene-optical-01",
          provider: "mock",
          collection: "sentinel-2-c1-l2a",
          acquisition_time: "2026-05-12T05:22:01.000Z",
          sensor_type: "multispectral",
          platform: "Sentinel-2B",
          cloud_cover: 4.2,
          bbox: [77.45, 12.85, 77.75, 13.15],
          available_bands: ["B02", "B03", "B04", "B08"],
        },
      ],
      returned_count: 1,
      provider_id: "earth-search",
      execution: {
        provider_id: "earth-search",
        provider_mode: "real",
        data_origin: "fallback",
        requested_at: "2026-09-18T12:00:00.000Z",
        attempt_count: 2,
        fallback_used: true,
        fallback_reason: "Primary STAC provider timed out.",
        cached: false,
        limitations: [],
      },
      warnings: [
        {
          code: "MOCK_DATA_USED",
          severity: "medium",
          title: "Mock Fallback Data Used",
          message: "Satellite search fell back to mock fixtures.",
          affected_evidence_ids: [],
        },
      ],
      data_origin: "fallback",
    };

    const parsed = sceneSearchResponseSchema.parse(fallbackResponse);
    expect(parsed.data_origin).toBe("fallback");
    expect(parsed.execution.fallback_used).toBe(true);
    expect(parsed.warnings[0].code).toBe("MOCK_DATA_USED");
  });
});
