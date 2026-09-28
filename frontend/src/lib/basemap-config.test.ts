import type { StyleSpecification } from "maplibre-gl";
import { describe, expect, it, beforeEach } from "vitest";
import {
  BASEMAP_OPTIONS_LIST,
  getBasemapConfig,
  getBasemapStyle,
  getStoredBasemap,
  setStoredBasemap,
} from "./basemap-config";

describe("basemap-config", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defines all three core basemaps: default, terrain, satellite", () => {
    expect(BASEMAP_OPTIONS_LIST.length).toBe(3);
    const ids = BASEMAP_OPTIONS_LIST.map((o) => o.id);
    expect(ids).toEqual(["default", "terrain", "satellite"]);
  });

  it("each basemap has required label, description, and attribution", () => {
    for (const option of BASEMAP_OPTIONS_LIST) {
      expect(option.label).toBeTruthy();
      expect(option.description).toBeTruthy();
      expect(option.attribution).toBeTruthy();
    }
  });

  it("provides valid style definitions for MapLibre", () => {
    const defaultStyle = getBasemapStyle("default");
    expect(typeof defaultStyle).toBe("string");

    const terrainStyle = getBasemapStyle("terrain") as StyleSpecification;
    expect(typeof terrainStyle).toBe("object");
    expect(terrainStyle.sources?.["opentopo-source"]).toBeDefined();

    const satelliteStyle = getBasemapStyle("satellite") as StyleSpecification;
    expect(typeof satelliteStyle).toBe("object");
    expect(satelliteStyle.sources?.["esri-satellite-source"]).toBeDefined();
  });

  it("persists and reads basemap selection in localStorage", () => {
    expect(getStoredBasemap()).toBe("default");

    setStoredBasemap("satellite");
    expect(getStoredBasemap()).toBe("satellite");

    setStoredBasemap("terrain");
    expect(getStoredBasemap()).toBe("terrain");
  });

  it("getBasemapConfig falls back gracefully to default for unknown id", () => {
    // @ts-expect-error testing invalid id
    const cfg = getBasemapConfig("unknown_basemap");
    expect(cfg.id).toBe("default");
  });
});
