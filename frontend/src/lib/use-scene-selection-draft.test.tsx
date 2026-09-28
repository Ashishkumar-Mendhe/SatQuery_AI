import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  CatalogueClientError,
  type CatalogueScene,
  type CatalogueSearchRequest,
} from "./catalog-client";
import {
  catalogueQueryFingerprintFromRequest,
  createCatalogueSceneSelection,
} from "./scene-selection";
import {
  SCENE_SELECTION_STORAGE_KEY,
  serializeStoredSceneSelection,
} from "./scene-selection-storage";
import {
  type SceneSelectionDraftClient,
  useSceneSelectionDraft,
} from "./use-scene-selection-draft";

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
  cloud_cover: null,
  limit: 6,
  cursor: null,
  sort: "acquired_desc",
};

function scene(retrievedAt = "2025-06-01T06:00:00Z"): CatalogueScene {
  return {
    provider: { id: "earth-search", name: "Earth Search" },
    provider_asset_id: "S2_SYNTHETIC_RESTORE",
    provider_asset_version: null,
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2 L2A" },
    acquisition: { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" },
    platform: "sentinel-2b",
    instruments: ["msi"],
    product_type: null,
    processing_level: "L2A",
    footprint: query.aoi,
    bbox: [77.5, 12.9, 77.7, 13.05],
    cloud_cover: null,
    spatial_resolution: [],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "provider_accessible", method: "provider_reference", reason: null },
    provenance: {
      adapter: "synthetic-test-adapter",
      adapter_version: "1.0",
      retrieved_at: retrievedAt,
      source_record_id: "S2_SYNTHETIC_RESTORE",
      source_record_version: null,
      metadata_digest_sha256: "b".repeat(64),
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

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("scene selection browser persistence", () => {
  it("restores stable identity and refreshes current metadata", async () => {
    const stored = createCatalogueSceneSelection(
      scene(),
      catalogueQueryFingerprintFromRequest(query),
      query,
    );
    localStorage.setItem(SCENE_SELECTION_STORAGE_KEY, serializeStoredSceneSelection(stored));
    const refreshed = { ...scene("2025-06-02T06:00:00Z"), platform: "sentinel-2c" };
    const client: SceneSelectionDraftClient = { getItem: vi.fn().mockResolvedValue(refreshed) };

    const { result } = renderHook(() => useSceneSelectionDraft(client));
    await waitFor(() => expect(result.current.persistenceState).toBe("restored"));

    expect(client.getItem).toHaveBeenCalledWith(
      "earth-search",
      "sentinel-2-c1-l2a",
      "S2_SYNTHETIC_RESTORE",
      expect.any(AbortSignal),
    );
    expect(result.current.selectedScene?.scene.platform).toBe("sentinel-2c");
    expect(result.current.selectedScene?.scene.provenance.retrieved_at).toBe(
      "2025-06-02T06:00:00Z",
    );
    expect(result.current.persistenceMessage).toMatch(/Saved in this browser/);
  });

  it("retains preserved provenance when the provider item is no longer available", async () => {
    const stored = createCatalogueSceneSelection(
      scene(),
      catalogueQueryFingerprintFromRequest(query),
      query,
    );
    localStorage.setItem(SCENE_SELECTION_STORAGE_KEY, serializeStoredSceneSelection(stored));
    const client: SceneSelectionDraftClient = {
      getItem: vi
        .fn()
        .mockRejectedValue(
          new CatalogueClientError("not_found", "The catalogue item was not found.", "missing-1"),
        ),
    };

    const { result } = renderHook(() => useSceneSelectionDraft(client));
    await waitFor(() => expect(result.current.persistenceState).toBe("stale"));

    expect(result.current.selectedScene?.identity.itemId).toBe("S2_SYNTHETIC_RESTORE");
    expect(result.current.selectedScene?.scene.provenance.source_record_id).toBe(
      "S2_SYNTHETIC_RESTORE",
    );
    expect(result.current.persistenceMessage).toMatch(/no longer available/);
  });

  it("discards corrupt storage without creating a selection", () => {
    localStorage.setItem(SCENE_SELECTION_STORAGE_KEY, "corrupt JSON");
    const client: SceneSelectionDraftClient = { getItem: vi.fn() };

    const { result } = renderHook(() => useSceneSelectionDraft(client));

    expect(result.current.selectedScene).toBeNull();
    expect(result.current.persistenceState).toBe("unavailable");
    expect(result.current.persistenceMessage).toMatch(/corrupt/);
    expect(localStorage.getItem(SCENE_SELECTION_STORAGE_KEY)).toBeNull();
    expect(client.getItem).not.toHaveBeenCalled();
  });

  it("keeps a new selection usable when browser storage denies the save", () => {
    const client: SceneSelectionDraftClient = { getItem: vi.fn() };
    const { result } = renderHook(() => useSceneSelectionDraft(client));
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Synthetic quota failure", "QuotaExceededError");
    });
    const selection = createCatalogueSceneSelection(
      scene(),
      catalogueQueryFingerprintFromRequest(query),
      query,
    );

    act(() => result.current.selectScene(selection));

    expect(result.current.selectedScene?.key).toBe(selection.key);
    expect(result.current.persistenceState).toBe("unavailable");
    expect(result.current.persistenceMessage).toMatch(/remains usable in this tab/);
  });
});
