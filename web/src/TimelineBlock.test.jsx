import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TimelineBlock from "./TimelineBlock.jsx";

afterEach(() => vi.restoreAllMocks());

const block = { start: "08:00", end: "09:00", label: "standup", state: "pending", tag: "Deep work" };
const axisStartMin = 8 * 60;

function renderBlock(overrides = {}, onMark = () => {}) {
  return render(
    <TimelineBlock block={{ ...block, ...overrides }} axisStartMin={axisStartMin}
      isActive={false} onMark={onMark} />
  );
}

test("Done toggles to done, and back to pending when already done", () => {
  const onMark = vi.fn();
  const { rerender } = renderBlock({}, onMark);
  fireEvent.click(screen.getByRole("button", { name: /^done$/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "done" });

  rerender(
    <TimelineBlock block={{ ...block, state: "done" }} axisStartMin={axisStartMin}
      isActive={false} onMark={onMark} />
  );
  fireEvent.click(screen.getByRole("button", { name: /^done$/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "pending" });
});

test("Skip toggles to skipped", () => {
  const onMark = vi.fn();
  renderBlock({}, onMark);
  fireEvent.click(screen.getByRole("button", { name: /^skip$/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "skipped" });
});

test("editing the label submits once on blur", () => {
  const onMark = vi.fn();
  renderBlock({}, onMark);
  fireEvent.click(screen.getByText("standup"));
  const input = screen.getByLabelText("edit label");
  fireEvent.change(input, { target: { value: "fixed bug" } });
  fireEvent.blur(input);
  expect(onMark).toHaveBeenCalledTimes(1);
  expect(onMark).toHaveBeenCalledWith("08:00", { label: "fixed bug" });
});
