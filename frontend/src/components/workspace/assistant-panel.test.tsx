import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantPanel } from "./assistant-panel";
import { createAoiFromBounds } from "@/lib/aoi";
import type { ChangeClient, ChangeResult } from "@/lib/change-client";
import type { GeoAgentClient } from "@/lib/geoagent-client";
import type { InferenceClient, InferenceJobStatus } from "@/lib/inference-client";
import type { InferenceGroundingOverlay } from "@/lib/inference-grounding-map-layer";
import type { SarScene } from "@/lib/optical-sar-client";
import type { SelectedCatalogueScene } from "@/lib/scene-selection";

const aoi = createAoiFromBounds([77.5, 12.9, 77.51, 12.91]);
const conversationId = "10000000-0000-4000-8000-000000000001";
const scene = (item = "SYNTHETIC_SCENE"): SelectedCatalogueScene => ({
  identity: { providerId: "earth-search", collectionId: "sentinel-2-c1-l2a", itemId: item },
  key: JSON.stringify(["earth-search", "sentinel-2-c1-l2a", item]),
  scene: {
    acquisition: { start: "2026-01-12T10:00:00Z", end: "2026-01-12T10:00:00Z" },
  } as SelectedCatalogueScene["scene"],
  queryFingerprint: "synthetic-query",
  query: { aoi: aoi.feature.geometry } as SelectedCatalogueScene["query"],
  previewMetadata: null,
});

function completed(
  operation: "visual_question_answering" | "image_captioning" | "referring_grounding",
): InferenceJobStatus {
  const chipId = "10000000-0000-4000-8000-000000000010";
  const source = {
    provider: "earth-search",
    collection: "sentinel-2-c1-l2a",
    item: "SYNTHETIC_SCENE",
  };
  const model = {
    provider: "fixture",
    model: "bounded-model",
    version: "v1",
    adapter_version: "test-v1",
    runtime: "local",
    weights: "public_checkpoint",
    licence_basis: "fixture",
    execution_hardware: "test",
  };
  const evidence = {
    request: { request_id: "10000000-0000-4000-8000-000000000011", operation, scene: source },
    source_chip: {
      chip_id: chipId,
      scene: source,
      acquired_at: "2026-01-12T10:00:00Z",
      checksum_sha256: "a".repeat(64),
      media_type: "image/png",
      byte_size: 120,
      width: 16,
      height: 16,
      band_order: ["red", "green", "blue"],
      rendering: { method: "fixed_linear", per_image_normalization: false },
      pixel_to_map: { crs: "EPSG:32643", affine: [10, 0, 770000, 0, -10, 1450000] },
      footprint_wgs84: { type: "Polygon", coordinates: [] },
      phase6_quality: { readiness: { state: "ready", explanation: "Ready" }, quality_checks: [] },
    },
    input_chip_artifact: {
      artifact_id: "10000000-0000-4000-8000-000000000012",
      kind: "inference_chip",
      media_type: "image/png",
      checksum_sha256: "a".repeat(64),
      byte_size: 120,
      access: { state: "available", reason: null },
    },
    quality_decision: { state: "proceed", reason: "Checks passed.", required_check_ids: [] },
    execution_state: "completed",
    execution_reason: null,
    answer:
      operation === "referring_grounding"
        ? null
        : {
            task: operation,
            source_chip_id: chipId,
            availability: "available",
            answer:
              operation === "image_captioning"
                ? "A satellite view of vegetation."
                : "Vegetation is visible.",
            reason: null,
            model,
            quality_warnings: [
              {
                code: "limit",
                severity: "warning",
                message: "Model interpretation may be wrong.",
                corrective_action: "Inspect source.",
              },
            ],
            calibrated_confidence: null,
          },
    grounding:
      operation !== "referring_grounding"
        ? null
        : {
            source_chip_id: chipId,
            status: "detected",
            model,
            reason: null,
            candidates: [
              {
                candidate_index: 0,
                label: "vegetation",
                model_score: 0.52,
                score_meaning: "uncalibrated_model_relevance",
                image_chip_box: {
                  coordinate_space: "image_pixel",
                  source_chip_id: chipId,
                  image_width: 16,
                  image_height: 16,
                  x_min: 2,
                  y_min: 3,
                  x_max: 10,
                  y_max: 12,
                },
                map_footprint: {
                  coordinate_space: "projected_map",
                  source_chip_id: chipId,
                  crs: "EPSG:32643",
                  rings: [
                    [
                      [770020, 1449970],
                      [770100, 1449970],
                      [770100, 1449880],
                      [770020, 1449880],
                      [770020, 1449970],
                    ],
                  ],
                },
              },
            ],
          },
    interpretation_disclaimer: "evidence_not_validation",
    interpretation_notice: "Evidence identifies pixels; it does not prove interpretation.",
  };
  return {
    schema_version: "1.0",
    job_id: "10000000-0000-4000-8000-000000000013",
    request_id: evidence.request.request_id,
    operation,
    state: "succeeded",
    submitted_at: "2026-01-12T10:01:00Z",
    started_at: "2026-01-12T10:01:01Z",
    finished_at: "2026-01-12T10:01:02Z",
    attempt: 1,
    current_stage: "evidence_committed",
    progress: { completed_units: 4, total_units: 4, units: "stages" },
    artifacts: [evidence.input_chip_artifact],
    result: evidence,
    error_code: null,
    safe_error_message: null,
  } as unknown as InferenceJobStatus;
}

function agent(status: InferenceJobStatus = completed("visual_question_answering")) {
  const get = vi.fn().mockResolvedValue({
    conversation_id: conversationId,
    selection_revision: 0,
    selection: { aoi: null, scenes: [] },
  });
  const turn = vi.fn().mockImplementation(async (_id, body) => ({
    conversation_id: conversationId,
    request_id: body.request_id,
    status: "executed",
    message: "Analysis completed.",
    selection_revision: 1,
    selection: body.selection,
    missing_reference: null,
    resolved_result: null,
    execution: {
      request_id: body.request_id,
      conversation_id: conversationId,
      status: "completed",
      summary: {
        intended_analysis: "single_image",
        tool: "inference_vqa",
        input_scenes: [body.selection.scenes[0].source],
        aoi_sha256: "a".repeat(64),
        status: "completed",
        job_id: status.job_id,
        result_id: "10000000-0000-4000-8000-000000000012",
      },
      job_id: status.job_id,
      result_id: "10000000-0000-4000-8000-000000000012",
      output: status,
      cancel_path: null,
      error_code: null,
      message: "Done",
      retry_same_request_id: false,
    },
  }));
  return { get, turn };
}

function Harness({
  client,
  selected = scene(),
  selectedAoi = aoi,
  onOverlay = () => {},
  onSelectionAction = () => {},
  initialDraft = "What is visible?",
  comparison = null,
  sarSelection = null,
  change,
  inference,
  onOpenChangeResult = () => {},
}: {
  client: GeoAgentClient;
  selected?: SelectedCatalogueScene | null;
  selectedAoi?: typeof aoi | null;
  onOverlay?: (overlay: InferenceGroundingOverlay | null) => void;
  onSelectionAction?: (action: string) => void;
  initialDraft?: string;
  comparison?: { sceneA: SelectedCatalogueScene; sceneB: SelectedCatalogueScene } | null;
  sarSelection?: { scene: SarScene; polarization: string } | null;
  change?: ChangeClient;
  inference?: InferenceClient;
  onOpenChangeResult?: (result: ChangeResult) => void;
}) {
  const [draft, setDraft] = useState(initialDraft);
  const [tab, setTab] = useState<"answer" | "evidence" | "activity">("answer");
  return (
    <AssistantPanel
      visible
      draft={draft}
      activeTab={tab}
      selectedAoi={selectedAoi}
      selectedScene={selected}
      comparison={comparison}
      sarSelection={sarSelection}
      onDraftChange={setDraft}
      onTabChange={setTab}
      onClose={() => {}}
      onGroundingOverlayChange={onOverlay}
      onSelectionAction={onSelectionAction}
      onOpenChangeResult={onOpenChangeResult}
      client={client}
      change={change}
      inference={inference}
    />
  );
}

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  sessionStorage.clear();
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

describe("GeoAgent assistant workspace", () => {
  it("submits current AOI and scene to the conversation API and renders actual evidence", async () => {
    const mock = agent();
    render(<Harness client={mock as unknown as GeoAgentClient} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Vegetation is visible.")).toBeVisible();
    expect(screen.getByText(/bounded-model/)).toBeVisible();
    expect(screen.getByText(/Model interpretation may be wrong/)).toBeVisible();
    expect(mock.turn).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        message: "What is visible?",
        selection: expect.objectContaining({
          aoi: aoi.feature.geometry,
          scenes: [
            expect.objectContaining({
              source: {
                provider: "earth-search",
                collection: "sentinel-2-c1-l2a",
                item: "SYNTHETIC_SCENE",
              },
            }),
          ],
        }),
      }),
      expect.any(AbortSignal),
    );
  });

  it("requests captioning through the conversation, without submitting draft text", async () => {
    const mock = agent(completed("image_captioning"));
    render(<Harness client={mock as unknown as GeoAgentClient} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "Caption" }));
    await user.click(screen.getByRole("button", { name: "Generate caption" }));
    expect(await screen.findByText("A satellite view of vegetation.")).toBeVisible();
    expect(mock.turn.mock.calls[0][1].message).toBe("Caption this image.");
  });

  it("keeps grounding tied to the source chip and toggles its overlay", async () => {
    const mock = agent(completed("referring_grounding"));
    const overlay = vi.fn<(overlay: InferenceGroundingOverlay | null) => void>();
    render(
      <Harness
        client={mock as unknown as GeoAgentClient}
        onOverlay={overlay}
        initialDraft="vegetation"
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "Locate" }));
    await user.click(screen.getByRole("button", { name: "Locate feature" }));
    expect(await screen.findByText(/1 validated candidate region/)).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: "Show validated region on map" }));
    expect(overlay).toHaveBeenLastCalledWith(
      expect.objectContaining({ sourceChipId: "10000000-0000-4000-8000-000000000010" }),
    );
    expect(mock.turn.mock.calls[0][1].message).toBe("Where is vegetation?");
  });

  it("offers a selection action for missing AOI and pair inputs", async () => {
    const mock = agent();
    const action = vi.fn();
    const view = render(
      <Harness
        client={mock as unknown as GeoAgentClient}
        selectedAoi={null}
        onSelectionAction={action}
      />,
    );
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
    await userEvent.setup().click(screen.getByRole("button", { name: "Choose an AOI" }));
    expect(action).toHaveBeenCalledWith("aoi");
    await userEvent.setup().clear(screen.getByRole("textbox", { name: "Question" }));
    await userEvent
      .setup()
      .type(screen.getByRole("textbox", { name: "Question" }), "What changed?");
    view.rerender(
      <Harness client={mock as unknown as GeoAgentClient} onSelectionAction={action} />,
    );
    expect(screen.getByRole("button", { name: "Select two dates" })).toBeVisible();
    expect(mock.turn).not.toHaveBeenCalled();
  });

  it("routes a two-date question to a committed change result and opens its referenced map layer", async () => {
    const before = scene("BEFORE");
    const after = scene("AFTER");
    before.scene.acquisition.start = "2026-01-01T00:00:00Z";
    after.scene.acquisition.start = "2026-02-01T00:00:00Z";
    const result = {
      schema_version: "1.0",
      job_id: "10000000-0000-4000-8000-000000000090",
      sources: [
        {
          temporal_role: "before",
          acquired_at: before.scene.acquisition.start,
          scene: { provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "BEFORE" },
        },
        {
          temporal_role: "after",
          acquired_at: after.scene.acquisition.start,
          scene: { provider: "earth-search", collection: "sentinel-2-c1-l2a", item: "AFTER" },
        },
      ],
      aoi: aoi.feature.geometry,
      grid: { bounds: aoi.bounds },
      method: "calibrated_rgb_rms_reflectance_difference",
      method_version: "v1",
      threshold: 0.1,
      threshold_units: "reflectance",
      area: {
        changed_area_square_metres: 1200,
        changed_percent_of_joint_valid_observed_area: 12,
        joint_valid_observed_area_square_metres: 10000,
        observed_coverage_percent_of_aoi: 80,
        unknown_area_square_metres: 2500,
        unknown_percent_of_aoi: 20,
      },
      alignment_statement: "Registration assessed.",
      warnings: [{ code: "seasonal", statement: "Seasonal effects are not isolated." }],
      statements: ["1200 m² of observed spectral change."],
      cause_or_land_cover_category: "not_determined",
      classification_artifact_id: "10000000-0000-4000-8000-000000000091",
      processing_version: "phase-8-test",
    } as ChangeResult;
    const mock = agent();
    mock.turn.mockImplementation(async (_id, body) => ({
      conversation_id: conversationId,
      request_id: body.request_id,
      status: "executed",
      message: "Completed.",
      selection_revision: 1,
      selection: body.selection,
      missing_reference: null,
      resolved_result: null,
      execution: {
        request_id: body.request_id,
        conversation_id: conversationId,
        status: "completed",
        summary: {
          intended_analysis: "before_after_change",
          tool: "optical_change",
          input_scenes: body.selection.scenes.map((s: { source: object }) => s.source),
          aoi_sha256: "a".repeat(64),
          status: "completed",
          job_id: result.job_id,
          result_id: result.classification_artifact_id,
        },
        job_id: result.job_id,
        result_id: result.classification_artifact_id,
        output: result,
        cancel_path: null,
        error_code: null,
        message: "Completed.",
        retry_same_request_id: false,
      },
    }));
    const open = vi.fn();
    render(
      <Harness
        client={mock as unknown as GeoAgentClient}
        selected={after}
        comparison={{ sceneA: before, sceneB: after }}
        initialDraft="What changed between these dates?"
        onOpenChangeResult={open}
      />,
    );
    expect(screen.getByRole("button", { name: "Show that change on the map" })).toBeVisible();
    await userEvent.setup().click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("1200 m² of observed spectral change.")).toBeVisible();
    expect(mock.turn.mock.calls[0][1].selection.scenes).toHaveLength(2);
    await userEvent.setup().click(screen.getByRole("button", { name: "Open change layer on map" }));
    expect(open).toHaveBeenCalledWith(result);
  });

  it("suggests optical/SAR questions only when a SAR scene is selected", () => {
    const mock = agent();
    const sar = {
      source: { provider: "inpe-bdc", collection: "sentinel-1-rtc", item: "SAR_SCENE" },
      acquisition: { start: "2026-01-13T10:00:00Z", end: "2026-01-13T10:01:00Z" },
      polarizations: ["VV"],
      native_resolution_metres: 20,
    } as SarScene;
    render(
      <Harness
        client={mock as unknown as GeoAgentClient}
        sarSelection={{ scene: sar, polarization: "VV" }}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Summarize optical and SAR observations." }),
    ).toBeVisible();
  });

  it("reports the actual queued job and stage before showing its committed answer", async () => {
    const completedStatus = completed("visual_question_answering");
    const mock = agent(completedStatus);
    mock.turn.mockImplementation(async (_id, body) => ({
      conversation_id: conversationId,
      request_id: body.request_id,
      status: "executed",
      message: "Queued.",
      selection_revision: 1,
      selection: body.selection,
      missing_reference: null,
      resolved_result: null,
      execution: {
        request_id: body.request_id,
        conversation_id: conversationId,
        status: "submitted",
        summary: {
          intended_analysis: "single_image_question",
          tool: "inference_vqa",
          input_scenes: [body.selection.scenes[0].source],
          aoi_sha256: "a".repeat(64),
          status: "submitted",
          job_id: completedStatus.job_id,
          result_id: null,
        },
        job_id: completedStatus.job_id,
        result_id: null,
        output: { ...completedStatus, state: "queued", result: null },
        cancel_path: "/api/v1/inference/jobs",
        error_code: null,
        message: "Queued.",
        retry_same_request_id: false,
      },
    }));
    const status = vi.fn().mockResolvedValue(completedStatus);
    render(
      <Harness
        client={mock as unknown as GeoAgentClient}
        inference={{ status } as unknown as InferenceClient}
      />,
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText(/inference_vqa: submitted/)).toBeVisible();
    expect(await screen.findByText("Vegetation is visible.")).toBeVisible();
    expect(status).toHaveBeenCalledWith(completedStatus.job_id, expect.any(AbortSignal));
  });

  it("keeps the verified conversation selection for a same-area follow-up", async () => {
    const mock = agent();
    mock.get
      .mockResolvedValueOnce({
        conversation_id: conversationId,
        selection_revision: 0,
        selection: { aoi: null, scenes: [] },
      })
      .mockResolvedValueOnce({
        conversation_id: conversationId,
        selection_revision: 1,
        selection: { aoi: aoi.feature.geometry, scenes: [] },
      });
    mock.turn
      .mockResolvedValueOnce({
        status: "clarification_required",
        message: "Name the observation to inspect.",
      })
      .mockResolvedValueOnce({
        status: "clarification_required",
        message: "Name the observation to inspect.",
      });
    const user = userEvent.setup();
    render(<Harness client={mock as unknown as GeoAgentClient} />);
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText("Name the observation to inspect.")).toBeVisible();
    await user.clear(screen.getByRole("textbox", { name: "Question" }));
    await user.type(screen.getByRole("textbox", { name: "Question" }), "What about this area?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    await waitFor(() => expect(mock.turn).toHaveBeenCalledTimes(2));
    expect(mock.turn.mock.calls[1][1].selection).toBeUndefined();
    expect(mock.turn.mock.calls[1][1].expected_selection_revision).toBe(1);
  });

  it("retains the draft for retry and marks an answer stale on selection change", async () => {
    const mock = agent();
    mock.turn.mockRejectedValueOnce(new Error("Temporary service failure."));
    const view = render(<Harness client={mock as unknown as GeoAgentClient} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Ask question" }));
    expect(await screen.findByText(/Temporary service failure/)).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveValue("What is visible?");
    await user.click(screen.getByRole("button", { name: "Retry analysis" }));
    expect(await screen.findByText("Vegetation is visible.")).toBeVisible();
    view.rerender(
      <Harness client={mock as unknown as GeoAgentClient} selected={scene("OTHER_SCENE")} />,
    );
    await waitFor(() =>
      expect(
        screen.getByText(/previous result is outdated|answer belongs to the previous imagery/i),
      ).toBeVisible(),
    );
  });
});
