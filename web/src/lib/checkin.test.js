import { expect, test } from "vitest";
import { shouldCheckIn, composeCheckIn } from "./checkin.js";

const block = { start: "09:00", end: "10:00", label: "work", tag: "Deep work" };

test("fires in the first minute of the hour for an active block", () => {
  expect(shouldCheckIn(9 * 60 + 0.4, block, null)).toBe(true);
});

test("does not fire mid-hour", () => {
  expect(shouldCheckIn(9 * 60 + 30, block, null)).toBe(false);
});

test("does not fire when no block is active", () => {
  expect(shouldCheckIn(9 * 60, null, null)).toBe(false);
});

test("does not re-fire for a block already prompted (deduped by start)", () => {
  expect(shouldCheckIn(9 * 60 + 0.4, block, "09:00")).toBe(false);
});

test("composeCheckIn carries the current label as the default", () => {
  const c = composeCheckIn(block);
  expect(c.defaultLabel).toBe("work");
  expect(c.question).toMatch(/working on/i);
  expect(c.title).toContain("09:00");
});
