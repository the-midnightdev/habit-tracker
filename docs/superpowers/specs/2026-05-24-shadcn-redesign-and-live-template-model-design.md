# shadcn/ui Redesign + "Days Follow the Template" Model — Design

**Date:** 2026-05-24
**Status:** Approved (design); pending implementation plan
**Supersedes parts of:** `2026-05-24-hourly-time-blocking-planner-design.md` (the
snapshot-on-write day model and the plain-CSS React UI).

## Summary

Two coupled changes to the hourly time-blocking planner:

1. **Behavior/model fix:** replace the snapshot-on-write day model with a **live
   template + per-day overrides** model, so editing the template is reflected on every
   day (including today). This fixes the reported bug where today showed a stale, frozen
   block instead of the current template.
2. **Front-end redesign:** rebuild the `web/` SPA's look with **shadcn/ui** (Tailwind +
   Radix), using a **Dashboard** Day view in a **light, emerald** theme.

The FastAPI backend and Python CLI keep their roles; the backend's day logic and storage
schema change. The CLI's observable behavior is unchanged.

## Root cause being fixed

`~/.plan/data.json` showed `days["2026-05-24"]` frozen as a single block
(`11:55–13:00 "work"`) that no longer exists in the template. The snapshot-on-write model
freezes a day on first touch, so subsequent template edits never reach it. Toggling dates
then shows different blocks on touched vs untouched days — the "data added and toggled
date" issue.

## Decisions captured during brainstorming

- **Day model:** Days always render the **current template**; per-day done/skip/label
  marks are layered on, keyed by block start time. (Chosen over "today live / past
  frozen" and "snapshot + show new blocks".)
- **Day view layout:** **Dashboard** — a summary header (date + progress bar "N / M
  done") over a compact row list.
- **Theme:** **Light**, **emerald** accent, fixed (not OS-following). Status colors:
  emerald = done, red = skipped, muted = pending.
- **UI toolkit:** **shadcn/ui** (Tailwind CSS + Radix primitives; components generated
  into the repo).
- **Errors:** surfaced as toasts (shadcn `Sonner`) rather than inline text.

## Behavior model (backend)

### Storage — schema version 3

The template is the source of truth for which blocks exist and their times/default
labels. Each day stores **only overrides**, keyed by block start time:

```json
{
  "version": 3,
  "template": [
    {"start": "13:00", "end": "14:00", "label": "break"}
  ],
  "days": {
    "2026-05-24": {
      "overrides": {
        "13:00": {"state": "done"},
        "14:00": {"state": "skipped", "label": "P3 escalation"}
      }
    }
  }
}
```

- An override stores `state` (`pending`/`done`/`skipped`) and an optional `label`.
- A day with no overrides for a block inherits the template's `label` and a `pending`
  state.

### Rendering a day

`get_day_blocks(data, date_iso)` builds the block list **from the current template**, and
for each block applies that day's override (if any): `state` from the override else
`pending`; `label` from the override else the template default. Overrides whose start no
longer exists in the template are **inert** (ignored) — they don't render and don't error.

### Mutations

- `set_block_state(data, date_iso, start, state)` / `set_block_label(...)`: validate the
  block's `start` exists **in the current template**; otherwise raise `ValidationError`.
  Store the value as an override under `days[date_iso].overrides[start]`. No
  materialization/freezing of the whole template.
- Setting a block back to `state="pending"` with no label override may drop the override
  entry (keeps storage tidy); a remaining label override is preserved.
- `history_dates` returns days that have at least one override.

### Migration v2 → v3

On load, a v2 file (`days[date].blocks` = full snapshots) converts to v3: for each day,
each snapshot block becomes an override keyed by its start, **kept only if** `state !=
"pending"` or it carried a non-template label. Pending-default blocks are dropped. Blocks
whose start isn't in the current template become inert overrides (harmless). Versions
other than 2 or 3 are still rejected as corrupt (backed up, empty start), as today.

### Consequences (accepted)

- Adding a template block shows it on every day immediately (the fix).
- Editing a block's time/label is reflected on all days (a day keeps its own label only
  where explicitly overridden).
- Removing a template block removes it everywhere; that block's marks become inert
  (its history is effectively dropped). Accepted trade-off for a personal planner.

## Front-end (shadcn/ui)

### Setup

Add Tailwind CSS + PostCSS to the Vite app; initialize shadcn/ui (generates
`web/src/components/ui/*` and theme tokens). New config: `web/tailwind.config.js`,
`web/postcss.config.js`, `web/src/index.css` (Tailwind layers + light/emerald theme
tokens). Path alias `@/` → `web/src`.

shadcn components used: `tabs, card, button, badge, progress, dialog, input, label,
popover, calendar, sonner`.

### App shell

shadcn `Tabs` for **Day** / **Template**; app title; a `Sonner` `<Toaster>` mounted once.

### Day view (Dashboard)

A `Card` with:
- Header: formatted date; **prev/next** `Button`s; a **date picker** (`Popover` +
  `Calendar`); a **Today** button. Dates computed in **local time** (no UTC slip).
- A `Progress` bar with a "**N / M done**" count (done counts completed blocks; M = total
  blocks that day).
- A compact list of **block rows**. Each row: time range, label, status, and marking
  controls.
- Empty state when the template has no blocks ("Add blocks in the Template tab").

### Marking & label interactions (block row)

- A two-button **Done / Skip** control (shadcn `Button`; active state shown via
  emerald/red `variant`/styling). Clicking the currently-active state returns the block to
  **pending**.
- The **label is click-to-edit** inline (`Input`); commit on blur/Enter, and a single
  keypress submits exactly once (Enter blurs the input). Local label state re-syncs when
  the block prop changes.
- API/validation errors → toast.

### Template view

A `Card` listing template blocks (`time range · label`) each with **Edit** and **Remove**
`Button`s. **Add** and **Edit** open a shadcn `Dialog` containing two time `Input`s and a
text `Input`, with Save/Cancel. Validation errors (overlap, duplicate start, bad format)
show as a toast. `<input type="time">` yields `HH:MM`, matching the backend.

### API client

`web/src/api.js` is essentially unchanged: the day shape stays `{date, blocks:[{start,
end, label, state}]}` and `markBlock(date, start, {state?, label?})` is unchanged — only
the backend's interpretation of storage changes.

## Components & files

- Backend: `core.py` (rendering/mutation/migration for v3), `api.py` (mark existence
  check against template; otherwise same endpoints), `cli.py` unchanged in behavior.
- Frontend: `web/tailwind.config.js`, `web/postcss.config.js`, `web/src/index.css`,
  `web/src/lib/utils.js`, `web/src/components/ui/*` (generated), and rebuilt
  `App.jsx`, `DayView.jsx`, `TemplateEditor.jsx`, `BlockRow.jsx`.

## Testing

- **Core:** day renders from the live template; adding/editing/removing template blocks
  reflects on a day; overrides persist by start and survive template edits; inert
  overrides ignored; `set_block_state`/`label` reject unknown (non-template) starts;
  v2→v3 migration; corrupt/unknown-version recovery preserved.
- **API:** endpoints behave with the new model (mark on a template block 200; mark on a
  non-template start 404; combined state+label; history).
- **CLI:** `today`/`done`/`skip`/`template` still pass (behavior unchanged).
- **Frontend:** Vitest happy-path tests for rebuilt components (render, Done/Skip toggle
  incl. toggle-to-pending, label submit-once / no-op-when-unchanged, template add/edit/
  remove call the client). Production build compiles.
- **Manual:** smoke test the running app (add a block → appears today; mark → progress
  updates; toggle dates; CLI shares data).

## Out of scope (YAGNI)

- Authentication / multi-user.
- Week or month calendar views; drag-to-reschedule.
- Notifications / reminders.
- OS theme-following (fixed light for now).
- Preserving history of blocks removed from the template.
