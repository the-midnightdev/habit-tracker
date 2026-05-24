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

test("Skip button calls onMark with skipped state", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /skip/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "skipped" });
});

test("editing the label submits the new value exactly once on blur", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByText("standup"));  // enter edit mode
  const input = screen.getByDisplayValue("standup");
  fireEvent.change(input, { target: { value: "fixed bug" } });
  fireEvent.blur(input);
  expect(onMark).toHaveBeenCalledTimes(1);
  expect(onMark).toHaveBeenCalledWith("08:00", { label: "fixed bug" });
});

test("blurring an unchanged label does not call onMark", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByText("standup"));
  fireEvent.blur(screen.getByDisplayValue("standup"));
  expect(onMark).not.toHaveBeenCalled();
});
