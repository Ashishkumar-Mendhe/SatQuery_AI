"use client";

import { type KeyboardEvent, useRef } from "react";

import { Icon, type IconName } from "@/components/icon";
import type { AnswerClaim, QueryAnswer, SuggestedNextAction } from "@/lib/query-contracts";
import type { VisualObservation, VisualQueryResponse } from "@/lib/visual-contracts";

export type ResultTab = "answer" | "evidence" | "activity";

const tabs: Array<{ id: ResultTab; label: string; icon: IconName }> = [
  { id: "answer", label: "Answer", icon: "question" },
  { id: "evidence", label: "Evidence", icon: "evidence" },
  { id: "activity", label: "Activity", icon: "activity" },
];

const emptyStates: Record<ResultTab, { title: string; detail: string }> = {
  answer: {
    title: "No answer yet",
    detail:
      "Enter a question above and click Analyze to generate an evidence-grounded answer or inspect visual imagery pixels.",
  },
  evidence: {
    title: "No evidence to inspect",
    detail:
      "Evidence appears after raster processing or bi-temporal analysis. Once computed, backing evidence and map regions will be listed here.",
  },
  activity: {
    title: "No activity recorded",
    detail:
      "Submit a question to view the step-by-step query routing, image manifest creation, and spatial grounding trace.",
  },
};

export interface ResultsTabsProps {
  activeTab: ResultTab;
  onChange: (tab: ResultTab) => void;
  answer?: QueryAnswer | null;
  visualResponse?: VisualQueryResponse | null;
  isSubmitting?: boolean;
  loadingStage?: string | null;
  selectedHighlightId?: string | null;
  selectedObservationId?: string | null;
  onSelectHighlight?: (regionId: string | null, evidenceId?: string | null) => void;
  onSelectObservation?: (observationId: string | null) => void;
  onExecuteAction?: (action: SuggestedNextAction) => void;
  onExportReport?: () => void;
}

export function ResultsTabs({
  activeTab,
  onChange,
  answer = null,
  visualResponse = null,
  isSubmitting = false,
  loadingStage = null,
  selectedHighlightId = null,
  selectedObservationId = null,
  onSelectHighlight,
  onSelectObservation,
  onExecuteAction,
  onExportReport,
}: ResultsTabsProps) {
  const tabRefs = useRef<Record<ResultTab, HTMLButtonElement | null>>({
    answer: null,
    evidence: null,
    activity: null,
  });

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, current: ResultTab) => {
    const currentIndex = tabs.findIndex((tab) => tab.id === current);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabs.length - 1;
    }
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = tabs[nextIndex].id;
    onChange(nextTab);
    tabRefs.current[nextTab]?.focus();
  };

  const activeEmptyState = emptyStates[activeTab];
  const hasContent = Boolean(answer || visualResponse);

  return (
    <div className="results-area">
      <div className="results-tabs-header">
        <div className="results-tabs" role="tablist" aria-label="Assistant result views">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              ref={(node) => {
                tabRefs.current[tab.id] = node;
              }}
              id={`${tab.id}-tab`}
              className="results-tab"
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`${tab.id}-panel`}
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => onChange(tab.id)}
              onKeyDown={(event) => onKeyDown(event, tab.id)}
            >
              <Icon name={tab.icon} />
              {tab.label}
            </button>
          ))}
        </div>
        {hasContent && onExportReport && (
          <button
            type="button"
            className="btn-export-dossier"
            onClick={onExportReport}
            title="Export Evidence Dossier (PDF / JSON)"
            aria-label="Export Evidence Dossier"
            data-testid="export-dossier-button"
          >
            <Icon name="report" width={14} height={14} />
            <span>Export Dossier</span>
          </button>
        )}
      </div>

      <section
        className="results-content-panel"
        id={`${activeTab}-panel`}
        role="tabpanel"
        aria-labelledby={`${activeTab}-tab`}
      >
        {isSubmitting ? (
          <div className="result-loading-state" role="status" aria-live="polite">
            <div className="loading-spinner" aria-hidden="true" />
            <p className="loading-stage-text">{loadingStage || "Processing query..."}</p>
            <span className="loading-subtext">
              Validating context, preparing image manifests, and grounding spatial predictions
            </span>
          </div>
        ) : !hasContent ? (
          <div className="result-empty-state">
            <span className="result-empty-icon">
              <Icon name={tabs.find((tab) => tab.id === activeTab)?.icon ?? "question"} />
            </span>
            <h3>{activeEmptyState.title}</h3>
            <p>{activeEmptyState.detail}</p>
          </div>
        ) : (
          <div className="result-active-view">
            {activeTab === "answer" && (
              <>
                {visualResponse && (
                  <VisualAnswerView
                    response={visualResponse}
                    selectedObservationId={selectedObservationId}
                    onSelectObservation={onSelectObservation}
                  />
                )}
                {answer && (
                  <AnswerView
                    answer={answer}
                    selectedHighlightId={selectedHighlightId}
                    onSelectHighlight={onSelectHighlight}
                    onExecuteAction={onExecuteAction}
                  />
                )}
              </>
            )}
            {activeTab === "evidence" && (
              <EvidenceView
                answer={answer}
                visualResponse={visualResponse}
                selectedHighlightId={selectedHighlightId}
                selectedObservationId={selectedObservationId}
                onSelectHighlight={onSelectHighlight}
                onSelectObservation={onSelectObservation}
              />
            )}
            {activeTab === "activity" && (
              <ActivityView answer={answer} visualResponse={visualResponse} />
            )}
          </div>
        )}
      </section>
    </div>
  );
}

function VisualAnswerView({
  response,
  selectedObservationId,
  onSelectObservation,
}: {
  response: VisualQueryResponse;
  selectedObservationId: string | null;
  onSelectObservation?: (observationId: string | null) => void;
}) {
  return (
    <div className="visual-answer-view">
      {/* Badges */}
      <div className="answer-header-row">
        <span className="status-pill badge-info">Image VQA</span>
        <span className="generation-mode-pill">
          <Icon name="spark" /> {response.generation_mode.replace(/_/g, " ")}
        </span>
        {response.data_origin === "mock" && (
          <span className="demo-data-pill">Synthetic Demo Data</span>
        )}
      </div>

      {/* Answer prose */}
      <div className="answer-summary-card">
        <h3 className="section-heading">Visual Interpretation</h3>
        <p className="summary-prose">{response.answer}</p>
      </div>

      {/* Visual Observations with Grounding */}
      {response.observations.length > 0 && (
        <div className="claims-section">
          <h4 className="subsection-heading">
            Visual Observations &amp; Predictions ({response.observations.length})
          </h4>
          <div className="claims-list">
            {response.observations.map((obs) => (
              <VisualObservationCard
                key={obs.observation_id}
                observation={obs}
                isSelected={selectedObservationId === obs.observation_id}
                onSelect={onSelectObservation}
              />
            ))}
          </div>
        </div>
      )}

      {/* Limitations Callout */}
      {response.limitations.length > 0 && (
        <div className="limitations-callout">
          <div className="callout-header">
            <Icon name="warning" />
            <strong>Visual Grounding Limitations</strong>
          </div>
          <ul className="limitations-list">
            {response.limitations.map((lim) => (
              <li key={lim}>{lim}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function VisualObservationCard({
  observation,
  isSelected,
  onSelect,
}: {
  observation: VisualObservation;
  isSelected: boolean;
  onSelect?: (observationId: string | null) => void;
}) {
  const boxStr = observation.canonical_box
    ? `[${observation.canonical_box.map((v) => v.toFixed(2)).join(", ")}]`
    : null;

  return (
    <div className={`claim-card visual-obs-card ${isSelected ? "claim-highlighted" : ""}`}>
      <div className="claim-card-header">
        <span className="claim-kind-pill kind-interpretation">
          <Icon name="spark" /> AI Prediction
        </span>
        <span
          className={`status-pill ${
            observation.coordinate_status === "valid" ? "badge-success" : "badge-warning"
          }`}
        >
          {observation.coordinate_status}
        </span>
        <span className="status-pill badge-neutral">
          {observation.map_grounding_status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="obs-content">
        <strong className="obs-label">{observation.label}</strong>
        <p className="claim-text">{observation.description}</p>
      </div>

      {boxStr && (
        <div className="box-coordinates-row">
          <span className="kv-label">Normalized Box:</span>
          <code>{boxStr}</code>
        </div>
      )}

      {observation.associated_evidence_ids.length > 0 && (
        <div className="claim-chips-row">
          <span className="kv-label">Matched Evidence:</span>
          {observation.associated_evidence_ids.map((evId) => (
            <span key={evId} className="chip evidence-chip">
              <Icon name="evidence" /> {evId}
            </span>
          ))}
        </div>
      )}

      <div className="obs-actions">
        <button
          type="button"
          className={`button button-sm ${isSelected ? "button-primary" : "button-quiet"}`}
          onClick={(e) => {
            e.stopPropagation();
            onSelect?.(observation.observation_id);
          }}
        >
          <Icon name="location" /> {isSelected ? "Selected" : "Highlight Region"}
        </button>
      </div>
    </div>
  );
}

function AnswerView({
  answer,
  selectedHighlightId,
  onSelectHighlight,
  onExecuteAction,
}: {
  answer: QueryAnswer;
  selectedHighlightId: string | null;
  onSelectHighlight?: (regionId: string | null, evidenceId?: string | null) => void;
  onExecuteAction?: (action: SuggestedNextAction) => void;
}) {
  const modeLabels: Record<string, string> = {
    llm_explanation: "AI Explanation",
    deterministic_summary: "Deterministic Evidence Summary",
    mock_demo: "Mock Demo AI",
  };

  const statusLabels: Record<string, { label: string; tone: string }> = {
    answerable: { label: "Answerable", tone: "badge-success" },
    partially_answerable: { label: "Partially Answerable", tone: "badge-warning" },
    needs_processing: { label: "Processing Required", tone: "badge-warning" },
    insufficient_evidence: { label: "Insufficient Evidence", tone: "badge-danger" },
    clarification_required: { label: "Clarification Required", tone: "badge-info" },
    unsupported: { label: "Unsupported Scope", tone: "badge-neutral" },
  };

  const statusInfo = statusLabels[answer.answer_status] || {
    label: answer.answer_status,
    tone: "badge-neutral",
  };

  return (
    <div className="answer-view-container">
      {/* Header Badges */}
      <div className="answer-header-row">
        <span className={`status-pill ${statusInfo.tone}`}>{statusInfo.label}</span>
        <span className="generation-mode-pill">
          <Icon name="spark" /> {modeLabels[answer.generation_mode] || answer.generation_mode}
        </span>
        {answer.data_origin === "mock" && (
          <span className="demo-data-pill">Synthetic Demo Data</span>
        )}
      </div>

      {/* Main Answer Summary */}
      <div className="answer-summary-card">
        <h3 className="section-heading">Summary</h3>
        <p className="summary-prose">{answer.summary}</p>
      </div>

      {/* Grounded Fact Cards / Claims */}
      {answer.claims.length > 0 && (
        <div className="claims-section">
          <h4 className="subsection-heading">Grounded Measurement Claims</h4>
          <div className="claims-list">
            {answer.claims.map((claim) => (
              <ClaimCard
                key={claim.claim_id}
                claim={claim}
                selectedHighlightId={selectedHighlightId}
                onSelectHighlight={onSelectHighlight}
              />
            ))}
          </div>
        </div>
      )}

      {/* Quality Factors */}
      {answer.quality_factors.length > 0 && (
        <div className="quality-factors-section">
          <h4 className="subsection-heading">Confidence & Verification</h4>
          <div className="quality-factors-grid">
            {answer.quality_factors.map((factor) => (
              <div key={factor.code} className="quality-factor-card">
                <div className="factor-header">
                  <span className="factor-label">{factor.label}</span>
                  <span className="factor-score">{Math.round(factor.score * 100)}%</span>
                </div>
                <p className="factor-explanation">{factor.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Limitations & Caveats */}
      {answer.limitations.length > 0 && (
        <div className="limitations-callout">
          <div className="callout-header">
            <Icon name="warning" />
            <strong>Important Analytical Limitations</strong>
          </div>
          <ul className="limitations-list">
            {answer.limitations.map((lim) => (
              <li key={lim}>{lim}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Suggested Next Actions */}
      {answer.suggested_actions.length > 0 && (
        <div className="suggested-actions-section">
          <h4 className="subsection-heading">Suggested Next Actions</h4>
          <div className="suggested-actions-list">
            {answer.suggested_actions.map((act) => (
              <div key={act.action_id} className="suggested-action-item">
                <div className="action-text">
                  <strong>{act.label}</strong>
                  <p>{act.description}</p>
                </div>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => onExecuteAction?.(act)}
                >
                  {act.label}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ClaimCard({
  claim,
  selectedHighlightId,
  onSelectHighlight,
}: {
  claim: AnswerClaim;
  selectedHighlightId: string | null;
  onSelectHighlight?: (regionId: string | null, evidenceId?: string | null) => void;
}) {
  const isHighlighted =
    claim.region_ids.some((r) => r === selectedHighlightId) ||
    claim.evidence_ids.some((e) => e === selectedHighlightId);

  return (
    <div className={`claim-card ${isHighlighted ? "claim-highlighted" : ""}`}>
      <div className="claim-card-header">
        <span className={`claim-kind-pill kind-${claim.kind}`}>{claim.kind}</span>
        <span className="claim-validation-pill">
          <Icon name="check" /> Grounded
        </span>
      </div>
      <p className="claim-text">{claim.display_text}</p>

      {/* Resolved Numeric Measurements */}
      {claim.resolved_measurement && (
        <div className="resolved-measurements-panel">
          <div className="measurement-keyvals">
            {Object.entries(claim.resolved_measurement).map(([k, v]) => (
              <div key={k} className="measurement-kv-row">
                <span className="kv-label">{k.replace(/_/g, " ")}:</span>
                <span className="kv-value">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Region & Evidence Reference Chips */}
      <div className="claim-chips-row">
        {claim.region_ids.map((regId) => (
          <button
            key={regId}
            type="button"
            className={`chip region-chip ${selectedHighlightId === regId ? "chip-active" : ""}`}
            onClick={() => onSelectHighlight?.(regId, claim.evidence_ids[0])}
            title="Highlight region on map"
          >
            <Icon name="location" /> {regId}
          </button>
        ))}
        {claim.evidence_ids.map((evId) => (
          <span key={evId} className="chip evidence-chip">
            <Icon name="evidence" /> {evId}
          </span>
        ))}
      </div>
    </div>
  );
}

function EvidenceView({
  answer,
  visualResponse,
  selectedHighlightId,
  selectedObservationId,
  onSelectHighlight,
  onSelectObservation,
}: {
  answer: QueryAnswer | null;
  visualResponse?: VisualQueryResponse | null;
  selectedHighlightId: string | null;
  selectedObservationId?: string | null;
  onSelectHighlight?: (regionId: string | null, evidenceId?: string | null) => void;
  onSelectObservation?: (observationId: string | null) => void;
}) {
  const evidenceRefs = answer?.evidence_references ?? visualResponse?.evidence_references ?? [];
  const groundedRegions = visualResponse?.grounded_regions ?? [];

  return (
    <div className="evidence-view-container">
      <h3 className="section-heading">Referenced Evidence ({evidenceRefs.length})</h3>
      <div className="evidence-items-list">
        {evidenceRefs.map((evId) => (
          <div key={evId} className="evidence-item-card">
            <div className="evidence-header">
              <Icon name="evidence" />
              <strong>{evId}</strong>
            </div>
            <p className="evidence-detail">
              Derived from verified raster calculation in active workspace context.
            </p>
          </div>
        ))}
      </div>

      {groundedRegions.length > 0 && (
        <div className="spatial-regions-section">
          <h4 className="subsection-heading">Grounded Visual Regions ({groundedRegions.length})</h4>
          <div className="spatial-regions-grid">
            {groundedRegions.map((gr) => (
              <div
                key={gr.region_id}
                className={`spatial-region-card ${
                  selectedObservationId === gr.observation_id ? "spatial-region-active" : ""
                }`}
              >
                <div className="spatial-region-header">
                  <Icon name="location" />
                  <span>{gr.region_id}</span>
                </div>
                <div className="region-meta">
                  <span className="kv-label">Clipping: {gr.clipping_status}</span>
                  {gr.overlap_area_km2 !== null && gr.overlap_area_km2 !== undefined && (
                    <span className="kv-label">Overlap: {gr.overlap_area_km2.toFixed(2)} km²</span>
                  )}
                </div>
                <button
                  type="button"
                  className="button button-quiet"
                  onClick={() => onSelectObservation?.(gr.observation_id)}
                >
                  Highlight on Map
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {answer && answer.spatial_references.length > 0 && (
        <div className="spatial-regions-section">
          <h4 className="subsection-heading">Grounded Map Regions</h4>
          <div className="spatial-regions-grid">
            {answer.spatial_references.map((regId) => (
              <div
                key={regId}
                className={`spatial-region-card ${
                  selectedHighlightId === regId ? "spatial-region-active" : ""
                }`}
              >
                <div className="spatial-region-header">
                  <Icon name="location" />
                  <span>{regId}</span>
                </div>
                <button
                  type="button"
                  className="button button-quiet"
                  onClick={() => onSelectHighlight?.(regId)}
                >
                  Highlight on Map
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {answer && answer.warnings.length > 0 && (
        <div className="warnings-section">
          <h4 className="subsection-heading">Data Quality Warnings</h4>
          <ul className="warnings-list">
            {answer.warnings.map((w) => (
              <li key={`${w.code}-${w.message}`} className="warning-item">
                <Icon name="warning" />
                <span>
                  <strong>{w.code}:</strong> {w.message}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ActivityView({
  answer,
  visualResponse,
}: {
  answer: QueryAnswer | null;
  visualResponse?: VisualQueryResponse | null;
}) {
  const manifests = visualResponse?.manifests ?? [];

  return (
    <div className="activity-view-container">
      {manifests.length > 0 && (
        <div className="manifests-activity-section">
          <h3 className="section-heading">Prepared Image Manifests ({manifests.length})</h3>
          <div className="manifests-grid">
            {manifests.map((mf) => (
              <div key={mf.manifest_id} className="manifest-card">
                <div className="manifest-header">
                  <span className="status-pill badge-info">Role: {mf.role}</span>
                  <code>{mf.manifest_id}</code>
                </div>
                <div className="manifest-details">
                  <div className="meta-item">
                    <span>Dimensions:</span>
                    <strong>
                      {mf.submitted_width} × {mf.submitted_height} px
                    </strong>
                  </div>
                  <div className="meta-item">
                    <span>CRS:</span>
                    <strong>{mf.crs || "None (non-georeferenced)"}</strong>
                  </div>
                  <div className="meta-item">
                    <span>Hash:</span>
                    <span className="hash-code">{mf.content_hash.slice(0, 18)}...</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {answer && answer.processing_trace.length > 0 && (
        <>
          <h3 className="section-heading">Query Execution Trace</h3>
          <div className="trace-timeline">
            {answer.processing_trace.map((step) => (
              <div key={`${step.stage}-${step.description}`} className="trace-step-card">
                <div className="trace-step-header">
                  <span className={`trace-status-dot status-${step.status}`} />
                  <strong className="trace-stage-name">{step.stage.replace(/_/g, " ")}</strong>
                  <span className="trace-duration">{step.duration_ms} ms</span>
                </div>
                <p className="trace-description">{step.description}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {(visualResponse?.provider_execution || answer?.provider_execution) && (
        <div className="provider-meta-card">
          <h4 className="subsection-heading">AI Provider Details</h4>
          <div className="provider-meta-row">
            <span>Provider:</span>
            <strong>
              {visualResponse?.provider_execution?.provider_id ||
                answer?.provider_execution?.provider_id}
            </strong>
          </div>
          <div className="provider-meta-row">
            <span>Mode:</span>
            <strong>
              {visualResponse?.provider_execution?.provider_mode ||
                answer?.provider_execution?.provider_mode}
            </strong>
          </div>
          <div className="provider-meta-row">
            <span>Duration:</span>
            <strong>
              {(visualResponse?.provider_execution?.duration_milliseconds ||
                answer?.provider_execution?.duration_milliseconds) ??
                0}{" "}
              ms
            </strong>
          </div>
        </div>
      )}
    </div>
  );
}
