# Hourly Time-Blocking Planner — Design

**Date:** 2026-05-24
**Status:** Approved (design); pending spec review

## Summary

The app pivots from a recurring daily-habit tracker into an **hourly time-blocking
planner**. The user defines a reusable **template** of time blocks (custom start/end
times, default label). Each day pre-fills from the template, and the user marks each
block **Pending / Done / Skipped**, optionally overriding that day's label. History is
kept per day.

The primary interface is a **local web app**: a **React/Vite SPA** talking to a
**FastAPI** JSON backend. A **minimal CLI** is kept alongside, sharing the same core
logic.

## Decisions captured during brainstorming

- **Concept:** replace the recurring-habit model entirely with hourly time-blocking.
- **Time spans:** each block has a custom **start and end** time.
- **Day model:** a reusable **template** auto-populates each day; user marks per day.
- **Template scope:** template defines **time slots + default labels**; per day the
  label can be overridden.
- **Block states:** three — **Pending**, **Done**, **Skipped** (explicit "missed").
- **Block reference:** by **start time**, with **row number** as a display-only backup.
- **Interface:** **local web UI**, built as a **React/Vite SPA + API**.
- **Backend:** **FastAPI** (natural fit for a JSON API feeding a React SPA; reuses the
  Python core).
- **CLI:** keep a **minimal CLI** alongside the web app, sharing the core logic.

### Defaulted items (override on review if desired)

1. **CLI command name:** rename `habit` → `plan`.
2. **Existing v1 data:** clean break — v1 files are rejected as unsupported (no
   migration). This is a fresh feature branch with no real user data.
3. **React testing depth:** minimal happy-path component render tests.

## Architecture

Three interfaces over one shared core:

- **Core logic** (`core.py`, Python, no web/CLI imports): the template, day
  materialization, state transitions, validation, and storage (`DataStore`). Fully
  testable in isolation.
- **FastAPI backend** (`api.py`): thin JSON API over the core.
- **React/Vite SPA** (`web/`): the clickable day grid and template editor; talks to the
  API on `localhost`.
- **Minimal CLI** (`cli.py`): a few text commands over the same core.

The core never imports FastAPI or React, keeping all three interfaces independent and
testable.

## Data model (Approach A — snapshot-on-write days)

JSON file at the existing data location, bumped to **schema version 2**. The current
corrupt-file → timestamped-backup → empty-start recovery is preserved.

```json
{
  "version": 2,
  "template": [
    {"start": "08:00", "end": "09:00", "label": "standup"}
  ],
  "days": {
    "2026-05-24": {
      "blocks": [
        {"start": "08:00", "end": "09:00", "label": "fixed login bug", "state": "done"}
      ]
    }
  }
}
```

- **Template** = ordered list of blocks (`start`, `end`, `label`). Times are `HH:MM`
  (24-hour). **Start times are unique** (enforced) so reference-by-start-time is
  unambiguous. Blocks may not overlap.
- A **day** under `days` is materialized as a frozen **copy** of the template the first
  time it is marked/overridden. Untouched days render live from the current template.
  Editing the template never rewrites an already-touched day → history stays honest.
- **State** per block: `pending` | `done` | `skipped`. A day-level `label` overrides the
  template default for that day only.

### Core operations

- Template: add / edit / remove block; list (sorted by start). Validation: `HH:MM`
  format, start < end, unique start, no overlap.
- Day: get materialized day for a date (live template if untouched, stored copy if
  touched); set block state; override block label. Setting state/label on an untouched
  day materializes it first.
- History: list dates that have stored days.

## Backend API (FastAPI)

```
GET    /api/template                      → list template blocks
POST   /api/template                      → add block {start, end, label}
PUT    /api/template/{start}              → edit a block
DELETE /api/template/{start}              → remove a block
GET    /api/days/{date}                   → materialized day (blocks + state + label)
POST   /api/days/{date}/blocks/{start}    → set {state} and/or {label}; materializes day
GET    /api/days                          → list of dates with history
```

Core validation errors (format / overlap / duplicate start / unknown block) surface as
**HTTP 400** with a message. Unknown date/block → **404** where appropriate.

## Frontend (React + Vite SPA)

- **Day view (home):** vertical timeline of the day's blocks, earliest → latest,
  color-coded by state (grey = pending, green = done, red = skipped). Each block shows
  its time range + label with **Done / Skip** toggles and inline label override for that
  day. A date picker / prev-next control navigates history.
- **Template editor:** add / edit / remove recurring blocks (start, end, label).
- No auth. Minimal client-side state; calls the API directly.

## Minimal CLI (`plan`)

Repurposed from the current CLI, sharing the core:

- `plan today` — text grid of today's blocks with state.
- `plan done <start>` — mark a block done today (start time; row number as backup).
- `plan skip <start>` — mark a block skipped today.
- `plan template` — list the template.

## Project structure

```
habit-tracker/
  core.py         # repurposed habit_core.py: template, day blocks, DataStore (v2), validation
  cli.py          # repurposed habit.py: minimal `plan` CLI
  api.py          # FastAPI app (run with uvicorn)
  web/            # React + Vite SPA (own package.json)
  tests/          # rewritten for the new model
  pyproject.toml  # add fastapi + uvicorn; keep rich for the CLI
```

Module renames are justified because the underlying model changes fundamentally; tests
are rewritten regardless.

## Error handling

- Preserve corrupt-file recovery: on unparseable/invalid JSON, back up to a timestamped
  `data.json.corrupt-*` and start empty (now for schema v2).
- **v1 files are rejected as unsupported** (treated as corrupt → backed up). No migration.

## Testing

- **Core:** materialization, state transitions, "template edit does not touch existing
  history", unique-start / overlap / format validation, corrupt-file recovery.
- **CLI:** each `plan` command, by start time and row-number backup.
- **API:** endpoint behavior via FastAPI `TestClient`, including 400/404 paths.
- **React:** minimal happy-path component render tests.

## Out of scope (YAGNI)

- Authentication / multi-user.
- Notifications / reminders.
- v1 → v2 data migration.
- Recurring exceptions (e.g. "skip this block on weekends").
