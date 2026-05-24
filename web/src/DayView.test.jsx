import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import DayView from "./DayView.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

const FIXED_NOW = new Date("2026-05-24T14:23:00");

function mockDay(blocks) {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks });
}

test("renders blocks, progress count, and the active countdown", async () => {
  mockDay([
    { start: "13:00", end: "14:00", label: "Lunch", state: "done", tag: "Break" },
    { start: "14:00", end: "15:00", label: "Auth bug", state: "pending", tag: "Deep work" },
  ]);
  render(<DayView now={FIXED_NOW} />);
  await waitFor(() => expect(screen.getByText("Auth bug")).toBeInTheDocument());
  expect(screen.getByText("1 / 2 done")).toBeInTheDocument();
  expect(screen.getByText("37:00")).toBeInTheDocument();
});

test("marks the active block done via Complete", async () => {
  mockDay([{ start: "14:00", end: "15:00", label: "Auth bug", state: "pending", tag: "Deep work" }]);
  const mark = vi.spyOn(api, "markBlock").mockResolvedValue({
    date: "2026-05-24",
    blocks: [{ start: "14:00", end: "15:00", label: "Auth bug", state: "done", tag: "Deep work" }],
  });
  render(<DayView now={FIXED_NOW} />);
  fireEvent.click(await screen.findByRole("button", { name: /complete/i }));
  await waitFor(() =>
    expect(mark).toHaveBeenCalledWith("2026-05-24", "14:00", { state: "done" })
  );
});

test("shows the empty state when there are no blocks", async () => {
  mockDay([]);
  render(<DayView now={FIXED_NOW} />);
  await waitFor(() => expect(screen.getByText(/no blocks/i)).toBeInTheDocument());
});
