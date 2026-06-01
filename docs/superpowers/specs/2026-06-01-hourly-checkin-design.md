# Hourly check-in — design

## Summary

A "chatbot-like" hourly prompt for the web planner. At the top of each clock
hour, while enabled and a block is active, the app fires a desktop notification
and opens an in-app modal asking what the user is working on this hour. The user
can save a new label, skip the hour, or dismiss. Scripted for now, with a clean
seam to swap in a real AI backend later.

## Behavior

- Triggers **strictly at the top of the hour** (first minute of `xx:00`) while
  the app is open. No catch-up if the app was closed at the tick.
- Only fires when **a block is active** and the viewed day **is today**
  (reuses DayView's existing `active`/`isToday` gating).
- Fires **once per hour** — deduped by the active block's `start`, so clock
  jitter or re-renders can't double-prompt.
- Never re-prompts a block already handled in the current session.
- Requires the user to have **enabled** check-ins (one-time permission grant).

When it fires:
1. **Desktop notification** (e.g. "⏰ 09:00 — what are you working on?") to grab
   attention even when the tab is backgrounded.
2. **In-app modal** showing the block's time range + tag, a friendly question,
   and a text input **prefilled with the current label**.
3. User actions:
   - **Save** → updates that hour's label.
   - **Skip this hour** → marks the block `skipped`.
   - **Dismiss (X)** → closes, changes nothing.

If notification permission is denied, the in-app modal still works; the user
just doesn't get the desktop ping.

## Architecture

Three small, isolated units plus a wiring effect. Timing logic lives in
`DayView` (which already owns the 1-second `clock`, the `active` block, and
`onMark`); the modal is pure presentation.

### `src/lib/checkin.js` (pure, no React)
- `shouldCheckIn(nowMin, active, lastStart)` → boolean.
  True when it is the top of the hour (`nowMin % 60 < 1`), `active` exists, and
  `active.start !== lastStart`.
- `composeCheckIn(block)` → `{ title, question, defaultLabel }`.
  **AI seam.** Returns scripted content today (e.g. title from the hour,
  question = "What are you working on this hour?", `defaultLabel` = current
  label). Later this can be replaced by an async call to the Claude API that
  returns the same shape — the modal never changes.

### `src/lib/notify.js` (thin browser-API wrapper)
- `requestPermission()` → Promise resolving to the permission state.
- `notify(title, body)` → shows a `Notification` when permission is granted;
  no-ops otherwise. Isolates the one piece that resists clean unit testing.

### `src/CheckInModal.jsx` (Radix dialog, presentation only)
- Reuses the dialog primitives already used by `BlockDialog`.
- Props: the composed content (`title`, `question`, `defaultLabel`), the active
  `block`, `open`, `onOpenChange`, `onSave(label)`, `onSkip()`.
- Renders block time range + tag, the question, an input prefilled with
  `defaultLabel`, a **Save** button, and a **Skip this hour** button.
- Contains **no timing logic**.

### Wiring in `src/DayView.jsx`
- Holds `enabled` (persisted in `localStorage`) and a `lastStart` ref.
- An effect keyed on `clock` checks `shouldCheckIn(nowMin, active, lastStart)`;
  when true and `enabled`, it records `lastStart`, calls `notify(...)`, and
  opens the modal.
- Modal **Save** → `onMark(active.start, { label })`.
- Modal **Skip** → `onMark(active.start, { state: "skipped" })`.
- Does not open the modal if one is already open.

### Enable control
- A small **"Hourly check-ins"** toggle in the sidebar (near the Now card).
- Clicking it calls `requestPermission()` and sets `enabled = true`, persisted
  in `localStorage`. Toggling off disables the trigger.

## No backend changes

Both label edits and skips use the existing
`POST /api/days/{date}/blocks/{start}` endpoint (`set_block_label` /
`set_block_state`). Label edits are per-day, so the reusable template is
untouched.

## Testing (TDD)

- `src/lib/checkin.test.js`
  - `shouldCheckIn`: true at `xx:00` with an active block; false at `xx:30`;
    false with no active block; false when `active.start === lastStart`.
  - `composeCheckIn`: returns the expected `title`/`question`/`defaultLabel`
    for a given block.
- `src/CheckInModal.test.jsx`
  - Renders the block's time range/tag and the question.
  - Input is prefilled with `defaultLabel`.
  - Save calls `onSave` with the typed label.
  - Skip calls `onSkip`.

`notify.js` is a thin wrapper exercised via mocking where it's consumed.

## Out of scope (YAGNI)

- Real AI/LLM backend (seam only).
- Cross-tab coordination.
- Catch-up prompts for hours missed while the app was closed.
- Persisting which hours were answered beyond the current session.
