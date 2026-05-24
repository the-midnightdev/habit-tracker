import { afterEach, expect, test, vi } from "vitest";
import { getDay, markBlock } from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("getDay fetches the day endpoint", async () => {
  const payload = { date: "2026-05-24", blocks: [] };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(payload),
  });
  const result = await getDay("2026-05-24");
  expect(global.fetch).toHaveBeenCalledWith("/api/days/2026-05-24");
  expect(result).toEqual(payload);
});

test("markBlock POSTs state to the block endpoint", async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ date: "2026-05-24", blocks: [] }),
  });
  await markBlock("2026-05-24", "08:00", { state: "done" });
  expect(global.fetch).toHaveBeenCalledWith(
    "/api/days/2026-05-24/blocks/08:00",
    expect.objectContaining({ method: "POST" })
  );
});
