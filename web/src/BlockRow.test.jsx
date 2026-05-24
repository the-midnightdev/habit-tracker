import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import BlockRow from "./BlockRow.jsx";

const block = { start: "08:00", end: "09:00", label: "standup", state: "pending" };

test("renders time range and label", () => {
  render(<BlockRow block={block} onMark={() => {}} />);
  expect(screen.getByText("08:00–09:00")).toBeInTheDocument();
  expect(screen.getByText("standup")).toBeInTheDocument();
});

test("Done button calls onMark with done state", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "done" });
});

test("clicking Done on an already-done block resets it to pending", () => {
  const onMark = vi.fn();
  render(<BlockRow block={{ ...block, state: "done" }} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "pending" });
});
