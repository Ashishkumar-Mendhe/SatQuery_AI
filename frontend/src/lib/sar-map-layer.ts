import { apiBaseUrl } from "@/lib/health-client";

export const SAR_IMAGE_SOURCE_ID = "satquery-sar-preview-source";
export const SAR_IMAGE_LAYER_ID = "satquery-sar-preview-layer";
export type SarMapOverlay = {
  previewUrl: string;
  bounds: [number, number, number, number];
  opacity: number;
  visible: boolean;
  preparationId: string;
};

type Map = import("maplibre-gl").Map;

export function syncSarLayer(map: Map, overlay: SarMapOverlay | null): void {
  if (map.getLayer(SAR_IMAGE_LAYER_ID)) map.removeLayer(SAR_IMAGE_LAYER_ID);
  if (map.getSource(SAR_IMAGE_SOURCE_ID)) map.removeSource(SAR_IMAGE_SOURCE_ID);
  if (!overlay?.visible) return;
  if (!/^\/api\/v1\/sar\/preparations\/[0-9a-f-]{36}\/preview\.png$/.test(overlay.previewUrl))
    return;
  const [west, south, east, north] = overlay.bounds;
  if (!(west < east && south < north)) return;
  const origin = new URL(apiBaseUrl()).origin;
  map.addSource(SAR_IMAGE_SOURCE_ID, {
    type: "image",
    url: `${origin}${overlay.previewUrl}`,
    coordinates: [
      [west, north],
      [east, north],
      [east, south],
      [west, south],
    ],
  });
  map.addLayer({
    id: SAR_IMAGE_LAYER_ID,
    type: "raster",
    source: SAR_IMAGE_SOURCE_ID,
    paint: { "raster-opacity": Math.max(0, Math.min(1, overlay.opacity)) },
  });
}
