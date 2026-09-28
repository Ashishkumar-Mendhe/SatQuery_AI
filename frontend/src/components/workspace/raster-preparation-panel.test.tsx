import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { PreparedRasterAsset } from "@/lib/preparation-contracts";
import { RasterPreparationPanel } from "./raster-preparation-panel";

const mockSingleAsset: PreparedRasterAsset = {
  asset_id: "ast-prep-1",
  source_asset_ids: ["ast-src-1"],
  scene_ids: ["S2A_20250101"],
  role: "single",
  format: "geotiff",
  crs: "EPSG:32643",
  bbox: [77.58, 12.96, 77.62, 13.0],
  width: 100,
  height: 100,
  pixel_size_x: 10.0,
  pixel_size_y: 10.0,
  transform: [10.0, 0.0, 500000.0, 0.0, -10.0, 1400000.0],
  band_count: 4,
  band_names: ["B02", "B03", "B04", "B08"],
  data_type: "float32",
  no_data_values: [-9999.0],
  valid_pixel_count: 9000,
  invalid_pixel_count: 1000,
  valid_data_percent: 90.0,
  resolution_meters: 10.0,
  resampling_method: "bilinear",
  clip_applied: true,
  mask_applied: true,
  created_at: new Date().toISOString(),
  data_origin: "real",
  provenance: {
    pipeline_version: "1.0",
    source_asset_ids: ["ast-src-1"],
    source_scene_ids: ["S2A_20250101"],
    operations: ["reproject", "clip"],
    parameters: { target_crs: "EPSG:32643" },
    software: "SatQuery Harmonizer",
    started_at: new Date().toISOString(),
    completed_at: new Date().toISOString(),
    duration_milliseconds: 40.0,
    data_origin: "real",
  },
  warnings: [],
  preview_url: "/api/v1/imagery/assets/prev-1",
};

describe("RasterPreparationPanel", () => {
  it("renders preparation controls and triggers start preparation", async () => {
    const user = userEvent.setup();
    const handleStart = vi.fn();
    const handleCrsChange = vi.fn();

    render(
      <RasterPreparationPanel
        mode="single"
        sceneId="S2A_20250101"
        targetCrs="AUTO"
        onTargetCrsChange={handleCrsChange}
        targetResolutionMeters={10}
        onTargetResolutionChange={vi.fn()}
        resamplingMethod="bilinear"
        onResamplingMethodChange={vi.fn()}
        strategy="common_intersection"
        onStrategyChange={vi.fn()}
        isPreparing={false}
        status="queued"
        preparedSingleAsset={null}
        preparedPair={null}
        error={null}
        warnings={[]}
        blockingIssues={[]}
        isReadyForAnalysis={false}
        showPreparedPreview={true}
        onTogglePreparedPreview={vi.fn()}
        onStartPreparation={handleStart}
        onCancelPreparation={vi.fn()}
      />,
    );

    expect(screen.getByText("Analysis Preparation & Raster Harmonization")).toBeInTheDocument();
    const prepareBtn = screen.getByRole("button", { name: /Harmonise & Prepare for Analysis/i });
    await user.click(prepareBtn);
    expect(handleStart).toHaveBeenCalledTimes(1);
  });

  it("displays metrics and scientific status disclaimer when prepared", () => {
    render(
      <RasterPreparationPanel
        mode="single"
        sceneId="S2A_20250101"
        targetCrs="AUTO"
        onTargetCrsChange={vi.fn()}
        targetResolutionMeters={10}
        onTargetResolutionChange={vi.fn()}
        resamplingMethod="bilinear"
        onResamplingMethodChange={vi.fn()}
        strategy="common_intersection"
        onStrategyChange={vi.fn()}
        isPreparing={false}
        status="ready"
        preparedSingleAsset={mockSingleAsset}
        preparedPair={null}
        error={null}
        warnings={[]}
        blockingIssues={[]}
        isReadyForAnalysis={true}
        showPreparedPreview={true}
        onTogglePreparedPreview={vi.fn()}
        onStartPreparation={vi.fn()}
        onCancelPreparation={vi.fn()}
      />,
    );

    expect(screen.getByText("Prepared Raster Metrics")).toBeInTheDocument();
    expect(screen.getByText("EPSG:32643")).toBeInTheDocument();
    expect(screen.getByText("90.0%")).toBeInTheDocument();
    expect(
      screen.getByText(/No spectral indices or change detection have been performed yet/i),
    ).toBeInTheDocument();
  });
});
