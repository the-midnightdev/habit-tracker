import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import CheckInToggle from "./CheckInToggle.jsx";

test("clicking the off-state control calls onToggle", () => {
  const onToggle = vi.fn();
  render(<CheckInToggle enabled={false} onToggle={onToggle} />);
  fireEvent.click(screen.getByRole("button", { name: /enable hourly check-ins/i }));
  expect(onToggle).toHaveBeenCalled();
});

test("when enabled the control exposes the disable action", () => {
  render(<CheckInToggle enabled={true} onToggle={() => {}} />);
  expect(screen.getByRole("button", { name: /disable hourly check-ins/i })).toBeInTheDocument();
});
