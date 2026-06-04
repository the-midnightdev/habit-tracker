import { afterEach, expect, test, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import InsightCard from "./InsightCard.jsx";

afterEach(cleanup);

test("shows the confidence meter when not ready", () => {
  render(<InsightCard insight={{ ready: false, daysChecked: 7, completions: 4 }} />);
  expect(screen.getByText(/7\s*\/\s*14 days/)).toBeTruthy();
});

test("shows the headline and keep/tweak/drop when ready", () => {
  const onTweak = vi.fn();
  const insight = {
    ready: true, headline: "Energy averaged +1.2 on days you completed deep work.",
    meanDelta: 1.2, suggestion: { action: "keep", blockId: "b1", text: "Worth keeping." },
  };
  render(<InsightCard insight={insight} onKeep={() => {}} onTweak={onTweak} onDrop={() => {}} />);
  expect(screen.getByText(/averaged \+1.2/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /tweak/i }));
  expect(onTweak).toHaveBeenCalledWith(insight.suggestion);
});
