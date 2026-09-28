import { Icon } from "@/components/icon";
import { ResultsTabs, type ResultTab } from "@/components/workspace/results-tabs";
import {
  type AnalysisMode,
  MAX_QUESTION_LENGTH,
  MIN_QUESTION_LENGTH,
} from "@/lib/analysis-contracts";
import { getAnalysisModeDefinition } from "@/lib/analysis-modes";
import { featureAvailability } from "@/lib/feature-availability";
import type { QueryAnswer, SuggestedNextAction } from "@/lib/query-contracts";
import type { VisualOperation, VisualQueryResponse } from "@/lib/visual-contracts";

export const suggestedQuestions = [
  "What changed between these images?",
  "Where is vegetation visible?",
  "Identify water-covered areas.",
  "What additional information does the SAR image provide?",
  "Show the largest detected change region.",
  "Why is confidence low?",
];

export const visualSuggestedQuestions: Record<VisualOperation, string[]> = {
  describe: [
    "Describe the visible land-cover patterns.",
    "What visual characteristics stand out in this scene?",
    "Where is vegetation visible?",
  ],
  locate: [
    "Highlight the prominent water-like region.",
    "Where is the largest visible built-up cluster?",
    "Identify water-covered areas.",
  ],
  compare: [
    "What visual differences are apparent between these dates?",
    "What changed between these images?",
    "Which visual observations match the measured change regions?",
  ],
};

export interface AssistantPanelProps {
  visible: boolean;
  draft: string;
  mode?: AnalysisMode;
  activeTab: ResultTab;
  onDraftChange: (draft: string) => void;
  onTabChange: (tab: ResultTab) => void;
  onClose: () => void;
  isSubmitting?: boolean;
  loadingStage?: string | null;
  answer?: QueryAnswer | null;
  visualResponse?: VisualQueryResponse | null;
  error?: string | null;
  isContextStale?: boolean;
  selectedHighlightId?: string | null;
  selectedObservationId?: string | null;
  queryType?: "evidence" | "visual";
  onQueryTypeChange?: (type: "evidence" | "visual") => void;
  visualOperation?: VisualOperation;
  onVisualOperationChange?: (op: VisualOperation) => void;
  selectedImageCount?: number;
  onSubmit?: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  onClearAnswer?: () => void;
  onSelectHighlight?: (regionId: string | null, evidenceId?: string | null) => void;
  onSelectObservation?: (observationId: string | null) => void;
  onExecuteAction?: (action: SuggestedNextAction) => void;
  onExportReport?: () => void;
}

export function AssistantPanel({
  visible,
  draft,
  mode = "visual_question_answering",
  activeTab,
  onDraftChange,
  onTabChange,
  onClose,
  isSubmitting = false,
  loadingStage = null,
  answer = null,
  visualResponse = null,
  error = null,
  isContextStale = false,
  selectedHighlightId = null,
  selectedObservationId = null,
  queryType = "visual",
  onQueryTypeChange,
  visualOperation = "describe",
  onVisualOperationChange,
  selectedImageCount = 0,
  onSubmit,
  onCancel,
  onRetry,
  onClearAnswer,
  onSelectHighlight,
  onSelectObservation,
  onExecuteAction,
  onExportReport,
}: AssistantPanelProps) {
  const modeDef = getAnalysisModeDefinition(mode);
  const isDraftValid = draft.trim().length >= MIN_QUESTION_LENGTH;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (isDraftValid && !isSubmitting && onSubmit) {
        onSubmit();
      }
    }
  };

  const activeSuggestions =
    queryType === "visual"
      ? visualSuggestedQuestions[visualOperation] || suggestedQuestions
      : suggestedQuestions;

  return (
    <aside className="assistant-panel" aria-label="SatQuery assistant" hidden={!visible}>
      <div className="assistant-header">
        <div>
          <p className="panel-kicker">
            <Icon name="spark" /> Assistant
          </p>
          <h2>Ask about the scene</h2>
        </div>
        <button
          className="icon-button"
          type="button"
          aria-label="Hide assistant panel"
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>

      {/* Query Mode Toggle */}
      {onQueryTypeChange && (
        <fieldset className="query-type-toggle-bar">
          <legend className="sr-only">Query mode selection</legend>
          <button
            type="button"
            className={`button button-sm ${queryType === "visual" ? "button-primary" : "button-quiet"}`}
            onClick={() => onQueryTypeChange("visual")}
          >
            <Icon name="spark" /> Image VQA
          </button>
          <button
            type="button"
            className={`button button-sm ${queryType === "evidence" ? "button-primary" : "button-quiet"}`}
            onClick={() => onQueryTypeChange("evidence")}
          >
            <Icon name="evidence" /> Evidence Summary
          </button>
        </fieldset>
      )}

      {/* Visual Operations Selector (when in visual mode) */}
      {queryType === "visual" && onVisualOperationChange && (
        <div className="visual-operation-selector">
          <span className="operation-label">Operation:</span>
          <div className="operation-buttons">
            {mode !== "change_detection" && (
              <>
                <button
                  type="button"
                  className={`op-pill ${visualOperation === "describe" ? "op-pill-active" : ""}`}
                  onClick={() => onVisualOperationChange("describe")}
                >
                  Describe
                </button>
                <button
                  type="button"
                  className={`op-pill ${visualOperation === "locate" ? "op-pill-active" : ""}`}
                  onClick={() => onVisualOperationChange("locate")}
                >
                  Locate Feature
                </button>
              </>
            )}
            {(mode === "change_detection" || mode === "multimodal_analysis" || !mode) && (
              <button
                type="button"
                className={`op-pill ${visualOperation === "compare" ? "op-pill-active" : ""}`}
                onClick={() => onVisualOperationChange("compare")}
              >
                Compare Pair
              </button>
            )}
          </div>
        </div>
      )}

      <div className="composer-section">
        <div className="composer-label-row">
          <label htmlFor="analysis-question">Question</label>
          <span className="character-count" aria-live="polite">
            {draft.length} / {MAX_QUESTION_LENGTH}
          </span>
        </div>
        <div className="composer-field">
          <textarea
            id="analysis-question"
            value={draft}
            rows={4}
            maxLength={MAX_QUESTION_LENGTH}
            placeholder={
              queryType === "visual"
                ? "e.g. 'Highlight the water reservoir' or 'Describe the land-cover patterns'"
                : modeDef.questionPlaceholder
            }
            onChange={(event) => onDraftChange(event.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isSubmitting}
          />
          <span className="composer-status">
            {isDraftValid
              ? "Press Enter to analyze"
              : `Minimum ${MIN_QUESTION_LENGTH} characters required`}
          </span>
        </div>

        {/* Selected Images Context Pill */}
        {queryType === "visual" && (
          <div
            className={`selected-assets-notice ${selectedImageCount > 0 ? "ready" : "prerequisite"}`}
          >
            <Icon name="layers" />
            <span>
              {selectedImageCount > 0
                ? `${selectedImageCount} image asset${selectedImageCount > 1 ? "s" : ""} selected for VQA`
                : "Select a satellite scene from the discovery panel or timeline to ask a visual question."}
            </span>
          </div>
        )}

        {/* Stale Context Notice */}
        {isContextStale && (answer || visualResponse) && (
          <div className="stale-context-notice" role="alert">
            <Icon name="warning" />
            <span>Active AOI or inputs changed since this answer was generated.</span>
          </div>
        )}

        {/* Error / Retry Banner */}
        {error && (
          <div className="query-error-banner" role="alert">
            <div className="error-message-row">
              <Icon name="warning" />
              <span>{error}</span>
            </div>
            {onRetry && (
              <button type="button" className="button button-quiet button-sm" onClick={onRetry}>
                Retry
              </button>
            )}
          </div>
        )}

        <fieldset className="suggestions">
          <legend id="suggestions-title">Try a question</legend>
          <div className="suggestion-list">
            {activeSuggestions.map((question) => (
              <button
                key={question}
                type="button"
                disabled={isSubmitting}
                onClick={() => onDraftChange(question)}
              >
                {question}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="composer-actions">
          <button
            className="button button-quiet"
            type="button"
            disabled={draft.length === 0 || isSubmitting}
            onClick={() => {
              onDraftChange("");
              onClearAnswer?.();
            }}
          >
            Clear draft
          </button>

          {isSubmitting ? (
            <button className="button button-secondary" type="button" onClick={onCancel}>
              Cancel
            </button>
          ) : (
            <button
              className="button button-primary"
              type="button"
              disabled={
                !isDraftValid ||
                isSubmitting ||
                (queryType === "visual" && selectedImageCount === 0)
              }
              onClick={onSubmit}
              title={
                queryType === "visual" && selectedImageCount === 0
                  ? "Select a scene first to analyze"
                  : undefined
              }
            >
              Analyze
            </button>
          )}
        </div>

        <p className="availability-note" id="analysis-unavailable">
          <Icon name="help" />
          <span>
            <strong>{featureAvailability.analysis.label}.</strong>{" "}
            {featureAvailability.analysis.explanation}
          </span>
        </p>
      </div>

      <ResultsTabs
        activeTab={activeTab}
        onChange={onTabChange}
        answer={answer}
        visualResponse={visualResponse}
        isSubmitting={isSubmitting}
        loadingStage={loadingStage}
        selectedHighlightId={selectedHighlightId}
        selectedObservationId={selectedObservationId}
        onSelectHighlight={onSelectHighlight}
        onSelectObservation={onSelectObservation}
        onExecuteAction={onExecuteAction}
        onExportReport={onExportReport}
      />
    </aside>
  );
}
