// Thin wrapper around the browser Notification API, isolated so nothing else in
// the app touches the global Notification directly (and so it can be mocked).

export function notificationsSupported() {
  return typeof Notification !== "undefined";
}

export async function requestPermission() {
  if (!notificationsSupported()) return "denied";
  return Notification.requestPermission();
}

export function notify(title, body) {
  if (!notificationsSupported() || Notification.permission !== "granted") return;
  new Notification(title, { body });
}
