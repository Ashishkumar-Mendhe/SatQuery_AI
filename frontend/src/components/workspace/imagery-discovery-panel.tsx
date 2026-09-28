"use client";

import Image from "next/image";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "@/components/icon";
import { formatAoiArea, formatAoiBounds, type SelectedAoi } from "@/lib/aoi";
import {
  CatalogueClientError,
  type CatalogueCollection,
  type CatalogueScene,
  type CatalogueSearchRequest,
  listCatalogueCollections,
  searchCatalogue,
} from "@/lib/catalog-client";
import {
  type CatalogueSceneContext,
  catalogueSceneKey,
  createCatalogueSceneSelection,
  type SelectedCatalogueScene,
} from "@/lib/scene-selection";
import type { SceneSelectionPersistenceState } from "@/lib/use-scene-selection-draft";

const PAGE_SIZE = 6;

type RequestMode = "search" | "load_more";
type RequestState =
  | { state: "idle" }
  | { state: "loading"; mode: RequestMode }
  | { state: "error"; mode: RequestMode; message: string; requestId: string | null };

interface ResultSet {
  fingerprint: string;
  aoiName: string;
  query: CatalogueSearchRequest;
  items: CatalogueScene[];
  nextCursor: string | null;
  searchedAt: string;
  attributions: string[];
}

export interface ImageryDiscoveryClient {
  listCollections: typeof listCatalogueCollections;
  search: typeof searchCatalogue;
}

const defaultClient: ImageryDiscoveryClient = {
  listCollections: listCatalogueCollections,
  search: searchCatalogue,
};
const ignoreSceneContext = (_context: CatalogueSceneContext | null) => {};
const ignoreSceneKey = (_sceneKey: string | null) => {};
const ignoreSceneSelection = (_selection: SelectedCatalogueScene) => {};
const ignoreClearScene = (_message?: string) => {};
const ignoreFitScene = (_scene: CatalogueScene) => {};

function defaultDateRange() {
  const end = new Date();
  const start = new Date(end);
  start.setUTCFullYear(start.getUTCFullYear() - 1);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10),
  };
}

function queryFingerprint(
  selectedAoi: SelectedAoi | null,
  collectionId: string,
  startDate: string,
  endDate: string,
  cloudThreshold: string,
) {
  return JSON.stringify({
    geometry: selectedAoi?.feature.geometry ?? null,
    collectionId,
    startDate,
    endDate,
    cloudThreshold: cloudThreshold === "" ? "" : String(Number(cloudThreshold)),
  });
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

function metadataList(values: string[]) {
  return values.length > 0 ? values.join(", ") : "Not reported";
}

function assetAccessLabel(scene: CatalogueScene) {
  switch (scene.asset_access.state) {
    case "metadata_only":
      return "Metadata only";
    case "provider_accessible":
      return "Provider assets";
    case "requires_authorization":
      return "Authorization required";
    case "requires_purchase":
      return "Purchase required";
    case "unavailable":
      return "Assets unavailable";
    default:
      return "Access unknown";
  }
}

function SceneCard({
  scene,
  sceneKey,
  current,
  selected,
  hovered,
  previewFailed,
  onPreviewError,
  onHover,
  onSelect,
  onFit,
}: {
  scene: CatalogueScene;
  sceneKey: string;
  current: boolean;
  selected: boolean;
  hovered: boolean;
  previewFailed: boolean;
  onPreviewError: () => void;
  onHover: (sceneKey: string | null) => void;
  onSelect: () => void;
  onFit: () => void;
}) {
  const previewHref =
    !previewFailed &&
    scene.preview?.href &&
    (scene.preview.access === "public" || scene.preview.access === "temporary")
      ? scene.preview.href
      : null;
  return (
    <li
      className={`imagery-scene-card ${selected ? "selected" : ""} ${hovered ? "hovered" : ""}`}
      onMouseEnter={() => onHover(sceneKey)}
      onMouseLeave={() => onHover(null)}
      onFocusCapture={() => onHover(sceneKey)}
      onBlurCapture={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) onHover(null);
      }}
    >
      <div className="imagery-preview">
        {previewHref ? (
          <Image
            src={previewHref}
            alt={`Provider thumbnail for ${scene.provider_asset_id}`}
            fill
            sizes="18rem"
            unoptimized
            onError={onPreviewError}
          />
        ) : (
          <div className="imagery-preview-missing">
            <Icon name="evidence" />
            <span>Thumbnail unavailable</span>
          </div>
        )}
        <span className="imagery-access-badge">{assetAccessLabel(scene)}</span>
      </div>
      <div className="imagery-card-body">
        <div className="imagery-card-heading">
          <div>
            <p className="imagery-card-kicker">Acquired in UTC</p>
            <h4 className="imagery-card-date">{formatDate(scene.acquisition.start)}</h4>
          </div>
          <span className="imagery-card-provider">{scene.provider.name}</span>
        </div>
        <p className="imagery-card-id" title={scene.provider_asset_id}>
          {scene.provider_asset_id}
        </p>
        <dl>
          <div>
            <dt>Collection</dt>
            <dd>{scene.collection.title ?? scene.collection.id}</dd>
          </div>
          <div>
            <dt>Platform</dt>
            <dd>{scene.platform ?? "Not reported"}</dd>
          </div>
          <div>
            <dt>Instruments</dt>
            <dd>{metadataList(scene.instruments)}</dd>
          </div>
          <div>
            <dt>Processing</dt>
            <dd>{scene.processing_level ?? "Not reported"}</dd>
          </div>
          <div>
            <dt>Scene cloud metadata</dt>
            <dd>
              {scene.cloud_cover ? `${scene.cloud_cover.percent.toFixed(1)}%` : "Not reported"}
            </dd>
          </div>
        </dl>
        <div className="imagery-card-actions">
          <button type="button" aria-pressed={selected} disabled={!current} onClick={onSelect}>
            {selected ? "Selected" : "Select scene"}
          </button>
          <button type="button" onClick={onFit}>
            Fit scene
          </button>
        </div>
      </div>
    </li>
  );
}

function SceneDetails({
  selection,
  persistenceState,
  previewFailed,
  onPreviewError,
  onClear,
  onFit,
  onRefresh,
  onOpen,
  onAssignComparison,
  openInViewer,
  viewerLoading,
}: {
  selection: SelectedCatalogueScene;
  persistenceState: SceneSelectionPersistenceState;
  previewFailed: boolean;
  onPreviewError: () => void;
  onClear: () => void;
  onFit: () => void;
  onRefresh: () => void;
  onOpen: () => void;
  onAssignComparison: (slot: "A" | "B") => void;
  openInViewer: boolean;
  viewerLoading: boolean;
}) {
  const { scene } = selection;
  const previewMetadata = selection.previewMetadata;
  const previewHref =
    !previewFailed &&
    scene.preview?.href &&
    (scene.preview.access === "public" || scene.preview.access === "temporary")
      ? scene.preview.href
      : null;
  return (
    <section className="scene-details" aria-labelledby="scene-details-title">
      <div className="scene-details-heading">
        <div>
          <p className="panel-kicker">Selected catalogue scene</p>
          <h3 id="scene-details-title">{formatDate(scene.acquisition.start)}</h3>
        </div>
        <div className="scene-details-heading-actions">
          <button type="button" disabled={persistenceState === "refreshing"} onClick={onRefresh}>
            {persistenceState === "refreshing" ? "Refreshing..." : "Refresh metadata"}
          </button>
          <button type="button" onClick={onClear}>
            Clear
          </button>
        </div>
      </div>
      <div className="scene-details-preview">
        {previewHref ? (
          <Image
            src={previewHref}
            alt={`Provider preview for ${scene.provider_asset_id}`}
            fill
            sizes="18rem"
            unoptimized
            onError={onPreviewError}
          />
        ) : (
          <div className="imagery-preview-missing">
            <Icon name="evidence" />
            <span>Preview unavailable</span>
          </div>
        )}
      </div>
      <p className="scene-preview-note">
        Provider preview only. It is not georeferenced or drawn over the map.
      </p>
      <p className="scene-details-id" title={scene.provider_asset_id}>
        {scene.provider_asset_id}
      </p>
      <dl>
        <div>
          <dt>Provider</dt>
          <dd>{scene.provider.name}</dd>
        </div>
        <div>
          <dt>Collection</dt>
          <dd>{scene.collection.title ?? scene.collection.id}</dd>
        </div>
        <div>
          <dt>Acquisition</dt>
          <dd>{formatTimestamp(scene.acquisition.start)} UTC</dd>
        </div>
        <div>
          <dt>Search dates</dt>
          <dd>
            {formatDate(selection.query.acquisition.start)} to{" "}
            {formatDate(selection.query.acquisition.end)} UTC
          </dd>
        </div>
        <div>
          <dt>Platform / sensor</dt>
          <dd>
            {scene.platform ?? "Not reported"} / {metadataList(scene.instruments)}
          </dd>
        </div>
        <div>
          <dt>Scene cloud metadata</dt>
          <dd>{scene.cloud_cover ? `${scene.cloud_cover.percent.toFixed(1)}%` : "Not reported"}</dd>
        </div>
        <div>
          <dt>Resolution</dt>
          <dd>
            {scene.spatial_resolution.length > 0
              ? scene.spatial_resolution.map((value) => `${value.value} m`).join(", ")
              : "Not reported"}
          </dd>
        </div>
        <div>
          <dt>Bounds</dt>
          <dd>{scene.bbox.map((value) => value.toFixed(4)).join(", ")}</dd>
        </div>
        <div>
          <dt>Access</dt>
          <dd>{assetAccessLabel(scene)}</dd>
        </div>
        <div>
          <dt>Preview role / type</dt>
          <dd>
            {previewMetadata
              ? `${previewMetadata.purpose} / ${previewMetadata.media_type ?? "type not reported"}`
              : "Not reported"}
          </dd>
        </div>
        <div>
          <dt>Licence</dt>
          <dd>
            {scene.license
              ? `${scene.license.name}; analytical use ${
                  scene.license.permits_analytical_use === null
                    ? "not reported"
                    : scene.license.permits_analytical_use
                      ? "reported permitted"
                      : "reported not permitted"
                }`
              : "Not reported"}
          </dd>
        </div>
        <div>
          <dt>Metadata retrieved</dt>
          <dd>{formatTimestamp(scene.provenance.retrieved_at)} UTC</dd>
        </div>
        <div>
          <dt>Source record</dt>
          <dd>
            {scene.provenance.source_record_id}
            {scene.provenance.source_record_version
              ? ` (${scene.provenance.source_record_version})`
              : ""}
          </dd>
        </div>
        <div>
          <dt>Adapter</dt>
          <dd>
            {scene.provenance.adapter} {scene.provenance.adapter_version}
          </dd>
        </div>
      </dl>
      <button className="scene-details-fit" type="button" onClick={onFit}>
        Fit scene on map
      </button>
      <button
        className="scene-details-open"
        type="button"
        disabled={viewerLoading}
        onClick={onOpen}
      >
        {viewerLoading ? "Opening imagery…" : openInViewer ? "Reload imagery" : "Open in viewer"}
      </button>
      <fieldset className="scene-comparison-assign">
        <legend className="sr-only">Assign selected scene to comparison</legend>
        <button type="button" onClick={() => onAssignComparison("A")}>
          Assign to comparison A
        </button>
        <button type="button" onClick={() => onAssignComparison("B")}>
          Assign to comparison B
        </button>
      </fieldset>
      <p className="scene-selection-boundary">
        Selecting a scene opens its georeferenced raster tiles. Displayed imagery remains
        visualization-only; analysis is unavailable.
      </p>
    </section>
  );
}

export function ImageryDiscoveryPanel({
  selectedAoi,
  client = defaultClient,
  selectedScene = null,
  hoveredSceneKey = null,
  selectionMessage = null,
  selectionPersistenceState = "empty",
  onSceneContextChange = ignoreSceneContext,
  onHoverScene = ignoreSceneKey,
  onSelectScene = ignoreSceneSelection,
  onClearScene = ignoreClearScene,
  onRefreshScene = () => {},
  onOpenScene = () => {},
  onAssignComparison = () => {},
  viewerSceneKey = null,
  viewerLoading = false,
  onFitScene = ignoreFitScene,
}: {
  selectedAoi: SelectedAoi | null;
  client?: ImageryDiscoveryClient;
  selectedScene?: SelectedCatalogueScene | null;
  hoveredSceneKey?: string | null;
  selectionMessage?: string | null;
  selectionPersistenceState?: SceneSelectionPersistenceState;
  onSceneContextChange?: (context: CatalogueSceneContext | null) => void;
  onHoverScene?: (sceneKey: string | null) => void;
  onSelectScene?: (selection: SelectedCatalogueScene) => void;
  onClearScene?: (message?: string) => void;
  onRefreshScene?: () => void;
  onOpenScene?: (selection: SelectedCatalogueScene) => void;
  onAssignComparison?: (selection: SelectedCatalogueScene, slot: "A" | "B") => void;
  viewerSceneKey?: string | null;
  viewerLoading?: boolean;
  onFitScene?: (scene: CatalogueScene) => void;
}) {
  const initialDates = useMemo(defaultDateRange, []);
  const [collections, setCollections] = useState<CatalogueCollection[]>([]);
  const [collectionId, setCollectionId] = useState("");
  const [collectionState, setCollectionState] = useState<"loading" | "ready" | "error">("loading");
  const [collectionMessage, setCollectionMessage] = useState<string | null>(null);
  const [startDate, setStartDate] = useState(initialDates.start);
  const [endDate, setEndDate] = useState(initialDates.end);
  const [cloudThreshold, setCloudThreshold] = useState("30");
  const [validationMessage, setValidationMessage] = useState<string | null>(null);
  const [requestState, setRequestState] = useState<RequestState>({ state: "idle" });
  const [resultSet, setResultSet] = useState<ResultSet | null>(null);
  const [failedPreviews, setFailedPreviews] = useState<Set<string>>(() => new Set());
  const activeRequest = useRef<{ id: number; controller: AbortController } | null>(null);
  const collectionRequest = useRef<AbortController | null>(null);
  const requestSequence = useRef(0);
  const currentFingerprint = queryFingerprint(
    selectedAoi,
    collectionId,
    startDate,
    endDate,
    cloudThreshold,
  );
  const fingerprintRef = useRef(currentFingerprint);
  const hydratedSelectionKey = useRef<string | null>(null);
  const selectedCollection = collections.find((collection) => collection.id === collectionId);
  const cloudApplicable = selectedCollection?.id === "sentinel-2-c1-l2a";
  const resultIsCurrent = resultSet?.fingerprint === currentFingerprint;

  useEffect(() => {
    onSceneContextChange(
      resultSet
        ? {
            fingerprint: resultSet.fingerprint,
            isCurrent: resultIsCurrent,
            scenes: resultSet.items,
            query: resultSet.query,
            hasMore: resultSet.nextCursor !== null,
          }
        : null,
    );
  }, [onSceneContextChange, resultIsCurrent, resultSet]);

  useEffect(() => {
    if (!selectedScene || resultSet || hydratedSelectionKey.current === selectedScene.key) return;
    hydratedSelectionKey.current = selectedScene.key;
    setCollectionId(selectedScene.query.collections[0] ?? selectedScene.identity.collectionId);
    setStartDate(selectedScene.query.acquisition.start.slice(0, 10));
    setEndDate(selectedScene.query.acquisition.end.slice(0, 10));
    setCloudThreshold(String(selectedScene.query.cloud_cover?.max_percent ?? 30));
  }, [resultSet, selectedScene]);

  useEffect(() => {
    if (
      selectedScene &&
      resultSet &&
      collectionState === "ready" &&
      collectionId &&
      selectedScene.queryFingerprint !== currentFingerprint
    ) {
      onClearScene(
        "Scene selection cleared because the AOI or search filters changed. Search to select again.",
      );
    }
  }, [collectionId, collectionState, currentFingerprint, onClearScene, resultSet, selectedScene]);

  const loadCollections = useCallback(async () => {
    collectionRequest.current?.abort();
    const controller = new AbortController();
    collectionRequest.current = controller;
    setCollectionState("loading");
    setCollectionMessage(null);
    try {
      const response = await client.listCollections(controller.signal);
      setCollections(response.items);
      setCollectionId((current) =>
        response.items.some((collection) => collection.id === current)
          ? current
          : (response.items[0]?.id ?? ""),
      );
      setCollectionState("ready");
      if (response.items.length === 0) setCollectionMessage("No collections are available.");
    } catch (error) {
      if (error instanceof CatalogueClientError && error.kind === "cancelled") return;
      setCollectionState("error");
      setCollectionMessage(
        error instanceof Error ? error.message : "Collections could not be loaded.",
      );
    } finally {
      if (collectionRequest.current === controller) collectionRequest.current = null;
    }
  }, [client]);

  useEffect(() => {
    void loadCollections();
    return () => collectionRequest.current?.abort();
  }, [loadCollections]);

  useEffect(() => {
    fingerprintRef.current = currentFingerprint;
    const current = activeRequest.current;
    if (current) {
      current.controller.abort();
      activeRequest.current = null;
      setRequestState({ state: "idle" });
    }
  }, [currentFingerprint]);

  useEffect(
    () => () => {
      activeRequest.current?.controller.abort();
    },
    [],
  );

  function buildQuery(): CatalogueSearchRequest | null {
    if (!selectedAoi) {
      setValidationMessage("Select an AOI before searching imagery.");
      return null;
    }
    if (!collectionId) {
      setValidationMessage("Choose an available collection.");
      return null;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(startDate) || !/^\d{4}-\d{2}-\d{2}$/.test(endDate)) {
      setValidationMessage("Enter valid start and end dates.");
      return null;
    }
    const start = new Date(`${startDate}T00:00:00.000Z`);
    const end = new Date(`${endDate}T23:59:59.999Z`);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || start > end) {
      setValidationMessage("The end date must be on or after the start date.");
      return null;
    }
    const cloud = Number(cloudThreshold);
    if (
      cloudApplicable &&
      (!cloudThreshold.trim() || !Number.isFinite(cloud) || cloud < 0 || cloud > 100)
    ) {
      setValidationMessage("Scene cloud threshold must be from 0 to 100 percent.");
      return null;
    }
    setValidationMessage(null);
    return {
      schema_version: "1.0",
      provider: "earth-search",
      aoi: selectedAoi.feature.geometry,
      acquisition: { start: start.toISOString(), end: end.toISOString() },
      collections: [collectionId],
      cloud_cover: cloudApplicable
        ? { max_percent: cloud, source: "provider_reported", include_unknown: false }
        : null,
      limit: PAGE_SIZE,
      cursor: null,
      sort: "acquired_desc",
    };
  }

  async function runSearch(mode: RequestMode) {
    const query = mode === "load_more" ? resultSet?.query : buildQuery();
    if (!query || !selectedAoi) return;
    if (mode === "load_more" && (!resultSet || !resultIsCurrent || !resultSet.nextCursor)) return;
    activeRequest.current?.controller.abort();
    const controller = new AbortController();
    const requestId = ++requestSequence.current;
    activeRequest.current = { id: requestId, controller };
    const fingerprint = currentFingerprint;
    const request = {
      ...query,
      cursor: mode === "load_more" ? (resultSet?.nextCursor ?? null) : null,
    };
    setRequestState({ state: "loading", mode });
    try {
      const response = await client.search(request, controller.signal);
      if (
        activeRequest.current?.id !== requestId ||
        controller.signal.aborted ||
        fingerprintRef.current !== fingerprint
      ) {
        return;
      }
      setResultSet((current) => {
        const prior =
          mode === "load_more" && current?.fingerprint === fingerprint ? current.items : [];
        const seen = new Set(prior.map(catalogueSceneKey));
        const items = [
          ...prior,
          ...response.items.filter((scene) => !seen.has(catalogueSceneKey(scene))),
        ];
        return {
          fingerprint,
          aoiName: selectedAoi.name,
          query: response.query,
          items,
          nextCursor: response.next_cursor,
          searchedAt: response.searched_at,
          attributions: response.attributions,
        };
      });
      setRequestState({ state: "idle" });
    } catch (error) {
      if (error instanceof CatalogueClientError && error.kind === "cancelled") return;
      if (activeRequest.current?.id !== requestId || fingerprintRef.current !== fingerprint) return;
      setRequestState({
        state: "error",
        mode,
        message: error instanceof Error ? error.message : "Imagery search failed.",
        requestId: error instanceof CatalogueClientError ? error.requestId : null,
      });
    } finally {
      if (activeRequest.current?.id === requestId) activeRequest.current = null;
    }
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void runSearch("search");
  }

  return (
    <section className="imagery-discovery" aria-labelledby="imagery-discovery-title">
      <div className="imagery-panel-heading">
        <div>
          <p className="panel-kicker">Catalogue</p>
          <h3 id="imagery-discovery-title" tabIndex={-1}>
            Find imagery
          </h3>
        </div>
        <span className="catalogue-live-badge">Live metadata</span>
      </div>

      <div className={`imagery-aoi-context ${selectedAoi ? "active" : ""}`}>
        <Icon className="imagery-aoi-icon" name="target" />
        <div>
          <span>Selected AOI</span>
          <strong>{selectedAoi?.name ?? "No area selected"}</strong>
          {selectedAoi ? (
            <small>
              {formatAoiArea(selectedAoi.areaSquareMeters)} | {formatAoiBounds(selectedAoi.bounds)}
            </small>
          ) : (
            <small>Draw, enter bounds, or import a Polygon.</small>
          )}
        </div>
      </div>

      <form className="imagery-search-form" onSubmit={handleSearch} noValidate>
        <label>
          Collection
          <select
            value={collectionId}
            disabled={collectionState !== "ready" || collections.length === 0}
            onChange={(event) => setCollectionId(event.target.value)}
          >
            {collections.length === 0 ? <option value="">No collection available</option> : null}
            {collections.map((collection) => (
              <option key={collection.id} value={collection.id}>
                {collection.title ?? collection.id}
              </option>
            ))}
          </select>
        </label>
        {collectionState === "loading" ? (
          <p className="imagery-inline-state" role="status">
            Loading collections...
          </p>
        ) : null}
        {collectionState === "error" ? (
          <div className="imagery-inline-error" role="alert">
            <p>{collectionMessage}</p>
            <button type="button" onClick={() => void loadCollections()}>
              Retry collections
            </button>
          </div>
        ) : null}

        <div className="imagery-date-grid">
          <label>
            Start date <span className="imagery-field-hint">UTC</span>
            <input
              type="date"
              value={startDate}
              max="9999-12-31"
              onChange={(event) => setStartDate(event.target.value)}
            />
          </label>
          <label>
            End date <span className="imagery-field-hint">UTC</span>
            <input
              type="date"
              value={endDate}
              max="9999-12-31"
              onChange={(event) => setEndDate(event.target.value)}
            />
          </label>
        </div>

        {cloudApplicable ? (
          <label>
            Max scene cloud cover
            <span className="imagery-field-hint">Provider-reported</span>
            <div className="imagery-cloud-input">
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                value={cloudThreshold}
                inputMode="decimal"
                onChange={(event) => setCloudThreshold(event.target.value)}
              />
              <span className="imagery-cloud-suffix">%</span>
            </div>
          </label>
        ) : null}

        {validationMessage ? (
          <p className="imagery-validation-error" role="alert">
            {validationMessage}
          </p>
        ) : null}
        <button
          className="imagery-primary-action"
          type="submit"
          disabled={!selectedAoi || collectionState !== "ready" || requestState.state === "loading"}
        >
          <Icon name="spark" />
          {requestState.state === "loading" && requestState.mode === "search"
            ? "Searching catalogue..."
            : "Search imagery"}
        </button>
      </form>

      {resultSet ? (
        <div className="imagery-query-context">
          <div className="imagery-query-heading">
            <strong>
              {resultSet.items.length} {resultSet.items.length === 1 ? "scene" : "scenes"} loaded
            </strong>
            <span className="imagery-query-meta">
              {resultSet.aoiName} | {formatDate(resultSet.query.acquisition.start)} to{" "}
              {formatDate(resultSet.query.acquisition.end)}
            </span>
          </div>
          {!resultIsCurrent ? (
            <p>Filters or AOI changed. These scenes belong to the prior query.</p>
          ) : null}
        </div>
      ) : null}

      {selectionMessage ? (
        <p className="scene-selection-message" role="status">
          {selectionMessage}
        </p>
      ) : null}

      {selectedScene ? (
        <SceneDetails
          selection={selectedScene}
          persistenceState={selectionPersistenceState}
          previewFailed={failedPreviews.has(selectedScene.key)}
          onPreviewError={() =>
            setFailedPreviews((current) => new Set(current).add(selectedScene.key))
          }
          onClear={() => onClearScene()}
          onFit={() => onFitScene(selectedScene.scene)}
          onRefresh={onRefreshScene}
          onOpen={() => onOpenScene(selectedScene)}
          onAssignComparison={(slot) => onAssignComparison(selectedScene, slot)}
          openInViewer={viewerSceneKey === selectedScene.key}
          viewerLoading={viewerSceneKey === selectedScene.key && viewerLoading}
        />
      ) : null}

      {requestState.state === "error" ? (
        <div className="imagery-provider-error" role="alert">
          <strong>Catalogue request failed</strong>
          <p>{requestState.message}</p>
          {requestState.requestId ? <small>Request {requestState.requestId}</small> : null}
          <button
            type="button"
            onClick={() => void runSearch(requestState.mode)}
            disabled={requestState.mode === "load_more" && !resultIsCurrent}
          >
            Retry {requestState.mode === "load_more" ? "load more" : "search"}
          </button>
        </div>
      ) : null}

      {resultSet && resultSet.items.length === 0 && requestState.state !== "loading" ? (
        <div className="imagery-empty-state" role="status">
          <Icon name="evidence" />
          <strong>No scenes matched</strong>
          <p>The catalogue returned an empty page for this exact AOI and date range.</p>
        </div>
      ) : null}

      {resultSet && resultSet.items.length > 0 ? (
        <div className="imagery-results">
          <ul className="imagery-result-list" aria-label="Loaded catalogue scenes">
            {resultSet.items.map((scene) => {
              const key = catalogueSceneKey(scene);
              return (
                <SceneCard
                  key={key}
                  scene={scene}
                  sceneKey={key}
                  current={resultIsCurrent}
                  selected={selectedScene?.key === key}
                  hovered={hoveredSceneKey === key}
                  previewFailed={failedPreviews.has(key)}
                  onPreviewError={() => setFailedPreviews((current) => new Set(current).add(key))}
                  onHover={onHoverScene}
                  onSelect={() =>
                    onSelectScene(
                      createCatalogueSceneSelection(scene, resultSet.fingerprint, resultSet.query),
                    )
                  }
                  onFit={() => onFitScene(scene)}
                />
              );
            })}
          </ul>
          {resultSet.attributions.map((attribution) => (
            <p className="imagery-attribution" key={attribution}>
              {attribution}
            </p>
          ))}
        </div>
      ) : null}

      {resultSet?.nextCursor ? (
        <button
          className="imagery-load-more"
          type="button"
          disabled={!resultIsCurrent || requestState.state === "loading"}
          onClick={() => void runSearch("load_more")}
        >
          {requestState.state === "loading" && requestState.mode === "load_more"
            ? "Loading more..."
            : "Load more"}
        </button>
      ) : null}
    </section>
  );
}
