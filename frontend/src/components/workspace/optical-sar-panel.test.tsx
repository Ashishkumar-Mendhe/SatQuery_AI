import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds } from "@/lib/aoi";
import type {
  OpticalSarClient,
  OpticalSarResult,
  SarPreparation,
  SarScene,
} from "@/lib/optical-sar-client";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";
import { OpticalSarPanel } from "./optical-sar-panel";

const optical = (item = "S2_REAL_ID"): SelectedCatalogueScene => ({
  identity: { providerId: "earth-search", collectionId: "sentinel-2-c1-l2a", itemId: item },
  key: item,
  scene: {
    acquisition: { start: "2024-06-01T00:00:00Z", end: "2024-06-01T00:00:00Z" },
  } as SelectedCatalogueScene["scene"],
  queryFingerprint: "q",
  query: { aoi: {} } as SelectedCatalogueScene["query"],
  previewMetadata: null,
});
const sarSource = { provider: "inpe-bdc", collection: "sentinel-1-rtc-1", item: "S1_REAL_ID" };
const sarScene = {
  source: sarSource,
  acquisition: { start: "2024-06-03T00:00:00Z", end: "2024-06-03T00:00:00Z" },
  polarizations: ["VV"],
  native_resolution_metres: 20,
} as SarScene;
const sarPreparation = {
  preparation_id: "00000000-0000-4000-8000-000000000001",
  source: sarSource,
  acquisition_time: "2024-06-03T00:00:00Z",
  polarization: "VV",
  bounds: [77.5, 12.9, 77.51, 12.91],
  preview_url: "/api/v1/sar/preparations/00000000-0000-4000-8000-000000000001/preview.png",
  display_scaling: "fixed dB display",
  warnings: [],
} as SarPreparation;
const observed = (modality: "optical" | "sar") => ({
  modality,
  source:
    modality === "optical"
      ? { provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "S2_REAL_ID" }
      : sarSource,
  acquired_at: modality === "optical" ? "2024-06-01T00:00:00Z" : "2024-06-03T00:00:00Z",
  layer:
    modality === "sar"
      ? "Sentinel-1 RTC VV gamma-0 power"
      : "Sentinel-2 L2A red surface reflectance",
  measured_value: 0.2,
  units: modality === "optical" ? "1" : "gamma0_power",
  valid_pixels: 80,
  denominator_pixels: 100,
  evidence_bounds: [1, 2, 3, 4],
  evidence_crs: "EPSG:32643",
  statement: `${modality} source measurement`,
});
const result = {
  request_id: "00000000-0000-4000-8000-000000000002",
  job_id: "00000000-0000-4000-8000-000000000003",
  state: "limited",
  answer_kind: "computed_observation_summary",
  answer: "Separate optical and SAR observations; cause not determined.",
  optical: observed("optical"),
  sar: observed("sar"),
  source_evidence: [
    {
      source: observed("optical").source,
      acquired_at: "2024-06-01T00:00:00Z",
      source_version: "fixture-v1",
      preparation_version: null,
      checksum: null,
      polarization: null,
    },
    {
      source: sarSource,
      acquired_at: "2024-06-03T00:00:00Z",
      source_version: null,
      preparation_version: "fixture-sar-v1",
      checksum: "fixture-checksum",
      polarization: "VV",
    },
  ],
  joint_usable_pixels: 70,
  aoi_pixels: 100,
  joint_usable_percent_of_aoi: 70,
  joint_usable_area_square_metres: 28000,
  time_gap_hours: 48,
  alignment_state: "unavailable",
  limitations: ["Independent registration unavailable."],
  processing_version: "9e-observation-v1",
  evidence_artifact_id: "00000000-0000-4000-8000-000000000004",
} as OpticalSarResult;

afterEach(() => vi.unstubAllEnvs());

describe("OpticalSarPanel", () => {
  it("discovers, previews, reports source-bound observations, and invalidates changed scenes", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
    const client = {
      search: vi.fn().mockResolvedValue({ scenes: [sarScene] }),
      prepare: vi.fn().mockResolvedValue(sarPreparation),
      start: vi.fn().mockResolvedValue({ job_id: result.job_id, state: "succeeded" }),
      status: vi.fn(),
      result: vi.fn().mockImplementation(() =>
        Promise.resolve({
          ...result,
          request_id: (client.start as ReturnType<typeof vi.fn>).mock.calls[0][0].request_id,
        }),
      ),
    } as unknown as OpticalSarClient;
    const overlay = vi.fn();
    const onResult = vi.fn();
    const aoi = createAoiFromBounds([77.5, 12.9, 77.51, 12.91]);
    const view = render(
      <OpticalSarPanel
        selectedAoi={aoi}
        selectedScene={optical()}
        onOverlayChange={overlay}
        onResultChange={onResult}
        client={client}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Find SAR scenes" }));
    expect(await screen.findByText(/1 SAR scene/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "View SAR layer" }));
    expect(await screen.findByText(/SAR layer prepared/)).toBeVisible();
    expect(overlay).toHaveBeenLastCalledWith(
      expect.objectContaining({ opacity: 0.6, visible: true }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Analyze optical + SAR" }));
    expect(
      await screen.findByText(/Separate optical and SAR observations; cause not determined/),
    ).toBeVisible();
    expect(onResult).toHaveBeenLastCalledWith(expect.objectContaining({ answer: result.answer }));
    expect(screen.getByText(/70.00% of AOI/)).toBeVisible();
    view.rerender(
      <OpticalSarPanel
        selectedAoi={aoi}
        selectedScene={optical("OTHER")}
        onOverlayChange={overlay}
        onResultChange={onResult}
        client={client}
      />,
    );
    await waitFor(() => expect(onResult).toHaveBeenLastCalledWith(null));
    expect(overlay).toHaveBeenLastCalledWith(null);
  });

  it("shows a safe job failure without fabricating a result", async () => {
    const client = {
      search: vi.fn().mockResolvedValue({ scenes: [sarScene] }),
      prepare: vi.fn().mockResolvedValue(sarPreparation),
      start: vi.fn().mockResolvedValue({
        job_id: result.job_id,
        state: "failed",
        safe_error_message: "INPE raster is unavailable.",
      }),
      status: vi.fn(),
      result: vi.fn(),
    } as unknown as OpticalSarClient;
    render(
      <OpticalSarPanel
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.51, 12.91])}
        selectedScene={optical()}
        onOverlayChange={vi.fn()}
        onResultChange={vi.fn()}
        client={client}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Find SAR scenes" }));
    await screen.findByText(/1 SAR scene/);
    await userEvent.click(screen.getByRole("button", { name: "View SAR layer" }));
    await screen.findByText(/SAR layer prepared/);
    await userEvent.click(screen.getByRole("button", { name: "Analyze optical + SAR" }));
    expect(await screen.findByText("INPE raster is unavailable.")).toBeVisible();
    expect(client.result).not.toHaveBeenCalled();
  });

  it("rejects an apparently matching item with the wrong provider in returned evidence", async () => {
    let startedRequestId: string | null = null;
    const client = {
      search: vi.fn().mockResolvedValue({ scenes: [sarScene] }),
      prepare: vi.fn().mockResolvedValue(sarPreparation),
      start: vi.fn().mockImplementation((body: { request_id: string }) => {
        startedRequestId = body.request_id;
        return Promise.resolve({ job_id: result.job_id, state: "succeeded" });
      }),
      status: vi.fn(),
      result: vi.fn().mockImplementation(() =>
        Promise.resolve({
          ...result,
          request_id: startedRequestId,
          sar: {
            ...result.sar,
            source: { ...sarSource, provider: "another-provider" },
          },
        }),
      ),
    } as unknown as OpticalSarClient;
    const onResult = vi.fn();
    render(
      <OpticalSarPanel
        selectedAoi={createAoiFromBounds([77.5, 12.9, 77.51, 12.91])}
        selectedScene={optical()}
        onOverlayChange={vi.fn()}
        onResultChange={onResult}
        client={client}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Find SAR scenes" }));
    await screen.findByText(/1 SAR scene/);
    await userEvent.click(screen.getByRole("button", { name: "View SAR layer" }));
    await screen.findByText(/SAR layer prepared/);
    await userEvent.click(screen.getByRole("button", { name: "Analyze optical + SAR" }));
    expect(await screen.findByText(/Result provenance does not match/)).toBeVisible();
    expect(onResult).not.toHaveBeenCalledWith(expect.objectContaining({ answer: result.answer }));
  });
});
