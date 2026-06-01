import { afterEach, expect, test, vi } from "vitest";

afterEach(() => vi.unstubAllGlobals());
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

import { addNote, editNote, deleteNote, dismissReminder } from "./api.js";

test("addNote POSTs to the day notes endpoint", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ date: "2026-05-24", notes: [] }), { status: 201 })
  );
  await addNote("2026-05-24", { text: "hi", flagged: false });
  expect(fetchMock).toHaveBeenCalledWith("/api/days/2026-05-24/notes", expect.objectContaining({ method: "POST" }));
});

test("dismissReminder POSTs to the dismiss endpoint", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await dismissReminder({ origin_date: "2026-05-24", kind: "note", ref: "x" });
  expect(fetchMock).toHaveBeenCalledWith("/api/reminders/dismiss", expect.objectContaining({ method: "POST" }));
});

test("deleteNote issues a DELETE", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await deleteNote("2026-05-24", "abc");
  expect(fetchMock).toHaveBeenCalledWith("/api/days/2026-05-24/notes/abc", { method: "DELETE" });
});

import { getPushKey, subscribePush, unsubscribePush } from "./api.js";

function mockFetch(status, body) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  }));
}

test("getPushKey GETs the key endpoint", async () => {
  mockFetch(200, { key: "abc" });
  await expect(getPushKey()).resolves.toEqual({ key: "abc" });
  expect(fetch).toHaveBeenCalledWith("/api/push/key");
});

test("subscribePush POSTs the subscription body", async () => {
  mockFetch(201, { ok: true });
  const sub = { endpoint: "https://push/1", keys: { p256dh: "p", auth: "a" } };
  await subscribePush(sub);
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("/api/push/subscribe");
  expect(opts.method).toBe("POST");
  expect(JSON.parse(opts.body)).toEqual(sub);
});

test("unsubscribePush POSTs the endpoint and handles 204", async () => {
  mockFetch(204, null);
  await expect(unsubscribePush("https://push/1")).resolves.toBeNull();
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("/api/push/unsubscribe");
  expect(JSON.parse(opts.body)).toEqual({ endpoint: "https://push/1" });
});
