import type { SelectedCatalogueScene } from "@/lib/scene-selection";

export type ComparisonSlots = {
  sceneA: SelectedCatalogueScene;
  sceneB: SelectedCatalogueScene;
};

export function orderComparisonScenes(
  first: SelectedCatalogueScene,
  second: SelectedCatalogueScene,
): ComparisonSlots | null {
  if (first.key === second.key) return null;
  return Date.parse(first.scene.acquisition.start) < Date.parse(second.scene.acquisition.start)
    ? { sceneA: first, sceneB: second }
    : { sceneA: second, sceneB: first };
}

export function sharedSceneBounds(
  first: readonly [number, number, number, number],
  second: readonly [number, number, number, number],
): [number, number, number, number] | null {
  const bounds: [number, number, number, number] = [
    Math.max(first[0], second[0]),
    Math.max(first[1], second[1]),
    Math.min(first[2], second[2]),
    Math.min(first[3], second[3]),
  ];
  return bounds[0] < bounds[2] && bounds[1] < bounds[3] ? bounds : null;
}

export function comparisonDifferences({ sceneA, sceneB }: ComparisonSlots): string[] {
  const differences: string[] = [];
  const resolution = (scene: SelectedCatalogueScene) =>
    scene.scene.spatial_resolution.map((entry) => entry.value).join(", ") || "not reported";
  const cloud = (scene: SelectedCatalogueScene) =>
    scene.scene.cloud_cover ? `${scene.scene.cloud_cover.percent.toFixed(1)}%` : "not reported";
  const processing = (scene: SelectedCatalogueScene) =>
    scene.scene.processing_level ?? "not reported";
  if (resolution(sceneA) !== resolution(sceneB))
    differences.push(`Resolution differs: A ${resolution(sceneA)} m; B ${resolution(sceneB)} m.`);
  if (cloud(sceneA) !== cloud(sceneB))
    differences.push(`Scene cloud metadata differs: A ${cloud(sceneA)}; B ${cloud(sceneB)}.`);
  if (processing(sceneA) !== processing(sceneB))
    differences.push(`Processing level differs: A ${processing(sceneA)}; B ${processing(sceneB)}.`);
  return differences;
}
