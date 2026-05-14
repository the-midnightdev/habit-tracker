# Habit Tracker CLI — Design

**Date:** 2026-05-14
**Status:** Approved

## Overview

A single-user command-line habit tracker. Tracks daily habits, computes
streaks, and renders a rich terminal UI. No accounts, no sync, no network.

## Stack

- **Language:** Python 3.13
- **Dependencies:** `rich` (TUI rendering), `pytest` (tests). No other runtime
  deps.
- **Project root:** `D:\habit-tracker\`
- **Entrypoint:** `habit.py`
- **Data file:** `~/.habit-tracker/data.json` (per-user, OS-default home).

## Commands

| Command | Behavior |
|---|---|
| `habit add <name>` | Create a habit. Name must be unique (case-insensitive). |
| `habit done <name>` | Mark today complete. Idempotent: a second call same day prints "already marked" and exits 0. |
| `habit undo <name>` | Remove today's completion. No-op if today wasn't marked. |
| `habit list` | Rich table: habit name, today status (✓/·), current streak, longest streak, 30-day completion %. |
| `habit show <name>` | Detail view for one habit: 12-week heatmap (GitHub-style cells, ending with the current week and going back 12 weeks), current streak, longest streak, total completions, created date. |
| `habit rm <name>` | Remove a habit. Prompts `Remove 'X' and all its history? [y/N]` unless `--yes` is passed. |
| `habit` (no args) | Equivalent to `habit list`. |

Names are matched case-insensitively but stored as the user typed them.

## Data Model

`~/.habit-tracker/data.json`:

```json
{
  "version": 1,
  "habits": [
    {
      "name": "water",
      "created": "2026-05-14",
      "completions": ["2026-05-12", "2026-05-13", "2026-05-14"]
    }
  ]
}
```

- `version`: integer, currently `1`. Allows future migrations.
- `completions`: ISO date strings (`YYYY-MM-DD`), sorted ascending, unique.
- Streaks and stats are computed on read, never stored.
- Dates use the local system date (not UTC) — "today" is what the user sees on
  their wall clock.

## Streak Rules

- **Current streak:** count consecutive days backward starting from today. If
  today is not yet marked, start from yesterday instead. This means the streak
  doesn't visibly break the moment a new day starts — it only breaks once a
  full day has been skipped.
- **Longest streak:** longest run of consecutive dates anywhere in
  `completions`.
- **30-day completion %:** count of completions in the last 30 days (inclusive
  of today) divided by 30, rendered as an integer percent.

## Error Handling

| Situation | Behavior |
|---|---|
| Unknown habit name | Print `No habit named 'X'. Run 'habit list' to see habits.` and exit 1. |
| `add` with duplicate name | Print `Habit 'X' already exists.` and exit 1. |
| `done` for already-marked today | Print `'X' already marked for today.` and exit 0. |
| `data.json` missing | Treat as empty habit list. Create on first write. |
| `data.json` corrupt (invalid JSON or schema) | Print error, back up the file as `data.json.corrupt-<timestamp>`, start with empty list. Exit 0 so user can continue. |
| `data.json` directory missing | Create it on first write. |

All user-facing errors go to stderr; success output to stdout.

## Out of Scope (YAGNI)

- Reminders, notifications, scheduling.
- Multi-user, sync, cloud storage.
- Sub-daily frequencies (e.g., "3 times per day").
- Tags, categories, or grouping.
- Import/export, backup commands.
- Editing past completions other than today.
- Configurable data path or color themes.

## Testing

- Framework: `pytest`.
- Each test gets an isolated temp directory injected as the data dir (via
  environment variable or function parameter — implementation choice).
- Coverage targets:
  - Streak math: today marked, today not marked, yesterday gap, single
    completion, empty list, completions far in the past.
  - Add/done/undo/rm round trips through the JSON file.
  - End-to-end command dispatch via `subprocess.run` against `habit.py`.
  - Corrupt-file recovery: write garbage to `data.json`, run a command,
    confirm backup is created and command succeeds.

## File Layout

```
D:\habit-tracker\
├── habit.py                # entrypoint + CLI dispatch
├── habit_core.py           # pure functions: streak math, data load/save
├── tests\
│   ├── test_streaks.py
│   ├── test_storage.py
│   └── test_cli.py
├── docs\superpowers\specs\
│   └── 2026-05-14-habit-tracker-cli-design.md
├── pyproject.toml          # rich + pytest deps
└── README.md
```

`habit.py` handles argument parsing and rich rendering. `habit_core.py` holds
pure logic (streaks, data load/save) so it can be unit-tested without touching
the CLI surface.
