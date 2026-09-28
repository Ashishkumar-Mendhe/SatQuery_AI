import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SatelliteScene } from "@/lib/analysis-contracts";
import type { SelectedAoi } from "@/lib/aoi";
import type { ImageryAsset } from "@/lib/imagery-contracts";
import { ImageryPreviewPanel } from "./imagery-preview-panel";

describe("ImageryPreviewPanel Component", () => {
  const sampleScene: SatelliteScene = {
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

  const sampleAsset: ImageryAsset = {
    asset_id: "ast-mock-123",
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
    checksum: "sha256-abcdef1234567890",
    created_at: "2026-09-20T00:00:00Z",
    display_url: "/api/v1/imagery/assets/ast-mock-123",
    provider_id: "earth-search",
    data_origin: "mock",
    warnings: [],
    processing_metadata: {},
  };

  it("renders scene header, badges, and initial controls", () => {
    render(
      <ImageryPreviewPanel
        scene={sampleScene}
        selectedAoi={sampleAoi}
        activeAsset={null}
        status="idle"
        error={null}
        selectedPreset="true_color"
        productType="map_preview"
        opacity={1.0}
        visible={true}
        onRequestImagery={vi.fn()}
        onClearImagery={vi.fn()}
        onPresetChange={vi.fn()}
        onProductTypeChange={vi.fn()}
        onOpacityChange={vi.fn()}
        onVisibilityToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("Scene Imagery & Preview")).toBeInTheDocument();
    expect(screen.getByTitle("S2A_20250101")).toBeInTheDocument();
    expect(screen.getByText("Retrieve Scene Imagery")).toBeInTheDocument();
  });

  it("handles preset and product selection change", () => {
    const onPresetChange = vi.fn();
    const onRequestImagery = vi.fn();

    render(
      <ImageryPreviewPanel
        scene={sampleScene}
        selectedAoi={sampleAoi}
        activeAsset={null}
        status="idle"
        error={null}
        selectedPreset="true_color"
        productType="map_preview"
        opacity={1.0}
        visible={true}
        onRequestImagery={onRequestImagery}
        onClearImagery={vi.fn()}
        onPresetChange={onPresetChange}
        onProductTypeChange={vi.fn()}
        onOpacityChange={vi.fn()}
        onVisibilityToggle={vi.fn()}
      />,
    );

    const presetSelect = screen.getByLabelText("Visualization Preset");
    fireEvent.change(presetSelect, { target: { value: "false_color" } });

    expect(onPresetChange).toHaveBeenCalledWith("false_color");
    expect(onRequestImagery).toHaveBeenCalledWith("false_color", "map_preview");
  });

  it("renders active asset details and toggles technical metadata", () => {
    render(
      <ImageryPreviewPanel
        scene={sampleScene}
        selectedAoi={sampleAoi}
        activeAsset={sampleAsset}
        status="ready"
        error={null}
        selectedPreset="true_color"
        productType="map_preview"
        opacity={0.8}
        visible={true}
        onRequestImagery={vi.fn()}
        onClearImagery={vi.fn()}
        onPresetChange={vi.fn()}
        onProductTypeChange={vi.fn()}
        onOpacityChange={vi.fn()}
        onVisibilityToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("DEMO DATA")).toBeInTheDocument();
    expect(screen.getByText("512 × 512 px")).toBeInTheDocument();
    expect(screen.getByText("EPSG:3857")).toBeInTheDocument();

    const toggleBtn = screen.getByText("▶ Show Technical Metadata");
    fireEvent.click(toggleBtn);

    expect(screen.getByText("ast-mock-123")).toBeInTheDocument();
    expect(screen.getByText("sha256-abcdef1234567890")).toBeInTheDocument();
  });

  it("renders loading and error alerts properly", () => {
    const { rerender } = render(
      <ImageryPreviewPanel
        scene={sampleScene}
        selectedAoi={sampleAoi}
        activeAsset={null}
        status="loading"
        error={null}
        selectedPreset="true_color"
        productType="map_preview"
        opacity={1.0}
        visible={true}
        onRequestImagery={vi.fn()}
        onClearImagery={vi.fn()}
        onPresetChange={vi.fn()}
        onProductTypeChange={vi.fn()}
        onOpacityChange={vi.fn()}
        onVisibilityToggle={vi.fn()}
      />,
    );

    expect(screen.getByText(/Retrieving and validating/)).toBeInTheDocument();

    rerender(
      <ImageryPreviewPanel
        scene={sampleScene}
        selectedAoi={sampleAoi}
        activeAsset={null}
        status="error"
        error="Cloud coverage excessive for preview"
        selectedPreset="true_color"
        productType="map_preview"
        opacity={1.0}
        visible={true}
        onRequestImagery={vi.fn()}
        onClearImagery={vi.fn()}
        onPresetChange={vi.fn()}
        onProductTypeChange={vi.fn()}
        onOpacityChange={vi.fn()}
        onVisibilityToggle={vi.fn()}
      />,
    );

    expect(screen.getByRole("alert")).toHaveTextContent("Cloud coverage excessive for preview");
  });
});
