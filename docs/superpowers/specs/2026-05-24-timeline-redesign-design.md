# Timeline Redesign — Design

**Date:** 2026-05-24
**Status:** Approved (design); pending implementation plan
**Builds on:** `2026-05-24-shadcn-redesign-and-live-template-model-design.md` (shadcn + live-template model).
**Visual reference:** `docs/design-reference/planner.jsx` (variant `VariantTimeline`) and `Time-Blocking Planner.html`.

## Summary

Restyle the SPA to the reference design's warm aesthetic and rebuild the **Day** view as
its **Timeline** variant: a vertical hour axis with blocks placed by real time, a live
NOW line, an active-block highlight, and a right sidebar (progress donut + a "Now" card
with a countdown). Keep the **Day / Template** tabs (the design's "Week" tab is out of
scope). Add an optional **tag** (type) to blocks. All "live" behavior is derived from the
current clock — no new tracked data.

## Decisions captured

- **Variant:** `01 · Timeline`.
- **Block tags:** add a real optional `tag` field (`Deep work | Break | Shallow | null`),
  editable in the Template dialog, shown as icon + pill.
- **Live features:** clock-derived only — NOW line, active-block highlight, countdown,
  progress donut, "Remaining" time, and "Focused" = Σ done-block durations. **Dropped:**
  streak, pause/resume, real focus tracking, Week view, dark mode.
- **Skipped** remains a state, rendered muted.
- **Hour axis** is derived from the day's blocks (not hard-coded 09–19).

## Palette & type (from the reference `PAL`)

- bg `#FAF8F4`, surface `#FFFFFF`, ink `#1B1A17`, ink2 `#3A3631`, muted `#6B655B`,
  hairline `#ECE7DC`, hairline2 `#E2DBCC`.
- accent/now `#E07A3B`, accentSoft `#FBE9D7`, accentDeep `#B65C24`.
- done `#4C8A6E`, doneSoft `#DDEBE2`; skip `#B0A89C`, skipSoft `#EFEBE3`.
- Fonts: **Geist** (sans), **Geist Mono** (times, labels, numerics), via Google Fonts.

These map onto the shadcn theme tokens in `index.css`: `--primary` = orange accent,
`--background` = cream, `--foreground` = ink, `--muted`/`--border` per above, plus a
`--font-mono`. Re-theming the tokens restyles the Template view and all shadcn primitives
automatically.

## Backend changes (core.py / api.py)

- **`TemplateBlock` gains `tag: str | None = None`.** Additive on schema v3 — files
  written without `tag` load via the dataclass default (no version bump). `save` includes
  `tag` (omit/None ok). Validation: if `tag` is not `None`, it must be one of
  `("Deep work", "Break", "Shallow")` → else `ValidationError`.
- **`DayBlock` gains `tag: str | None`.** `get_day_blocks` copies `tag` from the template
  block. `tag` is a block-type property, **not** a per-day override.
- `add_template_block(data, start, end, label, tag=None)` and
  `edit_template_block(..., tag=None)` accept and validate `tag`.
- API: `BlockIn` and `BlockEdit` gain optional `tag`; `POST`/`PUT /api/template` pass it
  through; `GET /api/days/{date}` blocks include `tag`. `mark_block` unchanged.
- Per-day overrides, live-template rendering, CLI: unchanged (CLI ignores `tag`).

## Frontend

### Theme setup
- Add Geist + Geist Mono (Google Fonts `<link>` in `web/index.html`).
- Rewrite `web/src/index.css` token values to the palette above; set `font-sans` = Geist,
  add `font-mono` = Geist Mono in `tailwind.config.js`.

### Day view (Timeline) — `DayView.jsx` + a `TimelineBlock` component
- **Header:** "Planner" + mono date; the Day/Template tab control; ◀ / Today / ▶; a
  primary **+ Block** button opening the add dialog (reuses the Template add dialog).
- **Left timeline:** axis range from `axisRange(blocks)` (floor(earliest start hour) →
  ceil(latest end hour)); hour gridlines with mono labels. Each block absolutely
  positioned (`top = (startMin − axisStartMin)/60 · pxPerHr`, `height = dur/60 · pxPerHr`,
  min height for short blocks): type icon, `start–end` (mono), a pill
  (`Now` if active / `Done` if done / tag otherwise), and the title (strikethrough when
  done, muted when skipped). A **NOW line** + dot when the viewed date is today and now is
  within the axis; the active block gets the orange highlight.
- **Right sidebar:** a **donut** (`% done`, with done/active/upcoming legend) and a **Now
  card**: active block title, `countdown(endMin, nowMin)` (mm:ss-style mono), a progress
  bar, and a **Complete** button (marks the active block done). Two stats: **Focused** =
  `focusedMinutes(blocks)`, **Remaining** = `remainingMinutes(blocks, nowMin)`. When no
  active block, the Now card shows a calm placeholder.
- Empty state when the template has no blocks.

### Status model
- Stored states: `pending | done | skipped` (unchanged). **Active** is a derived overlay:
  `activeStart(blocks, nowMin)` = the block whose `[start,end)` contains `now` and whose
  state ≠ `done`; only meaningful when the viewed date is today. Done blocks never show as
  active.

### Marking & label (per block)
- Done / Skip controls (clicking the active state → pending) and click-to-edit label
  (commit on blur; Enter blurs → single submit; local label re-syncs on prop change) —
  existing logic, restyled. On non-active blocks the controls appear on hover/focus but
  stay in the DOM. Errors → sonner toast.

### Template view — `TemplateEditor.jsx`
- Restyled to the warm theme; the add/edit **dialog gains a Tag select** (Deep work /
  Break / Shallow / none). The list row shows the tag icon + name.

### Pure time helpers — `web/src/lib/schedule.js`
All take explicit numbers/strings (no `Date.now()` inside) so they're unit-testable:
- `minOf("HH:MM") → number`
- `axisRange(blocks) → { startHour, endHour }` (empty → null)
- `activeStart(blocks, nowMin) → start | null`
- `focusedMinutes(blocks) → number` (Σ durations where state === "done")
- `remainingMinutes(blocks, nowMin) → number` (Σ durations where state ≠ "done" and end > now)
- `countdown(endMin, nowMin) → "M:SS"`/`"MM:SS"` minutes remaining
Components compute `nowMin` from the real local clock and pass it in.

## Testing

- **Core:** `tag` round-trips through save/load; v3 file without `tag` loads as `None`;
  `add`/`edit` accept `tag`; invalid tag → `ValidationError`; `get_day_blocks` includes
  `tag`.
- **API:** create/edit a block with a tag; `GET /api/days` blocks carry `tag`; invalid
  tag → 400.
- **Frontend:** unit tests for every `schedule.js` helper (active detection, axis range,
  focused/remaining, countdown, including edge cases — no blocks, now before/after all);
  DayView renders blocks + a progress figure + empty state; BlockRow Done/Skip/label;
  TemplateEditor edit calls `editTemplateBlock` with the chosen tag.
- **Manual:** run the app; today shows the timeline with a NOW line; Complete marks the
  active block; add a tagged block → appears with its icon.

## Out of scope (YAGNI)
Week/month views, streaks, pause/resume timers, real focus-time tracking, dark mode,
notifications.
