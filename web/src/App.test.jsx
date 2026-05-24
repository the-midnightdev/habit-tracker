import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("shows the day view by default and switches to template", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks: [] });
  vi.spyOn(api, "getTemplate").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByRole("button", { name: /day/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /template/i }));
  // findBy* awaits the TemplateEditor's async load, settling state inside act().
  expect(await screen.findByRole("heading", { name: /template/i })).toBeInTheDocument();
});
