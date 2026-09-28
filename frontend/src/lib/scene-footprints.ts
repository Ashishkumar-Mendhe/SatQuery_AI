import type { Feature, FeatureCollection, MultiPolygon, Polygon } from "geojson";

import type { CatalogueScene } from "@/lib/catalog-client";
import { type CatalogueSceneContext, catalogueSceneKey } from "@/lib/scene-selection";

export const SCENE_FOOTPRINT_SOURCE_ID = "satquery-catalogue-scenes";
export const SCENE_FOOTPRINT_FILL_LAYER_ID = "satquery-catalogue-scenes-fill";
export const SCENE_FOOTPRINT_LINE_LAYER_ID = "satquery-catalogue-scenes-line";

export interface SceneFootprintProperties {
  sceneKey: string;
  current: boolean;
}

export type SceneFootprintFeature = Feature<Polygon | MultiPolygon, SceneFootprintProperties>;
export type SceneFootprintCollection = FeatureCollection<
  Polygon | MultiPolygon,
  SceneFootprintProperties
>;

export function buildSceneFootprintCollection(
  context: CatalogueSceneContext | null,
  selectedScene: CatalogueScene | null,
): SceneFootprintCollection {
  const scenes = context?.scenes ?? [];
  const contextKeys = new Set(scenes.map(catalogueSceneKey));
  const sceneByKey = new Map(scenes.map((scene) => [catalogueSceneKey(scene), scene]));
  if (selectedScene) sceneByKey.set(catalogueSceneKey(selectedScene), selectedScene);

  return {
    type: "FeatureCollection",
    features: [...sceneByKey.values()].map((scene): SceneFootprintFeature => {
      const key = catalogueSceneKey(scene);
      return {
        type: "Feature",
        id: key,
        geometry: scene.footprint,
        properties: {
          sceneKey: key,
          current: context?.isCurrent === true && contextKeys.has(key),
        },
      };
    }),
  };
}
