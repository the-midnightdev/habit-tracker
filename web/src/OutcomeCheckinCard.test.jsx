import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import OutcomeCheckinCard from "./OutcomeCheckinCard.jsx";

afterEach(cleanup);

const active = [{ id: "o1", name: "More energy", status: "active", todayRating: null }];

test("renders one row per active outcome with a 1-5 scale", () => {
  render(<OutcomeCheckinCard outcomes={active} onRate={() => {}} />);
  expect(screen.getByText("More energy")).toBeTruthy();
  expect(screen.getByLabelText("rate More energy 5")).toBeTruthy();
});

test("a tap calls onRate with the outcome id and value", () => {
  const onRate = vi.fn();
  render(<OutcomeCheckinCard outcomes={active} onRate={onRate} />);
  fireEvent.click(screen.getByLabelText("rate More energy 4"));
  expect(onRate).toHaveBeenCalledWith("o1", 4);
});

test("renders nothing when there are no active outcomes", () => {
  const { container } = render(
    <OutcomeCheckinCard outcomes={[{ id: "o2", name: "x", status: "archived" }]} onRate={() => {}} />
  );
  expect(container.firstChild).toBeNull();
});
