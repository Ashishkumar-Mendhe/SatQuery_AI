import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  CatalogueClientError,
  type CatalogueSearchRequest,
  getCatalogueItem,
  listCatalogueCollections,
  searchCatalogue,
} from "./catalog-client";

const query: CatalogueSearchRequest = {
  schema_version: "1.0",
  provider: "earth-search",
  aoi: {
    type: "Polygon",
    coordinates: [
      [
        [77.5, 12.9],
        [77.7, 12.9],
        [77.7, 13.05],
        [77.5, 12.9],
      ],
    ],
  },
  acquisition: { start: "2025-01-01T00:00:00Z", end: "2025-12-31T23:59:59Z" },
  collections: ["sentinel-2-c1-l2a"],
  cloud_cover: { max_percent: 20, source: "provider_reported", include_unknown: false },
  limit: 6,
  cursor: null,
  sort: "acquired_desc",
};

function collectionResponse() {
  return {
    schema_version: "1.0",
    provider: { id: "earth-search", name: "Earth Search by Element 84" },
    items: [
      {
        id: "sentinel-2-c1-l2a",
        title: "Sentinel-2 Collection 1 Level-2A",
        description: null,
        license_name: "proprietary",
        license_url: null,
        temporal_start: "2015-06-27T10:25:31Z",
        temporal_end: null,
        platforms: ["sentinel-2a", "sentinel-2b"],
        instruments: ["msi"],
        spatial_resolutions_metres: [10, 20, 60],
      },
    ],
    returned_count: 1,
  };
}

function searchResponse() {
  return {
    schema_version: "1.0",
    search_id: "11111111-1111-4111-8111-111111111111",
    status: "succeeded",
    query,
    provider: { id: "earth-search", name: "Earth Search by Element 84" },
    items: [
      {
        provider: { id: "earth-search", name: "Earth Search by Element 84" },
        provider_asset_id: "S2_SYNTHETIC_FOR_CLIENT_TEST",
        provider_asset_version: null,
        collection: { id: "sentinel-2-c1-l2a", title: null },
        acquisition: {
          start: "2025-06-01T05:30:00Z",
          end: "2025-06-01T05:30:00Z",
        },
        platform: null,
        instruments: [],
        product_type: null,
        processing_level: null,
        footprint: query.aoi,
        bbox: [77.5, 12.9, 77.7, 13.05],
        cloud_cover: null,
        spatial_resolution: [],
        bands: [],
        polarizations: [],
        preview: null,
        license: null,
        asset_access: { state: "metadata_only", method: "none", reason: null },
        provenance: {
          adapter: "synthetic-test-adapter",
          adapter_version: "1.0",
          retrieved_at: "2025-06-01T06:00:00Z",
          source_record_id: "S2_SYNTHETIC_FOR_CLIENT_TEST",
          source_record_version: null,
          metadata_digest_sha256: "a".repeat(64),
          fields: [
            {
              normalized_field: "provider_asset_id",
              source: "provider_record",
              source_field: "id",
              method: null,
            },
          ],
        },
        unavailable_fields: [],
      },
    ],
    returned_count: 1,
    next_cursor: "opaque-page-2",
    searched_at: "2025-06-01T06:00:00Z",
    attributions: ["Synthetic client-test attribution"],
    warnings: [],
  };
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("catalogue API client", () => {
  it("validates collection and scene responses at the API boundary", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(collectionResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "collections-1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(searchResponse()), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "search-1" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(searchResponse().items[0]), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "item-1" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const collections = await listCatalogueCollections();
    const result = await searchCatalogue(query);
    const item = await getCatalogueItem(
      "earth-search",
      "sentinel-2-c1-l2a",
      "S2_SYNTHETIC_FOR_CLIENT_TEST",
    );

    expect(collections.items[0]?.instruments).toEqual(["msi"]);
    expect(result.items[0]?.provider_asset_version).toBeNull();
    expect(item.provenance.retrieved_at).toBe("2025-06-01T06:00:00Z");
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      "http://localhost:8000/api/v1/catalog/collections?provider=earth-search",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual(query);
    expect(String(fetchMock.mock.calls[2]?.[0])).toBe(
      "http://localhost:8000/api/v1/catalog/collections/sentinel-2-c1-l2a/items/S2_SYNTHETIC_FOR_CLIENT_TEST?provider=earth-search",
    );
  });

  it("rejects successful responses that do not match the runtime contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ schema_version: "1.0", items: "invalid" }), {
          status: 200,
          headers: { "Content-Type": "application/json", "X-Request-ID": "bad-shape" },
        }),
      ),
    );

    await expect(listCatalogueCollections()).rejects.toMatchObject({
      kind: "unexpected_response",
      requestId: "bad-shape",
    });
  });

  it("preserves provider error classification and request correlation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "RATE_LIMITED",
              message: "The catalogue provider rate limit was reached.",
              request_id: "rate-1",
              details: null,
              retryable: true,
            },
          }),
          { status: 429, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    const failure = await searchCatalogue(query).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(CatalogueClientError);
    expect(failure).toMatchObject({ kind: "rate_limit", requestId: "rate-1", retryable: true });
  });

  it("classifies an unavailable item during metadata refresh", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "CATALOGUE_ITEM_NOT_FOUND",
              message: "The catalogue item was not found.",
              request_id: "missing-1",
              details: null,
              retryable: false,
            },
          }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(
      getCatalogueItem("earth-search", "sentinel-2-c1-l2a", "missing"),
    ).rejects.toMatchObject({ kind: "not_found", requestId: "missing-1" });
  });
});
