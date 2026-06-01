import { getPushKey, subscribePush, unsubscribePush } from "../api.js";

export function isPushSupported() {
  return (
    typeof navigator !== "undefined" &&
    "serviceWorker" in navigator &&
    typeof window !== "undefined" &&
    "PushManager" in window
  );
}

// base64url VAPID public key -> Uint8Array, as pushManager.subscribe requires.
function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function registerServiceWorker() {
  return navigator.serviceWorker.register("/sw.js");
}

export async function subscribeToPush() {
  const reg = await navigator.serviceWorker.ready;
  const { key } = await getPushKey();
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  await subscribePush(subscription.toJSON());
  return subscription;
}

export async function unsubscribeFromPush() {
  const reg = await navigator.serviceWorker.ready;
  const subscription = await reg.pushManager.getSubscription();
  if (!subscription) return;
  await unsubscribePush(subscription.endpoint);
  await subscription.unsubscribe();
}
