# Hourly Check-in Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scripted hourly "what are you working on?" prompt to the web planner — a desktop notification plus an in-app modal that fires at the top of each hour and lets the user set the active block's label or skip the hour.

**Architecture:** Pure timing/content helpers in `lib/checkin.js`, a thin browser-notification wrapper in `lib/notify.js`, a presentation-only Radix `CheckInModal`, and a sidebar `CheckInToggle`. `DayView` (which already owns the 1-second clock, the active block, and `onMark`) wires them together via a single effect. No backend changes — label edits and skips reuse the existing `markBlock` API.

**Tech Stack:** React 18, Vite, Vitest + Testing Library, Radix UI dialog primitives, lucide-react icons, Tailwind.

All commands run from `D:\habit-tracker\web`.

---

### Task 1: Check-in timing + content helpers

**Files:**
- Create: `web/src/lib/checkin.js`
- Test: `web/src/lib/checkin.test.js`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/checkin.test.js`:

```js
import { expect, test } from "vitest";
import { shouldCheckIn, composeCheckIn } from "./checkin.js";

const block = { start: "09:00", end: "10:00", label: "work", tag: "Deep work" };

test("fires in the first minute of the hour for an active block", () => {
  expect(shouldCheckIn(9 * 60 + 0.4, block, null)).toBe(true);
});

test("does not fire mid-hour", () => {
  expect(shouldCheckIn(9 * 60 + 30, block, null)).toBe(false);
});

test("does not fire when no block is active", () => {
  expect(shouldCheckIn(9 * 60, null, null)).toBe(false);
});

test("does not re-fire for a block already prompted (deduped by start)", () => {
  expect(shouldCheckIn(9 * 60 + 0.4, block, "09:00")).toBe(false);
});

test("composeCheckIn carries the current label as the default", () => {
  const c = composeCheckIn(block);
  expect(c.defaultLabel).toBe("work");
  expect(c.question).toMatch(/working on/i);
  expect(c.title).toContain("09:00");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/lib/checkin.test.js`
Expected: FAIL — `Failed to resolve import "./checkin.js"`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/checkin.js`:

```js
// Pure helpers for the hourly check-in prompt. No React, no DOM — easy to test.

// True only in the first minute of the hour (nowMin % 60 < 1), when a block is
// active, and we have not already prompted for that block. `lastStart` is the
// start of the last block we prompted for, used to dedupe so the 1-second clock
// can't fire the prompt more than once per hour.
export function shouldCheckIn(nowMin, active, lastStart) {
  if (!active) return false;
  if (active.start === lastStart) return false;
  return nowMin % 60 < 1;
}

// Scripted content for the modal + notification.
// AI SEAM: to add a real assistant later, replace the body with an async call
// that returns the same { title, question, defaultLabel } shape — the modal and
// the DayView wiring stay unchanged.
export function composeCheckIn(block) {
  return {
    title: `${block.start} — new hour`,
    question: "What are you working on this hour?",
    defaultLabel: block.label,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/lib/checkin.test.js`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/checkin.js web/src/lib/checkin.test.js
git commit -m "feat(web): hourly check-in timing and content helpers"
```

---

### Task 2: Browser notification wrapper

**Files:**
- Create: `web/src/lib/notify.js`
- Test: `web/src/lib/notify.test.js`

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/notify.test.js`:

```js
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/lib/notify.test.js`
Expected: FAIL — `Failed to resolve import "./notify.js"`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/lib/notify.js`:

```js
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/lib/notify.test.js`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/notify.js web/src/lib/notify.test.js
git commit -m "feat(web): browser notification wrapper"
```

---

### Task 3: CheckInModal component

**Files:**
- Create: `web/src/CheckInModal.jsx`
- Test: `web/src/CheckInModal.test.jsx`

Mirrors the dialog usage in `web/src/BlockDialog.jsx`, but controlled (no trigger) and presentation-only — no timing logic.

- [ ] **Step 1: Write the failing test**

Create `web/src/CheckInModal.test.jsx`:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import CheckInModal from "./CheckInModal.jsx";

const block = { start: "09:00", end: "10:00", label: "work", tag: "Deep work" };
const content = {
  title: "09:00 — new hour",
  question: "What are you working on this hour?",
  defaultLabel: "work",
};

test("renders the question and prefills the label, then saves the edited value", () => {
  const onSave = vi.fn();
  render(<CheckInModal open onOpenChange={() => {}} content={content} block={block} onSave={onSave} onSkip={() => {}} />);
  expect(screen.getByText(/working on this hour/i)).toBeInTheDocument();
  const input = screen.getByLabelText("hour label");
  expect(input).toHaveValue("work");
  fireEvent.change(input, { target: { value: "Write the report" } });
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
  expect(onSave).toHaveBeenCalledWith("Write the report");
});

test("the skip button calls onSkip", () => {
  const onSkip = vi.fn();
  render(<CheckInModal open onOpenChange={() => {}} content={content} block={block} onSave={() => {}} onSkip={onSkip} />);
  fireEvent.click(screen.getByRole("button", { name: /skip this hour/i }));
  expect(onSkip).toHaveBeenCalled();
});

test("renders nothing when there is no active block", () => {
  const { container } = render(<CheckInModal open onOpenChange={() => {}} content={null} block={null} onSave={() => {}} onSkip={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/CheckInModal.test.jsx`
Expected: FAIL — `Failed to resolve import "./CheckInModal.jsx"`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/CheckInModal.jsx`:

```jsx
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { PAL } from "./lib/palette.js";

// Controlled, presentation-only. Timing lives in DayView; this just shows the
// question and reports the user's choice via onSave(label) / onSkip().
export default function CheckInModal({ open, onOpenChange, content, block, onSave, onSkip }) {
  const [label, setLabel] = useState("");

  // Re-seed the input each time the modal opens for a (new) block.
  useEffect(() => {
    if (open && content) setLabel(content.defaultLabel ?? "");
  }, [open, content]);

  if (!block || !content) return null;

  const save = (e) => {
    e.preventDefault();
    onSave(label.trim() || content.defaultLabel);
    onOpenChange(false);
  };
  const skip = () => {
    onSkip();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{content.title}</DialogTitle>
          <DialogDescription>
            {block.start}–{block.end}{block.tag ? ` · ${block.tag}` : ""}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <p className="text-sm" style={{ color: PAL.muted }}>{content.question}</p>
          <Input aria-label="hour label" autoFocus value={label}
            onChange={(e) => setLabel(e.target.value)} />
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" onClick={skip}>Skip this hour</Button>
            <Button type="submit">Save</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/CheckInModal.test.jsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/CheckInModal.jsx web/src/CheckInModal.test.jsx
git commit -m "feat(web): CheckInModal for the hourly prompt"
```

---

### Task 4: CheckInToggle sidebar control

**Files:**
- Create: `web/src/CheckInToggle.jsx`
- Test: `web/src/CheckInToggle.test.jsx`

A card-styled button (matching the other sidebar cards) that turns the feature on/off. Requesting notification permission happens in `DayView` on enable; this component only renders state and calls `onToggle`.

- [ ] **Step 1: Write the failing test**

Create `web/src/CheckInToggle.test.jsx`:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import CheckInToggle from "./CheckInToggle.jsx";

test("clicking the off-state control calls onToggle", () => {
  const onToggle = vi.fn();
  render(<CheckInToggle enabled={false} onToggle={onToggle} />);
  fireEvent.click(screen.getByRole("button", { name: /enable hourly check-ins/i }));
  expect(onToggle).toHaveBeenCalled();
});

test("when enabled the control exposes the disable action", () => {
  render(<CheckInToggle enabled={true} onToggle={() => {}} />);
  expect(screen.getByRole("button", { name: /disable hourly check-ins/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/CheckInToggle.test.jsx`
Expected: FAIL — `Failed to resolve import "./CheckInToggle.jsx"`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/CheckInToggle.jsx`:

```jsx
import { Bell, BellOff } from "lucide-react";
import { PAL } from "./lib/palette.js";

export default function CheckInToggle({ enabled, onToggle }) {
  return (
    <button
      onClick={onToggle}
      aria-label={enabled ? "disable hourly check-ins" : "enable hourly check-ins"}
      className="flex items-center justify-between rounded-2xl border bg-white p-4 text-left"
      style={{ borderColor: PAL.hairline }}
    >
      <div>
        <div className="font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
          Hourly check-ins
        </div>
        <div className="mt-1 text-sm" style={{ color: PAL.ink2 }}>
          {enabled ? "On — asked at the top of each hour" : "Off"}
        </div>
      </div>
      {enabled
        ? <Bell className="h-4 w-4 flex-shrink-0" style={{ color: PAL.accent }} />
        : <BellOff className="h-4 w-4 flex-shrink-0" style={{ color: PAL.muted }} />}
    </button>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/CheckInToggle.test.jsx`
Expected: PASS (2 tests).

Note: if `Bell`/`BellOff` are not exported by the installed lucide-react build, the import will throw at render. If that happens, substitute `BellRing` → `Bell` or use `Clock` (confirmed present elsewhere is `Check`); rerun the test. This is the only uncertain dependency in the plan.

- [ ] **Step 5: Commit**

```bash
git add web/src/CheckInToggle.jsx web/src/CheckInToggle.test.jsx
git commit -m "feat(web): CheckInToggle sidebar control"
```

---

### Task 5: Render the toggle in the sidebar

**Files:**
- Modify: `web/src/DaySidebar.jsx`

Add two props (`checkInOn`, `onToggleCheckIn`) and render `CheckInToggle` just below the Now card. This task has no new unit test (it is pure prop-threaded rendering, covered by Task 4's component test and the manual verification in Task 7); the existing `DayView` tests must still pass.

- [ ] **Step 1: Add the import**

In `web/src/DaySidebar.jsx`, after the existing `import NotesCard from "./NotesCard.jsx";` line, add:

```jsx
import CheckInToggle from "./CheckInToggle.jsx";
```

- [ ] **Step 2: Add the two props to the component signature**

Change the destructured props of `DaySidebar` from:

```jsx
export default function DaySidebar({
  blocks, active, nowMin, onComplete,
  reminders = [], notes = [],
  onDismissReminder, onAddNote, onToggleNoteFlag, onDeleteNote,
}) {
```

to:

```jsx
export default function DaySidebar({
  blocks, active, nowMin, onComplete,
  reminders = [], notes = [],
  onDismissReminder, onAddNote, onToggleNoteFlag, onDeleteNote,
  checkInOn = false, onToggleCheckIn = () => {},
}) {
```

- [ ] **Step 3: Render the toggle below the Now card**

In `web/src/DaySidebar.jsx`, find the closing `</div>` of the "Now" card (the `<div className="rounded-2xl border bg-white p-4" ...>` block that contains the `Now` label and the `active` countdown) and insert the toggle immediately after it, before `<NotesCard ... />`:

```jsx
      <CheckInToggle enabled={checkInOn} onToggle={onToggleCheckIn} />
      <NotesCard notes={notes} onAdd={onAddNote} onToggleFlag={onToggleNoteFlag} onDelete={onDeleteNote} />
```

(The `<NotesCard ... />` line already exists — the only change is adding the `<CheckInToggle ... />` line directly above it.)

- [ ] **Step 4: Run the existing suite to verify nothing broke**

Run: `npm test`
Expected: PASS — all existing tests green, including `DayView.test.jsx` (check-ins default off, so the toggle renders in its "Off" state and changes nothing).

- [ ] **Step 5: Commit**

```bash
git add web/src/DaySidebar.jsx
git commit -m "feat(web): show hourly check-in toggle in the sidebar"
```

---

### Task 6: Wire the check-in into DayView

**Files:**
- Modify: `web/src/DayView.jsx`

DayView already owns the 1-second `clock`, `nowMin`, the `active` block, `isToday`, and `onMark`. Add: persisted enable state, a `lastStart` ref, the firing effect, the save/skip handlers, the toggle handler, and the modal render. No new unit test here — the firing path requires fake timers + fetch mocking that would be brittle; the pure logic is already covered by Tasks 1–4, and Task 7 verifies the wired behavior in the real app. The existing `DayView` tests must still pass.

- [ ] **Step 1: Update the React import and add the new imports**

In `web/src/DayView.jsx`, change the first import line from:

```jsx
import { useEffect, useState } from "react";
```

to:

```jsx
import { useEffect, useRef, useState } from "react";
```

Then, after the existing `import BlockDialog from "./BlockDialog.jsx";` line, add:

```jsx
import CheckInModal from "./CheckInModal.jsx";
import { shouldCheckIn, composeCheckIn } from "./lib/checkin.js";
import { notify, requestPermission } from "./lib/notify.js";
```

- [ ] **Step 2: Add state, the ref, and handlers**

In `web/src/DayView.jsx`, locate the existing line:

```jsx
  const [reminders, setReminders] = useState([]);
```

Immediately after it, add:

```jsx
  const [checkInOn, setCheckInOn] = useState(() => localStorage.getItem("checkInOn") === "1");
  const [checkIn, setCheckIn] = useState(null); // { block, content } when the modal is open
  const lastStart = useRef(null);

  const toggleCheckIn = async () => {
    const next = !checkInOn;
    if (next) await requestPermission();
    localStorage.setItem("checkInOn", next ? "1" : "0");
    setCheckInOn(next);
  };
  const onCheckInSave = (label) =>
    checkIn && onMark(checkIn.block.start, { label });
  const onCheckInSkip = () =>
    checkIn && onMark(checkIn.block.start, { state: "skipped" });
```

- [ ] **Step 3: Add the firing effect**

In `web/src/DayView.jsx`, find these existing lines near the end of the component body (just before the `return (`):

```jsx
  const activeKey = isToday ? activeStart(blocks, nowMin) : null;
  const active = blocks.find((b) => b.start === activeKey) ?? null;
```

Immediately after them, add:

```jsx
  // At the top of each hour, prompt for the now-active block — but only when
  // enabled, viewing today, and no prompt is already open. shouldCheckIn dedupes
  // by block start so the 1-second clock fires this at most once per hour.
  useEffect(() => {
    if (!checkInOn || !isToday || checkIn) return;
    if (shouldCheckIn(nowMin, active, lastStart.current)) {
      lastStart.current = active.start;
      const content = composeCheckIn(active);
      notify(content.title, content.question);
      setCheckIn({ block: active, content });
    }
  }, [nowMin, active, checkInOn, isToday, checkIn]);
```

- [ ] **Step 4: Pass the toggle props to DaySidebar and render the modal**

In `web/src/DayView.jsx`, change the existing `<DaySidebar ... />` usage from:

```jsx
        <DaySidebar blocks={blocks} active={active} nowMin={nowMin}
          onComplete={(start) => onMark(start, { state: "done" })}
          reminders={reminders} notes={notes}
          onDismissReminder={onDismissReminder} onAddNote={onAddNote}
          onToggleNoteFlag={onToggleNoteFlag} onDeleteNote={onDeleteNote} />
```

to (add the two `checkIn` props):

```jsx
        <DaySidebar blocks={blocks} active={active} nowMin={nowMin}
          onComplete={(start) => onMark(start, { state: "done" })}
          reminders={reminders} notes={notes}
          onDismissReminder={onDismissReminder} onAddNote={onAddNote}
          onToggleNoteFlag={onToggleNoteFlag} onDeleteNote={onDeleteNote}
          checkInOn={checkInOn} onToggleCheckIn={toggleCheckIn} />
```

Then, find the final two closing lines of the component's JSX:

```jsx
      </div>
    </div>
  );
}
```

and insert the modal so it reads:

```jsx
      </div>
      {checkIn && (
        <CheckInModal open onOpenChange={(o) => !o && setCheckIn(null)}
          content={checkIn.content} block={checkIn.block}
          onSave={onCheckInSave} onSkip={onCheckInSkip} />
      )}
    </div>
  );
}
```

(The `{checkIn && (...)}` block goes immediately before the component's final `</div>` — i.e. inside the outermost wrapper `<div className="overflow-hidden rounded-2xl border ...">`.)

- [ ] **Step 5: Run the full suite**

Run: `npm test`
Expected: PASS — all tests green. The existing `DayView` tests render with check-ins off (`localStorage` empty) and `nowMin` not at a top-of-hour, so the effect is a no-op for them.

- [ ] **Step 6: Commit**

```bash
git add web/src/DayView.jsx
git commit -m "feat(web): wire hourly check-in prompt into the day view"
```

---

### Task 7: Manual verification in the running app

**Files:** none (verification only)

- [ ] **Step 1: Start the backend (if not already running)**

From `D:\habit-tracker`:
Run: `./.venv/Scripts/uvicorn.exe api:app --host 127.0.0.1 --port 8000`
Expected: "Application startup complete." / "Uvicorn running on http://127.0.0.1:8000".

- [ ] **Step 2: Start the frontend (if not already running)**

From `D:\habit-tracker\web`:
Run: `npm run dev`
Expected: "VITE ready" with Local: http://localhost:5173/.

- [ ] **Step 3: Enable check-ins**

Open `http://localhost:5173/`. In the sidebar, click the **Hourly check-ins** card. Accept the browser's notification-permission prompt. The card should switch to "On — asked at the top of each hour" with a filled bell icon.

- [ ] **Step 4: Verify the prompt fires and edits the label**

To avoid waiting for a real top-of-hour, temporarily widen the firing window for the test: in `web/src/lib/checkin.js`, change `return nowMin % 60 < 1;` to `return nowMin % 60 < 60;` and save (Vite hot-reloads). Reload the page — within a second the modal should appear for the active block. Confirm:
  - The modal shows the active block's time range and tag and the question "What are you working on this hour?".
  - The input is prefilled with the block's current label.
  - Type a new label and click **Save** → the modal closes and the block's label (timeline + Now card) updates to the new text.
  - Re-trigger (reload), click **Skip this hour** → the block is marked skipped (skip styling in the timeline).

- [ ] **Step 5: Revert the test tweak**

Undo the Step 4 change in `web/src/lib/checkin.js` so it reads `return nowMin % 60 < 1;` again. Run `npm test` to confirm the suite is still green, and confirm `git status` shows no unintended changes.

---

## Notes for the implementer

- **No backend changes.** Saving a label calls `markBlock(date, start, { label })`; skipping calls `markBlock(date, start, { state: "skipped" })`. Both already exist (`web/src/api.js`) and persist per-day, leaving the reusable template untouched.
- **The AI seam** is `composeCheckIn` in `web/src/lib/checkin.js`. Swapping in a real assistant later means making that function (or an injected variant) async and returning the same `{ title, question, defaultLabel }` shape — no other file needs to change.
- **Permission denied is fine:** the in-app modal still fires; only the desktop notification is suppressed (`notify` no-ops when permission isn't granted).
