import { describe, expect, it } from "vitest";

import type { CatalogueScene, CatalogueSearchRequest } from "@/lib/catalog-client";
import {
  catalogueQueryFingerprintFromRequest,
  createCatalogueSceneSelection,
} from "@/lib/scene-selection";
import {
  parseStoredSceneSelection,
  serializeStoredSceneSelection,
} from "@/lib/scene-selection-storage";

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
  cursor: "provider-page-must-not-persist",
  sort: "acquired_desc",
};

function scene(): CatalogueScene {
  return {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: "S2_SYNTHETIC_STORAGE",
    provider_asset_version: "v1",
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2 L2A" },
    acquisition: { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" },
    platform: "sentinel-2b",
    instruments: ["msi"],
    product_type: null,
    processing_level: "L2A",
    footprint: query.aoi,
    bbox: [77.5, 12.9, 77.7, 13.05],
    cloud_cover: { percent: 4.2, source_field: "eo:cloud_cover", semantics: "scene" },
    spatial_resolution: [{ value: 10, unit: "metre", axis: "nominal", source_field: "gsd" }],
    bands: [],
    polarizations: [],
    preview: {
      purpose: "thumbnail",
      access: "temporary",
      href: "https://example.test/preview.jpg?signature=must-not-persist",
      media_type: "image/jpeg",
      width: 512,
      height: 512,
      expires_at: "2025-06-01T07:00:00Z",
      attribution: "Synthetic preview",
    },
    license: {
      name: "Synthetic licence",
      url: "https://example.test/licence",
      permits_analytical_use: null,
      summary: "Synthetic test metadata only.",
    },
    asset_access: {
      state: "requires_authorization",
      method: "backend_mediated",
      reason: "Synthetic authorization requirement.",
    },
    provenance: {
      adapter: "synthetic-test-adapter",
      adapter_version: "1.0",
      retrieved_at: "2025-06-01T06:00:00Z",
      source_record_id: "provider-source-record",
      source_record_version: "source-v1",
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
  };
}

describe("catalogue scene selection storage", () => {
  it("round-trips identity, query, licence, access, and provenance without durable URLs or cursors", () => {
    const selection = createCatalogueSceneSelection(
      scene(),
      catalogueQueryFingerprintFromRequest(query),
      query,
    );
    const serialized = serializeStoredSceneSelection(selection, new Date("2025-06-01T06:15:00Z"));
    const restored = parseStoredSceneSelection(serialized);

    expect(serialized).not.toContain("signature=must-not-persist");
    expect(serialized).not.toContain("provider-page-must-not-persist");
    expect(restored.savedAt).toBe("2025-06-01T06:15:00.000Z");
    expect(restored.selection.identity).toEqual(selection.identity);
    expect(restored.selection.query.cursor).toBeNull();
    expect(restored.selection.scene.preview).toBeNull();
    expect(restored.selection.previewMetadata).toMatchObject({
      purpose: "thumbnail",
      media_type: "image/jpeg",
    });
    expect(restored.selection.scene.license?.name).toBe("Synthetic licence");
    expect(restored.selection.scene.asset_access.state).toBe("requires_authorization");
    expect(restored.selection.scene.provenance).toEqual(scene().provenance);
  });

  it("rejects corrupt, unsupported, and identity-mismatched drafts", () => {
    expect(() => parseStoredSceneSelection("not JSON")).toThrow(/corrupt/);
    expect(() => parseStoredSceneSelection('{"version":2}')).toThrow(/unsupported/);

    const raw = JSON.parse(
      serializeStoredSceneSelection(
        createCatalogueSceneSelection(scene(), catalogueQueryFingerprintFromRequest(query), query),
      ),
    );
    raw.identity.itemId = "different-item";
    expect(() => parseStoredSceneSelection(JSON.stringify(raw))).toThrow(/identity/);

    raw.identity.itemId = scene().provider_asset_id;
    raw.queryFingerprint = "{}";
    expect(() => parseStoredSceneSelection(JSON.stringify(raw))).toThrow(/fingerprint/);
  });
});
