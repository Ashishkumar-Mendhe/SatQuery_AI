import type { GeoJSONSource, MapLayerMouseEvent, Map as MapLibreMap } from "maplibre-gl";
import {
  buildSceneFootprintCollection,
  SCENE_FOOTPRINT_FILL_LAYER_ID,
  SCENE_FOOTPRINT_LINE_LAYER_ID,
  SCENE_FOOTPRINT_SOURCE_ID,
} from "@/lib/scene-footprints";
import type { CatalogueSceneContext, SelectedCatalogueScene } from "@/lib/scene-selection";

export function syncSceneFootprintLayers(
  map: MapLibreMap,
  context: CatalogueSceneContext | null,
  selectedScene: SelectedCatalogueScene | null,
  hoveredSceneKey: string | null,
) {
  if (!map.isStyleLoaded()) return;
  const collection = buildSceneFootprintCollection(context, selectedScene?.scene ?? null);
  const existingSource = map.getSource(SCENE_FOOTPRINT_SOURCE_ID) as GeoJSONSource | undefined;
  if (existingSource) {
    existingSource.setData(collection);
  } else {
    map.addSource(SCENE_FOOTPRINT_SOURCE_ID, { type: "geojson", data: collection });
  }
  const beforeAoiLayer = map.getLayer("satquery-aoi-polygon") ? "satquery-aoi-polygon" : undefined;
  if (!map.getLayer(SCENE_FOOTPRINT_FILL_LAYER_ID)) {
    map.addLayer(
      {
        id: SCENE_FOOTPRINT_FILL_LAYER_ID,
        type: "fill",
        source: SCENE_FOOTPRINT_SOURCE_ID,
        paint: {
          "fill-color": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            "#ff6b6b",
            ["boolean", ["feature-state", "hovered"], false],
            "#62d8e8",
            "#f2b84b",
          ],
          "fill-opacity": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            0.32,
            ["boolean", ["feature-state", "hovered"], false],
            0.22,
            ["boolean", ["get", "current"], false],
            0.11,
            0.04,
          ],
        },
      },
      beforeAoiLayer,
    );
  }
  if (!map.getLayer(SCENE_FOOTPRINT_LINE_LAYER_ID)) {
    map.addLayer(
      {
        id: SCENE_FOOTPRINT_LINE_LAYER_ID,
        type: "line",
        source: SCENE_FOOTPRINT_SOURCE_ID,
        paint: {
          "line-color": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            "#ff8a80",
            ["boolean", ["feature-state", "hovered"], false],
            "#8ce8f2",
            "#f2b84b",
          ],
          "line-opacity": ["case", ["boolean", ["get", "current"], false], 0.95, 0.38],
          "line-width": [
            "case",
            ["boolean", ["feature-state", "selected"], false],
            3,
            ["boolean", ["feature-state", "hovered"], false],
            2.5,
            1.5,
          ],
        },
      },
      beforeAoiLayer,
    );
  }
  for (const feature of collection.features) {
    map.setFeatureState(
      { source: SCENE_FOOTPRINT_SOURCE_ID, id: feature.id },
      {
        selected: feature.id === selectedScene?.key,
        hovered: feature.id === hoveredSceneKey,
      },
    );
  }
}

export function bindSceneFootprintInteractions(
  map: MapLibreMap,
  onHover: (sceneKey: string | null) => void,
  onSelect: (sceneKey: string) => void,
) {
  const readSceneKey = (event: MapLayerMouseEvent) => {
    const sceneKey = event.features?.[0]?.properties?.sceneKey;
    return typeof sceneKey === "string" ? sceneKey : null;
  };
  const handleEnter = (event: MapLayerMouseEvent) => {
    map.getCanvas().style.cursor = "pointer";
    onHover(readSceneKey(event));
  };
  const handleMove = (event: MapLayerMouseEvent) => onHover(readSceneKey(event));
  const handleLeave = () => {
    map.getCanvas().style.cursor = "";
    onHover(null);
  };
  const handleClick = (event: MapLayerMouseEvent) => {
    const sceneKey = readSceneKey(event);
    if (sceneKey) onSelect(sceneKey);
  };

  map.on("mouseenter", SCENE_FOOTPRINT_FILL_LAYER_ID, handleEnter);
  map.on("mousemove", SCENE_FOOTPRINT_FILL_LAYER_ID, handleMove);
  map.on("mouseleave", SCENE_FOOTPRINT_FILL_LAYER_ID, handleLeave);
  map.on("click", SCENE_FOOTPRINT_FILL_LAYER_ID, handleClick);

  return () => {
    map.off("mouseenter", SCENE_FOOTPRINT_FILL_LAYER_ID, handleEnter);
    map.off("mousemove", SCENE_FOOTPRINT_FILL_LAYER_ID, handleMove);
    map.off("mouseleave", SCENE_FOOTPRINT_FILL_LAYER_ID, handleLeave);
    map.off("click", SCENE_FOOTPRINT_FILL_LAYER_ID, handleClick);
    map.getCanvas().style.cursor = "";
  };
}
