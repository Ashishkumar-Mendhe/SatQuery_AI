import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkflowDateFilterPanel } from "./workflow-date-filter-panel";

describe("WorkflowDateFilterPanel", () => {
  const defaultFilters = {
    maxCloudCover: 20,
    sensorType: "optical" as const,
    limit: 12,
  };

  it("renders date inputs and presets", () => {
    render(
      <WorkflowDateFilterPanel
        mode="visual_question_answering"
        dateRange={{ start_date: "2026-01-01", end_date: "2026-01-31" }}
        sceneFilters={defaultFilters}
        onDateRangeChange={vi.fn()}
        onSceneFiltersChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Start Date")).toHaveValue("2026-01-01");
    expect(screen.getByLabelText("End Date")).toHaveValue("2026-01-31");
    expect(screen.getByRole("button", { name: "Last 30 Days" })).toBeInTheDocument();
  });

  it("displays validation error when start date is after end date", () => {
    render(
      <WorkflowDateFilterPanel
        mode="visual_question_answering"
        dateRange={{ start_date: "2026-02-15", end_date: "2026-02-01" }}
        sceneFilters={defaultFilters}
        onDateRangeChange={vi.fn()}
        onSceneFiltersChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Start date must precede or equal end date.")).toBeInTheDocument();
  });

  it("applies quick preset when clicking preset button", () => {
    const onDateRangeChange = vi.fn();
    render(
      <WorkflowDateFilterPanel
        mode="visual_question_answering"
        dateRange={null}
        sceneFilters={defaultFilters}
        onDateRangeChange={onDateRangeChange}
        onSceneFiltersChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Last 30 Days" }));
    expect(onDateRangeChange).toHaveBeenCalledWith(
      expect.objectContaining({
        start_date: expect.any(String),
        end_date: expect.any(String),
      }),
    );
  });
});
