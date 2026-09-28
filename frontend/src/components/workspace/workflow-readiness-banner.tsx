"use client";

import { Icon, type IconName } from "@/components/icon";
import type { WorkflowState } from "@/lib/workspace-workflow";

export interface WorkflowReadinessBannerProps {
  readonly workflowState: WorkflowState;
  readonly onTriggerAction?: (actionType: string) => void;
}

export function WorkflowReadinessBanner({
  workflowState,
  onTriggerAction,
}: WorkflowReadinessBannerProps) {
  const { stepNumber, totalSteps, readiness, nextAction, statusMessage } = workflowState;

  const steps =
    totalSteps === 5
      ? [
          { num: 1, label: "AOI", ready: readiness.isAoiReady },
          { num: 2, label: "Dates", ready: readiness.isDateRangeReady },
          { num: 3, label: "Pairing", ready: readiness.isScenesReady },
          { num: 4, label: "Harmonise", ready: readiness.isPreparationReady },
          {
            num: 5,
            label: "Analysis",
            ready: readiness.isAnalysisReady || readiness.isReportReady,
          },
        ]
      : [
          { num: 1, label: "AOI", ready: readiness.isAoiReady },
          { num: 2, label: "Dates", ready: readiness.isDateRangeReady },
          { num: 3, label: "Imagery", ready: readiness.isScenesReady },
          {
            num: 4,
            label: "Analysis",
            ready: readiness.isAnalysisReady || readiness.isReportReady,
          },
        ];

  const getActionIcon = (actionType: string): IconName => {
    switch (actionType) {
      case "draw_aoi":
      case "fix_aoi":
        return "target";
      case "set_dates":
        return "history";
      case "discover_scenes":
      case "pair_scenes":
        return "layers";
      case "prepare_raster":
        return "spark";
      case "calculate_change":
      case "analyze_fusion":
      case "ask_question":
        return "spark";
      case "export_report":
        return "report";
      default:
        return "arrow";
    }
  };

  return (
    <section className="workflow-readiness-banner" aria-label="Workflow progress and toolbar">
      <div className="readiness-left">
        <div className="step-progress-indicator">
          <span className="step-badge">
            Step {stepNumber} of {totalSteps}
          </span>
          <strong className="step-title">{nextAction.title}</strong>
        </div>
        <p className="readiness-status-msg" title={statusMessage}>
          {statusMessage}
        </p>
      </div>

      <ol className="readiness-pills-row" aria-label="Workflow step progress">
        {steps.map((s) => {
          const isCurrent = stepNumber === s.num;
          const isDone = s.ready && stepNumber > s.num;
          const stateClass = isCurrent ? "current" : isDone ? "ready" : "pending";
          return (
            <li
              key={s.num}
              className={`readiness-pill ${stateClass}`}
              title={`Step ${s.num}: ${s.label} (${stateClass})`}
            >
              <span className="pill-dot" aria-hidden="true" />
              <span className="pill-text">{s.label}</span>
            </li>
          );
        })}
      </ol>

      <div className="readiness-action-row">
        <button
          type="button"
          className="readiness-primary-action"
          onClick={() => onTriggerAction?.(nextAction.actionType)}
        >
          <Icon name={getActionIcon(nextAction.actionType)} />
          <span>{nextAction.actionLabel}</span>
        </button>
      </div>
    </section>
  );
}
