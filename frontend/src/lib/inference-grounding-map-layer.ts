import type { Map as MapLibreMap } from "maplibre-gl";

import type { InferenceEvidence } from "@/lib/inference-client";

export const INFERENCE_GROUNDING_SOURCE_ID = "satquery-inference-grounding";
const FILL_ID = `${INFERENCE_GROUNDING_SOURCE_ID}-fill`;
const LINE_ID = `${INFERENCE_GROUNDING_SOURCE_ID}-line`;

export type InferenceGroundingOverlay = {
  sourceChipId: string;
  sceneKey: string;
  geometry: {
    type: "FeatureCollection";
    features: Array<{
      type: "Feature";
      properties: { label: string; candidateIndex: number };
      geometry: { type: "Polygon"; coordinates: number[][][] };
    }>;
  };
};

export function groundingOverlayFromEvidence(
  evidence: InferenceEvidence,
  sceneKey: string,
): InferenceGroundingOverlay | null {
  if (!evidence.grounding || evidence.grounding.candidates.length === 0) return null;
  const features = evidence.grounding.candidates.flatMap((candidate) => {
    const converted = candidate.map_footprint.rings.map((ring) =>
      ring.map(([easting, northing]) => utmToWgs84(candidate.map_footprint.crs, easting, northing)),
    );
    if (
      converted.some((ring) =>
        ring.some(
          ([longitude, latitude]) => !Number.isFinite(longitude) || !Number.isFinite(latitude),
        ),
      )
    )
      return [];
    return [
      {
        type: "Feature" as const,
        properties: { label: candidate.label, candidateIndex: candidate.candidate_index },
        geometry: { type: "Polygon" as const, coordinates: converted },
      },
    ];
  });
  if (features.length === 0) return null;
  return {
    sourceChipId: evidence.source_chip.chip_id,
    sceneKey,
    geometry: { type: "FeatureCollection", features },
  };
}

export function syncInferenceGroundingLayer(
  map: MapLibreMap,
  overlay: InferenceGroundingOverlay | null,
) {
  if (map.getLayer(LINE_ID)) map.removeLayer(LINE_ID);
  if (map.getLayer(FILL_ID)) map.removeLayer(FILL_ID);
  if (map.getSource(INFERENCE_GROUNDING_SOURCE_ID)) map.removeSource(INFERENCE_GROUNDING_SOURCE_ID);
  if (!overlay) return;
  map.addSource(INFERENCE_GROUNDING_SOURCE_ID, {
    type: "geojson",
    data: overlay.geometry,
  });
  map.addLayer({
    id: FILL_ID,
    type: "fill",
    source: INFERENCE_GROUNDING_SOURCE_ID,
    paint: { "fill-color": "#f4c978", "fill-opacity": 0.16 },
  });
  map.addLayer({
    id: LINE_ID,
    type: "line",
    source: INFERENCE_GROUNDING_SOURCE_ID,
    paint: { "line-color": "#ffd98f", "line-width": 3, "line-opacity": 0.95 },
  });
}

export function utmToWgs84(crs: string, easting: number, northing: number): [number, number] {
  const match = /^EPSG:(326|327)(\d{2})$/.exec(crs);
  if (!match) return [Number.NaN, Number.NaN];
  const southern = match[1] === "327";
  const zone = Number(match[2]);
  if (zone < 1 || zone > 60) return [Number.NaN, Number.NaN];
  const a = 6378137;
  const eccentricity = 0.0818191908426215;
  const e1sq = 0.006739496742276434;
  const k0 = 0.9996;
  const x = easting - 500000;
  let y = northing;
  if (southern) y -= 10000000;
  const m = y / k0;
  const mu =
    m /
    (a *
      (1 - eccentricity ** 2 / 4 - (3 * eccentricity ** 4) / 64 - (5 * eccentricity ** 6) / 256));
  const e1 = (1 - Math.sqrt(1 - eccentricity ** 2)) / (1 + Math.sqrt(1 - eccentricity ** 2));
  const phi1 =
    mu +
    ((3 * e1) / 2 - (27 * e1 ** 3) / 32) * Math.sin(2 * mu) +
    ((21 * e1 ** 2) / 16 - (55 * e1 ** 4) / 32) * Math.sin(4 * mu) +
    ((151 * e1 ** 3) / 96) * Math.sin(6 * mu);
  const n1 = a / Math.sqrt(1 - eccentricity ** 2 * Math.sin(phi1) ** 2);
  const t1 = Math.tan(phi1) ** 2;
  const c1 = e1sq * Math.cos(phi1) ** 2;
  const r1 = (a * (1 - eccentricity ** 2)) / (1 - eccentricity ** 2 * Math.sin(phi1) ** 2) ** 1.5;
  const d = x / (n1 * k0);
  const latitude =
    phi1 -
    ((n1 * Math.tan(phi1)) / r1) *
      (d ** 2 / 2 -
        ((5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * e1sq) * d ** 4) / 24 +
        ((61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * e1sq - 3 * c1 ** 2) * d ** 6) / 720);
  const longitudeOrigin = (zone - 1) * 6 - 180 + 3;
  const longitude =
    ((d -
      ((1 + 2 * t1 + c1) * d ** 3) / 6 +
      ((5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * e1sq + 24 * t1 ** 2) * d ** 5) / 120) /
      Math.cos(phi1)) *
      (180 / Math.PI) +
    longitudeOrigin;
  return [longitude, latitude * (180 / Math.PI)];
}
