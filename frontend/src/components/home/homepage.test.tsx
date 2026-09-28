import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";

import { Homepage } from "./homepage";

it("exposes working homepage sections and workspace navigation", () => {
  render(<Homepage />);

  expect(
    screen.getByRole("heading", { name: "Turn satellite imagery into answers you can inspect." }),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: /open workspace/i })[0]).toHaveAttribute(
    "href",
    "/workspace",
  );
  expect(screen.getByRole("link", { name: "Explore capabilities" })).toHaveAttribute(
    "href",
    "#capabilities",
  );
  expect(
    screen.getByRole("heading", { name: "From a scene to a reviewable answer." }),
  ).toBeVisible();
});

it("opens and closes the keyboard-friendly mobile navigation", async () => {
  const user = userEvent.setup();
  render(<Homepage />);

  const menuButton = screen.getByRole("button", { name: "Open navigation" });
  await user.click(menuButton);

  expect(menuButton).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("navigation", { name: "Mobile navigation" })).toBeInTheDocument();

  await user.keyboard("{Escape}");

  expect(screen.queryByRole("navigation", { name: "Mobile navigation" })).not.toBeInTheDocument();
  expect(menuButton).toHaveFocus();
});
