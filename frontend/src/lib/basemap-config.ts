import type { StyleSpecification } from "maplibre-gl";

export type BasemapId = "default" | "terrain" | "satellite";

export interface BasemapOption {
  readonly id: BasemapId;
  readonly label: string;
  readonly description: string;
  readonly attribution: string;
  readonly style: string | StyleSpecification;
}

export const BASEMAP_STORAGE_KEY = "satquery.basemap_preference";
export const SATELLITE_LABELS_STORAGE_KEY = "satquery.satellite_labels_preference";

export const BASEMAP_OPTIONS: Record<BasemapId, BasemapOption> = {
  default: {
    id: "default",
    label: "Default",
    description:
      "Vector basemap with road networks, administrative boundaries, and hierarchical place names.",
    attribution:
      '&copy; <a href="https://www.openfreemap.org" target="_blank" rel="noreferrer">OpenFreeMap</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
    style: "https://tiles.openfreemap.org/styles/liberty",
  },
  terrain: {
    id: "terrain",
    label: "Terrain",
    description: "Topographic elevation contour and landform basemap for topographic context.",
    attribution:
      'Map data: &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors, SRTM | Style: &copy; <a href="https://opentopomap.org" target="_blank" rel="noreferrer">OpenTopoMap</a>',
    style: {
      version: 8,
      sources: {
        "opentopo-source": {
          type: "raster",
          tiles: [
            "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
            "https://b.tile.opentopomap.org/{z}/{x}/{y}.png",
            "https://c.tile.opentopomap.org/{z}/{x}/{y}.png",
          ],
          tileSize: 256,
          attribution:
            'Map data &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors, SRTM | Style &copy; <a href="https://opentopomap.org" target="_blank" rel="noreferrer">OpenTopoMap</a>',
          maxzoom: 17,
        },
      },
      layers: [
        {
          id: "opentopo-raster-layer",
          type: "raster",
          source: "opentopo-source",
          minzoom: 0,
          maxzoom: 18,
        },
      ],
    },
  },
  satellite: {
    id: "satellite",
    label: "Satellite",
    description:
      "Global satellite imagery hybrid with transparent place names and administrative boundaries.",
    attribution:
      'Imagery &copy; <a href="https://www.esri.com" target="_blank" rel="noreferrer">Esri</a>, Maxar, Earthstar Geographics &bull; Boundaries &copy; Esri',
    style: {
      version: 8,
      sources: {
        "esri-satellite-source": {
          type: "raster",
          tiles: [
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
          ],
          tileSize: 256,
          attribution:
            "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, USDA, USGS, and GIS User Community",
          maxzoom: 19,
        },
        "esri-reference-source": {
          type: "raster",
          tiles: [
            "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
          ],
          tileSize: 256,
          attribution: "Boundaries & Places &copy; Esri",
          maxzoom: 19,
        },
      },
      layers: [
        {
          id: "esri-satellite-raster-layer",
          type: "raster",
          source: "esri-satellite-source",
          minzoom: 0,
          maxzoom: 20,
        },
        {
          id: "satellite-hybrid-labels-layer",
          type: "raster",
          source: "esri-reference-source",
          minzoom: 0,
          maxzoom: 20,
          layout: {
            visibility: "visible",
          },
        },
      ],
    },
  },
};

export const BASEMAP_OPTIONS_LIST: BasemapOption[] = [
  BASEMAP_OPTIONS.default,
  BASEMAP_OPTIONS.terrain,
  BASEMAP_OPTIONS.satellite,
];

export function getBasemapConfig(id: BasemapId): BasemapOption {
  return BASEMAP_OPTIONS[id] ?? BASEMAP_OPTIONS.default;
}

export function getBasemapStyle(id: BasemapId): string | StyleSpecification {
  return getBasemapConfig(id).style;
}

export function getStoredBasemap(): BasemapId {
  if (typeof window === "undefined") return "default";
  try {
    const val = localStorage.getItem(BASEMAP_STORAGE_KEY);
    if (val === "default" || val === "terrain" || val === "satellite") {
      return val;
    }
  } catch {
    // Ignore storage access errors
  }
  return "default";
}

export function setStoredBasemap(id: BasemapId): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(BASEMAP_STORAGE_KEY, id);
  } catch {
    // Ignore storage access errors
  }
}

export function getStoredSatelliteLabels(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const val = localStorage.getItem(SATELLITE_LABELS_STORAGE_KEY);
    if (val !== null) {
      return val === "true";
    }
  } catch {
    // Ignore storage access errors
  }
  return true;
}

export function setStoredSatelliteLabels(visible: boolean): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(SATELLITE_LABELS_STORAGE_KEY, String(visible));
  } catch {
    // Ignore storage access errors
  }
}
