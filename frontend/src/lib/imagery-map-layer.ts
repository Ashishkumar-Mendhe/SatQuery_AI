import type { Map as MapLibreMap, MapSourceDataEvent } from "maplibre-gl";

import { absoluteTileTemplate } from "@/lib/imagery-tile-client";
import {
  type ImageryDisplaySettings,
  imageryDisplaySettingsSchema,
  type TileMetadata,
} from "@/lib/viewer-contracts";

export const IMAGERY_SOURCE_ID = "satquery-imagery";
export const IMAGERY_LAYER_ID = "satquery-imagery-raster";

export const DEFAULT_IMAGERY_DISPLAY_SETTINGS: ImageryDisplaySettings = {
  visible: true,
  opacity: 1,
  brightness_min: 0,
  brightness_max: 1,
  contrast: 0,
  saturation: 0,
};

export type ImageryMapState = "loading" | "ready" | "partial" | "failed" | "expired";

function escapeAttribution(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function removeImageryLayer(map: MapLibreMap) {
  if (map.getLayer(IMAGERY_LAYER_ID)) map.removeLayer(IMAGERY_LAYER_ID);
  if (map.getSource(IMAGERY_SOURCE_ID)) map.removeSource(IMAGERY_SOURCE_ID);
}

export function applyImageryDisplaySettings(map: MapLibreMap, settings: ImageryDisplaySettings) {
  const display = imageryDisplaySettingsSchema.parse(settings);
  if (!map.getLayer(IMAGERY_LAYER_ID)) return;
  map.setLayoutProperty(IMAGERY_LAYER_ID, "visibility", display.visible ? "visible" : "none");
  map.setPaintProperty(IMAGERY_LAYER_ID, "raster-opacity", display.opacity);
  map.setPaintProperty(IMAGERY_LAYER_ID, "raster-brightness-min", display.brightness_min);
  map.setPaintProperty(IMAGERY_LAYER_ID, "raster-brightness-max", display.brightness_max);
  map.setPaintProperty(IMAGERY_LAYER_ID, "raster-contrast", display.contrast);
  map.setPaintProperty(IMAGERY_LAYER_ID, "raster-saturation", display.saturation);
}

export function syncImageryLayer(
  map: MapLibreMap,
  metadata: TileMetadata | null,
  settings: ImageryDisplaySettings = DEFAULT_IMAGERY_DISPLAY_SETTINGS,
) {
  if (!map.isStyleLoaded()) return;
  const display = imageryDisplaySettingsSchema.parse(settings);
  removeImageryLayer(map);
  if (!metadata) return;
  if (!metadata.expires_at || Date.parse(metadata.expires_at) <= Date.now()) return;

  map.addSource(IMAGERY_SOURCE_ID, {
    type: "raster",
    tiles: [absoluteTileTemplate(metadata)],
    tileSize: metadata.tile_size,
    bounds: metadata.bounds,
    minzoom: metadata.min_zoom,
    maxzoom: metadata.max_zoom,
    scheme: "xyz",
    attribution: metadata.attributions.map(escapeAttribution).join(" · "),
  });
  const firstOverlay = map.getLayer("satquery-scene-footprints-fill")
    ? "satquery-scene-footprints-fill"
    : map.getLayer("satquery-aoi-polygon")
      ? "satquery-aoi-polygon"
      : undefined;
  map.addLayer(
    {
      id: IMAGERY_LAYER_ID,
      type: "raster",
      source: IMAGERY_SOURCE_ID,
      layout: { visibility: display.visible ? "visible" : "none" },
      paint: {
        "raster-opacity": display.opacity,
        "raster-brightness-min": display.brightness_min,
        "raster-brightness-max": display.brightness_max,
        "raster-contrast": display.contrast,
        "raster-saturation": display.saturation,
        "raster-fade-duration": 0,
      },
    },
    firstOverlay,
  );
  map.triggerRepaint();
}

export function bindImageryLayerEvents(
  map: MapLibreMap,
  onState: (state: ImageryMapState, message: string) => void,
) {
  let receivedTileContent = false;
  const handleSourceLoading = (event: MapSourceDataEvent) => {
    if (event.sourceId === IMAGERY_SOURCE_ID && event.sourceDataType === "metadata") {
      receivedTileContent = false;
    }
  };
  const handleSourceData = (event: MapSourceDataEvent) => {
    if (event.sourceId !== IMAGERY_SOURCE_ID) return;
    if (event.sourceDataType === "content") receivedTileContent = true;
    if (event.isSourceLoaded) onState("ready", "Imagery rendered from georeferenced raster tiles.");
  };
  const handleError = (event: unknown) => {
    const sourceId =
      typeof event === "object" && event !== null && "sourceId" in event
        ? (event as { sourceId?: unknown }).sourceId
        : undefined;
    if (sourceId !== IMAGERY_SOURCE_ID) return;
    onState(
      receivedTileContent ? "partial" : "failed",
      receivedTileContent
        ? "Some imagery tiles failed. Visible tiles may be incomplete; retry the layer."
        : "Imagery tiles failed to render. Retry the layer.",
    );
  };
  map.on("sourcedataloading", handleSourceLoading);
  map.on("sourcedata", handleSourceData);
  map.on("error", handleError);
  return () => {
    map.off("sourcedataloading", handleSourceLoading);
    map.off("sourcedata", handleSourceData);
    map.off("error", handleError);
  };
}
