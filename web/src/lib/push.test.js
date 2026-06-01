import { afterEach, expect, test, vi } from "vitest";

vi.mock("../api.js", () => ({
  getPushKey: vi.fn().mockResolvedValue({ key: "QUJDRA" }), // base64url of "ABCD"
  subscribePush: vi.fn().mockResolvedValue({ ok: true }),
  unsubscribePush: vi.fn().mockResolvedValue(null),
}));

import * as api from "../api.js";
import { isPushSupported, subscribeToPush, unsubscribeFromPush } from "./push.js";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

test("isPushSupported is true when serviceWorker and PushManager exist", () => {
  Object.defineProperty(navigator, "serviceWorker", { value: {}, configurable: true });
  Object.defineProperty(window, "PushManager", { value: function () {}, configurable: true });
  expect(isPushSupported()).toBe(true);
});

test("subscribeToPush subscribes and posts the subscription JSON", async () => {
  const fakeSub = {
    endpoint: "https://push/1",
    toJSON: () => ({ endpoint: "https://push/1", keys: { p256dh: "p", auth: "a" } }),
  };
  const reg = { pushManager: { subscribe: vi.fn().mockResolvedValue(fakeSub) } };
  vi.stubGlobal("navigator", { serviceWorker: { ready: Promise.resolve(reg) } });

  const sub = await subscribeToPush();
  expect(reg.pushManager.subscribe).toHaveBeenCalledWith(
    expect.objectContaining({ userVisibleOnly: true })
  );
  expect(api.subscribePush).toHaveBeenCalledWith({
    endpoint: "https://push/1",
    keys: { p256dh: "p", auth: "a" },
  });
  expect(sub).toBe(fakeSub);
});

test("unsubscribeFromPush unsubscribes and tells the backend", async () => {
  const fakeSub = { endpoint: "https://push/1", unsubscribe: vi.fn().mockResolvedValue(true) };
  const reg = { pushManager: { getSubscription: vi.fn().mockResolvedValue(fakeSub) } };
  vi.stubGlobal("navigator", { serviceWorker: { ready: Promise.resolve(reg) } });

  await unsubscribeFromPush();
  expect(api.unsubscribePush).toHaveBeenCalledWith("https://push/1");
  expect(fakeSub.unsubscribe).toHaveBeenCalled();
});

test("unsubscribeFromPush is a no-op when there is no subscription", async () => {
  const reg = { pushManager: { getSubscription: vi.fn().mockResolvedValue(null) } };
  vi.stubGlobal("navigator", { serviceWorker: { ready: Promise.resolve(reg) } });

  await unsubscribeFromPush();
  expect(api.unsubscribePush).not.toHaveBeenCalled();
});
