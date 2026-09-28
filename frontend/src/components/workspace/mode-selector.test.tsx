import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModeSelector } from "./mode-selector";

describe("ModeSelector", () => {
  it("renders primary analysis modes with radio role", () => {
    render(<ModeSelector selectedMode="visual_question_answering" onSelectMode={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Select Analysis Mode" })).toBeInTheDocument();
    const radios = screen.getAllByRole("radio");
    expect(radios.length).toBe(3);

    const singleImageRadio = screen.getByRole("radio", { name: /Single Image Analysis/ });
    expect(singleImageRadio).toHaveAttribute("aria-checked", "true");
  });

  it("calls onSelectMode when clicking an option", () => {
    const onSelect = vi.fn();
    render(<ModeSelector selectedMode="visual_question_answering" onSelectMode={onSelect} />);

    const changeRadio = screen.getByRole("radio", { name: /Change Detection/ });
    fireEvent.click(changeRadio);

    expect(onSelect).toHaveBeenCalledWith("change_detection");
  });
});
