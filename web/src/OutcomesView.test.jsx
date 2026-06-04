import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

vi.mock("./api.js", () => ({
  getOutcomes: vi.fn(() => Promise.resolve([
    { id: "o1", name: "More energy", status: "active", block_ids: [] },
  ])),
  getTemplate: vi.fn(() => Promise.resolve([])),
  getInsights: vi.fn(() => Promise.resolve({ ready: false, daysChecked: 3, completions: 1 })),
  createOutcome: vi.fn(() => Promise.resolve({ id: "o2" })),
  updateOutcome: vi.fn(() => Promise.resolve({})),
  addTemplateBlock: vi.fn(() => Promise.resolve({})),
}));

import OutcomesView from "./OutcomesView.jsx";

afterEach(cleanup);

test("lists outcomes and their insight state", async () => {
  render(<OutcomesView />);
  await waitFor(() => expect(screen.getByText("More energy")).toBeTruthy());
  expect(screen.getByText(/3\s*\/\s*14 days/)).toBeTruthy();
});
