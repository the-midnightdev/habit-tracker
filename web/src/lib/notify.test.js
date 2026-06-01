import { afterEach, expect, test, vi } from "vitest";
import { notify, requestPermission, notificationsSupported } from "./notify.js";

afterEach(() => vi.unstubAllGlobals());

test("notificationsSupported reflects whether Notification exists", () => {
  vi.stubGlobal("Notification", function () {});
  expect(notificationsSupported()).toBe(true);
});

test("notify constructs a Notification when permission is granted", () => {
  const ctor = vi.fn();
  ctor.permission = "granted";
  vi.stubGlobal("Notification", ctor);
  notify("hi", "body text");
  expect(ctor).toHaveBeenCalledWith("hi", { body: "body text" });
});

test("notify does nothing when permission is not granted", () => {
  const ctor = vi.fn();
  ctor.permission = "denied";
  vi.stubGlobal("Notification", ctor);
  notify("hi", "body text");
  expect(ctor).not.toHaveBeenCalled();
});

test("requestPermission delegates to Notification.requestPermission", async () => {
  const ctor = vi.fn();
  ctor.requestPermission = vi.fn().mockResolvedValue("granted");
  vi.stubGlobal("Notification", ctor);
  await expect(requestPermission()).resolves.toBe("granted");
  expect(ctor.requestPermission).toHaveBeenCalled();
});
