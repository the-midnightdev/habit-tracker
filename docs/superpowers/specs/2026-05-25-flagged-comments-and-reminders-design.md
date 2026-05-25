# Flagged comments & next-day reminders — design

**Date:** 2026-05-25
**Status:** Approved (pending spec review)

## Summary

Add comments to the planner at two levels — **per-block** (attached to a specific
time block on a specific day) and **day-level** (free-form notes for a day). Any
comment can be **flagged**. A flagged comment is **carried over** as an in-app
**reminder** on every following day until it is **dismissed**. Dismissing only
clears the flag; the comment text is retained on its origin day/block.

This follows the codebase's existing "store only deviations, render on read"
philosophy: comments live on the day they belong to, and the reminder list is
*computed* on read rather than copied forward.

## Decisions (locked)

- Comments attach to **both** a specific block and the whole day.
- A flagged comment **shows on the next day(s) until dismissed**.
- "Notification" means an **in-app Reminders card** (no browser/OS push).
- The Reminders card sits at the **top of the sidebar**, above PROGRESS, and
  renders only when there is at least one reminder.
- Entry UX: **per-block popover** (note icon → textarea + flag toggle) and a
  **day-level notes card** in the sidebar.
- Dismiss **keeps the comment text** and only clears the flag.
- Timeline blocks **show indicators**: a small dot when a block has a comment,
  and a ⚑ when that comment is flagged.
- The Reminders card supports **dismiss only**; editing/re-flagging is done on the
  origin day.

## Data model (`core.py`)

Schema version bumps **3 → 4**.

```python
@dataclass
class Override:                 # per-block, per-day deviation (existing)
    state: str = "pending"
    label: str | None = None
    comment: str | None = None  # NEW
    flagged: bool = False       # NEW

@dataclass
class Note:                     # NEW — day-level note
    id: str                     # uuid4 hex; stable handle for edit/dismiss/delete
    text: str
    flagged: bool = False

@dataclass
class Day:
    overrides: dict[str, Override] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)   # NEW
```

`DayBlock` (the rendered block returned to the UI) gains `comment: str | None`
and `flagged: bool` so blocks can render their note/flag indicators.

### Persistence

- `SCHEMA_VERSION = 4`.
- `save` writes `comment` only when not `None`, `flagged` only when `True`, and
  `notes` only when the list is non-empty — keeping files minimal, consistent
  with the current override serialization.
- `load`:
  - **v4:** read overrides (with optional `comment`/`flagged`) and `notes`.
  - **v3 → v4:** overrides get `comment=None, flagged=False`; each day gets
    `notes=[]`. No data is dropped.
  - **v2 → v4:** the existing `_migrate_v2_days` produces override-shaped days;
    those then carry the v4 defaults. (v2 had no comments/notes.)
  - Unknown/newer versions → corrupt-backup path (unchanged).
- Corrupt-file backup behavior is unchanged.

### Pruning

`_prune` currently deletes an override when `state == "pending"` and
`label is None`. New rule: also keep the override if it has a non-empty
`comment` **or** is `flagged`. A `Day` is removed only when it has **no**
overrides **and no** notes.

A day-level note is removed explicitly via `remove_note`; empty-text notes are
not auto-created.

## Reminder logic + dismiss

```python
@dataclass
class Reminder:
    origin_date: str          # ISO date the comment/note was created on
    kind: str                 # "block" | "note"
    ref: str                  # block start ("14:00") or note id
    text: str                 # the comment/note text
    block_label: str | None   # for kind=="block": the block's current label
    block_time: str | None    # for kind=="block": "14:00–15:00" for display

def get_reminders(data, date_iso) -> list[Reminder]:
    """All flagged block-comments and day-notes whose origin date is strictly
    before date_iso and are still flagged. Sorted by (origin_date, then block
    start / note order). Reading never mutates data."""
```

Behavior:
- On the **origin day**, a flagged comment shows inline (on its block / in the
  notes card) but is **not** in the Reminders card — the card is strictly
  carryover from earlier days (`origin_date < viewed_date`).
- From the next day onward it appears in the Reminders card until dismissed.
- For a `block` reminder, `block_label`/`block_time` are resolved against the
  **current** template (the live-template model). If the block's start no longer
  exists in the template, those fields are `None` but the reminder still shows
  its `text` (orphaned-but-visible).

### Mutations (core functions)

- `set_block_comment(data, date, start, comment)` — set/replace; clearing to
  empty sets `comment=None` and re-runs prune. Requires the block start to exist
  in the template (raises `ValidationError` otherwise, matching existing
  `_require_template_start`).
- `set_block_flag(data, date, start, flagged)` — sets the flag. Flagging requires
  a non-empty comment (raises `ValidationError` if there is no comment text).
- `add_note(data, date, text, flagged=False) -> Note` — generates a uuid4 hex id;
  flagging requires non-empty text.
- `edit_note(data, date, note_id, *, text=None, flagged=None) -> Note` — updates
  provided fields; raises if the note id is unknown.
- `remove_note(data, date, note_id) -> bool`.
- `dismiss_reminder(data, origin_date, kind, ref)` — clears `flagged` on the
  referenced block override or note. Idempotent: a no-op if the target is missing
  or already unflagged.

## API (`api.py`)

- `GET /api/days/{date}` → `{date, blocks, notes, reminders}`
  - `blocks`: each `DayBlock` now includes `comment` and `flagged`.
  - `notes`: the day's notes (`id`, `text`, `flagged`).
  - `reminders`: computed carryovers for this date.
- `POST /api/days/{date}/blocks/{start}` — `MarkIn` extended with optional
  `comment: str | None` and `flagged: bool | None`. Existing `state`/`label`
  behavior preserved. Returns the refreshed day payload.
- `POST /api/days/{date}/notes` `{text, flagged}` → create. `201`.
- `PUT /api/days/{date}/notes/{note_id}` `{text?, flagged?}` → edit. `404` if
  unknown id.
- `DELETE /api/days/{date}/notes/{note_id}` → delete. `204`; `404` if unknown.
- `POST /api/reminders/dismiss` `{origin_date, kind, ref}` → clear the flag.
  Returns `204`; idempotent.

All day mutations return `{date, blocks, notes, reminders}` so the client can
re-render in one round trip. `ValidationError` → HTTP 400; missing block/note →
HTTP 404, consistent with the existing endpoints.

## Web UI

- **`RemindersCard.jsx`** (new) — rendered at the top of the sidebar, only when
  `reminders.length > 0`. Each row shows the text, origin ("from Mon, May 25"),
  block context (time + label) when `kind === "block"`, and a dismiss (✓) button
  that calls `POST /api/reminders/dismiss` then reloads the day.
- **`NotesCard.jsx`** (new) — day-level notes in the sidebar: a list where each
  note has a flag toggle and a delete button, plus an input row to add a note
  with a "flag for tomorrow" toggle.
- **`TimelineBlock.jsx`** — add a 💬 note action beside ✓/✗ that opens a popover
  containing a textarea and a "flag for tomorrow" checkbox (saves on close / via a
  Save action). Blocks with a comment show a small dot; flagged blocks show a ⚑.
  Existing done/skip/label behavior unchanged.
- **`DaySidebar.jsx`** — compose RemindersCard (top) + existing PROGRESS + NOW +
  NotesCard.
- **`api.js`** — add `setBlockComment`/`flag` (folded into the existing mark
  call), `addNote`, `editNote`, `deleteNote`, `dismissReminder`.
- **`DayView.jsx`** — `getDay` now yields `notes` and `reminders`; hold both in
  state and thread handlers down.

### New dependency

`@radix-ui/react-popover` — for the per-block comment popover, consistent with
the Radix primitives already in use (dialog, tabs, progress, etc.).

## Edge cases & error handling

- **Flagging without text:** rejected (`ValidationError`) — a flag must have a
  comment/note body.
- **Orphaned block comment:** if a template block's start is later changed or
  removed, its per-day comment override becomes inert for inline rendering (the
  block no longer renders), but `get_reminders` scans overrides directly so the
  reminder still surfaces with `text` and `block_label/time = None`.
- **Dismiss idempotency:** dismissing a missing/already-unflagged target is a
  no-op (no error), so stale clients can't 500.
- **Empty notes:** an empty-text note is never created; editing a note's text to
  empty is rejected (use delete instead).
- **Note ids:** `uuid4().hex` (stdlib `uuid`, no new backend dependency).

## Testing

- **core (`tests/`):**
  - comment set then clear → override pruned only when no flag and pending/no-label.
  - flag persists across save/load round trip.
  - `get_reminders` returns only `origin_date < viewed_date` items, sorted;
    excludes dismissed; orphaned block comment still surfaces.
  - note CRUD (add/edit/delete) and id stability.
  - flagging without text raises.
  - v3 → v4 migration preserves data and adds defaults.
- **api:**
  - `GET /api/days/{date}` includes `notes` and `reminders`.
  - extend mark endpoint with comment+flag; flag a block comment then see it as a
    reminder on the next date; dismiss clears it.
  - note create (201) / edit / delete (204) / unknown id (404).
- **web (`web/src`):**
  - RemindersCard renders rows and dismiss calls the API + reloads.
  - NotesCard add/flag/delete.
  - TimelineBlock popover edits comment + toggles flag; dot/⚑ indicators render.
  - DayView wires `notes`/`reminders` into the sidebar.

## Out of scope (YAGNI)

- Browser/OS push notifications.
- Editing or re-flagging from the Reminders card.
- Reminders attached to the template itself (recurring reminders).
- Multi-user / shared reminders.
