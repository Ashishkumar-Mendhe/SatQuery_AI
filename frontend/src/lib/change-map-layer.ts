import type { Map as MapLibreMap } from "maplibre-gl";
import type { ChangeOverlay } from "@/components/workspace/change-analysis-panel";
import { changeTileTemplate } from "@/lib/change-client";

export const CHANGE_SOURCE_ID = "satquery-computed-change";
export function syncChangeLayer(map: MapLibreMap, overlay: ChangeOverlay | null) {
  if (map.getLayer(CHANGE_SOURCE_ID)) map.removeLayer(CHANGE_SOURCE_ID);
  if (map.getSource(CHANGE_SOURCE_ID)) map.removeSource(CHANGE_SOURCE_ID);
  if (!overlay?.visible) return;
  map.addSource(CHANGE_SOURCE_ID, {
    type: "raster",
    tiles: [changeTileTemplate(overlay.artifactId)],
    tileSize: 256,
    bounds: overlay.bounds,
    minzoom: 0,
    maxzoom: 16,
  });
  map.addLayer({
    id: CHANGE_SOURCE_ID,
    type: "raster",
    source: CHANGE_SOURCE_ID,
    paint: { "raster-opacity": overlay.opacity, "raster-fade-duration": 0 },
  });
}
