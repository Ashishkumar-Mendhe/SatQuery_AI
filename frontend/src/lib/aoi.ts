import { area as calculateGeodesicArea } from "@turf/area";
import { bbox as calculateBbox } from "@turf/bbox";
import { kinks } from "@turf/kinks";

export const AOI_MAX_FILE_BYTES = 1_000_000;
export const AOI_MAX_VERTICES = 500;
export const MAP_MAX_LATITUDE = 85.051129;

export type Position = [longitude: number, latitude: number];
export type AoiBounds = [west: number, south: number, east: number, north: number];
export type AoiSource = "rectangle" | "polygon" | "bbox" | "geojson";

export interface AoiPolygon {
  type: "Polygon";
  coordinates: Position[][];
}

export interface AoiFeature {
  type: "Feature";
  geometry: AoiPolygon;
  properties: {
    name: string;
    source: AoiSource;
  };
  bbox: AoiBounds;
}

export interface SelectedAoi {
  version: 1;
  feature: AoiFeature;
  name: string;
  source: AoiSource;
  bounds: AoiBounds;
  areaSquareMeters: number;
}

export class AoiValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AoiValidationError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function positionsEqual(first: Position, second: Position): boolean {
  return first[0] === second[0] && first[1] === second[1];
}

function parsePosition(value: unknown, index: number): Position {
  if (!Array.isArray(value) || value.length !== 2) {
    throw new AoiValidationError(`Vertex ${index + 1} must contain exactly [longitude, latitude].`);
  }
  const [longitude, latitude] = value;
  if (
    typeof longitude !== "number" ||
    typeof latitude !== "number" ||
    !Number.isFinite(longitude) ||
    !Number.isFinite(latitude)
  ) {
    throw new AoiValidationError(`Vertex ${index + 1} must contain finite numeric coordinates.`);
  }
  if (longitude < -180 || longitude > 180) {
    throw new AoiValidationError(`Vertex ${index + 1} longitude must be between -180 and 180.`);
  }
  if (latitude < -90 || latitude > 90) {
    throw new AoiValidationError(`Vertex ${index + 1} latitude must be between -90 and 90.`);
  }
  return [longitude, latitude];
}

function signedRingArea(ring: Position[]): number {
  let sum = 0;
  for (let index = 0; index < ring.length - 1; index += 1) {
    const current = ring[index];
    const next = ring[index + 1];
    sum +=
      (current[0] - ring[0][0]) * (next[1] - ring[0][1]) -
      (next[0] - ring[0][0]) * (current[1] - ring[0][1]);
  }
  return sum / 2;
}

function normalizeCounterClockwise(ring: Position[]): Position[] {
  if (signedRingArea(ring) >= 0) {
    return ring;
  }
  const openRing = ring.slice(0, -1).reverse();
  return [...openRing, openRing[0]];
}

function extractPolygonCandidate(value: unknown): {
  geometry: Record<string, unknown>;
  importedName: string | null;
} {
  if (!isRecord(value) || typeof value.type !== "string") {
    throw new AoiValidationError(
      "GeoJSON must be a Polygon, Feature, or one-feature FeatureCollection.",
    );
  }
  if ("crs" in value) {
    throw new AoiValidationError(
      "Legacy CRS metadata is unsupported. Convert to RFC 7946 WGS84 longitude/latitude before import.",
    );
  }

  if (value.type === "FeatureCollection") {
    if (!Array.isArray(value.features) || value.features.length !== 1) {
      throw new AoiValidationError("A FeatureCollection must contain exactly one Polygon feature.");
    }
    return extractPolygonCandidate(value.features[0]);
  }

  if (value.type === "Feature") {
    if (!isRecord(value.geometry)) {
      throw new AoiValidationError("The GeoJSON Feature must contain a Polygon geometry.");
    }
    const importedName =
      isRecord(value.properties) && typeof value.properties.name === "string"
        ? value.properties.name.trim().slice(0, 80)
        : null;
    return { geometry: value.geometry, importedName: importedName || null };
  }

  return { geometry: value, importedName: null };
}

export function createSelectedAoi(
  value: unknown,
  source: AoiSource,
  requestedName?: string,
): SelectedAoi {
  const { geometry, importedName } = extractPolygonCandidate(value);
  if ("crs" in geometry)
    throw new AoiValidationError("Convert geometry to RFC 7946 WGS84 before import.");
  if (geometry.type === "MultiPolygon") {
    throw new AoiValidationError(
      "MultiPolygon AOIs are not supported in this phase. Import one Polygon without disconnected parts.",
    );
  }
  if (geometry.type !== "Polygon" || !Array.isArray(geometry.coordinates)) {
    throw new AoiValidationError("Only Polygon AOIs are supported.");
  }
  if (geometry.coordinates.length !== 1) {
    throw new AoiValidationError(
      "Polygon holes are not supported in this phase. Import one exterior ring without holes.",
    );
  }

  const rawRing = geometry.coordinates[0];
  if (!Array.isArray(rawRing)) {
    throw new AoiValidationError("The Polygon exterior ring is missing.");
  }
  if (rawRing.length > AOI_MAX_VERTICES) {
    throw new AoiValidationError(`AOIs may contain at most ${AOI_MAX_VERTICES} ring positions.`);
  }
  if (rawRing.length < 4) {
    throw new AoiValidationError(
      "A Polygon ring needs at least three vertices plus its closing position.",
    );
  }

  const ring = rawRing.map(parsePosition);
  if (!positionsEqual(ring[0], ring[ring.length - 1])) {
    throw new AoiValidationError(
      "The Polygon ring must be closed with an identical first and last position.",
    );
  }

  const distinctVertices = new Set(
    ring.slice(0, -1).map(([longitude, latitude]) => `${longitude},${latitude}`),
  );
  if (distinctVertices.size < 3) {
    throw new AoiValidationError("A Polygon needs at least three distinct vertices.");
  }
  if (distinctVertices.size !== ring.length - 1) {
    throw new AoiValidationError("Polygon vertices must not repeat except at ring closure.");
  }
  // Reject collinear edge overlap/backtracking, which Turf kinks does not detect.
  for (let i = 0; i < ring.length - 1; i += 1) {
    const a = ring[i];
    const b = ring[i + 1];
    for (let j = 0; j < ring.length - 1; j += 1) {
      if (j === i || j === (i + 1) % (ring.length - 1)) continue;
      const p = ring[j];
      const cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]);
      if (
        cross === 0 &&
        p[0] >= Math.min(a[0], b[0]) &&
        p[0] <= Math.max(a[0], b[0]) &&
        p[1] >= Math.min(a[1], b[1]) &&
        p[1] <= Math.max(a[1], b[1])
      ) {
        throw new AoiValidationError("The Polygon has overlapping or touching edges.");
      }
    }
  }

  for (let index = 0; index < ring.length - 1; index += 1) {
    const current = ring[index];
    const next = ring[index + 1];
    if (Math.abs(current[0] - next[0]) > 180) {
      throw new AoiValidationError(
        "Antimeridian-crossing AOIs are not supported by this editor. Split the shape at ±180° before import.",
      );
    }
  }

  const normalizedRing = normalizeCounterClockwise(ring);
  const geometryValue: AoiPolygon = { type: "Polygon", coordinates: [normalizedRing] };
  const bareFeature = { type: "Feature" as const, properties: {}, geometry: geometryValue };
  if (kinks(bareFeature).features.length > 0) {
    throw new AoiValidationError("The Polygon intersects itself. Adjust its edges and try again.");
  }
  if (signedRingArea(ring) === 0)
    throw new AoiValidationError("The Polygon must enclose a nonzero area.");

  const areaSquareMeters = calculateGeodesicArea(bareFeature);
  if (!Number.isFinite(areaSquareMeters) || areaSquareMeters <= 0) {
    throw new AoiValidationError("The Polygon must enclose a nonzero geographic area.");
  }

  const rawBounds = calculateBbox(bareFeature);
  const bounds: AoiBounds = [rawBounds[0], rawBounds[1], rawBounds[2], rawBounds[3]];
  if (bounds[2] - bounds[0] > 180) {
    throw new AoiValidationError(
      "AOIs wider than 180 degrees are unsupported. Split the shape before import.",
    );
  }
  const defaultNames: Record<AoiSource, string> = {
    rectangle: "Rectangle AOI",
    polygon: "Polygon AOI",
    bbox: "Bounding box AOI",
    geojson: "Imported AOI",
  };
  const name = requestedName?.trim().slice(0, 80) || importedName || defaultNames[source];
  const feature: AoiFeature = {
    type: "Feature",
    geometry: geometryValue,
    properties: { name, source },
    bbox: bounds,
  };

  return { version: 1, feature, name, source, bounds, areaSquareMeters };
}

export function createAoiFromBounds(bounds: AoiBounds): SelectedAoi {
  const [west, south, east, north] = bounds;
  for (const value of bounds) {
    if (!Number.isFinite(value)) {
      throw new AoiValidationError("All bounding-box values must be finite numbers.");
    }
  }
  if (west < -180 || east > 180 || south < -90 || north > 90) {
    throw new AoiValidationError("Bounds must stay within longitude ±180° and latitude ±90°.");
  }
  if (west >= east) {
    throw new AoiValidationError(
      "West must be less than east. Antimeridian-crossing bounding boxes are not supported in this phase.",
    );
  }
  if (south >= north) {
    throw new AoiValidationError("South must be less than north.");
  }
  return createSelectedAoi(
    {
      type: "Polygon",
      coordinates: [
        [
          [west, south],
          [east, south],
          [east, north],
          [west, north],
          [west, south],
        ],
      ],
    },
    "bbox",
  );
}

export function getMapDisplayIssue(aoi: SelectedAoi): string | null {
  const [, south, , north] = aoi.bounds;
  if (south < -MAP_MAX_LATITUDE || north > MAP_MAX_LATITUDE) {
    return `This valid WGS84 AOI extends beyond the map display limit of ±${MAP_MAX_LATITUDE}° latitude.`;
  }
  return null;
}

export function formatAoiArea(areaSquareMeters: number): string {
  if (areaSquareMeters < 1) return "<1 m²";
  if (areaSquareMeters < 10_000) {
    return `${Math.round(areaSquareMeters).toLocaleString("en-US")} m²`;
  }
  if (areaSquareMeters < 1_000_000) {
    return `${(areaSquareMeters / 10_000).toFixed(2)} ha`;
  }
  return `${(areaSquareMeters / 1_000_000).toFixed(areaSquareMeters < 100_000_000 ? 2 : 1)} km²`;
}

export function formatAoiBounds(bounds: AoiBounds): string {
  return bounds.map((value) => value.toFixed(5)).join(", ");
}

export function parseGeoJsonText(text: string): SelectedAoi {
  if (new TextEncoder().encode(text).byteLength > AOI_MAX_FILE_BYTES) {
    throw new AoiValidationError("GeoJSON files may be at most 1 MB.");
  }
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch {
    throw new AoiValidationError("The selected file is not valid JSON.");
  }
  return createSelectedAoi(value, "geojson");
}

export function serializeAoi(aoi: SelectedAoi): string {
  const exportFeature: AoiFeature = {
    ...aoi.feature,
    bbox: [...aoi.bounds],
    properties: { name: aoi.name, source: aoi.source },
  };
  return `${JSON.stringify(exportFeature, null, 2)}\n`;
}
