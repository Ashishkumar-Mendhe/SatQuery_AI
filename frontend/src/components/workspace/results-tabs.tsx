"use client";

import Image from "next/image";
import { type KeyboardEvent, useRef } from "react";

import { Icon, type IconName } from "@/components/icon";
import type { InferenceEvidence, InferenceJobStatus } from "@/lib/inference-client";
import { inferenceArtifactUrl } from "@/lib/inference-client";

export type ResultTab = "answer" | "evidence" | "activity";

const tabs: Array<{ id: ResultTab; label: string; icon: IconName }> = [
  { id: "answer", label: "Answer", icon: "question" },
  { id: "evidence", label: "Evidence", icon: "evidence" },
  { id: "activity", label: "Activity", icon: "activity" },
];

export type AssistantResultView = {
  phase: "idle" | "loading" | "succeeded" | "failed";
  status: InferenceJobStatus | null;
  evidence: InferenceEvidence | null;
  error: string | null;
  retryable: boolean;
  sourceSceneKey: string | null;
  stale: boolean;
};

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="result-empty-state">
      <span className="result-empty-icon">
        <Icon name="question" />
      </span>
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

function AnswerView({ result }: { result: AssistantResultView }) {
  const evidence = result.evidence;
  if (result.phase === "loading")
    return (
      <Empty
        title="Inference in progress"
        detail={
          result.status?.current_stage
            ? `Current stage: ${result.status.current_stage.replaceAll("_", " ")}.`
            : "Waiting for the durable inference worker."
        }
      />
    );
  if (result.phase === "failed")
    return <Empty title="Inference failed" detail={result.error ?? "No result was produced."} />;
  if (!evidence)
    return (
      <Empty
        title="No answer yet"
        detail="Select supported imagery, then ask one image question or request a caption."
      />
    );
  const answer = evidence.answer;
  return (
    <div className="inference-result-card">
      {result.stale ? (
        <p className="result-stale" role="status">
          This result belongs to the previously selected scene. Its overlay is hidden.
        </p>
      ) : null}
      <p className="interpretation-label">
        Model interpretation · not a measured geospatial finding
      </p>
      {evidence.grounding ? (
        <p className="model-answer">
          Grounding result: {evidence.grounding.status.replaceAll("_", " ")}. Inspect Evidence for
          the exact source chip and validated region.
        </p>
      ) : answer?.availability === "available" ? (
        <p className="model-answer">{answer.answer}</p>
      ) : (
        <p className="result-unavailable">
          <strong>Unavailable.</strong>{" "}
          {answer?.reason ?? evidence.execution_reason ?? evidence.quality_decision.reason}
        </p>
      )}
      <dl className="result-metadata">
        <div className="result-metadata-row">
          <dt>Source scene</dt>
          <dd>{evidence.source_chip.scene.item}</dd>
        </div>
        <div className="result-metadata-row">
          <dt>Acquired</dt>
          <dd>{new Date(evidence.source_chip.acquired_at).toLocaleString()}</dd>
        </div>
        <div className="result-metadata-row">
          <dt>Status</dt>
          <dd>{evidence.execution_state.replaceAll("_", " ")}</dd>
        </div>
        {answer ? (
          <div className="result-metadata-row">
            <dt>Model</dt>
            <dd>
              {answer.model.model} · {answer.model.version}
            </dd>
          </div>
        ) : null}
      </dl>
      <p className="evidence-disclaimer">{evidence.interpretation_notice}</p>
      {answer?.quality_warnings.length ? (
        <fieldset className="quality-warning-list">
          <legend>Quality warnings</legend>
          {answer.quality_warnings.map((warning) => (
            <p key={warning.code}>
              <strong>{warning.severity}:</strong> {warning.message}
              {warning.corrective_action ? ` ${warning.corrective_action}` : ""}
            </p>
          ))}
        </fieldset>
      ) : null}
    </div>
  );
}

function EvidenceView({
  result,
  overlayVisible,
  onOverlayVisibleChange,
}: {
  result: AssistantResultView;
  overlayVisible: boolean;
  onOverlayVisibleChange: (visible: boolean) => void;
}) {
  const evidence = result.evidence;
  if (!evidence)
    return (
      <Empty
        title="No evidence to inspect"
        detail="Evidence appears only after the backend commits a result for identified scientific imagery."
      />
    );
  const candidates = evidence.grounding?.candidates ?? [];
  return (
    <div className="inference-evidence-card">
      <div className="grounding-chip" role="img" aria-label="Inference source chip with grounding">
        <Image
          src={inferenceArtifactUrl(evidence.input_chip_artifact.artifact_id)}
          alt={`Scientific RGB model chip for ${evidence.source_chip.scene.item}`}
          width={evidence.source_chip.width}
          height={evidence.source_chip.height}
          unoptimized
        />
        {candidates.map((candidate) => {
          const box = candidate.image_chip_box;
          return (
            <span
              key={candidate.candidate_index}
              className="grounding-box"
              title={candidate.label}
              style={{
                left: `${(box.x_min / box.image_width) * 100}%`,
                top: `${(box.y_min / box.image_height) * 100}%`,
                width: `${((box.x_max - box.x_min) / box.image_width) * 100}%`,
                height: `${((box.y_max - box.y_min) / box.image_height) * 100}%`,
              }}
            />
          );
        })}
      </div>
      <p>
        <strong>Source chip:</strong> {evidence.source_chip.chip_id}
      </p>
      <p>
        <strong>Pixel size:</strong> {evidence.source_chip.width} × {evidence.source_chip.height}
        {"; fixed RGB rendering, no per-image normalization."}
      </p>
      <p>
        <strong>Quality:</strong> {evidence.quality_decision.state.replaceAll("_", " ")} —{" "}
        {evidence.quality_decision.reason}
      </p>
      {evidence.grounding ? (
        <p>
          <strong>Grounding:</strong> {evidence.grounding.status.replaceAll("_", " ")} using{" "}
          {evidence.grounding.model.model} · {evidence.grounding.model.version}.{" "}
          {candidates.length
            ? `${candidates.length} validated candidate region(s).`
            : evidence.grounding.reason}
        </p>
      ) : (
        <p>No grounding was produced for this operation.</p>
      )}
      {candidates.length ? (
        <label className="overlay-toggle">
          <input
            type="checkbox"
            checked={overlayVisible && !result.stale}
            disabled={result.stale}
            onChange={(event) => onOverlayVisibleChange(event.target.checked)}
          />{" "}
          Show validated region on map
        </label>
      ) : null}
      {evidence.source_chip.phase6_quality.quality_checks.map((check) => (
        <p key={check.check_id} className={`quality-check quality-${check.outcome}`}>
          <strong>{check.outcome}:</strong> {check.explanation}
        </p>
      ))}
    </div>
  );
}

function ActivityView({ result }: { result: AssistantResultView }) {
  if (!result.status)
    return (
      <Empty
        title="No activity recorded"
        detail="Drafting a question does not create an inference job."
      />
    );
  const status = result.status;
  return (
    <div className="inference-activity-card">
      <p>
        <strong>Job:</strong> {status.job_id}
      </p>
      <p>
        <strong>State:</strong> {status.state}
      </p>
      <p>
        <strong>Stage:</strong> {status.current_stage?.replaceAll("_", " ") ?? "not started"}
      </p>
      {status.progress ? (
        <p>
          <strong>Completed stages:</strong> {status.progress.completed_units} of{" "}
          {status.progress.total_units}
        </p>
      ) : null}
      <p>No completion percentage is inferred from these stage units.</p>
    </div>
  );
}

export function ResultsTabs({
  activeTab,
  onChange,
  result,
  overlayVisible,
  onOverlayVisibleChange,
}: {
  activeTab: ResultTab;
  onChange: (tab: ResultTab) => void;
  result: AssistantResultView;
  overlayVisible: boolean;
  onOverlayVisibleChange: (visible: boolean) => void;
}) {
  const tabRefs = useRef<Record<ResultTab, HTMLButtonElement | null>>({
    answer: null,
    evidence: null,
    activity: null,
  });
  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, current: ResultTab) => {
    const currentIndex = tabs.findIndex((tab) => tab.id === current);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown")
      nextIndex = (currentIndex + 1) % tabs.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp")
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const nextTab = tabs[nextIndex].id;
    onChange(nextTab);
    tabRefs.current[nextTab]?.focus();
  };
  return (
    <div className="results-area">
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
      <section id={`${activeTab}-panel`} role="tabpanel" aria-labelledby={`${activeTab}-tab`}>
        {activeTab === "answer" ? <AnswerView result={result} /> : null}
        {activeTab === "evidence" ? (
          <EvidenceView
            result={result}
            overlayVisible={overlayVisible}
            onOverlayVisibleChange={onOverlayVisibleChange}
          />
        ) : null}
        {activeTab === "activity" ? <ActivityView result={result} /> : null}
      </section>
    </div>
  );
}
