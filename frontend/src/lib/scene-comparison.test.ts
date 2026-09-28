import { describe, expect, it } from "vitest";
import { orderComparisonScenes, sharedSceneBounds } from "@/lib/scene-comparison";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";

function selection(key: string, acquired: string): SelectedCatalogueScene {
  return {
    key,
    identity: { providerId: "earth-search", collectionId: "sentinel-2-c1-l2a", itemId: key },
    scene: { acquisition: { start: acquired } } as SelectedCatalogueScene["scene"],
    queryFingerprint: "query",
    query: {} as SelectedCatalogueScene["query"],
    previewMetadata: null,
  };
}

describe("scene comparison", () => {
  it("orders distinct acquisitions chronologically and rejects duplicate identity", () => {
    const earlier = selection("EARLIER", "2025-01-01T00:00:00Z");
    const later = selection("LATER", "2025-02-01T00:00:00Z");
    expect(orderComparisonScenes(later, earlier)).toEqual({ sceneA: earlier, sceneB: later });
    expect(orderComparisonScenes(earlier, earlier)).toBeNull();
  });

  it("returns only a positive shared viewable area", () => {
    expect(sharedSceneBounds([1, 1, 3, 3], [2, 0, 4, 2])).toEqual([2, 1, 3, 2]);
    expect(sharedSceneBounds([1, 1, 2, 2], [2, 2, 3, 3])).toBeNull();
  });
});
