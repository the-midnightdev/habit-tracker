import { expect, test } from "vitest";
import {
  minOf, durMin, axisRange, activeStart, focusedMinutes, remainingMinutes, countdown,
} from "./schedule.js";

const blocks = [
  { start: "13:00", end: "14:00", state: "done" },
  { start: "14:00", end: "15:00", state: "pending" },
  { start: "15:00", end: "16:30", state: "pending" },
];

test("minOf parses HH:MM", () => {
  expect(minOf("14:30")).toBe(870);
});

test("durMin is end minus start", () => {
  expect(durMin({ start: "15:00", end: "16:30" })).toBe(90);
});

test("axisRange floors earliest hour and ceils latest", () => {
  expect(axisRange(blocks)).toEqual({ startHour: 13, endHour: 17 });
  expect(axisRange([])).toBeNull();
});

test("activeStart finds the non-done block containing now", () => {
  expect(activeStart(blocks, minOf("14:23"))).toBe("14:00");
});

test("activeStart ignores done blocks and returns null when nothing matches", () => {
  expect(activeStart(blocks, minOf("13:30"))).toBeNull(); // 13:00 block is done
  expect(activeStart(blocks, minOf("20:00"))).toBeNull();
});

test("focusedMinutes sums done durations", () => {
  expect(focusedMinutes(blocks)).toBe(60);
});

test("remainingMinutes sums pending blocks ending after now", () => {
  expect(remainingMinutes(blocks, minOf("14:23"))).toBe(60 + 90); // 14:00 and 15:00 blocks
  expect(remainingMinutes(blocks, minOf("15:30"))).toBe(90);       // only the 15:00 block
});

test("remainingMinutes excludes skipped blocks", () => {
  const withSkip = [
    { start: "14:00", end: "15:00", state: "skipped" },
    { start: "15:00", end: "16:00", state: "pending" },
  ];
  expect(remainingMinutes(withSkip, minOf("13:00"))).toBe(60); // only the pending block
});

test("countdown renders mm:ss and clamps at zero", () => {
  expect(countdown(minOf("15:00"), minOf("14:23"))).toBe("37:00");
  expect(countdown(minOf("15:00"), 14 * 60 + 23.5)).toBe("36:30");
  expect(countdown(minOf("14:00"), minOf("15:00"))).toBe("0:00");
});
