import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import CheckInModal from "./CheckInModal.jsx";

const block = { start: "09:00", end: "10:00", label: "work", tag: "Deep work" };
const content = {
  title: "09:00 — new hour",
  question: "What are you working on this hour?",
  defaultLabel: "work",
};

test("renders the question and prefills the label, then saves the edited value", () => {
  const onSave = vi.fn();
  render(<CheckInModal open onOpenChange={() => {}} content={content} block={block} onSave={onSave} onSkip={() => {}} />);
  expect(screen.getByText(/working on this hour/i)).toBeInTheDocument();
  const input = screen.getByLabelText("hour label");
  expect(input).toHaveValue("work");
  fireEvent.change(input, { target: { value: "Write the report" } });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
  expect(onSave).toHaveBeenCalledWith("Write the report");
});

test("the skip button calls onSkip", () => {
  const onSkip = vi.fn();
  render(<CheckInModal open onOpenChange={() => {}} content={content} block={block} onSave={() => {}} onSkip={onSkip} />);
  fireEvent.click(screen.getByRole("button", { name: /skip this hour/i }));
  expect(onSkip).toHaveBeenCalled();
});

test("renders nothing when there is no active block", () => {
  const { container } = render(<CheckInModal open onOpenChange={() => {}} content={null} block={null} onSave={() => {}} onSkip={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});
