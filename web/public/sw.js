/* Service Worker for hourly check-in push notifications. */

self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : {};
  const title = payload.title || "Time to check in";
  const body = payload.question || "What are you working on this hour?";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: "hourly-checkin",
      data: payload,
      actions: [
        { action: "skip", title: "Skip this hour" },
        { action: "open", title: "Open" },
      ],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  const data = event.notification.data || {};
  event.notification.close();

  if (event.action === "skip") {
    event.waitUntil(
      fetch(`/api/days/${data.date}/blocks/${encodeURIComponent(data.start)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: "skipped" }),
      })
    );
    return;
  }

  const message = { type: "checkin-open", block: data };
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        for (const client of clients) {
          if ("focus" in client) {
            client.postMessage(message);
            return client.focus();
          }
        }
        return self.clients.openWindow("/").then((c) => c && c.postMessage(message));
      })
  );
});
