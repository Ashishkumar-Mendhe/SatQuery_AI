import type { Map as MapLibreMap } from "maplibre-gl";

import type { PreparationMaskOverlay } from "@/components/workspace/preparation-panel";
import { preparationMaskTileTemplate } from "@/lib/preparation-client";

export const PREPARATION_MASK_SOURCE_PREFIX = "satquery-preparation-mask-";
const MAX_SCENES = 2;

function remove(map: MapLibreMap) {
  for (let index = 0; index < MAX_SCENES; index += 1) {
    for (const mask of ["usable", "exclusions"] as const) {
      const id = `${PREPARATION_MASK_SOURCE_PREFIX}${mask}-${index}`;
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    }
  }
}

export function syncPreparationMaskLayers(
  map: MapLibreMap,
  overlay: PreparationMaskOverlay | null,
) {
  remove(map);
  if (!overlay) return;
  overlay.qualityArtifactIds.slice(0, MAX_SCENES).forEach((artifactId, index) => {
    for (const mask of ["usable", "exclusions"] as const) {
      if (!overlay[mask]) continue;
      const id = `${PREPARATION_MASK_SOURCE_PREFIX}${mask}-${index}`;
      map.addSource(id, {
        type: "raster",
        tiles: [preparationMaskTileTemplate(artifactId, mask)],
        tileSize: 256,
        bounds: overlay.bounds,
        minzoom: 0,
        maxzoom: 16,
      });
      map.addLayer({
        id,
        type: "raster",
        source: id,
        paint: { "raster-opacity": mask === "usable" ? 0.36 : 0.5, "raster-fade-duration": 0 },
      });
    }
  });
}
