import { expect, test } from "vitest";
import { CURATED_OUTCOMES } from "./outcomes.js";

test("curated outcomes each have a name, direction, and question", () => {
  expect(CURATED_OUTCOMES.length).toBeGreaterThan(0);
  for (const o of CURATED_OUTCOMES) {
    expect(o.name).toBeTruthy();
    expect(["increase", "decrease"]).toContain(o.direction);
    expect(o.question).toBeTruthy();
  }
});
