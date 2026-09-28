"use client";

import { useId, useState } from "react";
import type { SelectedAoi } from "@/lib/aoi";
import type {
  ImageryAsset,
  ImageryProductType,
  VisualizationPreset,
} from "@/lib/imagery-contracts";
import { getCompatiblePresets } from "@/lib/use-imagery";

export interface PreviewSceneInput {
  readonly id?: string;
  readonly provider_asset_id?: string;
  readonly sensor_type?: "unknown" | "sar" | "optical" | "multispectral" | string;
  readonly provider?: string | { id: string; name: string };
  readonly collection?: string | { id: string; title: string | null };
  readonly acquisition_time?: string;
  readonly acquisition?: { start: string; end: string };
  readonly bbox?: [number, number, number, number];
  readonly metadata?: Record<string, unknown> | null;
  readonly platform?: string | null;
}

export interface ImageryPreviewPanelProps {
  readonly scene: PreviewSceneInput;
  readonly selectedAoi: SelectedAoi | null;
  readonly activeAsset: ImageryAsset | null;
  readonly status: "idle" | "loading" | "ready" | "error";
  readonly error: string | null;
  readonly selectedPreset: VisualizationPreset;
  readonly productType: ImageryProductType;
  readonly opacity: number;
  readonly visible: boolean;
  readonly onRequestImagery: (preset?: VisualizationPreset, product?: ImageryProductType) => void;
  readonly onClearImagery: () => void;
  readonly onPresetChange: (preset: VisualizationPreset) => void;
  readonly onProductTypeChange: (product: ImageryProductType) => void;
  readonly onOpacityChange: (opacity: number) => void;
  readonly onVisibilityToggle: () => void;
  readonly onFitImagery?: () => void;
}

const PRESET_LABELS: Record<VisualizationPreset, { label: string; desc: string }> = {
  true_color: { label: "True Color (RGB)", desc: "Red (B04), Green (B03), Blue (B02)" },
  false_color: { label: "False Color (NIR)", desc: "NIR (B08), Red (B04), Green (B03)" },
  vegetation: { label: "Vegetation Contrast", desc: "NIR (B08), Red (B04), Green (B03)" },
  water: { label: "Water Bodies (SWIR)", desc: "Green (B03), NIR (B08), SWIR1 (B11)" },
  urban: { label: "Urban & Built-Up", desc: "SWIR2 (B12), SWIR1 (B11), Red (B04)" },
  sar_grayscale: { label: "SAR Grayscale", desc: "Calibrated Radar Amplitude" },
  sar_vv: { label: "SAR VV Polarization", desc: "Vertical-Transmit Vertical-Receive" },
  sar_vh: { label: "SAR VH Polarization", desc: "Vertical-Transmit Horizontal-Receive" },
};

export function ImageryPreviewPanel({
  scene,
  selectedAoi,
  activeAsset,
  status,
  error,
  selectedPreset,
  productType,
  opacity,
  visible,
  onRequestImagery,
  onClearImagery,
  onPresetChange,
  onProductTypeChange,
  onOpacityChange,
  onVisibilityToggle,
  onFitImagery,
}: ImageryPreviewPanelProps) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const presetSelectId = useId();
  const productSelectId = useId();
  const opacitySliderId = useId();

  const compatiblePresets = getCompatiblePresets(scene.sensor_type);
  const origin = activeAsset?.data_origin ?? (scene.metadata?.data_origin as string) ?? "real";

  return (
    <section className="imagery-preview-panel" aria-label="Scene Imagery Preview">
      <div className="preview-panel-header">
        <div>
          <h3 className="preview-panel-title">Scene Imagery &amp; Preview</h3>
          <span className="preview-scene-id" title={scene.id ?? scene.provider_asset_id ?? "Scene"}>
            {scene.id ?? scene.provider_asset_id ?? "Scene"}
          </span>
        </div>
        <div className="preview-badges">
          <span className={`origin-badge origin-${origin}`}>
            {origin === "mock" ? "DEMO DATA" : origin.toUpperCase()}
          </span>
          <span className="product-badge">
            {productType === "analysis_raster"
              ? "Analysis Raster (GeoTIFF)"
              : productType === "map_preview"
                ? "Map Preview (PNG)"
                : "Thumbnail"}
          </span>
        </div>
      </div>

      {/* Preset & Product Selection */}
      <div className="preview-controls-grid">
        <div className="control-group">
          <label htmlFor={presetSelectId} className="control-label">
            Visualization Preset
          </label>
          <select
            id={presetSelectId}
            className="preset-select"
            value={selectedPreset}
            onChange={(e) => {
              const nextPreset = e.target.value as VisualizationPreset;
              onPresetChange(nextPreset);
              if (selectedAoi) {
                onRequestImagery(nextPreset, productType);
              }
            }}
            disabled={status === "loading" || !selectedAoi}
          >
            {compatiblePresets.map((preset) => (
              <option key={preset} value={preset}>
                {PRESET_LABELS[preset]?.label ?? preset}
              </option>
            ))}
          </select>
          <span className="control-hint">
            {PRESET_LABELS[selectedPreset]?.desc ?? "Custom band mapping"}
          </span>
        </div>

        <div className="control-group">
          <label htmlFor={productSelectId} className="control-label">
            Product Mode
          </label>
          <select
            id={productSelectId}
            className="product-select"
            value={productType}
            onChange={(e) => {
              const nextProduct = e.target.value as ImageryProductType;
              onProductTypeChange(nextProduct);
              if (selectedAoi) {
                onRequestImagery(selectedPreset, nextProduct);
              }
            }}
            disabled={status === "loading" || !selectedAoi}
          >
            <option value="map_preview">Map Preview (Display)</option>
            <option value="analysis_raster">Analysis Raster (GeoTIFF)</option>
          </select>
        </div>
      </div>

      {/* Opacity and Visibility Controls */}
      <div className="preview-rendering-controls">
        <div className="opacity-control">
          <label htmlFor={opacitySliderId} className="control-label">
            Opacity: {Math.round(opacity * 100)}%
          </label>
          <input
            id={opacitySliderId}
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(e) => onOpacityChange(parseFloat(e.target.value))}
            className="opacity-slider"
            disabled={!activeAsset}
          />
        </div>

        <div className="rendering-button-row">
          <button
            type="button"
            className={`preview-toggle-btn ${visible ? "active" : ""}`}
            onClick={onVisibilityToggle}
            disabled={!activeAsset}
          >
            {visible ? "Hide Layer" : "Show Layer"}
          </button>

          {onFitImagery && (
            <button
              type="button"
              className="preview-action-btn"
              onClick={onFitImagery}
              disabled={!activeAsset}
            >
              Fit to Imagery
            </button>
          )}

          {activeAsset && (
            <button
              type="button"
              className="preview-clear-btn"
              onClick={onClearImagery}
              disabled={status === "loading"}
            >
              Remove Layer
            </button>
          )}
        </div>
      </div>

      {/* Action / Retrieve Button */}
      {!activeAsset && status !== "loading" && (
        <button
          type="button"
          className="retrieve-imagery-btn"
          onClick={() => onRequestImagery(selectedPreset, productType)}
          disabled={!selectedAoi}
        >
          {selectedAoi ? "Retrieve Scene Imagery" : "Select an AOI to retrieve imagery"}
        </button>
      )}

      {/* Status & Alerts */}
      {status === "loading" && (
        <div className="imagery-status-box loading" role="status">
          <span className="spinner" /> Retrieving and validating bounded scene imagery…
        </div>
      )}

      {status === "error" && error && (
        <div className="imagery-status-box error" role="alert">
          <strong>Retrieval Failed:</strong> {error}
        </div>
      )}

      {/* Active Asset Metadata Summary */}
      {activeAsset && (
        <div className="asset-metadata-summary">
          <div className="metadata-metric">
            <span className="metric-label">Dimensions</span>
            <span className="metric-value">
              {activeAsset.width} × {activeAsset.height} px
            </span>
          </div>
          <div className="metadata-metric">
            <span className="metric-label">Resolution</span>
            <span className="metric-value">{activeAsset.resolution_meters}m</span>
          </div>
          <div className="metadata-metric">
            <span className="metric-label">CRS</span>
            <span className="metric-value">{activeAsset.crs}</span>
          </div>
          <div className="metadata-metric">
            <span className="metric-label">Format</span>
            <span className="metric-value">{activeAsset.format.toUpperCase()}</span>
          </div>

          {activeAsset.warnings && activeAsset.warnings.length > 0 && (
            <div className="asset-warnings-list">
              {activeAsset.warnings.map((w) => (
                <div key={`${w.code}-${w.message}`} className="asset-warning-badge" role="status">
                  ⚠ {w.message}
                </div>
              ))}
            </div>
          )}

          {/* Technical Details Toggle */}
          <button
            type="button"
            className="toggle-technical-btn"
            onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          >
            {showTechnicalDetails ? "▼ Hide Technical Metadata" : "▶ Show Technical Metadata"}
          </button>

          {showTechnicalDetails && (
            <div className="technical-metadata-collapsible">
              <dl className="tech-dl">
                <dt>Asset ID:</dt>
                <dd>{activeAsset.asset_id}</dd>
                <dt>Checksum (SHA-256):</dt>
                <dd className="hash-value">{activeAsset.checksum}</dd>
                <dt>Content Type:</dt>
                <dd>{activeAsset.content_type}</dd>
                <dt>Size (bytes):</dt>
                <dd>{activeAsset.size_bytes.toLocaleString()}</dd>
                <dt>Bbox (W, S, E, N):</dt>
                <dd>
                  [{activeAsset.bbox[0].toFixed(4)}, {activeAsset.bbox[1].toFixed(4)},{" "}
                  {activeAsset.bbox[2].toFixed(4)}, {activeAsset.bbox[3].toFixed(4)}]
                </dd>
                <dt>Bands Included:</dt>
                <dd>{activeAsset.bands.join(", ") || "Standard RGB"}</dd>
                {activeAsset.expires_at && (
                  <>
                    <dt>Expires At (UTC):</dt>
                    <dd>{activeAsset.expires_at}</dd>
                  </>
                )}
              </dl>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
