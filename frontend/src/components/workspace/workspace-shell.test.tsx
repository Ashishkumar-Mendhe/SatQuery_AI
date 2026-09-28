import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WorkspaceShell } from "./workspace-shell";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://localhost:8000/api/v1");
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("synthetic network failure")));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("WorkspaceShell", () => {
  it("renders useful empty states before imagery is selected", async () => {
    render(<WorkspaceShell />);

    expect(screen.getAllByText("No imagery selected").length).toBeGreaterThan(0);
    expect(screen.getAllByText("No area selected").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Ask question" })).toBeDisabled();
    expect(screen.getByText("Select an AOI before analysis.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Choose an AOI" })).toBeVisible();
    expect(await screen.findByText("Backend unreachable")).toBeVisible();
  });

  it("inserts, edits, and clears a suggested question", async () => {
    const user = userEvent.setup();
    render(<WorkspaceShell />);
    const composer = screen.getByRole("textbox", { name: "Question" });

    await user.click(screen.getByRole("button", { name: "What is visible in this image?" }));
    expect(composer).toHaveValue("What is visible in this image?");

    await user.type(composer, " Please focus on the selected area.");
    expect(composer).toHaveValue(
      "What is visible in this image? Please focus on the selected area.",
    );

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

    await user.click(screen.getByRole("button", { name: /History/ }));
    expect(screen.getByText(/History: No analysis history exists/)).toBeInTheDocument();
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
