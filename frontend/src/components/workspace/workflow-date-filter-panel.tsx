"use client";

import { useId } from "react";
import type { AnalysisMode } from "@/lib/analysis-contracts";
import type { SceneFiltersDraft } from "@/lib/workspace-draft-storage";
import { isDateRangeValid } from "@/lib/workspace-workflow";

export interface WorkflowDateFilterPanelProps {
  readonly mode: AnalysisMode;
  readonly dateRange: { start_date: string; end_date: string } | null;
  readonly beforeWindow?: { start_date: string; end_date: string } | null;
  readonly afterWindow?: { start_date: string; end_date: string } | null;
  readonly sceneFilters: SceneFiltersDraft;
  readonly onDateRangeChange: (dates: { start_date: string; end_date: string } | null) => void;
  readonly onBeforeWindowChange?: (dates: { start_date: string; end_date: string } | null) => void;
  readonly onAfterWindowChange?: (dates: { start_date: string; end_date: string } | null) => void;
  readonly onSceneFiltersChange: (filters: SceneFiltersDraft) => void;
  readonly disabled?: boolean;
}

export function WorkflowDateFilterPanel({
  mode,
  dateRange,
  beforeWindow,
  afterWindow,
  sceneFilters,
  onDateRangeChange,
  onBeforeWindowChange,
  onAfterWindowChange,
  onSceneFiltersChange,
  disabled = false,
}: WorkflowDateFilterPanelProps) {
  const startDateId = useId();
  const endDateId = useId();
  const beforeStartId = useId();
  const beforeEndId = useId();
  const afterStartId = useId();
  const afterEndId = useId();
  const cloudCoverId = useId();
  const sensorTypeId = useId();
  const limitId = useId();

  const startDate = dateRange?.start_date ?? "";
  const endDate = dateRange?.end_date ?? "";
  const isValid = isDateRangeValid(dateRange);
  const isBiTemporal = mode === "change_detection";
  const hasDualWindows = isBiTemporal && onBeforeWindowChange && onAfterWindowChange;

  const bStart = beforeWindow?.start_date ?? "";
  const bEnd = beforeWindow?.end_date ?? "";
  const isBeforeValid = isDateRangeValid(beforeWindow ?? null);

  const aStart = afterWindow?.start_date ?? "";
  const aEnd = afterWindow?.end_date ?? "";
  const isAfterValid = isDateRangeValid(afterWindow ?? null);

  function handleStartChange(value: string) {
    onDateRangeChange({
      start_date: value,
      end_date: endDate || value,
    });
  }

  function handleEndChange(value: string) {
    onDateRangeChange({
      start_date: startDate || value,
      end_date: value,
    });
  }

  function handleBeforeStartChange(value: string) {
    if (onBeforeWindowChange) {
      onBeforeWindowChange({
        start_date: value,
        end_date: bEnd || value,
      });
    }
  }

  function handleBeforeEndChange(value: string) {
    if (onBeforeWindowChange) {
      onBeforeWindowChange({
        start_date: bStart || value,
        end_date: value,
      });
    }
  }

  function handleAfterStartChange(value: string) {
    if (onAfterWindowChange) {
      onAfterWindowChange({
        start_date: value,
        end_date: aEnd || value,
      });
    }
  }

  function handleAfterEndChange(value: string) {
    if (onAfterWindowChange) {
      onAfterWindowChange({
        start_date: aStart || value,
        end_date: value,
      });
    }
  }

  function applyPreset(daysAgo: number) {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - daysAgo);

    onDateRangeChange({
      start_date: start.toISOString().split("T")[0],
      end_date: end.toISOString().split("T")[0],
    });
  }

  function applyBiTemporalPreset(monthsGap: number) {
    const endAfter = new Date();
    const startAfter = new Date(endAfter);
    startAfter.setDate(endAfter.getDate() - 30);

    const endBefore = new Date(startAfter);
    endBefore.setMonth(endBefore.getMonth() - monthsGap);
    const startBefore = new Date(endBefore);
    startBefore.setDate(endBefore.getDate() - 30);

    if (onBeforeWindowChange && onAfterWindowChange) {
      onBeforeWindowChange({
        start_date: startBefore.toISOString().split("T")[0],
        end_date: endBefore.toISOString().split("T")[0],
      });
      onAfterWindowChange({
        start_date: startAfter.toISOString().split("T")[0],
        end_date: endAfter.toISOString().split("T")[0],
      });
    }
  }

  return (
    <section className="workflow-date-filter-panel" aria-labelledby="date-filter-title">
      <div className="date-filter-header">
        <div>
          <p className="panel-kicker">Temporal & Scene Parameters</p>
          <h3 id="date-filter-title">
            {isBiTemporal
              ? "Bi-Temporal Date Windows (Before & After)"
              : "Search Date Range & Filters"}
          </h3>
        </div>
      </div>

      {hasDualWindows ? (
        <div className="bitemporal-dual-windows">
          {/* BEFORE WINDOW */}
          <div className="window-box before-window-box">
            <h4 className="window-subheading">1. Before Period (Baseline / T_A)</h4>
            <div className="date-inputs-grid">
              <div className="date-field-group">
                <label htmlFor={beforeStartId}>Start Date</label>
                <input
                  id={beforeStartId}
                  type="date"
                  value={bStart}
                  disabled={disabled}
                  className={`date-input ${bStart && !isBeforeValid ? "invalid" : ""}`}
                  onChange={(e) => handleBeforeStartChange(e.target.value)}
                />
              </div>
              <div className="date-field-group">
                <label htmlFor={beforeEndId}>End Date</label>
                <input
                  id={beforeEndId}
                  type="date"
                  value={bEnd}
                  disabled={disabled}
                  className={`date-input ${bEnd && !isBeforeValid ? "invalid" : ""}`}
                  onChange={(e) => handleBeforeEndChange(e.target.value)}
                />
              </div>
            </div>
            {bStart && bEnd && !isBeforeValid ? (
              <p className="date-validation-error" role="alert">
                Before start date must precede or equal end date.
              </p>
            ) : null}
          </div>

          {/* AFTER WINDOW */}
          <div className="window-box after-window-box">
            <h4 className="window-subheading">2. After Period (Comparative / T_B)</h4>
            <div className="date-inputs-grid">
              <div className="date-field-group">
                <label htmlFor={afterStartId}>Start Date</label>
                <input
                  id={afterStartId}
                  type="date"
                  value={aStart}
                  disabled={disabled}
                  className={`date-input ${aStart && !isAfterValid ? "invalid" : ""}`}
                  onChange={(e) => handleAfterStartChange(e.target.value)}
                />
              </div>
              <div className="date-field-group">
                <label htmlFor={afterEndId}>End Date</label>
                <input
                  id={afterEndId}
                  type="date"
                  value={aEnd}
                  disabled={disabled}
                  className={`date-input ${aEnd && !isAfterValid ? "invalid" : ""}`}
                  onChange={(e) => handleAfterEndChange(e.target.value)}
                />
              </div>
            </div>
            {aStart && aEnd && !isAfterValid ? (
              <p className="date-validation-error" role="alert">
                After start date must precede or equal end date.
              </p>
            ) : null}
          </div>

          <fieldset className="date-presets-row" aria-label="Bi-temporal presets">
            <button
              type="button"
              disabled={disabled}
              className="preset-pill"
              onClick={() => applyBiTemporalPreset(1)}
            >
              1 Month Interval
            </button>
            <button
              type="button"
              disabled={disabled}
              className="preset-pill"
              onClick={() => applyBiTemporalPreset(6)}
            >
              6 Months Interval
            </button>
            <button
              type="button"
              disabled={disabled}
              className="preset-pill"
              onClick={() => applyBiTemporalPreset(12)}
            >
              1 Year Interval
            </button>
          </fieldset>
        </div>
      ) : (
        <>
          <div className="date-inputs-grid">
            <div className="date-field-group">
              <label htmlFor={startDateId}>
                {isBiTemporal ? "Earliest Date (Before / T_A)" : "Start Date"}
              </label>
              <input
                id={startDateId}
                type="date"
                value={startDate}
                disabled={disabled}
                className={`date-input ${startDate && !isValid ? "invalid" : ""}`}
                onChange={(e) => handleStartChange(e.target.value)}
              />
            </div>

            <div className="date-field-group">
              <label htmlFor={endDateId}>
                {isBiTemporal ? "Latest Date (After / T_B)" : "End Date"}
              </label>
              <input
                id={endDateId}
                type="date"
                value={endDate}
                disabled={disabled}
                className={`date-input ${endDate && !isValid ? "invalid" : ""}`}
                onChange={(e) => handleEndChange(e.target.value)}
              />
            </div>
          </div>

          {startDate && endDate && !isValid ? (
            <p className="date-validation-error" role="alert">
              Start date must precede or equal end date.
            </p>
          ) : null}

          <fieldset className="date-presets-row" aria-label="Date range quick presets">
            <button
              type="button"
              disabled={disabled}
              className="preset-pill"
              onClick={() => applyPreset(30)}
            >
              Last 30 Days
            </button>
            <button
              type="button"
              disabled={disabled}
              className="preset-pill"
              onClick={() => applyPreset(90)}
            >
              Last 90 Days
            </button>
            <button
              type="button"
              disabled={disabled}
              className="preset-pill"
              onClick={() => applyPreset(365)}
            >
              Last 1 Year
            </button>
            {dateRange ? (
              <button
                type="button"
                disabled={disabled}
                className="preset-pill clear"
                onClick={() => onDateRangeChange(null)}
              >
                Clear Dates
              </button>
            ) : null}
          </fieldset>
        </>
      )}

      <div className="scene-filters-collapsible">
        <div className="filter-slider-group">
          <div className="slider-label-row">
            <label htmlFor={cloudCoverId}>Maximum scene cloud cover — optical only</label>
            <span className="slider-value">
              {sceneFilters.sensorType === "sar" ? "N/A" : `${sceneFilters.maxCloudCover}%`}
            </span>
          </div>
          <p
            className="filter-field-hint"
            style={{ fontSize: "0.72rem", color: "#8b9cb0", margin: "0.2rem 0 0.4rem" }}
          >
            {sceneFilters.sensorType === "sar"
              ? "Not applicable to SAR (radar penetrates cloud cover)."
              : "Filters optical search results using provider-reported cloud percentage for the full scene. Actual cloud over your AOI may differ."}
          </p>
          <input
            id={cloudCoverId}
            type="range"
            min="0"
            max="100"
            step="5"
            value={sceneFilters.maxCloudCover}
            disabled={disabled || sceneFilters.sensorType === "sar"}
            className="filter-slider"
            onChange={(e) =>
              onSceneFiltersChange({
                ...sceneFilters,
                maxCloudCover: Number(e.target.value),
              })
            }
          />
        </div>

        <div className="filter-select-grid">
          <div className="filter-field-group">
            <label htmlFor={sensorTypeId}>Sensor Type</label>
            <select
              id={sensorTypeId}
              value={sceneFilters.sensorType}
              disabled={disabled}
              className="filter-select"
              onChange={(e) =>
                onSceneFiltersChange({
                  ...sceneFilters,
                  sensorType: e.target.value as SceneFiltersDraft["sensorType"],
                })
              }
            >
              <option value="optical">Optical (Multispectral)</option>
              <option value="sar">SAR (Synthetic Aperture Radar)</option>
              <option value="multispectral">Multispectral (All)</option>
            </select>
          </div>

          <div className="filter-field-group">
            <label htmlFor={limitId}>Max Scenes per Period</label>
            <select
              id={limitId}
              value={sceneFilters.limit}
              disabled={disabled}
              className="filter-select"
              onChange={(e) =>
                onSceneFiltersChange({
                  ...sceneFilters,
                  limit: Number(e.target.value),
                })
              }
            >
              <option value={6}>6 scenes</option>
              <option value={12}>12 scenes</option>
              <option value={24}>24 scenes</option>
              <option value={50}>50 scenes</option>
            </select>
          </div>
        </div>
      </div>
    </section>
  );
}
