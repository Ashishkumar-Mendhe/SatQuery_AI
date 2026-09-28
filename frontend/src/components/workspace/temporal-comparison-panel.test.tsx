import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SatelliteScene } from "@/lib/analysis-contracts";
import type { SelectedAoi } from "@/lib/aoi";
import type { TemporalImageryResponse } from "@/lib/imagery-contracts";
import { TemporalComparisonPanel } from "./temporal-comparison-panel";

describe("TemporalComparisonPanel Component", () => {
  const sampleBeforeScene: SatelliteScene = {
    id: "S2A_20250101",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-01T05:20:00Z",
    sensor_type: "multispectral",
    platform: "Sentinel-2A",
    cloud_cover: 2.5,
    bbox: [77.5, 12.8, 77.7, 13.1],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleAfterScene: SatelliteScene = {
    id: "S2B_20250120",
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    acquisition_time: "2025-01-20T05:20:00Z",
    sensor_type: "multispectral",
    platform: "Sentinel-2B",
    cloud_cover: 3.5,
    bbox: [77.5, 12.8, 77.7, 13.1],
    available_bands: ["B02", "B03", "B04", "B08"],
    resolution_meters: 10,
    metadata: { data_origin: "real" },
  };

  const sampleAoi: SelectedAoi = {
    version: 1,
    name: "Test AOI",
    source: "rectangle",
    bounds: [77.5, 12.9, 77.7, 13.1],
    areaSquareMeters: 45000000,
    feature: {
      type: "Feature",
      bbox: [77.5, 12.9, 77.7, 13.1],
      properties: { name: "Test AOI", source: "rectangle" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [77.5, 12.9],
            [77.7, 12.9],
            [77.7, 13.1],
            [77.5, 13.1],
            [77.5, 12.9],
          ],
        ],
      },
    },
  };

  const sampleTemporalResponse: TemporalImageryResponse = {
    request_id: "req-temp-999",
    pair_id: "pair-999",
    before_asset: {
      asset_id: "ast-before",
      scene_id: "S2A_20250101",
      product_type: "map_preview",
      format: "png",
      content_type: "image/png",
      width: 512,
      height: 512,
      resolution_meters: 10,
      bbox: [77.5, 12.9, 77.7, 13.1],
      crs: "EPSG:3857",
      bands: ["B04", "B03", "B02"],
      size_bytes: 45000,
      checksum: "sha-before",
      created_at: "2026-09-20T00:00:00Z",
      display_url: "/api/v1/imagery/assets/ast-before",
      provider_id: "earth-search",
      data_origin: "real",
      warnings: [],
      processing_metadata: {},
    },
    after_asset: {
      asset_id: "ast-after",
      scene_id: "S2B_20250120",
      product_type: "map_preview",
      format: "png",
      content_type: "image/png",
      width: 512,
      height: 512,
      resolution_meters: 10,
      bbox: [77.5, 12.9, 77.7, 13.1],
      crs: "EPSG:3857",
      bands: ["B04", "B03", "B02"],
      size_bytes: 46000,
      checksum: "sha-after",
      created_at: "2026-09-20T00:00:00Z",
      display_url: "/api/v1/imagery/assets/ast-after",
      provider_id: "earth-search",
      data_origin: "real",
      warnings: [],
      processing_metadata: {},
    },
    alignment_status: "aligned",
    data_origin: "real",
    warnings: [],
    processing_metadata: {},
  };

  it("renders before and after scene details and action button", () => {
    render(
      <TemporalComparisonPanel
        beforeScene={sampleBeforeScene}
        afterScene={sampleAfterScene}
        selectedAoi={sampleAoi}
        temporalResponse={null}
        status="idle"
        error={null}
        beforePreset="true_color"
        afterPreset="true_color"
        comparisonMode="swipe"
        swipePosition={50}
        blendOpacity={0.5}
        onRequestComparison={vi.fn()}
        onClearComparison={vi.fn()}
        onBeforePresetChange={vi.fn()}
        onAfterPresetChange={vi.fn()}
        onComparisonModeChange={vi.fn()}
        onSwipePositionChange={vi.fn()}
        onBlendOpacityChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Multitemporal Scene Comparison")).toBeInTheDocument();
    expect(screen.getByTitle("S2A_20250101")).toBeInTheDocument();
    expect(screen.getByTitle("S2B_20250120")).toBeInTheDocument();
    expect(screen.getByText("Retrieve Multitemporal Imagery")).toBeInTheDocument();
  });

  it("switches comparison modes between Swipe, Side-by-Side, and Blend", () => {
    const onComparisonModeChange = vi.fn();

    render(
      <TemporalComparisonPanel
        beforeScene={sampleBeforeScene}
        afterScene={sampleAfterScene}
        selectedAoi={sampleAoi}
        temporalResponse={sampleTemporalResponse}
        status="ready"
        error={null}
        beforePreset="true_color"
        afterPreset="true_color"
        comparisonMode="swipe"
        swipePosition={50}
        blendOpacity={0.5}
        onRequestComparison={vi.fn()}
        onClearComparison={vi.fn()}
        onBeforePresetChange={vi.fn()}
        onAfterPresetChange={vi.fn()}
        onComparisonModeChange={onComparisonModeChange}
        onSwipePositionChange={vi.fn()}
        onBlendOpacityChange={vi.fn()}
      />,
    );

    const splitBtn = screen.getByRole("button", { name: "Side-by-Side" });
    fireEvent.click(splitBtn);
    expect(onComparisonModeChange).toHaveBeenCalledWith("split");

    const blendBtn = screen.getByRole("button", { name: "Opacity Blend" });
    fireEvent.click(blendBtn);
    expect(onComparisonModeChange).toHaveBeenCalledWith("blend");
  });

  it("renders alignment status and explanation", () => {
    render(
      <TemporalComparisonPanel
        beforeScene={sampleBeforeScene}
        afterScene={sampleAfterScene}
        selectedAoi={sampleAoi}
        temporalResponse={sampleTemporalResponse}
        status="ready"
        error={null}
        beforePreset="true_color"
        afterPreset="true_color"
        comparisonMode="swipe"
        swipePosition={50}
        blendOpacity={0.5}
        onRequestComparison={vi.fn()}
        onClearComparison={vi.fn()}
        onBeforePresetChange={vi.fn()}
        onAfterPresetChange={vi.fn()}
        onComparisonModeChange={vi.fn()}
        onSwipePositionChange={vi.fn()}
        onBlendOpacityChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Alignment Status: Grids Aligned")).toBeInTheDocument();
    expect(
      screen.getByText("Scenes share identical CRS, resolution, and pixel alignment."),
    ).toBeInTheDocument();
  });

  it("adjusts swipe slider position", () => {
    const onSwipePositionChange = vi.fn();

    render(
      <TemporalComparisonPanel
        beforeScene={sampleBeforeScene}
        afterScene={sampleAfterScene}
        selectedAoi={sampleAoi}
        temporalResponse={sampleTemporalResponse}
        status="ready"
        error={null}
        beforePreset="true_color"
        afterPreset="true_color"
        comparisonMode="swipe"
        swipePosition={50}
        blendOpacity={0.5}
        onRequestComparison={vi.fn()}
        onClearComparison={vi.fn()}
        onBeforePresetChange={vi.fn()}
        onAfterPresetChange={vi.fn()}
        onComparisonModeChange={vi.fn()}
        onSwipePositionChange={onSwipePositionChange}
        onBlendOpacityChange={vi.fn()}
      />,
    );

    const slider = screen.getByLabelText(/Swipe Divider:/);
    fireEvent.change(slider, { target: { value: "70" } });
    expect(onSwipePositionChange).toHaveBeenCalledWith(70);
  });
});
