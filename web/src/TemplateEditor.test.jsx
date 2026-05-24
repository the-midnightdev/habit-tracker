import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TemplateEditor from "./TemplateEditor.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("lists existing template blocks", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup" },
  ]);
  render(<TemplateEditor />);
  await waitFor(() => expect(screen.getByText("standup")).toBeInTheDocument());
  expect(screen.getByText(/08:00/)).toBeInTheDocument();
});
