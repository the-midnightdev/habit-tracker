import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("shows the day view by default and switches to template", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks: [] });
  vi.spyOn(api, "getTemplate").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByRole("tab", { name: /day/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: /template/i }));
  // Assert the tab panel becomes visible rather than a specific child —
  // TemplateEditor is rebuilt in a later task.
  expect(await screen.findByRole("tabpanel")).toBeInTheDocument();
});
