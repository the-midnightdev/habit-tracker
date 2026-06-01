import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  // "Auth bug" appears in the timeline block AND the active "Now" card.
  await waitFor(() => expect(screen.getAllByText("Auth bug").length).toBeGreaterThan(0));
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

test("day navigation updates the relative-day label", async () => {
  mockDay([{ start: "09:00", end: "10:00", label: "Standup", state: "pending", tag: "Deep work" }]);
  render(<DayView now={FIXED_NOW} />);
  // The jump-to-today button's label tracks the viewed day.
  const label = () => screen.getByRole("button", { name: /go to today/i }).textContent.trim();
  await waitFor(() => expect(label()).toBe("Today"));

  fireEvent.click(screen.getByRole("button", { name: /next day/i }));
  await waitFor(() => expect(label()).toBe("Tomorrow"));

  fireEvent.click(screen.getByRole("button", { name: /previous day/i }));
  fireEvent.click(screen.getByRole("button", { name: /previous day/i }));
  await waitFor(() => expect(label()).toBe("Yesterday"));

  fireEvent.click(screen.getByRole("button", { name: /go to today/i }));
  await waitFor(() => expect(label()).toBe("Today"));
});

test("shows the empty state when there are no blocks", async () => {
  mockDay([]);
  render(<DayView now={FIXED_NOW} />);
  await waitFor(() => expect(screen.getByText(/no blocks/i)).toBeInTheDocument());
});

test("renders reminders and notes from the day payload", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({
    date: "2026-05-24",
    blocks: [{ start: "09:00", end: "10:00", label: "work", state: "pending", tag: "Deep work", comment: null, flagged: false }],
    notes: [{ id: "n1", text: "call Sam", flagged: false }],
    reminders: [{ origin_date: "2026-05-23", kind: "note", ref: "old", text: "from yesterday" }],
  });
  render(<DayView now={FIXED_NOW} />);
  expect(await screen.findByText("from yesterday")).toBeInTheDocument();
  expect(screen.getByText("call Sam")).toBeInTheDocument();
});

test("dismissing a reminder calls the API and reloads", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({
    date: "2026-05-24",
    blocks: [],
    notes: [],
    reminders: [{ origin_date: "2026-05-23", kind: "note", ref: "old", text: "from yesterday" }],
  });
  const dismiss = vi.spyOn(api, "dismissReminder").mockResolvedValue(null);
  render(<DayView now={FIXED_NOW} />);
  fireEvent.click(await screen.findByRole("button", { name: /dismiss reminder/i }));
  await waitFor(() =>
    expect(dismiss).toHaveBeenCalledWith({ origin_date: "2026-05-23", kind: "note", ref: "old" })
  );
});

test("deleting a note calls the API and reloads", async () => {
  vi.spyOn(api, "getDay")
    .mockResolvedValueOnce({ date: "2026-05-24", blocks: [], notes: [{ id: "n1", text: "call Sam", flagged: false }], reminders: [] })
    .mockResolvedValue({ date: "2026-05-24", blocks: [], notes: [], reminders: [] });
  const del = vi.spyOn(api, "deleteNote").mockResolvedValue(null);
  render(<DayView now={FIXED_NOW} />);
  fireEvent.click(await screen.findByRole("button", { name: /delete note/i }));
  await waitFor(() => expect(del).toHaveBeenCalledWith("2026-05-24", "n1"));
  await waitFor(() => expect(screen.queryByText("call Sam")).not.toBeInTheDocument());
});

test("a service-worker checkin-open message opens the modal on the pushed day", async () => {
  let swHandler;
  const swStub = {
    addEventListener: (type, fn) => { if (type === "message") swHandler = fn; },
    removeEventListener: () => {},
  };
  Object.defineProperty(navigator, "serviceWorker", { value: swStub, configurable: true });
  try {
    mockDay([{ start: "09:00", end: "10:00", label: "work", state: "pending", tag: "Deep work" }]);
    render(<DayView now={FIXED_NOW} />);   // FIXED_NOW is 2026-05-24T14:23:00 (today = 2026-05-24)
    await screen.findByText("Planner");
    // Fire a push "open" for a DIFFERENT day than the one being viewed
    swHandler({ data: { type: "checkin-open", block: { date: "2026-05-20", start: "09:00", end: "10:00", label: "work", tag: "Deep work", title: "09:00 — new hour", question: "What are you working on this hour?" } } });
    // The jump-to-today button label should now reflect the navigated (pushed) day, not "Today"
    // (The modal opens at the same time, which sets aria-hidden on the background, so we
    // must pass hidden:true to find the nav button while the modal is open.)
    await waitFor(() => {
      const btn = screen.getByRole("button", { name: /go to today/i, hidden: true });
      expect(btn.textContent.trim()).not.toBe("Today");
    });
  } finally {
    // Unmount before removing the stub so the SW cleanup effect can call removeEventListener
    cleanup();
    try {
      delete navigator.serviceWorker;
    } catch {
      Object.defineProperty(navigator, "serviceWorker", { value: undefined, configurable: true });
    }
  }
});
