import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
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

test("custom name + decrease direction submits direction decrease", () => {
  const onCreate = vi.fn();
  render(<OutcomeWizard open blocks={[]} onCreate={onCreate} onOpenChange={() => {}}
                        onAddBlock={() => Promise.resolve({})} />);
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Less screen time" } });
  fireEvent.click(screen.getByLabelText("direction decrease"));
  fireEvent.click(screen.getByRole("button", { name: /create outcome/i }));
  expect(onCreate).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Less screen time", direction: "decrease", block_ids: [] })
  );
});

test("add an experiment creates and links a new block", async () => {
  const onCreate = vi.fn();
  const onAddBlock = vi.fn(() =>
    Promise.resolve({ id: "new1", start: "07:00", end: "07:30", label: "morning walk" }));
  render(<OutcomeWizard open blocks={[]} onCreate={onCreate} onOpenChange={() => {}}
                        onAddBlock={onAddBlock} />);
  fireEvent.click(screen.getByRole("button", { name: /add an experiment/i }));
  fireEvent.change(screen.getByLabelText("start"), { target: { value: "07:00" } });
  fireEvent.change(screen.getByLabelText("end"), { target: { value: "07:30" } });
  fireEvent.change(screen.getByLabelText("label"), { target: { value: "morning walk" } });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
  await screen.findByText(/morning walk/);   // appears in the list, auto-linked
  fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Move more" } });
  fireEvent.click(screen.getByRole("button", { name: /create outcome/i }));
  expect(onAddBlock).toHaveBeenCalled();
  expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ block_ids: ["new1"] }));
});
