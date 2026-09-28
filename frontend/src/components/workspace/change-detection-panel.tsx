"use client";

import { useId } from "react";

import type { AnalysisWarning } from "@/lib/analysis-contracts";
import type {
  ChangeDetectionDefinition,
  ChangeDetectionMethod,
  ChangeDetectionResult,
  ChangeRegion,
  ChangeThresholdConfig,
  ThresholdStrategy,
} from "@/lib/change-contracts";
import type { PreparedTemporalPair } from "@/lib/preparation-contracts";
import type { ChangeOverlayDisplayMode } from "@/lib/use-change-detection";

export interface ChangeDetectionPanelProps {
  readonly preparedPair: PreparedTemporalPair | null;
  readonly methods: readonly ChangeDetectionDefinition[];
  readonly selectedMethod: ChangeDetectionMethod;
  readonly onSelectMethod: (method: ChangeDetectionMethod) => void;
  readonly currentDefinition: ChangeDetectionDefinition | null;
  readonly thresholdConfig: ChangeThresholdConfig;
  readonly onThresholdStrategyChange: (strategy: ThresholdStrategy) => void;
  readonly onPositiveThresholdChange: (threshold: number) => void;
  readonly onNegativeThresholdChange: (threshold: number) => void;
  readonly onStdMultiplierChange: (multiplier: number) => void;
  readonly onMinClusterSizeChange: (size: number) => void;
  readonly isCalculating: boolean;
  readonly result: ChangeDetectionResult | null;
  readonly error: string | null;
  readonly warnings: readonly AnalysisWarning[];
  readonly selectedRegion: ChangeRegion | null;
  readonly onSelectRegion: (region: ChangeRegion | null) => void;
  readonly overlayMode: ChangeOverlayDisplayMode;
  readonly onOverlayModeChange: (mode: ChangeOverlayDisplayMode) => void;
  readonly overlayOpacity: number;
  readonly onOverlayOpacityChange: (opacity: number) => void;
  readonly onCalculateChange: () => void;
  readonly onCancelCalculation: () => void;
  readonly onReset: () => void;
}

export function ChangeDetectionPanel({
  preparedPair,
  methods,
  selectedMethod,
  onSelectMethod,
  currentDefinition,
  thresholdConfig,
  onThresholdStrategyChange,
  onPositiveThresholdChange,
  onNegativeThresholdChange,
  onStdMultiplierChange,
  onMinClusterSizeChange,
  isCalculating,
  result,
  error,
  warnings,
  selectedRegion,
  onSelectRegion,
  overlayMode,
  onOverlayModeChange,
  overlayOpacity,
  onOverlayOpacityChange,
  onCalculateChange,
  onCancelCalculation,
  onReset,
}: ChangeDetectionPanelProps) {
  const methodSelectId = useId();
  const stratSelectId = useId();
  const posThreshId = useId();
  const negThreshId = useId();
  const stdMultId = useId();
  const clusterSizeId = useId();
  const opacityId = useId();

  const isPairReady = Boolean(preparedPair?.ready_for_analysis);

  return (
    <section className="change-detection-panel" aria-label="Change Detection Panel">
      {/* Header */}
      <div className="change-panel-header flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Pixel-Level Change Detection &amp; Evidence
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Strict pixel-to-pixel differencing on co-registered grids over shared valid pixels
          </p>
        </div>
        {result && (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
              Confidence: {Math.round(result.confidence * 100)}%
            </span>
          </div>
        )}
      </div>

      {/* Temporal Pair Status */}
      <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 text-xs">
        <div className="flex items-center justify-between font-medium text-slate-700 dark:text-slate-300">
          <span>Analysis Pair:</span>
          {isPairReady ? (
            <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
              ✓ Co-Registered &amp; Ready
            </span>
          ) : (
            <span className="text-amber-600 dark:text-amber-400 font-medium">
              ⚠ Requires Harmonized Pair
            </span>
          )}
        </div>
        {preparedPair ? (
          <div className="mt-2 grid grid-cols-2 gap-2 text-slate-600 dark:text-slate-400">
            <div>
              <span className="font-medium text-slate-700 dark:text-slate-300">Before Scene:</span>{" "}
              {preparedPair.before_asset.scene_ids[0] ?? "N/A"}
            </div>
            <div>
              <span className="font-medium text-slate-700 dark:text-slate-300">After Scene:</span>{" "}
              {preparedPair.after_asset.scene_ids[0] ?? "N/A"}
            </div>
            <div>
              <span className="font-medium text-slate-700 dark:text-slate-300">Grid CRS:</span>{" "}
              {preparedPair.common_crs}
            </div>
            <div>
              <span className="font-medium text-slate-700 dark:text-slate-300">Shared Valid:</span>{" "}
              {preparedPair.shared_valid_percent.toFixed(1)}% (
              {preparedPair.shared_valid_pixel_count.toLocaleString()} px)
            </div>
          </div>
        ) : (
          <p className="mt-1 text-slate-500 italic">
            Please prepare a temporal pair in the preparation panel before running change detection.
          </p>
        )}
      </div>

      {/* Method Selection & Configuration */}
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        <div>
          <label
            htmlFor={methodSelectId}
            className="block font-medium text-slate-700 dark:text-slate-300 mb-1"
          >
            Change Detection Method
          </label>
          <select
            id={methodSelectId}
            value={selectedMethod}
            onChange={(e) => onSelectMethod(e.target.value as ChangeDetectionMethod)}
            disabled={isCalculating}
            className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200"
          >
            {methods.length > 0 ? (
              methods.map((m) => (
                <option key={m.method} value={m.method}>
                  {m.display_name}
                </option>
              ))
            ) : (
              <>
                <option value="ndvi_difference">NDVI Difference (Vegetation Change)</option>
                <option value="ndwi_difference">NDWI Difference (Water Surface Change)</option>
                <option value="ndbi_difference">NDBI Difference (Built-Up Spectral Change)</option>
                <option value="absolute_index_difference">Absolute Index Difference</option>
                <option value="multiband_change_magnitude">Multiband Change Magnitude</option>
              </>
            )}
          </select>
          {currentDefinition && (
            <p className="mt-1 text-slate-500 dark:text-slate-400">
              Formula:{" "}
              <code className="font-mono text-blue-600 dark:text-blue-400">
                {currentDefinition.formula}
              </code>
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor={stratSelectId}
            className="block font-medium text-slate-700 dark:text-slate-300 mb-1"
          >
            Threshold Strategy
          </label>
          <select
            id={stratSelectId}
            value={thresholdConfig.strategy}
            onChange={(e) => onThresholdStrategyChange(e.target.value as ThresholdStrategy)}
            disabled={isCalculating}
            className="w-full px-2.5 py-1.5 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-800 dark:text-slate-200"
          >
            <option value="fixed">Fixed Cutoffs</option>
            <option value="standard_deviation">Standard Deviation (Mean ± k·σ)</option>
            <option value="percentile">Percentile Cutoff (Upper tail)</option>
            <option value="otsu">Otsu Automatic Clustering</option>
            <option value="manual">Manual Parameterized</option>
          </select>
        </div>
      </div>

      {/* Threshold Parameter Adjustments */}
      <div className="mt-3 p-3 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 text-xs">
        <h4 className="font-semibold text-slate-700 dark:text-slate-300 mb-2">
          Threshold &amp; Noise Parameters
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {(thresholdConfig.strategy === "fixed" || thresholdConfig.strategy === "manual") && (
            <>
              <div>
                <label htmlFor={posThreshId} className="block text-slate-500 mb-1">
                  Gain Cutoff (+Δ)
                </label>
                <input
                  id={posThreshId}
                  type="number"
                  step="0.01"
                  value={thresholdConfig.positive_threshold}
                  onChange={(e) => onPositiveThresholdChange(parseFloat(e.target.value) || 0)}
                  disabled={isCalculating}
                  className="w-full px-2 py-1 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700"
                />
              </div>
              <div>
                <label htmlFor={negThreshId} className="block text-slate-500 mb-1">
                  Loss Cutoff (-Δ)
                </label>
                <input
                  id={negThreshId}
                  type="number"
                  step="0.01"
                  value={thresholdConfig.negative_threshold}
                  onChange={(e) => onNegativeThresholdChange(parseFloat(e.target.value) || 0)}
                  disabled={isCalculating}
                  className="w-full px-2 py-1 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700"
                />
              </div>
            </>
          )}

          {thresholdConfig.strategy === "standard_deviation" && (
            <div>
              <label htmlFor={stdMultId} className="block text-slate-500 mb-1">
                Std Multiplier (k)
              </label>
              <input
                id={stdMultId}
                type="number"
                step="0.1"
                min="0.5"
                max="5.0"
                value={thresholdConfig.std_multiplier}
                onChange={(e) => onStdMultiplierChange(parseFloat(e.target.value) || 1.5)}
                disabled={isCalculating}
                className="w-full px-2 py-1 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700"
              />
            </div>
          )}

          <div>
            <label htmlFor={clusterSizeId} className="block text-slate-500 mb-1">
              Min Cluster Size (px)
            </label>
            <input
              id={clusterSizeId}
              type="number"
              step="1"
              min="1"
              max="1000"
              value={thresholdConfig.min_cluster_size_pixels}
              onChange={(e) => onMinClusterSizeChange(parseInt(e.target.value, 10) || 5)}
              disabled={isCalculating}
              className="w-full px-2 py-1 rounded bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700"
            />
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCalculateChange}
            disabled={!isPairReady || isCalculating}
            className="px-4 py-2 rounded-md font-medium text-xs bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition"
          >
            {isCalculating ? "Calculating Change..." : "Calculate Change Detection"}
          </button>
          {isCalculating && (
            <button
              type="button"
              onClick={onCancelCalculation}
              className="px-3 py-2 rounded-md font-medium text-xs bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 text-slate-800 dark:text-slate-200 transition"
            >
              Cancel
            </button>
          )}
        </div>
        {result && (
          <button
            type="button"
            onClick={onReset}
            disabled={isCalculating}
            className="px-3 py-1.5 rounded text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 underline"
          >
            Reset Analysis
          </button>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div
          role="alert"
          className="mt-3 p-3 rounded-lg bg-rose-50 dark:bg-rose-950/30 border border-rose-300 dark:border-rose-800 text-xs text-rose-800 dark:text-rose-300"
        >
          <strong className="font-semibold">Calculation Error:</strong> {error}
        </div>
      )}

      {/* Scientific Warnings */}
      {warnings.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {warnings.map((w) => (
            <div
              key={`${w.code}-${w.message}`}
              className="p-2.5 rounded-md bg-amber-50 dark:bg-amber-950/30 border border-amber-300 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2"
            >
              <span className="font-semibold">⚠ [{w.code}]</span>
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="mt-5 space-y-4">
          {/* Scientific Disclaimer Banner */}
          <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-xs text-blue-900 dark:text-blue-200">
            <strong className="font-semibold">Scientific Change Evidence:</strong>
            <p className="mt-0.5 text-blue-800 dark:text-blue-300">
              Results reflect measured pixel-level spectral reflectance differences. They do not
              constitute definitive land-cover classification or confirmed construction/destruction
              without secondary field verification.
            </p>
          </div>

          {/* Quantitative Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <span className="text-xs text-slate-500 dark:text-slate-400 block">
                Spectral Gain
              </span>
              <span className="text-base font-bold text-emerald-600 dark:text-emerald-400">
                {result.metrics.gain_area_km2.toFixed(3)} km²
              </span>
              <span className="text-xs text-slate-500 block mt-0.5">
                {result.metrics.pixel_counts.gain_percent.toFixed(1)}% of valid
              </span>
            </div>

            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <span className="text-xs text-slate-500 dark:text-slate-400 block">
                Spectral Loss
              </span>
              <span className="text-base font-bold text-rose-600 dark:text-rose-400">
                {result.metrics.loss_area_km2.toFixed(3)} km²
              </span>
              <span className="text-xs text-slate-500 block mt-0.5">
                {result.metrics.pixel_counts.loss_percent.toFixed(1)}% of valid
              </span>
            </div>

            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <span className="text-xs text-slate-500 dark:text-slate-400 block">Stable Area</span>
              <span className="text-base font-bold text-slate-700 dark:text-slate-300">
                {result.metrics.stable_area_km2.toFixed(3)} km²
              </span>
              <span className="text-xs text-slate-500 block mt-0.5">
                {result.metrics.pixel_counts.stable_percent.toFixed(1)}% of valid
              </span>
            </div>

            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              <span className="text-xs text-slate-500 dark:text-slate-400 block">
                Shared Valid Area
              </span>
              <span className="text-base font-bold text-blue-600 dark:text-blue-400">
                {result.metrics.shared_valid_area_km2.toFixed(3)} km²
              </span>
              <span className="text-xs text-slate-500 block mt-0.5">
                {result.metrics.pixel_counts.shared_valid_pixels.toLocaleString()} pixels
              </span>
            </div>
          </div>

          {/* Map Overlay Controls */}
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 text-xs flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-700 dark:text-slate-300">
                Overlay Display:
              </span>
              <fieldset className="inline-flex rounded-md shadow-sm border-0 p-0 m-0">
                <button
                  type="button"
                  onClick={() => onOverlayModeChange("continuous")}
                  className={`px-2.5 py-1 text-xs font-medium rounded-l-lg border ${
                    overlayMode === "continuous"
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700"
                  }`}
                >
                  Continuous Δ
                </button>
                <button
                  type="button"
                  onClick={() => onOverlayModeChange("classified")}
                  className={`px-2.5 py-1 text-xs font-medium border-t border-b ${
                    overlayMode === "classified"
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700"
                  }`}
                >
                  3-Class Mask
                </button>
                <button
                  type="button"
                  onClick={() => onOverlayModeChange("none")}
                  className={`px-2.5 py-1 text-xs font-medium rounded-r-lg border ${
                    overlayMode === "none"
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700"
                  }`}
                >
                  Hidden
                </button>
              </fieldset>
            </div>

            {overlayMode !== "none" && (
              <div className="flex items-center gap-2">
                <label htmlFor={opacityId} className="text-slate-500">
                  Opacity: {Math.round(overlayOpacity * 100)}%
                </label>
                <input
                  id={opacityId}
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={overlayOpacity}
                  onChange={(e) => onOverlayOpacityChange(parseFloat(e.target.value))}
                  className="w-24 accent-blue-600"
                />
              </div>
            )}
          </div>

          {/* Detected Candidate Change Regions */}
          {result.regions.length > 0 && (
            <div className="p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-xs">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-semibold text-slate-800 dark:text-slate-200">
                  Candidate Change Regions ({result.regions.length})
                </h4>
                <span className="text-slate-400 text-xs">Ranked by spatial area</span>
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
                {result.regions.map((reg) => {
                  const isSelected = selectedRegion?.id === reg.id;
                  return (
                    <button
                      key={reg.id}
                      type="button"
                      onClick={() => onSelectRegion(isSelected ? null : reg)}
                      className={`w-full text-left p-2 rounded flex items-center justify-between border transition ${
                        isSelected
                          ? "bg-blue-50 dark:bg-blue-900/30 border-blue-400 dark:border-blue-600"
                          : "bg-slate-50 dark:bg-slate-900/40 border-slate-200 dark:border-slate-700/60 hover:bg-slate-100 dark:hover:bg-slate-800"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            reg.category === "spectral_gain"
                              ? "bg-emerald-500"
                              : reg.category === "spectral_loss"
                                ? "bg-rose-500"
                                : "bg-amber-500"
                          }`}
                        />
                        <span className="font-medium text-slate-800 dark:text-slate-200">
                          {reg.id}
                        </span>
                        <span className="text-slate-400 capitalize">
                          ({reg.category.replace("_", " ")})
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-slate-500 dark:text-slate-400">
                        <span>{reg.area_km2.toFixed(4)} km²</span>
                        <span>{reg.pixel_count} px</span>
                        <span>
                          Mean Δ:{" "}
                          {reg.mean_magnitude > 0
                            ? `+${reg.mean_magnitude.toFixed(2)}`
                            : reg.mean_magnitude.toFixed(2)}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Traceability & Provenance */}
          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-slate-800 text-xs space-y-1 text-slate-600 dark:text-slate-400 font-mono">
            <div>
              <span className="font-sans font-semibold text-slate-700 dark:text-slate-300">
                Result ID:
              </span>{" "}
              {result.result_id}
            </div>
            <div>
              <span className="font-sans font-semibold text-slate-700 dark:text-slate-300">
                Diff Asset:
              </span>{" "}
              {result.difference_asset_id}
            </div>
            <div>
              <span className="font-sans font-semibold text-slate-700 dark:text-slate-300">
                Engine:
              </span>{" "}
              {result.provenance.software} ({result.provenance.duration_milliseconds} ms)
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
