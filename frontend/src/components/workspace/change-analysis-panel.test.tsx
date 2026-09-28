import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createAoiFromBounds } from "@/lib/aoi";
import type { ChangeClient, ChangeResult } from "@/lib/change-client";
import type { ProcessingJobStatus } from "@/lib/preparation-client";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";
import { ChangeAnalysisPanel } from "./change-analysis-panel";

const scene = (item: string, date: string): SelectedCatalogueScene => ({
  identity: { providerId: "earth-search", collectionId: "sentinel-2-c1-l2a", itemId: item },
  key: item,
  scene: { acquisition: { start: date, end: date } } as SelectedCatalogueScene["scene"],
  queryFingerprint: "query",
  query: { aoi: {} } as SelectedCatalogueScene["query"],
  previewMetadata: null,
});

describe("ChangeAnalysisPanel", () => {
  it("shows measured pair results and publishes an opacity-controlled overlay", async () => {
    const status = {
      job_id: "10000000-0000-4000-8000-000000000090",
      state: "succeeded",
      artifacts: [],
    } as unknown as ProcessingJobStatus;
    const result = {
      job_id: status.job_id,
      classification_artifact_id: "10000000-0000-4000-8000-000000000091",
      sources: [
        {
          temporal_role: "before",
          acquired_at: "2026-01-01T00:00:00Z",
          scene: { provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "BEFORE" },
        },
        {
          temporal_role: "after",
          acquired_at: "2026-02-01T00:00:00Z",
          scene: { provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "AFTER" },
        },
      ],
      method: "calibrated_rgb_rms_reflectance_difference",
      method_version: "8c-calibrated-rgb-rms-v1",
      processing_version: "phase-8f-test",
      area: {
        changed_area_square_metres: 1200,
        changed_percent_of_joint_valid_observed_area: 12,
        observed_coverage_percent_of_aoi: 80,
        joint_valid_observed_area_square_metres: 10000,
        unknown_area_square_metres: 2500,
        unknown_percent_of_aoi: 20,
      },
      alignment_statement: "Registration was assessed as reliable.",
      warnings: [{ code: "seasonal", statement: "Seasonal effects are not isolated." }],
    } as unknown as ChangeResult;
    const client = {
      start: vi.fn().mockResolvedValue(status),
      status: vi.fn(),
      result: vi.fn().mockResolvedValue(result),
    } as unknown as ChangeClient;
    const overlay = vi.fn();
    const onResult = vi.fn();
    const view = render(
      <ChangeAnalysisPanel
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.51, 12.91])}
        comparison={{
          sceneA: scene("BEFORE", "2026-01-01T00:00:00Z"),
          sceneB: scene("AFTER", "2026-02-01T00:00:00Z"),
        }}
        client={client}
        onOverlayChange={overlay}
        onResultChange={onResult}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Start change analysis" }));
    expect(await screen.findByText(/1,200 m²/)).toBeVisible();
    expect(screen.getByText(/80.00%/)).toBeVisible();
    expect(screen.getByText(/BEFORE.*AFTER/)).toBeVisible();
    expect(screen.getByText(/8c-calibrated-rgb-rms-v1/)).toBeVisible();
    expect(screen.getByRole("img", { name: /Change legend/ })).toBeVisible();
    expect(overlay).toHaveBeenLastCalledWith(
      expect.objectContaining({
        artifactId: result.classification_artifact_id,
        opacity: 0.7,
        visible: true,
      }),
    );
    view.rerender(
      <ChangeAnalysisPanel
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.51, 12.91])}
        comparison={{
          sceneA: scene("BEFORE", "2026-01-01T00:00:00Z"),
          sceneB: scene("DIFFERENT_AFTER", "2026-03-01T00:00:00Z"),
        }}
        client={client}
        onOverlayChange={overlay}
        onResultChange={onResult}
      />,
    );
    expect(await screen.findByText("Inputs changed. Run change analysis again.")).toBeVisible();
    expect(onResult).toHaveBeenLastCalledWith(null);
    expect(overlay).toHaveBeenLastCalledWith(null);
  });

  it("shows the durable job failure reason", async () => {
    const failed = {
      job_id: "10000000-0000-4000-8000-000000000092",
      state: "failed",
      safe_error_message: "Registration estimates did not agree.",
      artifacts: [],
    } as unknown as ProcessingJobStatus;
    const client = {
      start: vi.fn().mockResolvedValue(failed),
      status: vi.fn(),
      result: vi.fn(),
    } as unknown as ChangeClient;
    render(
      <ChangeAnalysisPanel
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.51, 12.91])}
        comparison={{
          sceneA: scene("BEFORE", "2026-01-01T00:00:00Z"),
          sceneB: scene("AFTER", "2026-02-01T00:00:00Z"),
        }}
        client={client}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Start change analysis" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Registration estimates did not agree.",
    );
    expect(client.result).not.toHaveBeenCalled();
  });
});
