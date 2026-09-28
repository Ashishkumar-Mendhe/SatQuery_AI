import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { deriveWorkflowState } from "@/lib/workspace-workflow";
import { WorkflowReadinessBanner } from "./workflow-readiness-banner";

describe("WorkflowReadinessBanner", () => {
  it("renders step 1 when AOI is not defined", () => {
    const workflowState = deriveWorkflowState({
      mode: "visual_question_answering",
      selectedAoi: null,
    });

    render(<WorkflowReadinessBanner workflowState={workflowState} />);

    expect(screen.getByText("Step 1 of 4")).toBeInTheDocument();
    expect(screen.getByText("Define Area of Interest")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Draw AOI/ })).toBeInTheDocument();
  });

  it("triggers action callback when action button is clicked", () => {
    const onTrigger = vi.fn();
    const workflowState = {
      step: "ready_for_scene_discovery" as const,
      stepNumber: 3,
      totalSteps: 4,
      readiness: {
        isModeReady: true,
        isAoiReady: true,
        isDateRangeReady: true,
        isScenesReady: false,
        isPreparationReady: false,
        isAnalysisReady: false,
        isQuestionReady: true,
        isReportReady: false,
        canDiscoverScenes: true,
      },
      nextAction: {
        stepNumber: 3,
        title: "Discover Satellite Imagery",
        description: "Query Sentinel-2 L2A scenes",
        actionLabel: "Discover Imagery",
        actionType: "discover_scenes" as const,
        isReady: true,
      },
      statusMessage: "Workspace ready for satellite imagery discovery.",
    };

    render(<WorkflowReadinessBanner workflowState={workflowState} onTriggerAction={onTrigger} />);

    const button = screen.getByRole("button", { name: /Discover Imagery/ });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onTrigger).toHaveBeenCalledWith("discover_scenes");
  });
});
