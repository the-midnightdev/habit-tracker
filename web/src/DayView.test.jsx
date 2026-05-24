import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import DayView from "./DayView.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("renders blocks and a done-count summary", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({
    date: "2026-05-24",
    blocks: [
      { start: "08:00", end: "09:00", label: "standup", state: "done" },
      { start: "09:00", end: "10:00", label: "code", state: "pending" },
    ],
  });
  render(<DayView />);
  await waitFor(() => expect(screen.getByText("standup")).toBeInTheDocument());
  expect(screen.getByText("1 / 2 done")).toBeInTheDocument(); // exact: only the count span
});

test("shows an empty state when there are no blocks", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks: [] });
  render(<DayView />);
  await waitFor(() => expect(screen.getByText(/no blocks/i)).toBeInTheDocument());
});
