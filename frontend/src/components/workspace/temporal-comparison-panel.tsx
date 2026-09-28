"use client";

import { useId, useState } from "react";
import type { SatelliteScene } from "@/lib/analysis-contracts";
import type { SelectedAoi } from "@/lib/aoi";
import type {
  AlignmentStatus,
  ImageryProductType,
  TemporalImageryResponse,
  VisualizationPreset,
} from "@/lib/imagery-contracts";
import { type ComparisonMode, getCompatiblePresets } from "@/lib/use-imagery";

export interface TemporalComparisonPanelProps {
  readonly beforeScene: SatelliteScene;
  readonly afterScene: SatelliteScene;
  readonly selectedAoi: SelectedAoi | null;
  readonly temporalResponse: TemporalImageryResponse | null;
  readonly status: "idle" | "loading" | "ready" | "error";
  readonly error: string | null;
  readonly beforePreset: VisualizationPreset;
  readonly afterPreset: VisualizationPreset;
  readonly comparisonMode: ComparisonMode;
  readonly swipePosition: number;
  readonly blendOpacity: number;
  readonly onRequestComparison: (
    beforePreset?: VisualizationPreset,
    afterPreset?: VisualizationPreset,
    product?: ImageryProductType,
  ) => void;
  readonly onClearComparison: () => void;
  readonly onBeforePresetChange: (preset: VisualizationPreset) => void;
  readonly onAfterPresetChange: (preset: VisualizationPreset) => void;
  readonly onComparisonModeChange: (mode: ComparisonMode) => void;
  readonly onSwipePositionChange: (pos: number) => void;
  readonly onBlendOpacityChange: (opacity: number) => void;
}

const PRESET_NAMES: Record<VisualizationPreset, string> = {
  true_color: "True Color (RGB)",
  false_color: "False Color (NIR)",
  vegetation: "Vegetation Contrast",
  water: "Water Bodies (SWIR)",
  urban: "Urban & Built-Up",
  sar_grayscale: "SAR Grayscale",
  sar_vv: "SAR VV",
  sar_vh: "SAR VH",
};

const ALIGNMENT_DESCRIPTIONS: Record<
  AlignmentStatus,
  { label: string; badgeClass: string; message: string }
> = {
  aligned: {
    label: "Grids Aligned",
    badgeClass: "badge-aligned",
    message: "Scenes share identical CRS, resolution, and pixel alignment.",
  },
  approximately_aligned: {
    label: "Approximately Aligned",
    badgeClass: "badge-approx",
    message: "Scenes share CRS and resolution with minor sub-pixel grid offsets.",
  },
  requires_alignment: {
    label: "Alignment Recommended",
    badgeClass: "badge-warning",
    message:
      "Different pixel sizes or grid transforms detected. Visual comparison is enabled; analytical change detection requires co-registration (Phase 3B).",
  },
  incompatible: {
    label: "Incompatible Grids",
    badgeClass: "badge-error",
    message:
      "Different CRS or spatial bounds; scenes cannot be accurately co-registered without reprojection.",
  },
  unknown: {
    label: "Alignment Unknown",
    badgeClass: "badge-neutral",
    message: "Grid alignment metadata is incomplete.",
  },
};

function formatAcquisitionDate(isoStr: string): string {
  try {
    const d = new Date(isoStr);
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }).format(d);
  } catch {
    return isoStr;
  }
}

export function TemporalComparisonPanel({
  beforeScene,
  afterScene,
  selectedAoi,
  temporalResponse,
  status,
  error,
  beforePreset,
  afterPreset,
  comparisonMode,
  swipePosition,
  blendOpacity,
  onRequestComparison,
  onClearComparison,
  onBeforePresetChange,
  onAfterPresetChange,
  onComparisonModeChange,
  onSwipePositionChange,
  onBlendOpacityChange,
}: TemporalComparisonPanelProps) {
  const productType: ImageryProductType = "map_preview";
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const beforePresetId = useId();
  const afterPresetId = useId();
  const swipeSliderId = useId();
  const blendSliderId = useId();

  const beforePresets = getCompatiblePresets(beforeScene.sensor_type);
  const afterPresets = getCompatiblePresets(afterScene.sensor_type);

  const alignment = (temporalResponse?.alignment_status ?? "unknown") as AlignmentStatus;
  const alignInfo = ALIGNMENT_DESCRIPTIONS[alignment] ?? ALIGNMENT_DESCRIPTIONS.unknown;

  const beforeOrigin =
    temporalResponse?.before_asset.data_origin ??
    (beforeScene.metadata?.data_origin as string) ??
    "real";
  const afterOrigin =
    temporalResponse?.after_asset.data_origin ??
    (afterScene.metadata?.data_origin as string) ??
    "real";

  return (
    <section className="temporal-comparison-panel" aria-label="Multitemporal Imagery Comparison">
      <div className="comparison-panel-header">
        <div>
          <h3 className="comparison-panel-title">Multitemporal Scene Comparison</h3>
          <p className="comparison-subtitle">
            Compare validated before and after satellite scene acquisitions.
          </p>
        </div>
      </div>

      {/* Before & After Cards Grid */}
      <div className="comparison-scenes-grid">
        {/* Before Scene Card */}
        <div className="scene-period-card before-card">
          <div className="period-badge-row">
            <span className="period-label">BEFORE SCENE</span>
            <span className={`origin-badge origin-${beforeOrigin}`}>
              {beforeOrigin === "mock" ? "DEMO DATA" : beforeOrigin.toUpperCase()}
            </span>
          </div>
          <div className="period-scene-id" title={beforeScene.id}>
            {beforeScene.id}
          </div>
          <div className="period-meta-text">
            <span>{formatAcquisitionDate(beforeScene.acquisition_time)}</span>
            <span>{beforeScene.platform ?? beforeScene.collection}</span>
          </div>
          <div className="period-preset-control">
            <label htmlFor={beforePresetId} className="control-label">
              Preset:
            </label>
            <select
              id={beforePresetId}
              className="preset-select-small"
              value={beforePreset}
              onChange={(e) => {
                const next = e.target.value as VisualizationPreset;
                onBeforePresetChange(next);
                if (selectedAoi) {
                  onRequestComparison(next, afterPreset, productType);
                }
              }}
              disabled={status === "loading"}
            >
              {beforePresets.map((p) => (
                <option key={p} value={p}>
                  {PRESET_NAMES[p] ?? p}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* After Scene Card */}
        <div className="scene-period-card after-card">
          <div className="period-badge-row">
            <span className="period-label">AFTER SCENE</span>
            <span className={`origin-badge origin-${afterOrigin}`}>
              {afterOrigin === "mock" ? "DEMO DATA" : afterOrigin.toUpperCase()}
            </span>
          </div>
          <div className="period-scene-id" title={afterScene.id}>
            {afterScene.id}
          </div>
          <div className="period-meta-text">
            <span>{formatAcquisitionDate(afterScene.acquisition_time)}</span>
            <span>{afterScene.platform ?? afterScene.collection}</span>
          </div>
          <div className="period-preset-control">
            <label htmlFor={afterPresetId} className="control-label">
              Preset:
            </label>
            <select
              id={afterPresetId}
              className="preset-select-small"
              value={afterPreset}
              onChange={(e) => {
                const next = e.target.value as VisualizationPreset;
                onAfterPresetChange(next);
                if (selectedAoi) {
                  onRequestComparison(beforePreset, next, productType);
                }
              }}
              disabled={status === "loading"}
            >
              {afterPresets.map((p) => (
                <option key={p} value={p}>
                  {PRESET_NAMES[p] ?? p}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Comparison Mode Selector */}
      <div className="comparison-mode-bar">
        <span className="mode-bar-label">Comparison Mode:</span>
        <div className="mode-button-group">
          <button
            type="button"
            className={`mode-btn ${comparisonMode === "swipe" ? "selected" : ""}`}
            onClick={() => onComparisonModeChange("swipe")}
            aria-pressed={comparisonMode === "swipe"}
          >
            Swipe Slider
          </button>
          <button
            type="button"
            className={`mode-btn ${comparisonMode === "split" ? "selected" : ""}`}
            onClick={() => onComparisonModeChange("split")}
            aria-pressed={comparisonMode === "split"}
          >
            Side-by-Side
          </button>
          <button
            type="button"
            className={`mode-btn ${comparisonMode === "blend" ? "selected" : ""}`}
            onClick={() => onComparisonModeChange("blend")}
            aria-pressed={comparisonMode === "blend"}
          >
            Opacity Blend
          </button>
        </div>
      </div>

      {/* Mode-specific interactive controls */}
      {comparisonMode === "swipe" && (
        <div className="mode-interaction-control">
          <label htmlFor={swipeSliderId} className="control-label">
            Swipe Divider: {swipePosition}% (Before ◀ ▶ After)
          </label>
          <input
            id={swipeSliderId}
            type="range"
            min="0"
            max="100"
            value={swipePosition}
            onChange={(e) => onSwipePositionChange(parseInt(e.target.value, 10))}
            className="swipe-slider"
          />
        </div>
      )}

      {comparisonMode === "blend" && (
        <div className="mode-interaction-control">
          <label htmlFor={blendSliderId} className="control-label">
            After Scene Opacity: {Math.round(blendOpacity * 100)}%
          </label>
          <input
            id={blendSliderId}
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={blendOpacity}
            onChange={(e) => onBlendOpacityChange(parseFloat(e.target.value))}
            className="blend-slider"
          />
        </div>
      )}

      {/* Retrieve / Clear Action Buttons */}
      <div className="comparison-action-row">
        <button
          type="button"
          className="retrieve-comparison-btn"
          onClick={() => onRequestComparison(beforePreset, afterPreset, productType)}
          disabled={status === "loading" || !selectedAoi}
        >
          {status === "loading"
            ? "Retrieving Pair Imagery…"
            : temporalResponse
              ? "Re-fetch Imagery Pair"
              : "Retrieve Multitemporal Imagery"}
        </button>

        {temporalResponse && (
          <button
            type="button"
            className="clear-comparison-btn"
            onClick={onClearComparison}
            disabled={status === "loading"}
          >
            Clear Pair
          </button>
        )}
      </div>

      {/* Loading & Error States */}
      {status === "loading" && (
        <div className="imagery-status-box loading" role="status">
          <span className="spinner" /> Retrieving and validating multitemporal satellite rasters…
        </div>
      )}

      {status === "error" && error && (
        <div className="imagery-status-box error" role="alert">
          <strong>Retrieval Failed:</strong> {error}
        </div>
      )}

      {/* Alignment Status Banner */}
      {temporalResponse && (
        <div className={`alignment-banner ${alignInfo.badgeClass}`} role="status">
          <div className="alignment-header">
            <strong>Alignment Status: {alignInfo.label}</strong>
          </div>
          <p className="alignment-explanation">{alignInfo.message}</p>
        </div>
      )}

      {/* Interactive Visual Comparison Viewer Frame */}
      {temporalResponse && (
        <section className="temporal-visual-viewer" aria-label="Visual comparison output">
          {comparisonMode === "swipe" && (
            <div
              className="swipe-container"
              style={{ position: "relative", overflow: "hidden", minHeight: "260px" }}
            >
              {/* biome-ignore lint/performance/noImgElement: dynamic user-selected raster asset */}
              <img
                src={temporalResponse.after_asset.display_url}
                alt={`After scene: ${afterScene.id}`}
                className="comparison-img after-img"
                style={{ width: "100%", height: "auto", display: "block" }}
              />
              <div
                className="swipe-clip"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: `${swipePosition}%`,
                  height: "100%",
                  overflow: "hidden",
                  borderRight: "2px solid #38bdf8",
                }}
              >
                {/* biome-ignore lint/performance/noImgElement: dynamic user-selected raster asset */}
                <img
                  src={temporalResponse.before_asset.display_url}
                  alt={`Before scene: ${beforeScene.id}`}
                  className="comparison-img before-img"
                  style={{ width: "100%", height: "auto", display: "block", maxWidth: "none" }}
                />
              </div>
              <div className="swipe-label-overlay left">BEFORE ({swipePosition}%)</div>
              <div className="swipe-label-overlay right">AFTER ({100 - swipePosition}%)</div>
            </div>
          )}

          {comparisonMode === "split" && (
            <div
              className="split-container"
              style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}
            >
              <div className="split-pane">
                <div className="split-pane-label">
                  BEFORE: {formatAcquisitionDate(beforeScene.acquisition_time)}
                </div>
                {/* biome-ignore lint/performance/noImgElement: dynamic user-selected raster asset */}
                <img
                  src={temporalResponse.before_asset.display_url}
                  alt={`Before scene: ${beforeScene.id}`}
                  className="comparison-img"
                  style={{ width: "100%", height: "auto", display: "block" }}
                />
              </div>
              <div className="split-pane">
                <div className="split-pane-label">
                  AFTER: {formatAcquisitionDate(afterScene.acquisition_time)}
                </div>
                {/* biome-ignore lint/performance/noImgElement: dynamic user-selected raster asset */}
                <img
                  src={temporalResponse.after_asset.display_url}
                  alt={`After scene: ${afterScene.id}`}
                  className="comparison-img"
                  style={{ width: "100%", height: "auto", display: "block" }}
                />
              </div>
            </div>
          )}

          {comparisonMode === "blend" && (
            <div className="blend-container" style={{ position: "relative", minHeight: "260px" }}>
              {/* biome-ignore lint/performance/noImgElement: dynamic user-selected raster asset */}
              <img
                src={temporalResponse.before_asset.display_url}
                alt={`Before scene: ${beforeScene.id}`}
                className="comparison-img before-img"
                style={{ width: "100%", height: "auto", display: "block" }}
              />
              {/* biome-ignore lint/performance/noImgElement: dynamic user-selected raster asset */}
              <img
                src={temporalResponse.after_asset.display_url}
                alt={`After scene: ${afterScene.id}`}
                className="comparison-img after-img"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  height: "auto",
                  display: "block",
                  opacity: blendOpacity,
                }}
              />
              <div className="blend-label-overlay">
                BLEND (Before + {Math.round(blendOpacity * 100)}% After)
              </div>
            </div>
          )}

          {/* Technical Details */}
          <button
            type="button"
            className="toggle-technical-btn"
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          >
            {showTechnicalDetails ? "▼ Hide Pair Metadata" : "▶ Show Pair Metadata"}
          </button>

          {showTechnicalDetails && (
            <div className="technical-metadata-collapsible">
              <dl className="tech-dl">
                <dt>Pair Request ID:</dt>
                <dd>{temporalResponse.request_id}</dd>
                <dt>Alignment Status:</dt>
                <dd>{temporalResponse.alignment_status}</dd>
                <dt>Before Asset ID:</dt>
                <dd>{temporalResponse.before_asset.asset_id}</dd>
                <dt>After Asset ID:</dt>
                <dd>{temporalResponse.after_asset.asset_id}</dd>
                <dt>Before Dimensions:</dt>
                <dd>
                  {temporalResponse.before_asset.width} × {temporalResponse.before_asset.height} px
                </dd>
                <dt>After Dimensions:</dt>
                <dd>
                  {temporalResponse.after_asset.width} × {temporalResponse.after_asset.height} px
                </dd>
                <dt>Before CRS / After CRS:</dt>
                <dd>
                  {temporalResponse.before_asset.crs} / {temporalResponse.after_asset.crs}
                </dd>
              </dl>
            </div>
          )}
        </section>
      )}
    </section>
  );
}
