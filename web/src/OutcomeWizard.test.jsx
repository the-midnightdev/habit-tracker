import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import OutcomeWizard from "./OutcomeWizard.jsx";

afterEach(cleanup);

const blocks = [
  { id: "b1", start: "08:00", end: "09:00", label: "deep work" },
  { id: "b2", start: "18:00", end: "18:30", label: "walk" },
];

test("clicking a curated chip fills the name and links a block on submit", () => {
  const onCreate = vi.fn();
  render(<OutcomeWizard open blocks={blocks} onCreate={onCreate} onOpenChange={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "More energy" }));
  fireEvent.click(screen.getByLabelText("link deep work"));
  fireEvent.click(screen.getByRole("button", { name: /create outcome/i }));
  expect(onCreate).toHaveBeenCalledWith(
    expect.objectContaining({ name: "More energy", direction: "increase", block_ids: ["b1"] })
  );
});
