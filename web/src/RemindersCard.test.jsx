import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import RemindersCard from "./RemindersCard.jsx";

const reminder = {
  origin_date: "2026-05-24", kind: "block", ref: "08:00",
  text: "ping Sam", block_label: "standup", block_time: "08:00–09:00",
};

test("renders nothing when there are no reminders", () => {
  const { container } = render(<RemindersCard reminders={[]} onDismiss={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

test("renders a reminder and dismiss calls back with it", () => {
  const onDismiss = vi.fn();
  render(<RemindersCard reminders={[reminder]} onDismiss={onDismiss} />);
  expect(screen.getByText("ping Sam")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /dismiss reminder/i }));
  expect(onDismiss).toHaveBeenCalledWith(reminder);
});
