# Background push notifications for hourly check-in — design

## Summary

Make the hourly check-in notification fire reliably even when the planner tab
is discarded or its window is closed (as long as the FastAPI backend and
Chrome's background process are alive). This requires **Web Push**: a Service
Worker plus VAPID keys plus a backend scheduler in the FastAPI process that
sends a push notification at the top of each hour. The desktop notification
carries inline **Skip this hour** / **Open** action buttons.

This builds on the already-shipped hourly check-in feature (in-app modal +
client-side trigger + `notify()` wrapper).

## Why Web Push (alternatives rejected)

- **Notification Triggers API** (client-side scheduled notifications, no
  server): experimental, never standardized, removed from Chrome. Rejected.
- **Periodic Background Sync**: browser-enforced minimum interval ~12 hours.
  Cannot do hourly. Rejected.
- **Web Push** (Service Worker + VAPID + server push): the only viable web
  approach for "fires when the tab is closed." Chosen.

## Behavior

- Enabling check-ins now: request notification permission → register the
  Service Worker → subscribe to push → POST the subscription to the backend.
- "Enabled" == "the backend has a stored push subscription." Disabling
  unsubscribes and tells the backend to drop the subscription.
- At each top of the hour the backend scheduler finds today's active block
  (server local time == the single user's local time) and sends a push to
  every stored subscription. No active block or no subscriptions → nothing sent.
- The Service Worker shows a desktop notification with the hour + question and
  two action buttons:
  - **Skip this hour** → the Service Worker calls the backend to mark the block
    skipped, without opening the app.
  - **Open** (and clicking the notification body) → focus/open the app and
    `postMessage` it to open the in-app check-in modal for that block.

## Architecture

### Backend (Python / FastAPI)

A new module `push.py` owns all push concerns; `api.py` wires endpoints and
starts the scheduler; `core.py` gains a small server-side active-block helper if
one is not already reusable.

- **VAPID keys**: generated once on first need and persisted to
  `~/.plan/vapid.json` (respecting the existing `PLAN_DATA_DIR` override). The
  public key (application server key) is served to the client.
- **Subscription store**: persisted to `~/.plan/push_subscriptions.json` — a
  list of subscription objects. Operations: load, add (dedupe by endpoint),
  remove (by endpoint), prune (drop on push failure 404/410).
- **Endpoints**:
  - `GET /api/push/key` → `{ "key": "<base64url VAPID public key>" }`
  - `POST /api/push/subscribe` (body: the browser PushSubscription JSON) → 201
  - `POST /api/push/unsubscribe` (body: `{ "endpoint": "..." }`) → 204
- **Scheduler**: an asyncio task started on FastAPI startup. It computes the
  delay to the next `xx:00`, sleeps, then on each tick:
  1. loads the data store, finds today's active block (by server local time),
  2. if a block is active and subscriptions exist, builds the payload and sends
     a web-push to each subscription,
  3. prunes subscriptions that return 404/410,
  4. reschedules for the next hour.
  The task is cancelled on shutdown.
- **Payload** (JSON): `{ date, start, end, label, tag, title, question }` where
  `title`/`question` come from a server-side `compose_checkin(block)` mirroring
  the JS `composeCheckIn`.
- **Sending**: via `pywebpush` using the VAPID private key and a contact
  `sub` (mailto). `pywebpush` (and its `cryptography` / `py-vapid` deps) added
  to `pyproject.toml` dependencies.

### Frontend

- **`web/public/sw.js`** (classic Service Worker, served at the origin root):
  - `push` event → `event.waitUntil(self.registration.showNotification(title, {
    body, tag, data: { date, start, ... }, actions: [{action:'skip', title:'Skip
    this hour'}, {action:'open', title:'Open'}] }))`.
  - `notificationclick` event → if `event.action === 'skip'`, `fetch` POST the
    backend mark-skipped endpoint for `data.date`/`data.start`; otherwise focus
    an existing client (or `clients.openWindow('/')`) and `postMessage`
    `{ type: 'checkin-open', block }` so the page shows the modal. Always close
    the notification.
  - Logic kept thin (no build step / no ES module imports at runtime).
- **`web/src/lib/push.js`**: `registerServiceWorker()`,
  `subscribeToPush()` (GET key → `pushManager.subscribe` → POST subscribe),
  `unsubscribeFromPush()` (`getSubscription` → unsubscribe → POST unsubscribe),
  `isPushSupported()`. Pure-ish wrappers over `navigator.serviceWorker` /
  `PushManager` / `fetch`, mockable in vitest.
- **`web/src/api.js`**: add `getPushKey`, `subscribePush`, `unsubscribePush`
  client functions following the existing `request(...)` pattern.
- **Rewire the toggle**: `toggleCheckIn` in `DayView.jsx` now drives
  subscribe/unsubscribe (enable → permission + register + subscribe; disable →
  unsubscribe). The local persisted flag still records the on/off state for UI.
  DayView listens for `navigator.serviceWorker` `message` events and opens the
  check-in modal on `{ type: 'checkin-open' }`.

### Reconciling with the shipped feature

- The existing **in-app modal trigger** (client-side `shouldCheckIn` effect)
  stays — it gives an instant, offline-capable prompt when the app is focused.
- The page-level **`notify()` OS-notification call is removed** from the effect:
  push is now the single source of OS notifications, preventing duplicates.
  `notify.js` may remain unused or be deleted if nothing else references it.
- Both the foreground timer and a notification "Open" click route through the
  same `setCheckIn`, deduped by the existing `lastStart` ref so the same hour is
  never prompted twice in-app.

## Data flow (top of hour, tab closed)

1. Scheduler tick → active block found → `pywebpush` to each subscription.
2. Push service delivers to the browser; Chrome wakes the Service Worker.
3. SW `push` handler shows the notification with Skip/Open actions.
4. User clicks **Skip** → SW POSTs mark-skipped → block persisted skipped.
   Or **Open** → app focused/opened → modal shown for the block.

## Error handling

- VAPID file / subscription file missing or corrupt → treat as empty/regenerate
  (never crash the API).
- Push send failure 404/410 → prune that subscription. Other errors → log and
  continue (one bad subscription must not stop the others).
- No internet at `xx:00` → sends fail and are logged; the scheduler continues to
  the next hour. (Documented constraint, not a recoverable error.)
- Service Worker `skip` fetch failure → notification still closes; the in-app
  modal remains available next time the app is opened.

## Testing

- **Backend (pytest, existing harness, pywebpush mocked):**
  - VAPID keys generated once and persisted; reload returns the same keys.
  - Subscription store: add (dedupe by endpoint), remove by endpoint, prune.
  - `compose_checkin` returns the expected title/question/defaultLabel for a
    block.
  - Active-block selection by a given local time (active vs none).
  - One scheduler tick: active block + subscriptions → push sent per
    subscription with the right payload; 410 response prunes the subscription;
    no active block → no send.
  - Endpoints: `GET /api/push/key`, subscribe, unsubscribe round-trip.
- **Frontend (vitest):** `push.js` subscribe and unsubscribe flows with
  `navigator.serviceWorker`, `PushManager`, and `fetch` mocked; `isPushSupported`
  detection.
- **Service Worker:** kept thin; **verified manually** (jsdom cannot run a real
  Service Worker). Manual script: enable check-ins, close the tab, trigger a
  push (temporarily shorten the scheduler delay), confirm the toast + buttons,
  click Skip → block skipped, click Open → app opens to the modal.

## Constraints (documented, accepted)

- The backend must be running at `xx:00` with internet access to the push
  service.
- Fires when the tab is discarded / window closed only while Chrome's background
  process is alive ("continue running background apps"). If Chrome is fully
  quit, nothing fires — out of scope.
- When the app is focused at `xx:00`, both the in-app modal and the OS toast
  appear (a push must always show a notification; it cannot be suppressed for a
  focused tab). Accepted for simplicity.

## Out of scope (YAGNI)

- Native OS agent / scheduled task for the "Chrome fully quit" case.
- Multi-user subscription routing (this is a single-user app; all subscriptions
  belong to the one user).
- Rich notification content beyond title + question + Skip/Open.
- Retry/backoff for transient push failures (prune on gone, log others).
