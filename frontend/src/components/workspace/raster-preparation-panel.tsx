"use client";

import { useId } from "react";

import type { AnalysisWarning } from "@/lib/analysis-contracts";
import type {
  PreparedRasterAsset,
  PreparedTemporalPair,
  PreparationStatus,
  ResamplingMethod,
  TargetGridStrategy,
} from "@/lib/preparation-contracts";

export interface RasterPreparationPanelProps {
  readonly mode: "single" | "temporal";
  readonly sceneId?: string;
  readonly beforeSceneId?: string;
  readonly afterSceneId?: string;
  readonly targetCrs: string;
  readonly onTargetCrsChange: (crs: string) => void;
  readonly targetResolutionMeters: number | null;
  readonly onTargetResolutionChange: (res: number | null) => void;
  readonly resamplingMethod: ResamplingMethod;
  readonly onResamplingMethodChange: (method: ResamplingMethod) => void;
  readonly strategy: TargetGridStrategy;
  readonly onStrategyChange: (strategy: TargetGridStrategy) => void;
  readonly isPreparing: boolean;
  readonly status: PreparationStatus;
  readonly preparedSingleAsset: PreparedRasterAsset | null;
  readonly preparedPair: PreparedTemporalPair | null;
  readonly error: string | null;
  readonly warnings: readonly AnalysisWarning[];
  readonly blockingIssues: readonly string[];
  readonly isReadyForAnalysis: boolean;
  readonly showPreparedPreview: boolean;
  readonly onTogglePreparedPreview: (show: boolean) => void;
  readonly onStartPreparation: () => void;
  readonly onCancelPreparation: () => void;
  readonly onContinueToAnalysis?: () => void;
}

export function RasterPreparationPanel({
  mode,
  sceneId,
  beforeSceneId,
  afterSceneId,
  targetCrs,
  onTargetCrsChange,
  targetResolutionMeters,
  onTargetResolutionChange,
  resamplingMethod,
  onResamplingMethodChange,
  strategy,
  onStrategyChange,
  isPreparing,
  status,
  preparedSingleAsset,
  preparedPair,
  error,
  warnings,
  blockingIssues,
  isReadyForAnalysis,
  showPreparedPreview,
  onTogglePreparedPreview,
  onStartPreparation,
  onCancelPreparation,
  onContinueToAnalysis,
}: RasterPreparationPanelProps) {
  const crsInputId = useId();
  const resSelectId = useId();
  const resampSelectId = useId();
  const stratSelectId = useId();
  const previewToggleId = useId();

  const isComplete = status === "ready" || status === "ready_with_warnings";
  const hasPreparedData = mode === "single" ? preparedSingleAsset !== null : preparedPair !== null;

  return (
    <section className="raster-preparation-panel" aria-label="Raster Preparation Panel">
      <div className="preparation-panel-header">
        <div>
          <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Analysis Preparation &amp; Raster Harmonization
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {mode === "single"
              ? `Reproject and clip scene ${sceneId ?? ""} to metric analysis grid`
              : `Harmonise and strictly co-register temporal pair onto identical pixel grid`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300">
            {mode === "single" ? "Single Scene" : "Temporal Pair"}
          </span>
          {isComplete && (
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                status === "ready"
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                  : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
              }`}
            >
              {status === "ready" ? "Ready for Analysis" : "Ready (with warnings)"}
            </span>
          )}
        </div>
      </div>

      {/* Configuration Controls */}
      <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3 bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
        <div>
          <label
            htmlFor={crsInputId}
            className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1"
          >
            Target Analysis CRS
          </label>
          <select
            id={crsInputId}
            value={targetCrs}
            onChange={(e) => onTargetCrsChange(e.target.value)}
            disabled={isPreparing}
            className="w-full text-xs rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-slate-900 dark:text-slate-100"
          >
            <option value="AUTO">Auto-Select UTM Metric Grid (Recommended)</option>
            <option value="EPSG:32643">UTM Zone 43N (EPSG:32643)</option>
            <option value="EPSG:32644">UTM Zone 44N (EPSG:32644)</option>
            <option value="EPSG:3857">Web Mercator (EPSG:3857)</option>
            <option value="EPSG:4326">WGS84 Geographic (EPSG:4326)</option>
          </select>
        </div>

        <div>
          <label
            htmlFor={resSelectId}
            className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1"
          >
            Target Resolution
          </label>
          <select
            id={resSelectId}
            value={targetResolutionMeters ?? "auto"}
            onChange={(e) =>
              onTargetResolutionChange(
                e.target.value === "auto" ? null : parseFloat(e.target.value),
              )
            }
            disabled={isPreparing}
            className="w-full text-xs rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-slate-900 dark:text-slate-100"
          >
            <option value="10">10 metres / pixel (Native Sentinel-2)</option>
            <option value="20">20 metres / pixel (RedEdge / SWIR)</option>
            <option value="30">30 metres / pixel (Landsat compatible)</option>
            <option value="auto">Auto (Preserve native)</option>
          </select>
        </div>

        {mode === "temporal" && (
          <div>
            <label
              htmlFor={stratSelectId}
              className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1"
            >
              Grid &amp; Extent Strategy
            </label>
            <select
              id={stratSelectId}
              value={strategy}
              onChange={(e) => onStrategyChange(e.target.value as TargetGridStrategy)}
              disabled={isPreparing}
              className="w-full text-xs rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-slate-900 dark:text-slate-100"
            >
              <option value="common_intersection">Common AOI Intersection (Recommended)</option>
              <option value="reference_before">Reference Before Scene Grid</option>
              <option value="reference_after">Reference After Scene Grid</option>
              <option value="highest_resolution">Highest Resolution Grid</option>
            </select>
          </div>
        )}

        <div>
          <label
            htmlFor={resampSelectId}
            className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1"
          >
            Resampling Method
          </label>
          <select
            id={resampSelectId}
            value={resamplingMethod}
            onChange={(e) => onResamplingMethodChange(e.target.value as ResamplingMethod)}
            disabled={isPreparing}
            className="w-full text-xs rounded border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-2.5 py-1.5 text-slate-900 dark:text-slate-100"
          >
            <option value="bilinear">Bilinear Interpolation (Continuous Reflectance)</option>
            <option value="cubic">Bicubic Convolution (Smooth)</option>
            <option value="average">Area Averaging (Downsampling)</option>
            <option value="nearest">Nearest Neighbour (Categorical / Masks)</option>
          </select>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onStartPreparation}
            disabled={isPreparing}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white disabled:opacity-50 transition-colors shadow-sm"
          >
            {isPreparing ? (
              <>
                <svg
                  className="animate-spin -ml-0.5 mr-1.5 h-3.5 w-3.5 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Processing ({status.replace(/_/g, " ")})...
              </>
            ) : hasPreparedData ? (
              "Re-run Preparation"
            ) : (
              "Harmonise & Prepare for Analysis"
            )}
          </button>

          {isPreparing && (
            <button
              type="button"
              onClick={onCancelPreparation}
              className="px-3 py-2 rounded-md text-xs font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
          )}
        </div>

        {hasPreparedData && (
          <div className="flex items-center gap-2">
            <label
              htmlFor={previewToggleId}
              className="flex items-center gap-1.5 text-xs font-medium text-slate-700 dark:text-slate-300 cursor-pointer"
            >
              <input
                id={previewToggleId}
                type="checkbox"
                checked={showPreparedPreview}
                onChange={(e) => onTogglePreparedPreview(e.target.checked)}
                className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              Show Prepared Preview on Map
            </label>
          </div>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="mt-3 p-3 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-md text-xs text-red-700 dark:text-red-300">
          <p className="font-semibold">Preparation Error</p>
          <p className="mt-0.5">{error}</p>
        </div>
      )}

      {/* Blocking issues */}
      {blockingIssues.length > 0 && (
        <div className="mt-3 p-3 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 rounded-md text-xs text-rose-800 dark:text-rose-200">
          <p className="font-bold">Blocking Issues (Analysis Not Supported):</p>
          <ul className="list-disc list-inside mt-1 space-y-0.5">
            {blockingIssues.map((issue) => (
              <li key={issue}>{issue.replace(/_/g, " ")}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings display */}
      {warnings.length > 0 && (
        <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-md text-xs text-amber-800 dark:text-amber-200">
          <p className="font-semibold">Preparation Warnings:</p>
          <ul className="list-disc list-inside mt-1 space-y-0.5">
            {warnings.map((w) => (
              <li key={`${w.code}-${w.message}`}>
                <span className="font-medium">{w.title || w.code}:</span> {w.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Prepared Output Metrics Card */}
      {hasPreparedData && (
        <div className="mt-4 p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wide">
              Prepared Raster Metrics
            </h4>
            <span className="text-[11px] text-slate-500 dark:text-slate-400">
              {mode === "single"
                ? `Asset: ${preparedSingleAsset?.asset_id}`
                : `Pair Prep: ${preparedPair?.preparation_id}`}
            </span>
          </div>

          {mode === "single" && preparedSingleAsset && (
            <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                <span className="block text-[11px] text-slate-500 dark:text-slate-400">CRS</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {preparedSingleAsset.crs}
                </span>
              </div>
              <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                  Dimensions
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {preparedSingleAsset.width} × {preparedSingleAsset.height} px
                </span>
              </div>
              <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                  Valid Data
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {preparedSingleAsset.valid_data_percent.toFixed(1)}%
                </span>
              </div>
              <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                  Resolution
                </span>
                <span className="font-semibold text-slate-800 dark:text-slate-200">
                  {preparedSingleAsset.resolution_meters.toFixed(1)} m/px
                </span>
              </div>
            </div>
          )}

          {mode === "temporal" && preparedPair && (
            <div className="mt-2 space-y-2 text-xs">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                  <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                    Common CRS
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {preparedPair.common_crs}
                  </span>
                </div>
                <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                  <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                    Co-registered Grid
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {preparedPair.common_width} × {preparedPair.common_height} px
                  </span>
                </div>
                <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                  <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                    Shared Valid Pixels
                  </span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {preparedPair.shared_valid_percent.toFixed(1)}% (
                    {preparedPair.shared_valid_pixel_count.toLocaleString()} px)
                  </span>
                </div>
                <div className="p-2 bg-slate-50 dark:bg-slate-800 rounded">
                  <span className="block text-[11px] text-slate-500 dark:text-slate-400">
                    Alignment Status
                  </span>
                  <span className="font-semibold text-emerald-700 dark:text-emerald-400">
                    {preparedPair.alignment_status.toUpperCase()}
                  </span>
                </div>
              </div>

              <div className="p-2 bg-slate-50 dark:bg-slate-800/60 rounded flex items-center justify-between text-[11px] text-slate-600 dark:text-slate-400">
                <span>
                  <strong>Before Scene:</strong> {beforeSceneId ?? "Scene A"} (
                  {preparedPair.before_asset.resolution_meters}m)
                </span>
                <span>
                  <strong>After Scene:</strong> {afterSceneId ?? "Scene B"} (
                  {preparedPair.after_asset.resolution_meters}m)
                </span>
                <span>
                  <strong>Quality Score:</strong> {preparedPair.quality.quality_score.toFixed(2)}
                </span>
              </div>
            </div>
          )}

          {/* Scientific Boundary Disclaimer Banner */}
          <div className="mt-3 p-2 bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-800/40 rounded text-[11px] text-blue-900 dark:text-blue-200 flex items-start gap-1.5">
            <svg
              className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 mt-0.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span>
              <strong>Scientific Preparation Status:</strong> Images are spatially prepared and
              strictly co-registered for subsequent analysis. No spectral indices or change
              detection have been performed yet.
            </span>
          </div>
        </div>
      )}

      {/* Continuation to Spectral/Change Analysis */}
      {onContinueToAnalysis && (
        <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-800 flex justify-end">
          <button
            type="button"
            onClick={onContinueToAnalysis}
            disabled={!isReadyForAnalysis}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-sm"
          >
            Continue to Spectral Analysis &rarr;
          </button>
        </div>
      )}
    </section>
  );
}
