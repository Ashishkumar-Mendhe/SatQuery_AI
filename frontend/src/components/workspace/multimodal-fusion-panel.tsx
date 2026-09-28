"use client";

import { useId } from "react";

import type { AnalysisWarning } from "@/lib/analysis-contracts";
import type {
  FusionCapabilitiesResponse,
  FusionResult,
  JointObservationState,
  SARThresholdConfig,
} from "@/lib/fusion-contracts";

export interface MultimodalFusionPanelProps {
  readonly opticalResultId: string | null;
  readonly onSelectOpticalResultId: (id: string | null) => void;
  readonly sarBeforeAssetId: string | null;
  readonly onSelectSarBeforeAssetId: (id: string | null) => void;
  readonly sarAfterAssetId: string | null;
  readonly onSelectSarAfterAssetId: (id: string | null) => void;
  readonly temporalToleranceDays: number;
  readonly onTemporalToleranceDaysChange: (days: number) => void;
  readonly sarThresholdConfig: SARThresholdConfig;
  readonly onSarThresholdConfigChange: (config: SARThresholdConfig) => void;
  readonly allowPartial?: boolean;
  readonly onAllowPartialChange?: (allow: boolean) => void;
  readonly capabilities: FusionCapabilitiesResponse | null;
  readonly isExecuting: boolean;
  readonly result: FusionResult | null;
  readonly error: string | null;
  readonly warnings?: readonly AnalysisWarning[];
  readonly selectedRegionId: string | null;
  readonly onSelectRegionId: (id: string | null) => void;
  readonly overlayVisible: boolean;
  readonly onOverlayVisibleChange: (visible: boolean) => void;
  readonly overlayOpacity: number;
  readonly onOverlayOpacityChange: (opacity: number) => void;
  readonly onExecuteFusion: () => void;
  readonly onClearResult: () => void;
}

export function MultimodalFusionPanel({
  opticalResultId,
  onSelectOpticalResultId,
  sarBeforeAssetId,
  onSelectSarBeforeAssetId,
  sarAfterAssetId,
  onSelectSarAfterAssetId,
  temporalToleranceDays,
  onTemporalToleranceDaysChange,
  sarThresholdConfig,
  onSarThresholdConfigChange,
  allowPartial: _allowPartial = false,
  onAllowPartialChange: _onAllowPartialChange,
  capabilities: _capabilities = null,
  isExecuting,
  result,
  error,
  warnings: _warnings = [],
  selectedRegionId,
  onSelectRegionId,
  overlayVisible,
  onOverlayVisibleChange,
  overlayOpacity,
  onOverlayOpacityChange,
  onExecuteFusion,
  onClearResult,
}: MultimodalFusionPanelProps) {
  const optInputId = useId();
  const sarBeforeInputId = useId();
  const sarAfterInputId = useId();
  const tolInputId = useId();
  const sarIncThreshId = useId();
  const sarDecThreshId = useId();
  const opacityId = useId();

  const canRun = Boolean(opticalResultId || (sarBeforeAssetId && sarAfterAssetId));

  const stateLabels: Record<JointObservationState, { label: string; color: string; desc: string }> =
    {
      both_detect_change: {
        label: "Both Sensors Detected Response Change",
        color: "bg-amber-500 text-white",
        desc: "Co-occurring optical index differencing and SAR backscatter change within validated tolerance.",
      },
      optical_response_only: {
        label: "Optical Response Only",
        color: "bg-emerald-600 text-white",
        desc: "Optical detected spectral change while SAR backscatter remained below cutoff.",
      },
      sar_response_only: {
        label: "SAR Response Only",
        color: "bg-blue-600 text-white",
        desc: "SAR backscatter delta exceeded threshold while optical spectral index remained below cutoff.",
      },
      neither_above_threshold: {
        label: "Neither Above Threshold (Stable)",
        color: "bg-slate-500 text-white",
        desc: "Both sensors observed valid data with change magnitudes below their respective thresholds.",
      },
      uncertain: {
        label: "Uncertain / Noise-Filtered",
        color: "bg-purple-600 text-white",
        desc: "Observations in this region were flagged with uncertainty or low confidence.",
      },
    };

  return (
    <section
      className="multimodal-fusion-panel p-4 space-y-6 bg-slate-900 border border-slate-800 rounded-xl text-slate-100"
      aria-label="Multimodal Optical and SAR Evidence Fusion"
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-800">
        <div>
          <h2 className="text-lg font-semibold text-white">Multimodal Evidence Fusion</h2>
          <p className="text-xs text-slate-400">
            Combine measured optical and SAR evidence across co-registered grids and compatible
            observation windows.
          </p>
        </div>
        {result && (
          <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-950/80 border border-emerald-500/40 text-emerald-400">
            Quality Score: {Math.round(result.quality.score * 100)}%
          </span>
        )}
      </div>

      {/* Input Configuration & 4-Role Timeline */}
      <div className="space-y-4">
        <h3 className="text-sm font-medium text-slate-300">Observation Stream Selection</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <label htmlFor={optInputId} className="block text-xs font-medium text-slate-400 mb-1">
              Optical Change Result ID
            </label>
            <input
              id={optInputId}
              type="text"
              value={opticalResultId || ""}
              onChange={(e) => onSelectOpticalResultId(e.target.value.trim() || null)}
              placeholder="e.g. change-res-..."
              className="w-full px-3 py-1.5 text-xs rounded bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-amber-500"
            />
          </div>
          <div>
            <label
              htmlFor={sarBeforeInputId}
              className="block text-xs font-medium text-slate-400 mb-1"
            >
              SAR Before Asset ID
            </label>
            <input
              id={sarBeforeInputId}
              type="text"
              value={sarBeforeAssetId || ""}
              onChange={(e) => onSelectSarBeforeAssetId(e.target.value.trim() || null)}
              placeholder="e.g. sar-prepared-before-..."
              className="w-full px-3 py-1.5 text-xs rounded bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-amber-500"
            />
          </div>
          <div>
            <label
              htmlFor={sarAfterInputId}
              className="block text-xs font-medium text-slate-400 mb-1"
            >
              SAR After Asset ID
            </label>
            <input
              id={sarAfterInputId}
              type="text"
              value={sarAfterAssetId || ""}
              onChange={(e) => onSelectSarAfterAssetId(e.target.value.trim() || null)}
              placeholder="e.g. sar-prepared-after-..."
              className="w-full px-3 py-1.5 text-xs rounded bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-amber-500"
            />
          </div>
        </div>

        {/* 4-Role Observation Timeline (if result exists) */}
        {result?.observations && result.observations.length === 4 && (
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-300">
                4-Role Temporal Observations
              </span>
              <span
                className={`text-[11px] px-2 py-0.5 rounded font-medium ${
                  result.compatibility.status === "valid"
                    ? "bg-emerald-950 text-emerald-400 border border-emerald-500/30"
                    : result.compatibility.status === "compatible_with_warnings"
                      ? "bg-amber-950 text-amber-400 border border-amber-500/30"
                      : "bg-rose-950 text-rose-400 border border-rose-500/30"
                }`}
              >
                {result.compatibility.status.replace(/_/g, " ").toUpperCase()}
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-[11px]">
              {result.observations.map((obs) => (
                <div key={obs.role} className="p-2 rounded bg-slate-900/60 border border-slate-800">
                  <div className="font-semibold text-slate-300 capitalize">
                    {obs.role.replace(/_/g, " ")}
                  </div>
                  <div className="text-slate-400 truncate" title={obs.scene_id}>
                    {obs.scene_id}
                  </div>
                  <div className="text-slate-500">
                    {new Date(obs.acquisition_timestamp).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
            {result.compatibility.timing && (
              <div className="text-[11px] text-slate-400 flex gap-4 pt-1 border-t border-slate-800/60">
                <span>
                  Before Offset:{" "}
                  <strong className="text-slate-200">
                    {result.compatibility.timing.before_offset_days.toFixed(1)}d
                  </strong>
                </span>
                <span>
                  After Offset:{" "}
                  <strong className="text-slate-200">
                    {result.compatibility.timing.after_offset_days.toFixed(1)}d
                  </strong>
                </span>
                <span>
                  Interval Overlap:{" "}
                  <strong className="text-slate-200">
                    {Math.round(result.compatibility.timing.interval_overlap_ratio * 100)}%
                  </strong>
                </span>
              </div>
            )}
          </div>
        )}

        {/* Parameters */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-xs">
          <div>
            <label htmlFor={tolInputId} className="block text-slate-400 mb-1">
              Temporal Tolerance (Days)
            </label>
            <input
              id={tolInputId}
              type="number"
              min={1}
              max={365}
              value={temporalToleranceDays}
              onChange={(e) => onTemporalToleranceDaysChange(Number(e.target.value) || 30)}
              className="w-full px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200"
            />
          </div>
          <div>
            <label htmlFor={sarIncThreshId} className="block text-slate-400 mb-1">
              SAR Increase Cutoff (dB)
            </label>
            <input
              id={sarIncThreshId}
              type="number"
              step="0.1"
              value={sarThresholdConfig.increase_threshold_db}
              onChange={(e) =>
                onSarThresholdConfigChange({
                  ...sarThresholdConfig,
                  increase_threshold_db: Number(e.target.value) || 2.0,
                })
              }
              className="w-full px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200"
            />
          </div>
          <div>
            <label htmlFor={sarDecThreshId} className="block text-slate-400 mb-1">
              SAR Decrease Cutoff (dB)
            </label>
            <input
              id={sarDecThreshId}
              type="number"
              step="0.1"
              value={sarThresholdConfig.decrease_threshold_db}
              onChange={(e) =>
                onSarThresholdConfigChange({
                  ...sarThresholdConfig,
                  decrease_threshold_db: Number(e.target.value) || -2.0,
                })
              }
              className="w-full px-2.5 py-1 rounded bg-slate-900 border border-slate-700 text-slate-200"
            />
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onExecuteFusion}
          disabled={!canRun || isExecuting}
          className="px-4 py-2 text-xs font-semibold rounded bg-amber-500 hover:bg-amber-400 text-slate-950 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isExecuting ? "Executing Fusion..." : "Run Multimodal Evidence Fusion"}
        </button>
        {result && (
          <button
            type="button"
            onClick={onClearResult}
            className="px-3 py-2 text-xs font-medium rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
          >
            Clear Result
          </button>
        )}
      </div>

      {error && (
        <div className="p-3 bg-rose-950/80 border border-rose-800 text-rose-300 text-xs rounded-lg">
          {error}
        </div>
      )}

      {/* Scientific Limitations & Non-Physical Grounding Disclaimer Banner */}
      <div className="p-3 bg-amber-950/40 border border-amber-800/60 rounded-lg text-xs text-amber-300/90 flex items-start gap-2.5">
        <span className="font-bold text-amber-400 text-sm">ℹ</span>
        <div>
          <strong className="font-semibold text-amber-200">Scientific Grounding Disclaimer:</strong>{" "}
          Evidence-level fusion reports spatial-temporal co-occurrence of measured optical spectral
          differences and calibrated SAR backscatter delta (&Delta;dB). It does <em>not</em>{" "}
          establish a confirmed physical cause (e.g. flood inundation, building construction, or
          crop loss). Physical causes remain unverified hypotheses.
        </div>
      </div>

      {/* Results View */}
      {result && (
        <div className="space-y-6 pt-3 border-t border-slate-800">
          {/* Coverage Partitioning Section (Total AOI breakdown) */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-slate-200">AOI Coverage Partitioning</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">Jointly Observable (J)</div>
                <div className="text-base font-bold text-slate-100">
                  {result.coverage.jointly_observable_area_km2.toFixed(4)} km²
                </div>
                <div className="text-[11px] text-amber-400">
                  {result.coverage.joint_percent_of_aoi.toFixed(1)}% of AOI
                </div>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">Optical Coverage Only</div>
                <div className="text-base font-bold text-slate-100">
                  {result.coverage.optical_only_area_km2.toFixed(4)} km²
                </div>
                <div className="text-[11px] text-emerald-400">
                  {result.coverage.optical_only_percent_of_aoi.toFixed(1)}% of AOI
                </div>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">SAR Coverage Only</div>
                <div className="text-base font-bold text-slate-100">
                  {result.coverage.sar_only_area_km2.toFixed(4)} km²
                </div>
                <div className="text-[11px] text-blue-400">
                  {result.coverage.sar_only_percent_of_aoi.toFixed(1)}% of AOI
                </div>
              </div>
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg">
                <div className="text-slate-400">Neither Sensor Available</div>
                <div className="text-base font-bold text-slate-100">
                  {result.coverage.neither_area_km2.toFixed(4)} km²
                </div>
                <div className="text-[11px] text-slate-500">
                  {result.coverage.neither_percent_of_aoi.toFixed(1)}% of AOI
                </div>
              </div>
            </div>
          </div>

          {/* Joint State Breakdown Table (Denominator strictly J) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200">
                Joint Observation States (Within J ={" "}
                {result.coverage.jointly_observable_area_km2.toFixed(4)} km²)
              </h3>
              <span className="text-[11px] text-slate-400 italic">
                Denominator: strictly jointly observable area J
              </span>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/50 text-slate-400">
                    <th className="p-2.5">Observation State</th>
                    <th className="p-2.5 text-right">Area (km²)</th>
                    <th className="p-2.5 text-right">Pixels</th>
                    <th className="p-2.5 text-right">% of Joint (J)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  <tr className="hover:bg-slate-900/40">
                    <td className="p-2.5 font-medium flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block" />
                      Both Sensors Detected Response Change
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.both_detect_change_area_km2.toFixed(4)}
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.pixel_counts.both_detect_change_pixels}
                    </td>
                    <td className="p-2.5 text-right font-semibold text-amber-400">
                      {result.joint_metrics.both_detect_change_percent != null
                        ? `${result.joint_metrics.both_detect_change_percent.toFixed(1)}%`
                        : "N/A"}
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-900/40">
                    <td className="p-2.5 font-medium flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />
                      Optical Response Only
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.optical_response_only_area_km2.toFixed(4)}
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.pixel_counts.optical_response_only_pixels}
                    </td>
                    <td className="p-2.5 text-right font-semibold text-emerald-400">
                      {result.joint_metrics.optical_response_only_percent != null
                        ? `${result.joint_metrics.optical_response_only_percent.toFixed(1)}%`
                        : "N/A"}
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-900/40">
                    <td className="p-2.5 font-medium flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block" />
                      SAR Response Only
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.sar_response_only_area_km2.toFixed(4)}
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.pixel_counts.sar_response_only_pixels}
                    </td>
                    <td className="p-2.5 text-right font-semibold text-blue-400">
                      {result.joint_metrics.sar_response_only_percent != null
                        ? `${result.joint_metrics.sar_response_only_percent.toFixed(1)}%`
                        : "N/A"}
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-900/40">
                    <td className="p-2.5 font-medium flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-slate-500 inline-block" />
                      Neither Above Threshold (Stable)
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.neither_above_threshold_area_km2.toFixed(4)}
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.pixel_counts.neither_above_threshold_pixels}
                    </td>
                    <td className="p-2.5 text-right font-semibold text-slate-400">
                      {result.joint_metrics.neither_above_threshold_percent != null
                        ? `${result.joint_metrics.neither_above_threshold_percent.toFixed(1)}%`
                        : "N/A"}
                    </td>
                  </tr>
                  <tr className="hover:bg-slate-900/40">
                    <td className="p-2.5 font-medium flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-purple-500 inline-block" />
                      Uncertain / Noise-Filtered
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.uncertain_area_km2.toFixed(4)}
                    </td>
                    <td className="p-2.5 text-right font-mono">
                      {result.joint_metrics.pixel_counts.uncertain_pixels}
                    </td>
                    <td className="p-2.5 text-right font-semibold text-purple-400">
                      {result.joint_metrics.uncertain_percent != null
                        ? `${result.joint_metrics.uncertain_percent.toFixed(1)}%`
                        : "N/A"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Fused Vector Regions */}
          {result.regions.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-slate-200">
                Fused Candidate Regions ({result.regions.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                {result.regions.map((reg) => {
                  const isSelected = reg.id === selectedRegionId;
                  const st = stateLabels[reg.state];
                  return (
                    <button
                      key={reg.id}
                      type="button"
                      onClick={() => onSelectRegionId(isSelected ? null : reg.id)}
                      className={`p-3 rounded-lg border text-left text-xs transition-all ${
                        isSelected
                          ? "bg-slate-800 border-amber-500 shadow-md ring-1 ring-amber-500/50"
                          : "bg-slate-950 border-slate-800 hover:bg-slate-900"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${st.color}`}>
                          {st.label}
                        </span>
                        <span className="font-mono text-slate-300 font-semibold">
                          {reg.area_km2.toFixed(4)} km²
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-2 mb-1">
                        {reg.rule_explanation}
                      </p>
                      <div className="text-[10px] text-slate-500">
                        Pixels: {reg.pixel_count} | Confidence: {Math.round(reg.confidence * 100)}%
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Map Overlay Controls */}
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex items-center justify-between text-xs">
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={overlayVisible}
                  onChange={(e) => onOverlayVisibleChange(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-amber-500 focus:ring-0"
                />
                <span className="font-medium text-slate-300">Show Fusion Map Overlay</span>
              </label>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor={opacityId} className="text-slate-400">
                Opacity:
              </label>
              <input
                id={opacityId}
                type="range"
                min="0.1"
                max="1.0"
                step="0.05"
                value={overlayOpacity}
                onChange={(e) => onOverlayOpacityChange(parseFloat(e.target.value))}
                className="w-24 accent-amber-500"
              />
              <span className="font-mono text-slate-300 w-8">
                {Math.round(overlayOpacity * 100)}%
              </span>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
