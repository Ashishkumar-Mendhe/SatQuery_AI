import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("synthetic network failure")));
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("WorkspaceShell", () => {
  it("renders useful empty states while analysis and map features are unavailable", async () => {
    render(<WorkspaceShell />);

    expect(screen.getAllByText("No imagery selected").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No area selected").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Analyze" })).toBeDisabled();
    expect(screen.getByText(/Analytical pipelines available/)).toBeVisible();
    expect(await screen.findByText("Backend unreachable")).toBeVisible();
  });

  it("inserts, edits, and clears a suggested question", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);
    const composer = screen.getByRole("textbox", { name: "Question" });

    await user.click(screen.getByRole("button", { name: "Where is vegetation visible?" }));
    expect(composer).toHaveValue("Where is vegetation visible?");

    await user.type(composer, " Please focus on the selected area.");
    expect(composer).toHaveValue("Where is vegetation visible? Please focus on the selected area.");

    await user.click(screen.getByRole("button", { name: "Clear draft" }));
    expect(composer).toHaveValue("");
  });

  it("preserves a draft across tabs and assistant visibility changes", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);
    const composer = screen.getByRole("textbox", { name: "Question" });
    fireEvent.change(composer, {
      target: { value: "Review the imagery once a real asset is selected." },
    });

    await user.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("No evidence to inspect");

    await user.click(screen.getAllByRole("button", { name: "Hide assistant" })[0]);
    expect(screen.queryByRole("textbox", { name: "Question" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show assistant" }));
    expect(screen.getByRole("textbox", { name: "Question" })).toHaveValue(
      "Review the imagery once a real asset is selected.",
    );
    expect(screen.getByRole("tab", { name: "Evidence" })).toHaveAttribute("aria-selected", "true");
  });

  it("supports arrow, Home, and End navigation across result tabs", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);
    const answerTab = screen.getByRole("tab", { name: "Answer" });
    answerTab.focus();

    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Evidence" })).toHaveFocus();
    expect(screen.getByRole("tabpanel")).toHaveTextContent("No evidence to inspect");

    await user.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Activity" })).toHaveFocus();

    await user.keyboard("{Home}");
    expect(answerTab).toHaveFocus();
  });

  it("collapses the desktop sidebar and explains planned destinations", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);
    const collapse = screen.getByRole("button", { name: "Collapse navigation sidebar" });

    await user.click(collapse);
    expect(screen.getByRole("button", { name: "Expand navigation sidebar" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    expect(screen.getByRole("link", { name: /History/ })).toHaveAttribute("href", "/history");
    expect(screen.getByRole("link", { name: /Saved AOIs/ })).toHaveAttribute("href", "/saved-aois");
    expect(screen.getByRole("link", { name: /Reports/ })).toHaveAttribute("href", "/reports");

    await user.click(screen.getByRole("button", { name: /Missions/ }));
    expect(screen.getByText(/Missions: Multi-target persistent campaign/)).toBeInTheDocument();
  });

  it("opens mobile navigation and closes it through its backdrop control", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);

    await user.click(screen.getByRole("button", { name: "Open workspace navigation" }));
    expect(screen.getByLabelText("Workspace navigation")).toHaveClass("mobile-open");

    await user.click(screen.getByRole("button", { name: "Close workspace navigation" }));
    expect(screen.getByLabelText("Workspace navigation")).not.toHaveClass("mobile-open");
  });

  it("contains dialog focus, closes with Escape, and restores trigger focus", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);
    const trigger = screen.getByRole("button", { name: "Open workspace guide" });
    trigger.focus();
    await user.click(trigger);

    expect(screen.getByRole("dialog", { name: "What is available here?" })).toBeInTheDocument();
    const close = screen.getByRole("button", { name: "Close workspace guide" });
    expect(close).toHaveFocus();

    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: "Got it" })).toHaveFocus();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
