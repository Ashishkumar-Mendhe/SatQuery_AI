import type { CatalogueScene } from "@/lib/catalog-client";
import { catalogueSceneKey } from "@/lib/scene-selection";

export interface AcquisitionTimelineEntry {
  key: string;
  scene: CatalogueScene;
  timestamp: string;
  sameDateCount: number;
  sameDateIndex: number;
}

export function buildAcquisitionTimeline(scenes: CatalogueScene[]): AcquisitionTimelineEntry[] {
  const ordered = [...scenes].sort((left, right) => {
    const time = Date.parse(left.acquisition.start) - Date.parse(right.acquisition.start);
    return time || catalogueSceneKey(left).localeCompare(catalogueSceneKey(right));
  });
  const dateCounts = new Map<string, number>();
  for (const scene of ordered) {
    const date = scene.acquisition.start.slice(0, 10);
    dateCounts.set(date, (dateCounts.get(date) ?? 0) + 1);
  }
  const dateIndexes = new Map<string, number>();
  return ordered.map((scene) => {
    const date = scene.acquisition.start.slice(0, 10);
    const sameDateIndex = (dateIndexes.get(date) ?? 0) + 1;
    dateIndexes.set(date, sameDateIndex);
    return {
      key: catalogueSceneKey(scene),
      scene,
      timestamp: scene.acquisition.start,
      sameDateCount: dateCounts.get(date) ?? 1,
      sameDateIndex,
    };
  });
}
