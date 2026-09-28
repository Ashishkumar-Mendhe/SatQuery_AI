import { render, screen } from "@testing-library/react";
import type React from "react";
import { describe, expect, it, vi } from "vitest";
import { WorkspaceErrorBoundary } from "./workspace-error-boundary";

function FaultyComponent(): React.ReactNode {
  throw new Error("Simulated rendering failure");
}

describe("WorkspaceErrorBoundary", () => {
  it("renders children when no error occurs", () => {
    render(
      <WorkspaceErrorBoundary>
        <div>Workspace child content</div>
      </WorkspaceErrorBoundary>,
    );

    expect(screen.getByText("Workspace child content")).toBeInTheDocument();
  });

  it("catches errors and displays fallback UI", () => {
    // Suppress console.error in test output
    vi.spyOn(console, "error").mockImplementation(() => {});

    render(
      <WorkspaceErrorBoundary>
        <FaultyComponent />
      </WorkspaceErrorBoundary>,
    );

    expect(
      screen.getByRole("heading", { name: "Workspace encountered an error" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Simulated rendering failure")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload Workspace" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start Fresh (Clear Draft)" })).toBeInTheDocument();
  });
});
