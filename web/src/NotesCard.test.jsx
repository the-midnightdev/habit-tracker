import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import NotesCard from "./NotesCard.jsx";

const note = { id: "n1", text: "call Sam", flagged: false };

test("adding a note calls onAdd with text and flag, then clears input", () => {
  const onAdd = vi.fn();
  render(<NotesCard notes={[]} onAdd={onAdd} onToggleFlag={() => {}} onDelete={() => {}} />);
  fireEvent.change(screen.getByLabelText("new note"), { target: { value: "buy milk" } });
  fireEvent.click(screen.getByRole("button", { name: /flag for tomorrow/i }));
  fireEvent.click(screen.getByRole("button", { name: /add note/i }));
  expect(onAdd).toHaveBeenCalledWith({ text: "buy milk", flagged: true });
});

test("toggle and delete call back with the note", () => {
  const onToggleFlag = vi.fn();
  const onDelete = vi.fn();
  render(<NotesCard notes={[note]} onAdd={() => {}} onToggleFlag={onToggleFlag} onDelete={onDelete} />);
  fireEvent.click(screen.getByRole("button", { name: /flag note/i }));
  expect(onToggleFlag).toHaveBeenCalledWith(note);
  fireEvent.click(screen.getByRole("button", { name: /delete note/i }));
  expect(onDelete).toHaveBeenCalledWith(note);
});
