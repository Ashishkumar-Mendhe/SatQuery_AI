import { describe, expect, it } from "vitest";

import {
  activeImageryLayerSchema,
  comparisonSelectionSchema,
  resolvedImageryAssetSchema,
  savedViewerStateSchema,
  tileMetadataSchema,
  timelineSelectionSchema,
} from "@/lib/viewer-contracts";

function scene(item: string, acquiredAt: string) {
  return {
    scene: {
      provider: "synthetic-provider",
      collection: "synthetic-optical-l2",
      item,
    },
    acquisition: { start: acquiredAt, end: acquiredAt },
  };
}

function asset() {
  const selectedScene = scene("scene-synthetic-001", "2026-01-12T10:00:00Z");
  return {
    schema_version: "1.0",
    identity: {
      scene: selectedScene.scene,
      asset: "synthetic-visual-asset",
      asset_version: "v1",
    },
    acquisition: selectedScene.acquisition,
    media_type: "image/tiff",
    bounds: [77.5, 12.9, 77.7, 13.05],
    render_presets: [
      {
        id: "true_color",
        title: "Synthetic true color",
        description: "Synthetic visualization preset; no real imagery is represented.",
        mode: "rgb",
        bands: ["synthetic-red", "synthetic-green", "synthetic-blue"],
        purpose: "visualization",
      },
    ],
    default_render_preset: "true_color",
    catalogue_availability: { state: "available", reason: null },
    asset_accessibility: {
      state: "accessible",
      method: "backend_mediated",
      reason: null,
      expires_at: "2026-01-12T11:30:00Z",
    },
    analysis_readiness: {
      state: "not_assessed",
      reason: "Viewer resolution does not perform analytical validation.",
    },
    attributions: ["Synthetic fixture; not provider imagery."],
    resolved_at: "2026-01-12T11:00:00Z",
  };
}

function display() {
  return {
    visible: true,
    opacity: 0.8,
    brightness_min: 0.05,
    brightness_max: 0.95,
    contrast: 0.1,
    saturation: -0.1,
  };
}

describe("viewer contracts", () => {
  it("validates stable scene identity, render presets, and independent capability states", () => {
    const parsed = resolvedImageryAssetSchema.parse(asset());

    expect(parsed.identity.scene).toEqual({
      provider: "synthetic-provider",
      collection: "synthetic-optical-l2",
      item: "scene-synthetic-001",
    });
    expect(parsed.catalogue_availability.state).toBe("available");
    expect(parsed.asset_accessibility.state).toBe("accessible");
    expect(parsed.analysis_readiness.state).toBe("not_assessed");
  });

  it("rejects unsupported presets and inconsistent asset access", () => {
    expect(
      resolvedImageryAssetSchema.safeParse({ ...asset(), default_render_preset: "missing" })
        .success,
    ).toBe(false);
    expect(
      resolvedImageryAssetSchema.safeParse({
        ...asset(),
        asset_accessibility: {
          state: "unavailable",
          method: "backend_mediated",
          reason: "Synthetic failure.",
          expires_at: null,
        },
      }).success,
    ).toBe(false);
  });

  it("accepts only mediated, expiring, contract-bound tile metadata", () => {
    const resolved = asset();
    const tile = {
      schema_version: "1.0",
      tile_set_id: "00000000-0000-4000-8000-000000000005",
      asset: resolved.identity,
      render_preset: "true_color",
      bounds: resolved.bounds,
      min_zoom: 4,
      max_zoom: 14,
      tile_size: 256,
      media_type: "image/png",
      url_template: "/api/v1/viewer/tiles/00000000-0000-4000-8000-000000000005/{z}/{x}/{y}",
      expires_at: "2026-01-12T11:30:00Z",
      attributions: resolved.attributions,
      access: { state: "available", reason: null },
    };

    expect(tileMetadataSchema.parse(tile).access.state).toBe("available");
    expect(
      tileMetadataSchema.safeParse({
        ...tile,
        url_template: "https://provider.test/{z}/{x}/{y}",
      }).success,
    ).toBe(false);
    expect(tileMetadataSchema.safeParse({ ...tile, expires_at: null }).success).toBe(false);
  });

  it("keeps accessible, failed rendering, and unassessed analysis as separate states", () => {
    const resolved = asset();
    const parsed = activeImageryLayerSchema.parse({
      layer_id: "primary_imagery",
      asset: resolved.identity,
      acquisition: resolved.acquisition,
      render_preset: "true_color",
      tile_set_id: null,
      display: display(),
      catalogue_availability: resolved.catalogue_availability,
      asset_accessibility: resolved.asset_accessibility,
      render_status: { state: "failed", reason: "Synthetic tile load failure." },
      analysis_readiness: resolved.analysis_readiness,
    });

    expect(parsed.asset_accessibility.state).toBe("accessible");
    expect(parsed.render_status.state).toBe("failed");
    expect(parsed.analysis_readiness.state).toBe("not_assessed");
  });

  it("requires distinct chronological comparison and timeline selections", () => {
    const sceneA = scene("scene-a", "2026-01-01T10:00:00Z");
    const sceneB = scene("scene-b", "2026-02-01T10:00:00Z");

    expect(comparisonSelectionSchema.parse({ scene_a: sceneA, scene_b: sceneB }).scene_a).toEqual(
      sceneA,
    );
    expect(comparisonSelectionSchema.safeParse({ scene_a: sceneB, scene_b: sceneA }).success).toBe(
      false,
    );
    expect(
      timelineSelectionSchema.parse({
        scenes: [sceneA, sceneB],
        selected_scene: sceneB.scene,
      }).selected_scene,
    ).toEqual(sceneB.scene);
  });

  it("versions saved viewer state and excludes tile URLs and render claims", () => {
    const resolved = asset();
    const saved = {
      version: 1,
      saved_at: "2026-01-12T11:05:00Z",
      aoi_reference: {
        storage_key: "satquery.aoi-draft.v1",
        geometry_fingerprint: '{"type":"Polygon"}',
      },
      camera: { center: [77.6, 13], zoom: 8, bearing: 0, pitch: 0 },
      active_layer: {
        layer_id: "primary_imagery",
        asset: resolved.identity,
        acquisition: resolved.acquisition,
        render_preset: "true_color",
        display: display(),
      },
      comparison_slots: null,
      comparison: null,
      timeline: null,
    };

    expect(savedViewerStateSchema.parse(saved).version).toBe(1);
    expect(
      savedViewerStateSchema.safeParse({ ...saved, tile_url: "/api/v1/viewer/tiles/secret" })
        .success,
    ).toBe(false);
  });

  it("retains one comparison slot without inventing the other", () => {
    const sceneA = scene("scene-a", "2026-01-01T10:00:00Z");
    const base = {
      version: 1 as const,
      saved_at: "2026-01-12T11:05:00Z",
      aoi_reference: null,
      camera: null,
      active_layer: null,
      comparison_slots: { scene_a: sceneA, scene_b: null },
      comparison: null,
      timeline: null,
    };
    expect(savedViewerStateSchema.parse(base).comparison_slots?.scene_a).toEqual(sceneA);
    expect(
      savedViewerStateSchema.safeParse({
        ...base,
        comparison_slots: { scene_a: sceneA, scene_b: sceneA },
      }).success,
    ).toBe(false);
  });
});
