import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAoiFromBounds } from "@/lib/aoi";
import {
  CatalogueClientError,
  type CatalogueScene,
  type CatalogueSearchRequest,
  type CatalogueSearchResponse,
  type listCatalogueCollections,
  type searchCatalogue,
} from "@/lib/catalog-client";
import { createCatalogueSceneSelection } from "@/lib/scene-selection";
import { ImageryDiscoveryPanel } from "./imagery-discovery-panel";

const mockListCatalogueCollections = vi.fn<typeof listCatalogueCollections>();
const mockSearchCatalogue = vi.fn<typeof searchCatalogue>();
const client = {
  listCollections: mockListCatalogueCollections,
  search: mockSearchCatalogue,
};

const collectionResult = {
  schema_version: "1.0" as const,
  provider: { id: "earth-search", name: "Earth Search by Element 84" },
  items: [
    {
      id: "sentinel-2-c1-l2a",
      title: "Sentinel-2 Collection 1 Level-2A",
      description: null,
      license_name: "proprietary",
      license_url: null,
      temporal_start: "2015-06-27T10:25:31Z",
      temporal_end: null,
      platforms: ["sentinel-2a"],
      instruments: ["msi"],
      spatial_resolutions_metres: [10, 20, 60],
    },
  ],
  returned_count: 1,
};

function scene(id: string): CatalogueScene {
  return {
    provider: { id: "earth-search", name: "Earth Search by Element 84" },
    provider_asset_id: id,
    provider_asset_version: null,
    collection: { id: "sentinel-2-c1-l2a", title: "Sentinel-2 Collection 1 Level-2A" },
    acquisition: { start: "2025-06-01T05:30:00Z", end: "2025-06-01T05:30:00Z" },
    platform: null,
    instruments: [],
    product_type: null,
    processing_level: null,
    footprint: {
      type: "Polygon" as const,
      coordinates: [
        [
          [77.5, 12.9] as [number, number],
          [77.7, 12.9] as [number, number],
          [77.7, 13.05] as [number, number],
          [77.5, 12.9] as [number, number],
        ],
      ],
    },
    bbox: [77.5, 12.9, 77.7, 13.05] as [number, number, number, number],
    cloud_cover: null,
    spatial_resolution: [],
    bands: [],
    polarizations: [],
    preview: null,
    license: null,
    asset_access: { state: "metadata_only" as const, method: "none" as const, reason: null },
    provenance: {
      adapter: "synthetic-test-adapter",
      adapter_version: "1.0",
      retrieved_at: "2025-06-01T06:00:00Z",
      source_record_id: id,
      source_record_version: null,
      metadata_digest_sha256: "b".repeat(64),
      fields: [
        {
          normalized_field: "provider_asset_id",
          source: "provider_record" as const,
          source_field: "id",
          method: null,
        },
      ],
    },
    unavailable_fields: [],
  };
}

function responseFor(
  request: CatalogueSearchRequest,
  items: ReturnType<typeof scene>[],
  nextCursor: string | null,
): CatalogueSearchResponse {
  return {
    schema_version: "1.0",
    search_id: "11111111-1111-4111-8111-111111111111",
    status: "succeeded",
    query: request,
    provider: { id: "earth-search", name: "Earth Search by Element 84" },
    items,
    returned_count: items.length,
    next_cursor: nextCursor,
    searched_at: "2025-06-01T06:00:00Z",
    attributions: ["Synthetic component-test attribution"],
    warnings: [],
  };
}

beforeEach(() => {
  mockListCatalogueCollections.mockReset().mockResolvedValue(collectionResult);
  mockSearchCatalogue.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("imagery discovery panel", () => {
  it("summarizes the missing AOI and keeps search unavailable", async () => {
    render(<ImageryDiscoveryPanel selectedAoi={null} client={client} />);
    expect(
      await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" }),
    ).toBeVisible();
    expect(screen.getByText("No area selected")).toBeVisible();

    expect(screen.getByRole("button", { name: "Search imagery" })).toBeDisabled();
    expect(mockSearchCatalogue).not.toHaveBeenCalled();
  });

  it("searches the exact AOI and renders honest missing-metadata fallbacks", async () => {
    const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    mockSearchCatalogue.mockImplementation(async (request) =>
      responseFor(request, [scene("S2_SYNTHETIC_PANEL_TEST")], "page-2"),
    );
    render(<ImageryDiscoveryPanel selectedAoi={aoi} client={client} />);
    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });

    await userEvent.click(screen.getByRole("button", { name: "Search imagery" }));

    expect(await screen.findByText("S2_SYNTHETIC_PANEL_TEST")).toBeVisible();
    const request = mockSearchCatalogue.mock.calls[0]?.[0];
    expect(request?.aoi).toEqual(aoi.feature.geometry);
    expect(request?.cloud_cover).toEqual({
      max_percent: 30,
      source: "provider_reported",
      include_unknown: false,
    });
    expect(screen.getByText("Thumbnail unavailable")).toBeVisible();
    expect(screen.getAllByText("Not reported").length).toBeGreaterThan(1);
    expect(screen.getByText("Scene cloud metadata")).toBeVisible();
    expect(screen.getByText("1 scene loaded")).toBeVisible();
  });

  it("disregards an outdated response when the AOI changes", async () => {
    const firstAoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    const secondAoi = createAoiFromBounds([78, 13, 78.2, 13.2]);
    let resolveSearch: () => void = () => {};
    mockSearchCatalogue.mockImplementation(
      (request) =>
        new Promise((resolve) => {
          resolveSearch = () => resolve(responseFor(request, [scene("STALE_SCENE")], null));
        }),
    );
    const { rerender } = render(<ImageryDiscoveryPanel selectedAoi={firstAoi} client={client} />);
    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });
    await userEvent.click(screen.getByRole("button", { name: "Search imagery" }));
    expect(screen.getByRole("button", { name: "Searching catalogue..." })).toBeDisabled();

    rerender(<ImageryDiscoveryPanel selectedAoi={secondAoi} client={client} />);
    resolveSearch();

    await waitFor(() => expect(screen.queryByText("STALE_SCENE")).not.toBeInTheDocument());
  });

  it("marks prior-AOI results stale and revalidates the retained scene selection", async () => {
    const firstAoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    const secondAoi = createAoiFromBounds([78, 13, 78.2, 13.2]);
    const onSelectScene = vi.fn();
    const onClearScene = vi.fn();
    mockSearchCatalogue.mockImplementation(async (request) =>
      responseFor(request, [scene("AOI_SELECTION")], null),
    );
    const { rerender } = render(
      <ImageryDiscoveryPanel
        selectedAoi={firstAoi}
        client={client}
        onSelectScene={onSelectScene}
        onClearScene={onClearScene}
      />,
    );
    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });
    await userEvent.click(screen.getByRole("button", { name: "Search imagery" }));
    await userEvent.click(await screen.findByRole("button", { name: "Select scene" }));
    const selection = onSelectScene.mock.calls[0]?.[0];

    rerender(
      <ImageryDiscoveryPanel
        selectedAoi={secondAoi}
        client={client}
        selectedScene={selection}
        onSelectScene={onSelectScene}
        onClearScene={onClearScene}
      />,
    );

    expect(screen.getByText(/belong to the prior query/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Selected" })).toBeDisabled();
    await waitFor(() => expect(onClearScene).toHaveBeenCalledWith(expect.stringMatching(/AOI/)));
  });

  it("presents restored provenance and retained query filters without inventing current results", async () => {
    const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    const storedQuery: CatalogueSearchRequest = {
      schema_version: "1.0",
      provider: "earth-search",
      aoi: aoi.feature.geometry,
      acquisition: { start: "2024-01-02T00:00:00.000Z", end: "2024-03-04T23:59:59.999Z" },
      collections: ["sentinel-2-c1-l2a"],
      cloud_cover: { max_percent: 12, source: "provider_reported", include_unknown: false },
      limit: 6,
      cursor: null,
      sort: "acquired_desc",
    };
    const selection = createCatalogueSceneSelection(
      scene("RESTORED_SELECTION"),
      "stored-query",
      storedQuery,
    );
    const onClearScene = vi.fn();
    const onRefreshScene = vi.fn();

    render(
      <ImageryDiscoveryPanel
        selectedAoi={aoi}
        client={client}
        selectedScene={selection}
        selectionMessage="Current catalogue metadata is unavailable. Preserved metadata may be stale."
        selectionPersistenceState="stale"
        onClearScene={onClearScene}
        onRefreshScene={onRefreshScene}
      />,
    );

    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });
    await waitFor(() => expect(screen.getByLabelText(/Start date/)).toHaveValue("2024-01-02"));
    expect(screen.getByLabelText(/End date/)).toHaveValue("2024-03-04");
    expect(screen.getByRole("spinbutton", { name: /Max scene cloud cover/ })).toHaveValue(12);
    expect(screen.getByText("synthetic-test-adapter 1.0")).toBeVisible();
    expect(screen.getByText(/Preserved metadata may be stale/)).toBeVisible();
    expect(screen.queryByText(/scene loaded/)).not.toBeInTheDocument();
    expect(onClearScene).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Refresh metadata" }));
    expect(onRefreshScene).toHaveBeenCalledOnce();
  });

  it("loads the provider continuation without reporting a catalogue total", async () => {
    const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    mockSearchCatalogue
      .mockImplementationOnce(async (request) =>
        responseFor(request, [scene("SCENE_ONE")], "page-2"),
      )
      .mockImplementationOnce(async (request) => responseFor(request, [scene("SCENE_TWO")], null));
    render(<ImageryDiscoveryPanel selectedAoi={aoi} client={client} />);
    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });
    await userEvent.click(screen.getByRole("button", { name: "Search imagery" }));
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));

    expect(await screen.findByText("SCENE_TWO")).toBeVisible();
    expect(screen.getByText("2 scenes loaded")).toBeVisible();
    expect(mockSearchCatalogue.mock.calls[1]?.[0].cursor).toBe("page-2");
    expect(screen.queryByText(/total/i)).not.toBeInTheDocument();
  });

  it("shows provider errors, retries, and preserves an honest empty page", async () => {
    const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    mockSearchCatalogue
      .mockRejectedValueOnce(
        new CatalogueClientError(
          "provider",
          "The catalogue provider is unavailable.",
          "req-4d",
          true,
        ),
      )
      .mockImplementationOnce(async (request) => responseFor(request, [], null));
    render(<ImageryDiscoveryPanel selectedAoi={aoi} client={client} />);
    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });
    await userEvent.click(screen.getByRole("button", { name: "Search imagery" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("provider is unavailable");
    expect(screen.getByText("Request req-4d")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Retry search" }));

    expect(await screen.findByText("No scenes matched")).toBeVisible();
    expect(screen.getByText(/exact AOI and date range/)).toBeVisible();
  });

  it("cancels a current result association when filters change", async () => {
    const aoi = createAoiFromBounds([77.5, 12.9, 77.7, 13.05]);
    mockSearchCatalogue.mockImplementation(async (request) =>
      responseFor(request, [scene("FILTERED_SCENE")], "page-2"),
    );
    render(<ImageryDiscoveryPanel selectedAoi={aoi} client={client} />);
    await screen.findByRole("option", { name: "Sentinel-2 Collection 1 Level-2A" });
    await userEvent.click(screen.getByRole("button", { name: "Search imagery" }));
    await screen.findByText("FILTERED_SCENE");

    fireEvent.change(screen.getByRole("spinbutton", { name: /Max scene cloud cover/ }), {
      target: { value: "10" },
    });

    expect(screen.getByText(/belong to the prior query/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Load more" })).toBeDisabled();
  });
});
