import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import EndOfDayReview from "./EndOfDayReview.jsx";

afterEach(cleanup);

const blocks = [
  { start: "08:00", end: "09:00", label: "deep work", state: "done" },
  { start: "18:00", end: "18:30", label: "walk", state: "pending" },
];

test("lists only still-pending blocks and marks one done", () => {
  const onMark = vi.fn();
  render(<EndOfDayReview blocks={blocks} onMark={onMark} />);
  expect(screen.queryByText(/deep work/)).toBeNull();      // done block hidden
  fireEvent.click(screen.getByLabelText("mark walk done"));
  expect(onMark).toHaveBeenCalledWith("18:00", { state: "done" });
});

test("renders nothing when no blocks are pending", () => {
  const allDone = [{ start: "08:00", end: "09:00", label: "x", state: "done" }];
  const { container } = render(<EndOfDayReview blocks={allDone} onMark={() => {}} />);
  expect(container.firstChild).toBeNull();
});
