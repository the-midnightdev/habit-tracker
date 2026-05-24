import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TemplateEditor from "./TemplateEditor.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("lists existing template blocks with their tag", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup", tag: "Deep work" },
  ]);
  render(<TemplateEditor />);
  expect(await screen.findByText(/standup/)).toBeInTheDocument();
  expect(screen.getByText(/Deep work/)).toBeInTheDocument();
});

test("editing a block sends the chosen tag", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup", tag: null },
  ]);
  const edit = vi.spyOn(api, "editTemplateBlock").mockResolvedValue({});
  render(<TemplateEditor />);

  fireEvent.click(await screen.findByRole("button", { name: /edit/i }));
  fireEvent.change(screen.getByLabelText("tag"), { target: { value: "Break" } });
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  await waitFor(() =>
    expect(edit).toHaveBeenCalledWith("08:00", {
      new_start: "08:00", new_end: "09:00", label: "standup", tag: "Break",
    })
  );
});
