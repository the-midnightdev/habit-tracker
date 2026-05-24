import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

test("editing a block calls editTemplateBlock with the new values", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup" },
  ]);
  const edit = vi.spyOn(api, "editTemplateBlock").mockResolvedValue({});
  render(<TemplateEditor />);

  fireEvent.click(await screen.findByRole("button", { name: /edit/i }));
  fireEvent.change(screen.getByLabelText("edit label"), {
    target: { value: "morning sync" },
  });
  fireEvent.change(screen.getByLabelText("edit start"), {
    target: { value: "08:30" },
  });
  fireEvent.click(screen.getByRole("button", { name: /save/i }));

  expect(edit).toHaveBeenCalledWith("08:00", {
    new_start: "08:30",
    new_end: "09:00",
    label: "morning sync",
  });
});
