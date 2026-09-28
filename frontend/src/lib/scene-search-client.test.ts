import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SceneSearchClientError, searchScenes } from "./scene-search-client";
import type { SceneSearchRequest } from "./scene-search-contracts";

describe("sceneSearchClient", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  const validRequest: SceneSearchRequest = {
    aoi: {
      type: "Polygon",
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
    },
    max_cloud_cover: 20,
    limit: 10,
    sort_order: "desc",
    collections: ["sentinel-2-c1-l2a"],
    sensor_types: ["multispectral"],
    required_bands: [],
    include_preview: true,
  };

  it("successfully searches and parses real response", async () => {
    const mockResponsePayload = {
      request_id: "search_req_test",
      scenes: [
        {
          id: "S2B_T43PGQ_20251223T051848_L2A",
          provider: "earth-search",
          collection: "sentinel-2-c1-l2a",
          acquisition_time: "2025-12-23T05:25:18.674Z",
          sensor_type: "multispectral",
          platform: "Sentinel-2B",
          cloud_cover: 4.3,
          bbox: [77.45, 12.85, 77.75, 13.15],
          thumbnail_url:
            "https://e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com/thumbnail.jpg",
          available_bands: ["B02", "B03", "B04", "B08"],
          resolution_meters: 10,
          quality_score: 0.95,
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
        completed_at: "2026-09-18T12:00:00.400Z",
        duration_milliseconds: 400,
        attempt_count: 1,
        fallback_used: false,
        cached: false,
        limitations: [],
      },
      warnings: [],
      data_origin: "real",
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "X-Request-ID": "test-id" }),
      json: async () => mockResponsePayload,
    } as Response);

    const result = await searchScenes(validRequest);
    expect(result.returned_count).toBe(1);
    expect(result.data_origin).toBe("real");
    expect(result.scenes[0].id).toBe("S2B_T43PGQ_20251223T051848_L2A");
  });

  it("handles structured provider error", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      headers: new Headers({ "X-Request-ID": "err-req" }),
      json: async () => ({
        error: {
          code: "PROVIDER_NOT_CONFIGURED",
          message: "Satellite provider credentials are not configured.",
          retryable: false,
        },
      }),
    } as Response);

    await expect(searchScenes(validRequest)).rejects.toThrowError(SceneSearchClientError);
  });

  it("handles network failure gracefully", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("Connection refused"));

    await expect(searchScenes(validRequest)).rejects.toThrowError(
      /Network error contacting satellite scenes search service/,
    );
  });
});
