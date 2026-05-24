import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import BlockRow from "./BlockRow.jsx";

afterEach(() => vi.restoreAllMocks());

const block = { start: "08:00", end: "09:00", label: "standup", state: "pending" };

test("renders time range and label", () => {
  render(<BlockRow block={block} onMark={() => {}} />);
  expect(screen.getByText("08:00–09:00")).toBeInTheDocument();
  expect(screen.getByText("standup")).toBeInTheDocument();
});

test("Done calls onMark with done", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "done" });
});

test("clicking Done on a done block resets to pending", () => {
  const onMark = vi.fn();
  render(<BlockRow block={{ ...block, state: "done" }} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "pending" });
});

test("Skip calls onMark with skipped", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /skip/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "skipped" });
});

test("editing the label submits once on blur", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByText("standup"));
  const input = screen.getByDisplayValue("standup");
  fireEvent.change(input, { target: { value: "fixed bug" } });
  fireEvent.blur(input);
  expect(onMark).toHaveBeenCalledTimes(1);
  expect(onMark).toHaveBeenCalledWith("08:00", { label: "fixed bug" });
});
