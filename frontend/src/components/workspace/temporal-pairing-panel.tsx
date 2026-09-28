"use client";

import { useId, useState } from "react";
import type { SatelliteScene } from "@/lib/analysis-contracts";
import type { SelectedAoi } from "@/lib/aoi";
import type {
  PairCompatibilityIssue,
  TemporalPairValidationResult,
  TemporalSceneCandidates,
} from "@/lib/temporal-contracts";
import { useImagery } from "@/lib/use-imagery";
import { TemporalComparisonPanel } from "./temporal-comparison-panel";

export interface TemporalPairingPanelProps {
  readonly selectedAoi?: SelectedAoi | null;
  readonly candidates: TemporalSceneCandidates | null;
  readonly searchState: "idle" | "searching" | "error";
  readonly searchError: string | null;
  readonly selectedBeforeScene: SatelliteScene | null;
  readonly selectedAfterScene: SatelliteScene | null;
  readonly validationResult: TemporalPairValidationResult | null;
  readonly validationState: "idle" | "validating" | "error";
  readonly validationError: string | null;
  readonly onSearchCandidates: () => void;
  readonly onSelectBeforeScene: (scene: SatelliteScene | null) => void;
  readonly onSelectAfterScene: (scene: SatelliteScene | null) => void;
  readonly onApplyRecommendedPair: () => void;
  readonly onClearSelection: () => void;
  readonly onContinue?: () => void;
  readonly disabled?: boolean;
}

function formatTimestamp(isoStr: string): string {
  try {
    const dt = new Date(isoStr);
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }).format(dt);
  } catch {
    return isoStr;
  }
}

function CandidateCard({
  scene,
  isSelected,
  onSelect,
  periodRole,
}: {
  readonly scene: SatelliteScene;
  readonly isSelected: boolean;
  readonly onSelect: () => void;
  readonly periodRole: "before" | "after";
}) {
  const isOptical = scene.sensor_type === "optical" || scene.sensor_type === "multispectral";
  const cloudCover =
    scene.cloud_cover !== null && scene.cloud_cover !== undefined
      ? `${scene.cloud_cover.toFixed(1)}%`
      : "N/A";
  const origin = (scene.metadata?.data_origin as string) ?? "real";

  return (
    <div className={`temporal-candidate-card ${isSelected ? "selected" : ""}`}>
      <div className="candidate-card-header">
        <span className="candidate-platform-badge">{scene.platform ?? scene.collection}</span>
        <span className={`candidate-origin-badge origin-${origin}`}>{origin.toUpperCase()}</span>
      </div>

      <div className="candidate-id" title={scene.id}>
        {scene.id}
      </div>

      <div className="candidate-meta-grid">
        <div className="meta-item">
          <span className="meta-label">Acquired (UTC):</span>
          <span className="meta-value">{formatTimestamp(scene.acquisition_time)}</span>
        </div>
        {isOptical ? (
          <div className="meta-item">
            <span className="meta-label">Cloud Cover:</span>
            <span
              className={`meta-value ${scene.cloud_cover && scene.cloud_cover > 20 ? "warn-cloud" : ""}`}
            >
              {cloudCover}
            </span>
          </div>
        ) : null}
        <div className="meta-item">
          <span className="meta-label">Resolution:</span>
          <span className="meta-value">
            {scene.resolution_meters ? `${scene.resolution_meters}m` : "10m"}
          </span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Bands:</span>
          <span className="meta-value">
            {scene.available_bands.slice(0, 4).join(", ") || "Standard"}
          </span>
        </div>
      </div>

      <button
        type="button"
        className={`candidate-select-btn ${isSelected ? "active" : ""}`}
        onClick={onSelect}
        aria-pressed={isSelected}
      >
        {isSelected
          ? `✓ Selected as ${periodRole.toUpperCase()}`
          : `Select for ${periodRole.toUpperCase()}`}
      </button>
    </div>
  );
}

function CompatibilitySummary({
  result,
  validationState,
  onClear,
  onContinue,
}: {
  readonly result: TemporalPairValidationResult;
  readonly validationState: "idle" | "validating" | "error";
  readonly onClear: () => void;
  readonly onContinue?: () => void;
}) {
  const scorePercent = Math.round(result.compatibility_score * 100);
  const statusLabel =
    result.status === "compatible"
      ? "Strong Match (Compatible)"
      : result.status === "compatible_with_warnings"
        ? "Usable with Warnings"
        : "Incompatible";

  const statusClass =
    result.status === "compatible"
      ? "status-compatible"
      : result.status === "compatible_with_warnings"
        ? "status-warnings"
        : "status-incompatible";

  return (
    <section className="temporal-compatibility-summary" aria-labelledby="compat-heading">
      <div className="compat-header">
        <div>
          <span className="panel-kicker">Authoritative Pair Compatibility</span>
          <h4 id="compat-heading" className={`compat-status-title ${statusClass}`}>
            {statusLabel}
          </h4>
        </div>
        <div className="compat-score-pill">
          <span className="score-num">{scorePercent}%</span>
          <span className="score-label">Compatibility</span>
        </div>
      </div>

      <div className="compat-metrics-grid">
        <div className="compat-metric-card">
          <span className="metric-title">Temporal Gap</span>
          <span className="metric-val">{result.temporal_gap_days.toFixed(1)} days</span>
        </div>
        <div className="compat-metric-card">
          <span className="metric-title">Mutual AOI Coverage</span>
          <span className="metric-val">
            {result.spatial_metrics?.mutual_aoi_coverage_percent !== undefined
              ? `${result.spatial_metrics.mutual_aoi_coverage_percent.toFixed(1)}%`
              : "100%"}
          </span>
        </div>
        <div className="compat-metric-card">
          <span className="metric-title">Footprint Overlap</span>
          <span className="metric-val">
            {result.spatial_metrics?.scene_overlap_percent !== undefined
              ? `${result.spatial_metrics.scene_overlap_percent.toFixed(1)}%`
              : "100%"}
          </span>
        </div>
        <div className="compat-metric-card">
          <span className="metric-title">Data Origin</span>
          <span className="metric-val origin-text">{result.data_origin_status.toUpperCase()}</span>
        </div>
      </div>

      {result.issues.length > 0 ? (
        <div className="compat-issues-list">
          <h5>Detected Compatibility Factors & Alerts</h5>
          {result.issues.map((issue: PairCompatibilityIssue) => (
            <div
              key={issue.code}
              className={`issue-alert ${issue.blocking ? "blocking-issue" : "warning-issue"}`}
              role="alert"
            >
              <div className="issue-title-row">
                <span className="issue-badge">{issue.blocking ? "BLOCKING" : "WARNING"}</span>
                <strong>{issue.title}</strong>
              </div>
              <p className="issue-msg">{issue.message}</p>
              {issue.suggested_action ? (
                <p className="issue-action">
                  <em>Action:</em> {issue.suggested_action}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="compat-factors-breakdown">
        <h5>Compatibility Factor Weights</h5>
        <div className="factors-row">
          {result.factors.map((f) => (
            <div key={f.name} className="factor-pill">
              <span className="factor-name">{f.name.replace(/_/g, " ")}:</span>
              <span className="factor-score">{(f.score * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="compat-actions-row">
        <button type="button" className="action-btn secondary" onClick={onClear}>
          Clear Selection
        </button>
        <button
          type="button"
          className="action-btn primary"
          disabled={!result.valid || validationState === "validating"}
          onClick={onContinue}
        >
          {result.valid ? "Continue to Imagery Preparation →" : "Selection Incompatible"}
        </button>
      </div>
    </section>
  );
}

export function TemporalPairingPanel({
  selectedAoi,
  candidates,
  searchState,
  searchError,
  selectedBeforeScene,
  selectedAfterScene,
  validationResult,
  validationState,
  validationError,
  onSearchCandidates,
  onSelectBeforeScene,
  onSelectAfterScene,
  onApplyRecommendedPair,
  onClearSelection,
  onContinue,
  disabled = false,
}: TemporalPairingPanelProps) {
  const panelTitleId = useId();
  const [showComparison, setShowComparison] = useState(false);

  const beforeScenes = candidates?.before_scenes ?? [];
  const afterScenes = candidates?.after_scenes ?? [];

  const imagery = useImagery({
    selectedAoi,
    beforeSceneId: selectedBeforeScene?.id,
    afterSceneId: selectedAfterScene?.id,
    sensorType: selectedBeforeScene?.sensor_type,
  });

  const handleContinue = () => {
    setShowComparison(true);
    onContinue?.();
  };

  return (
    <section className="temporal-pairing-panel" aria-labelledby={panelTitleId}>
      <div className="temporal-panel-header">
        <div>
          <p className="panel-kicker">Bi-Temporal Discovery & Pairing</p>
          <h3 id={panelTitleId}>Select Before & After Satellite Scenes</h3>
        </div>
        <button
          type="button"
          disabled={disabled || searchState === "searching"}
          className="search-temporal-btn"
          onClick={onSearchCandidates}
        >
          {searchState === "searching" ? "Searching Catalogue…" : "Discover Scene Candidates"}
        </button>
      </div>

      {searchError ? (
        <div className="temporal-error-banner" role="alert">
          <p>{searchError}</p>
        </div>
      ) : null}

      {candidates?.recommended_pair ? (
        <div className="recommended-pair-banner">
          <div className="rec-info">
            <span className="rec-badge">RECOMMENDED PAIR</span>
            <span className="rec-score">
              {Math.round(candidates.recommended_pair.compatibility_score * 100)}% Match
            </span>
            <p className="rec-reason">{candidates.recommended_pair.reason}</p>
          </div>
          <button type="button" className="apply-rec-btn" onClick={onApplyRecommendedPair}>
            Apply Recommended Pair
          </button>
        </div>
      ) : null}

      <div className="temporal-periods-grid">
        {/* BEFORE PERIOD COLUMN */}
        <div className="period-column">
          <div className="period-header before">
            <h4>1. Baseline Period (Before / T_A)</h4>
            <span className="period-count">{beforeScenes.length} candidates</span>
          </div>

          {beforeScenes.length === 0 ? (
            <div className="empty-period-placeholder">
              <p>
                {searchState === "searching"
                  ? "Searching baseline candidates…"
                  : "Click 'Discover Scene Candidates' to search before scenes."}
              </p>
            </div>
          ) : (
            <div className="candidate-cards-list">
              {beforeScenes.map((scene) => (
                <CandidateCard
                  key={scene.id}
                  scene={scene}
                  periodRole="before"
                  isSelected={selectedBeforeScene?.id === scene.id}
                  onSelect={() =>
                    onSelectBeforeScene(selectedBeforeScene?.id === scene.id ? null : scene)
                  }
                />
              ))}
            </div>
          )}
        </div>

        {/* AFTER PERIOD COLUMN */}
        <div className="period-column">
          <div className="period-header after">
            <h4>2. Comparative Period (After / T_B)</h4>
            <span className="period-count">{afterScenes.length} candidates</span>
          </div>

          {afterScenes.length === 0 ? (
            <div className="empty-period-placeholder">
              <p>
                {searchState === "searching"
                  ? "Searching comparative candidates…"
                  : "Click 'Discover Scene Candidates' to search after scenes."}
              </p>
            </div>
          ) : (
            <div className="candidate-cards-list">
              {afterScenes.map((scene) => (
                <CandidateCard
                  key={scene.id}
                  scene={scene}
                  periodRole="after"
                  isSelected={selectedAfterScene?.id === scene.id}
                  onSelect={() =>
                    onSelectAfterScene(selectedAfterScene?.id === scene.id ? null : scene)
                  }
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {validationError ? (
        <div className="temporal-error-banner" role="alert">
          <p>{validationError}</p>
        </div>
      ) : null}

      {validationResult ? (
        <CompatibilitySummary
          result={validationResult}
          validationState={validationState}
          onClear={() => {
            setShowComparison(false);
            onClearSelection();
          }}
          onContinue={handleContinue}
        />
      ) : null}

      {/* Multitemporal Comparison Panel (Phase 3A) */}
      {selectedBeforeScene && selectedAfterScene && (showComparison || validationResult?.valid) && (
        <TemporalComparisonPanel
          beforeScene={selectedBeforeScene}
          afterScene={selectedAfterScene}
          selectedAoi={selectedAoi ?? null}
          temporalResponse={imagery.temporalResponse}
          status={imagery.temporalStatus}
          error={imagery.temporalError}
          beforePreset={imagery.beforePreset}
          afterPreset={imagery.afterPreset}
          comparisonMode={imagery.comparisonMode}
          swipePosition={imagery.swipePosition}
          blendOpacity={imagery.blendOpacity}
          onRequestComparison={(bPreset, aPreset, pType) => {
            if (selectedAoi) {
              void imagery.fetchTemporalImagery(
                selectedBeforeScene.id,
                selectedAfterScene.id,
                selectedAoi,
                bPreset,
                aPreset,
                pType,
              );
            }
          }}
          onClearComparison={imagery.clearTemporalImagery}
          onBeforePresetChange={imagery.setBeforePreset}
          onAfterPresetChange={imagery.setAfterPreset}
          onComparisonModeChange={imagery.setComparisonMode}
          onSwipePositionChange={imagery.setSwipePosition}
          onBlendOpacityChange={imagery.setBlendOpacity}
        />
      )}
    </section>
  );
}
