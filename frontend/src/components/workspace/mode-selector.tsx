"use client";

import { Icon } from "@/components/icon";
import type { AnalysisMode } from "@/lib/analysis-contracts";
import { ANALYSIS_MODE_OPTIONS, type AnalysisModeDefinition } from "@/lib/analysis-modes";

export interface ModeSelectorProps {
  readonly selectedMode: AnalysisMode;
  readonly onSelectMode: (mode: AnalysisMode) => void;
  readonly disabled?: boolean;
}

export function ModeSelector({ selectedMode, onSelectMode, disabled = false }: ModeSelectorProps) {
  return (
    <section className="mode-selector-section" aria-labelledby="mode-selector-title">
      <div className="mode-selector-header">
        <div>
          <p className="panel-kicker">Analysis Intent</p>
          <h3 id="mode-selector-title">Select Analysis Mode</h3>
        </div>
      </div>

      <div className="mode-options-grid" role="radiogroup" aria-labelledby="mode-selector-title">
        {ANALYSIS_MODE_OPTIONS.map((opt: AnalysisModeDefinition) => {
          const isSelected = opt.key === selectedMode;
          const isUpcoming = opt.status === "upcoming";

          return (
            // biome-ignore lint/a11y/useSemanticElements: custom accessible card radiogroup pattern
            <button
              key={opt.key}
              type="button"
              role="radio"
              aria-checked={isSelected}
              disabled={disabled}
              className={`mode-option-card ${isSelected ? "selected" : ""} ${isUpcoming ? "upcoming" : ""}`}
              onClick={() => onSelectMode(opt.key)}
            >
              <div className="mode-card-header">
                <span className="mode-card-icon">
                  <Icon name={opt.icon} />
                </span>
                <div className="mode-card-title-group">
                  <strong className="mode-card-title">{opt.label}</strong>
                  <span className={`mode-badge ${isUpcoming ? "upcoming" : "ready"}`}>
                    {opt.badge}
                  </span>
                </div>
              </div>
              <p className="mode-card-description">{opt.description}</p>
              <div className="mode-card-requirements">
                <span className="requirements-label">Requires:</span>
                <span className="requirements-text">{opt.requiredInputs.join(" · ")}</span>
              </div>
            </button>
          );
        })}
      </div>
    </section>
  );
}
