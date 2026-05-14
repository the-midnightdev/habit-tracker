# Habit Tracker CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-user Python CLI that tracks daily habits, computes streaks, and renders a rich terminal UI, backed by a JSON file.

**Architecture:** Two modules — `habit_core.py` holds pure data and logic (load/save, streaks, mutations) so it can be unit-tested without touching the terminal. `habit.py` is the CLI entrypoint: argparse dispatch, rich rendering, exit codes. Data lives in a JSON file whose path is controlled by the `HABIT_DATA_DIR` environment variable (defaulting to `~/.habit-tracker/`), which makes tests trivially isolatable.

**Tech Stack:** Python 3.13, `rich` (TUI), `pytest` (tests), `argparse` (stdlib).

**Spec:** `docs/superpowers/specs/2026-05-14-habit-tracker-cli-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, runtime + dev deps (`rich`, `pytest`). |
| `.gitignore` | Exclude `__pycache__/`, `.pytest_cache/`, `.venv/`, `*.egg-info/`. |
| `README.md` | Short usage notes. |
| `habit_core.py` | Pure logic: `Habit` dataclass, `DataStore` (load/save/corrupt-recovery), streak math, completion %, habit list operations (add/find/mark/unmark/remove). No `print`, no `argparse`, no `rich`. |
| `habit.py` | CLI: argparse wiring, command handlers, rich rendering. Resolves data dir from `HABIT_DATA_DIR` env var or default. |
| `tests/__init__.py` | Empty marker. |
| `tests/conftest.py` | Shared fixtures: `data_dir` (tmp dir + env var), `run_cli` (subprocess helper). |
| `tests/test_storage.py` | DataStore round-trip, missing file, corrupt file. |
| `tests/test_streaks.py` | `current_streak`, `longest_streak`, `completion_pct_30d`. |
| `tests/test_habits.py` | Add/find/mark/unmark/remove operations. |
| `tests/test_cli.py` | End-to-end subprocess tests for every command. |

`habit_core.py` is the single source of truth for behavior. `habit.py` is a thin shell around it.

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `tests/__init__.py`
- Create: `habit_core.py` (stub)
- Create: `habit.py` (stub)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "habit-tracker"
version = "0.1.0"
description = "Single-user CLI habit tracker"
requires-python = ">=3.13"
dependencies = ["rich>=13.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
habit = "habit:main"

[tool.setuptools]
py-modules = ["habit", "habit_core"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.gitignore`**

```
__pycache__/
.pytest_cache/
.venv/
*.egg-info/
dist/
build/
```

- [ ] **Step 3: Create `README.md`**

```markdown
# habit-tracker

Single-user CLI habit tracker.

## Install (dev)

    python -m venv .venv
    .venv\Scripts\activate    # Windows
    pip install -e ".[dev]"

## Use

    habit add water
    habit done water
    habit list
    habit show water

Data is stored at `~/.habit-tracker/data.json`. Override with the
`HABIT_DATA_DIR` environment variable.
```

- [ ] **Step 4: Create stub `habit_core.py`**

```python
"""Pure logic for the habit tracker: storage, streaks, mutations."""
```

- [ ] **Step 5: Create stub `habit.py`**

```python
"""CLI entrypoint for the habit tracker."""


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Create `tests/__init__.py`** (empty file)

- [ ] **Step 7: Create venv and install**

Run:
```
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```
Expected: installs `rich` and `pytest` without errors.

- [ ] **Step 8: Run pytest to confirm wiring**

Run: `.venv\Scripts\pytest -q`
Expected: `no tests ran` (exit code 5 is fine — the harness works).

- [ ] **Step 9: Commit**

```
git add pyproject.toml .gitignore README.md habit_core.py habit.py tests/__init__.py
git commit -m "chore: bootstrap habit tracker project"
```

---

## Task 2: Storage Layer (`DataStore`)

**Files:**
- Modify: `habit_core.py`
- Create: `tests/conftest.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Create `tests/conftest.py` with shared fixtures**

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolated data directory for one test."""
    d = tmp_path / "habit-data"
    d.mkdir()
    monkeypatch.setenv("HABIT_DATA_DIR", str(d))
    return d


@pytest.fixture
def run_cli(data_dir):
    """Run habit.py as a subprocess with the isolated data dir."""
    repo_root = Path(__file__).resolve().parent.parent

    def _run(*args, stdin: str | None = None):
        env = {**os.environ, "HABIT_DATA_DIR": str(data_dir)}
        return subprocess.run(
            [sys.executable, str(repo_root / "habit.py"), *args],
            capture_output=True,
            text=True,
            input=stdin,
            env=env,
            cwd=str(repo_root),
        )

    return _run
```

- [ ] **Step 2: Write the failing storage tests**

Create `tests/test_storage.py`:

```python
import json
from pathlib import Path

from habit_core import DataStore, Habit


def test_load_returns_empty_when_file_missing(data_dir: Path):
    store = DataStore(data_dir)
    assert store.load() == []


def test_save_then_load_round_trips(data_dir: Path):
    store = DataStore(data_dir)
    habits = [Habit(name="water", created="2026-05-01", completions=["2026-05-01"])]
    store.save(habits)

    again = DataStore(data_dir).load()
    assert again == habits


def test_save_creates_parent_directory(tmp_path: Path, monkeypatch):
    nested = tmp_path / "a" / "b"
    monkeypatch.setenv("HABIT_DATA_DIR", str(nested))
    store = DataStore(nested)
    store.save([Habit(name="x", created="2026-05-01", completions=[])])
    assert (nested / "data.json").exists()


def test_corrupt_file_is_backed_up_and_load_returns_empty(data_dir: Path):
    (data_dir / "data.json").write_text("{ this is not json")

    store = DataStore(data_dir)
    assert store.load() == []

    backups = list(data_dir.glob("data.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "{ this is not json"


def test_unknown_version_is_treated_as_corrupt(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({"version": 999, "habits": []}))

    store = DataStore(data_dir)
    assert store.load() == []
    assert list(data_dir.glob("data.json.corrupt-*"))
```

- [ ] **Step 3: Run the failing tests**

Run: `.venv\Scripts\pytest tests/test_storage.py -v`
Expected: ImportError — `DataStore`, `Habit` don't exist yet.

- [ ] **Step 4: Implement `Habit` and `DataStore` in `habit_core.py`**

Replace the stub with:

```python
"""Pure logic for the habit tracker: storage, streaks, mutations."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DATA_FILENAME = "data.json"
SCHEMA_VERSION = 1


@dataclass
class Habit:
    name: str
    created: str
    completions: list[str] = field(default_factory=list)


class DataStore:
    """Reads and writes habits to a JSON file in a fixed directory."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.path = self.directory / DATA_FILENAME

    def load(self) -> list[Habit]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("root is not an object")
            if raw.get("version") != SCHEMA_VERSION:
                raise ValueError(f"unsupported schema version: {raw.get('version')!r}")
            return [Habit(**h) for h in raw["habits"]]
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            self._backup_corrupt()
            return []

    def save(self, habits: list[Habit]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {"version": SCHEMA_VERSION, "habits": [asdict(h) for h in habits]}
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _backup_corrupt(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{DATA_FILENAME}.corrupt-{timestamp}")
        self.path.rename(backup)
```

- [ ] **Step 5: Run the storage tests**

Run: `.venv\Scripts\pytest tests/test_storage.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```
git add habit_core.py tests/conftest.py tests/test_storage.py
git commit -m "feat: add DataStore with corrupt-file recovery"
```

---

## Task 3: Streak Math

**Files:**
- Modify: `habit_core.py`
- Create: `tests/test_streaks.py`

- [ ] **Step 1: Write failing tests for `current_streak`**

Create `tests/test_streaks.py`:

```python
from datetime import date

from habit_core import current_streak, longest_streak, completion_pct_30d


T = date(2026, 5, 14)  # fixed "today" for these tests


def test_current_streak_empty():
    assert current_streak([], today=T) == 0


def test_current_streak_only_today():
    assert current_streak(["2026-05-14"], today=T) == 1


def test_current_streak_today_and_yesterday():
    assert current_streak(["2026-05-13", "2026-05-14"], today=T) == 2


def test_current_streak_yesterday_only_does_not_break():
    # Today not yet marked; streak counts back from yesterday.
    assert current_streak(["2026-05-13"], today=T) == 1


def test_current_streak_yesterday_and_day_before():
    assert current_streak(["2026-05-12", "2026-05-13"], today=T) == 2


def test_current_streak_breaks_after_full_day_skipped():
    # Day before yesterday only — yesterday was skipped.
    assert current_streak(["2026-05-12"], today=T) == 0


def test_current_streak_ignores_future_dates():
    assert current_streak(["2026-05-20"], today=T) == 0


def test_longest_streak_empty():
    assert longest_streak([]) == 0


def test_longest_streak_single_run():
    assert longest_streak(["2026-05-12", "2026-05-13", "2026-05-14"]) == 3


def test_longest_streak_picks_max_run():
    completions = [
        "2026-04-01", "2026-04-02",                         # run of 2
        "2026-04-10", "2026-04-11", "2026-04-12", "2026-04-13",  # run of 4
        "2026-05-14",                                       # run of 1
    ]
    assert longest_streak(completions) == 4


def test_completion_pct_30d_empty():
    assert completion_pct_30d([], today=T) == 0


def test_completion_pct_30d_full():
    completions = [
        (date.fromordinal(T.toordinal() - i)).isoformat() for i in range(30)
    ]
    assert completion_pct_30d(completions, today=T) == 100


def test_completion_pct_30d_half():
    completions = [
        (date.fromordinal(T.toordinal() - i)).isoformat() for i in range(0, 30, 2)
    ]
    assert completion_pct_30d(completions, today=T) == 50


def test_completion_pct_30d_ignores_old_dates():
    completions = ["2025-01-01", "2025-01-02"]
    assert completion_pct_30d(completions, today=T) == 0
```

- [ ] **Step 2: Run the failing tests**

Run: `.venv\Scripts\pytest tests/test_streaks.py -v`
Expected: ImportError on `current_streak`, `longest_streak`, `completion_pct_30d`.

- [ ] **Step 3: Implement the three functions in `habit_core.py`**

Append to `habit_core.py`:

```python
from datetime import date, timedelta


def _parse(d: str) -> date:
    return date.fromisoformat(d)


def current_streak(completions: list[str], today: date | None = None) -> int:
    """Count consecutive days back from today (or yesterday if today not done)."""
    today = today or date.today()
    done = {_parse(c) for c in completions if _parse(c) <= today}
    cursor = today if today in done else today - timedelta(days=1)
    streak = 0
    while cursor in done:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(completions: list[str]) -> int:
    """Length of the longest run of consecutive dates in completions."""
    if not completions:
        return 0
    days = sorted({_parse(c) for c in completions})
    best = current = 1
    for prev, curr in zip(days, days[1:]):
        if (curr - prev).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def completion_pct_30d(completions: list[str], today: date | None = None) -> int:
    """Percent of the last 30 days (inclusive of today) that have a completion."""
    today = today or date.today()
    window_start = today - timedelta(days=29)  # 30-day inclusive window
    hits = sum(1 for c in completions if window_start <= _parse(c) <= today)
    return round(hits / 30 * 100)
```

- [ ] **Step 4: Run the streak tests**

Run: `.venv\Scripts\pytest tests/test_streaks.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```
git add habit_core.py tests/test_streaks.py
git commit -m "feat: add streak and completion-percent math"
```

---

## Task 4: Habit Collection Operations

**Files:**
- Modify: `habit_core.py`
- Create: `tests/test_habits.py`

- [ ] **Step 1: Write failing tests for habit operations**

Create `tests/test_habits.py`:

```python
from datetime import date

import pytest

from habit_core import (
    Habit,
    add_habit,
    find_habit,
    mark_done,
    remove_habit,
    unmark_today,
)


def test_add_habit_appends():
    habits: list[Habit] = []
    add_habit(habits, "water", today=date(2026, 5, 14))
    assert habits == [Habit(name="water", created="2026-05-14", completions=[])]


def test_add_habit_rejects_duplicate_case_insensitive():
    habits = [Habit(name="Water", created="2026-05-01", completions=[])]
    with pytest.raises(ValueError, match="already exists"):
        add_habit(habits, "water", today=date(2026, 5, 14))


def test_find_habit_case_insensitive():
    habits = [Habit(name="Water", created="2026-05-01", completions=[])]
    assert find_habit(habits, "water") is habits[0]
    assert find_habit(habits, "WATER") is habits[0]


def test_find_habit_returns_none_when_missing():
    assert find_habit([], "water") is None


def test_mark_done_adds_today():
    h = Habit(name="water", created="2026-05-01", completions=[])
    changed = mark_done(h, today=date(2026, 5, 14))
    assert changed is True
    assert h.completions == ["2026-05-14"]


def test_mark_done_is_idempotent():
    h = Habit(name="water", created="2026-05-01", completions=["2026-05-14"])
    changed = mark_done(h, today=date(2026, 5, 14))
    assert changed is False
    assert h.completions == ["2026-05-14"]


def test_mark_done_keeps_completions_sorted():
    h = Habit(name="water", created="2026-05-01", completions=["2026-05-15"])
    mark_done(h, today=date(2026, 5, 14))
    assert h.completions == ["2026-05-14", "2026-05-15"]


def test_unmark_today_removes_today():
    h = Habit(name="water", created="2026-05-01", completions=["2026-05-13", "2026-05-14"])
    changed = unmark_today(h, today=date(2026, 5, 14))
    assert changed is True
    assert h.completions == ["2026-05-13"]


def test_unmark_today_is_noop_if_not_marked():
    h = Habit(name="water", created="2026-05-01", completions=["2026-05-13"])
    changed = unmark_today(h, today=date(2026, 5, 14))
    assert changed is False
    assert h.completions == ["2026-05-13"]


def test_remove_habit_deletes_by_name_case_insensitive():
    habits = [
        Habit(name="Water", created="2026-05-01", completions=[]),
        Habit(name="run", created="2026-05-01", completions=[]),
    ]
    removed = remove_habit(habits, "WATER")
    assert removed is True
    assert [h.name for h in habits] == ["run"]


def test_remove_habit_returns_false_when_missing():
    habits = [Habit(name="run", created="2026-05-01", completions=[])]
    assert remove_habit(habits, "water") is False
```

- [ ] **Step 2: Run the failing tests**

Run: `.venv\Scripts\pytest tests/test_habits.py -v`
Expected: ImportError on `add_habit`, `find_habit`, `mark_done`, `unmark_today`, `remove_habit`.

- [ ] **Step 3: Implement the operations in `habit_core.py`**

Append to `habit_core.py`:

```python
def add_habit(habits: list[Habit], name: str, today: date | None = None) -> Habit:
    if find_habit(habits, name) is not None:
        raise ValueError(f"Habit {name!r} already exists")
    today = today or date.today()
    habit = Habit(name=name, created=today.isoformat(), completions=[])
    habits.append(habit)
    return habit


def find_habit(habits: list[Habit], name: str) -> Habit | None:
    needle = name.casefold()
    for h in habits:
        if h.name.casefold() == needle:
            return h
    return None


def mark_done(habit: Habit, today: date | None = None) -> bool:
    today = today or date.today()
    iso = today.isoformat()
    if iso in habit.completions:
        return False
    habit.completions.append(iso)
    habit.completions.sort()
    return True


def unmark_today(habit: Habit, today: date | None = None) -> bool:
    today = today or date.today()
    iso = today.isoformat()
    if iso not in habit.completions:
        return False
    habit.completions.remove(iso)
    return True


def remove_habit(habits: list[Habit], name: str) -> bool:
    habit = find_habit(habits, name)
    if habit is None:
        return False
    habits.remove(habit)
    return True
```

- [ ] **Step 4: Run all core tests**

Run: `.venv\Scripts\pytest tests/test_storage.py tests/test_streaks.py tests/test_habits.py -v`
Expected: all green (5 + 13 + 11 = 29 passed).

- [ ] **Step 5: Commit**

```
git add habit_core.py tests/test_habits.py
git commit -m "feat: add habit list mutation operations"
```

---

## Task 5: CLI Skeleton + Default `list` Dispatch

**Files:**
- Modify: `habit.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write a failing CLI test**

Create `tests/test_cli.py`:

```python
def test_no_args_shows_friendly_empty_state(run_cli):
    result = run_cli()
    assert result.returncode == 0
    assert "no habits" in result.stdout.lower()
```

- [ ] **Step 2: Run it (will fail)**

Run: `.venv\Scripts\pytest tests/test_cli.py -v`
Expected: assertion fails — current `habit.py` prints nothing.

- [ ] **Step 3: Implement the CLI skeleton**

Replace `habit.py` with:

```python
"""CLI entrypoint for the habit tracker."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console

from habit_core import DataStore

DEFAULT_DATA_DIR = Path.home() / ".habit-tracker"


def _data_dir() -> Path:
    override = os.environ.get("HABIT_DATA_DIR")
    return Path(override) if override else DEFAULT_DATA_DIR


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="habit", description="Daily habit tracker")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List habits")
    return parser


def cmd_list(store: DataStore, console: Console, err: Console) -> int:
    habits = store.load()
    if not habits:
        console.print("No habits yet. Add one with: habit add <name>")
        return 0
    # Full table comes in Task 8.
    for h in habits:
        console.print(h.name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = DataStore(_data_dir())
    console = Console()
    err = Console(stderr=True)

    command = args.command or "list"
    if command == "list":
        return cmd_list(store, console, err)
    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI test**

Run: `.venv\Scripts\pytest tests/test_cli.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```
git add habit.py tests/test_cli.py
git commit -m "feat: CLI skeleton with default list dispatch"
```

---

## Task 6: `habit add` Command

**Files:**
- Modify: `habit.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for `add`**

Append to `tests/test_cli.py`:

```python
def test_add_creates_habit_and_list_shows_it(run_cli):
    add = run_cli("add", "water")
    assert add.returncode == 0
    assert "water" in add.stdout.lower()

    listing = run_cli("list")
    assert listing.returncode == 0
    assert "water" in listing.stdout.lower()


def test_add_duplicate_exits_nonzero(run_cli):
    run_cli("add", "water")
    second = run_cli("add", "WATER")
    assert second.returncode == 1
    assert "already exists" in second.stderr.lower()
```

- [ ] **Step 2: Run them (will fail)**

Run: `.venv\Scripts\pytest tests/test_cli.py -v`
Expected: 2 fail (parser rejects `add` subcommand).

- [ ] **Step 3: Wire the `add` command**

In `habit.py`, update `_build_parser` and add `cmd_add`. Also import `add_habit`:

```python
from habit_core import DataStore, add_habit
```

Replace `_build_parser` with:

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="habit", description="Daily habit tracker")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List habits")

    p_add = sub.add_parser("add", help="Add a new habit")
    p_add.add_argument("name")

    return parser
```

Add the handler above `main`:

```python
def cmd_add(store: DataStore, console: Console, err: Console, name: str) -> int:
    habits = store.load()
    try:
        add_habit(habits, name)
    except ValueError as e:
        err.print(str(e))
        return 1
    store.save(habits)
    console.print(f"Added habit {name!r}.")
    return 0
```

Update `main`'s dispatch block:

```python
    command = args.command or "list"
    if command == "list":
        return cmd_list(store, console, err)
    if command == "add":
        return cmd_add(store, console, err, args.name)
    parser.error(f"unknown command: {command}")
    return 2
```

- [ ] **Step 4: Run the CLI tests**

Run: `.venv\Scripts\pytest tests/test_cli.py -v`
Expected: all passing (3 so far).

- [ ] **Step 5: Commit**

```
git add habit.py tests/test_cli.py
git commit -m "feat: habit add command"
```

---

## Task 7: `habit done` and `habit undo`

**Files:**
- Modify: `habit.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
import json


def _read_data(data_dir):
    return json.loads((data_dir / "data.json").read_text())


def test_done_marks_today(run_cli, data_dir):
    run_cli("add", "water")
    result = run_cli("done", "water")
    assert result.returncode == 0
    data = _read_data(data_dir)
    assert len(data["habits"][0]["completions"]) == 1


def test_done_twice_is_noop(run_cli, data_dir):
    run_cli("add", "water")
    run_cli("done", "water")
    second = run_cli("done", "water")
    assert second.returncode == 0
    assert "already" in second.stdout.lower()
    assert len(_read_data(data_dir)["habits"][0]["completions"]) == 1


def test_done_unknown_habit_exits_nonzero(run_cli):
    result = run_cli("done", "ghost")
    assert result.returncode == 1
    assert "no habit" in result.stderr.lower()


def test_undo_removes_today(run_cli, data_dir):
    run_cli("add", "water")
    run_cli("done", "water")
    result = run_cli("undo", "water")
    assert result.returncode == 0
    assert _read_data(data_dir)["habits"][0]["completions"] == []


def test_undo_when_not_marked_is_noop(run_cli, data_dir):
    run_cli("add", "water")
    result = run_cli("undo", "water")
    assert result.returncode == 0
    assert _read_data(data_dir)["habits"][0]["completions"] == []
```

- [ ] **Step 2: Run them (will fail)**

Run: `.venv\Scripts\pytest tests/test_cli.py -v`
Expected: 5 fail — `done`/`undo` not registered.

- [ ] **Step 3: Wire `done` and `undo`**

In `habit.py`, expand the imports:

```python
from habit_core import DataStore, add_habit, find_habit, mark_done, unmark_today
```

Add to `_build_parser` (before `return parser`):

```python
    p_done = sub.add_parser("done", help="Mark today complete for a habit")
    p_done.add_argument("name")

    p_undo = sub.add_parser("undo", help="Unmark today for a habit")
    p_undo.add_argument("name")
```

Add the handlers:

```python
def _resolve(habits, name, err: Console):
    habit = find_habit(habits, name)
    if habit is None:
        err.print(f"No habit named {name!r}. Run 'habit list' to see habits.")
    return habit


def cmd_done(store: DataStore, console: Console, err: Console, name: str) -> int:
    habits = store.load()
    habit = _resolve(habits, name, err)
    if habit is None:
        return 1
    if mark_done(habit):
        store.save(habits)
        console.print(f"Marked {habit.name!r} done for today.")
    else:
        console.print(f"{habit.name!r} already marked for today.")
    return 0


def cmd_undo(store: DataStore, console: Console, err: Console, name: str) -> int:
    habits = store.load()
    habit = _resolve(habits, name, err)
    if habit is None:
        return 1
    if unmark_today(habit):
        store.save(habits)
        console.print(f"Unmarked today for {habit.name!r}.")
    else:
        console.print(f"{habit.name!r} was not marked for today.")
    return 0
```

Add to dispatch in `main`:

```python
    if command == "done":
        return cmd_done(store, console, err, args.name)
    if command == "undo":
        return cmd_undo(store, console, err, args.name)
```

- [ ] **Step 4: Run all tests**

Run: `.venv\Scripts\pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```
git add habit.py tests/test_cli.py
git commit -m "feat: habit done and undo commands"
```

---

## Task 8: `habit list` Rich Table

**Files:**
- Modify: `habit.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_list_shows_table_columns(run_cli):
    run_cli("add", "water")
    run_cli("done", "water")
    result = run_cli("list")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert "water" in out
    for column in ("habit", "today", "current", "longest", "30d"):
        assert column in out
```

- [ ] **Step 2: Run it (will fail — current cmd_list just prints names)**

Run: `.venv\Scripts\pytest tests/test_cli.py::test_list_shows_table_columns -v`
Expected: missing column headers.

- [ ] **Step 3: Replace `cmd_list` with a rich table**

Update imports in `habit.py`:

```python
from datetime import date

from rich.console import Console
from rich.table import Table

from habit_core import (
    DataStore,
    add_habit,
    completion_pct_30d,
    current_streak,
    find_habit,
    longest_streak,
    mark_done,
    unmark_today,
)
```

Replace `cmd_list`:

```python
def cmd_list(store: DataStore, console: Console, err: Console) -> int:
    habits = store.load()
    if not habits:
        console.print("No habits yet. Add one with: habit add <name>")
        return 0

    today = date.today()
    table = Table(title="Habits")
    table.add_column("Habit")
    table.add_column("Today")
    table.add_column("Current", justify="right")
    table.add_column("Longest", justify="right")
    table.add_column("30d %", justify="right")

    today_iso = today.isoformat()
    for h in habits:
        marked = today_iso in h.completions
        table.add_row(
            h.name,
            "[green]✓[/green]" if marked else "·",
            str(current_streak(h.completions, today=today)),
            str(longest_streak(h.completions)),
            f"{completion_pct_30d(h.completions, today=today)}%",
        )
    console.print(table)
    return 0
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```
git add habit.py tests/test_cli.py
git commit -m "feat: rich table for habit list"
```

---

## Task 9: `habit show` (Heatmap + Stats)

**Files:**
- Modify: `habit.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write a failing test**

Append to `tests/test_cli.py`:

```python
def test_show_renders_heatmap_and_stats(run_cli):
    run_cli("add", "water")
    run_cli("done", "water")
    result = run_cli("show", "water")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert "water" in out
    assert "current streak" in out
    assert "longest streak" in out
    assert "total" in out


def test_show_unknown_habit_exits_nonzero(run_cli):
    result = run_cli("show", "ghost")
    assert result.returncode == 1
```

- [ ] **Step 2: Run it (will fail)**

Run: `.venv\Scripts\pytest tests/test_cli.py -k show -v`
Expected: parser rejects `show`.

- [ ] **Step 3: Implement `cmd_show`**

Add to `_build_parser`:

```python
    p_show = sub.add_parser("show", help="Show details for one habit")
    p_show.add_argument("name")
```

Add the handler:

```python
def cmd_show(store: DataStore, console: Console, err: Console, name: str) -> int:
    from datetime import timedelta

    habits = store.load()
    habit = _resolve(habits, name, err)
    if habit is None:
        return 1

    today = date.today()
    done = {date.fromisoformat(c) for c in habit.completions}

    # 12-week heatmap ending with the current week (Mon-Sun rows).
    weeks = 12
    end_of_week = today + timedelta(days=(6 - today.weekday()))  # Sunday
    start = end_of_week - timedelta(weeks=weeks - 1, days=6)     # Monday

    console.print(f"[bold]{habit.name}[/bold]  (created {habit.created})")
    console.print()

    # Build 7 rows (Mon..Sun) x 12 columns of cells.
    grid = [[" "] * weeks for _ in range(7)]
    for col in range(weeks):
        for row in range(7):
            d = start + timedelta(weeks=col, days=row)
            if d > today:
                grid[row][col] = " "
            elif d in done:
                grid[row][col] = "[green]■[/green]"
            else:
                grid[row][col] = "[grey37]·[/grey37]"

    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for label, row in zip(labels, grid):
        console.print(f"{label}  " + " ".join(row))

    console.print()
    console.print(f"Current streak: {current_streak(habit.completions, today=today)}")
    console.print(f"Longest streak: {longest_streak(habit.completions)}")
    console.print(f"Total completions: {len(habit.completions)}")
    return 0
```

Add to dispatch:

```python
    if command == "show":
        return cmd_show(store, console, err, args.name)
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```
git add habit.py tests/test_cli.py
git commit -m "feat: habit show with 12-week heatmap"
```

---

## Task 10: `habit rm` Command

**Files:**
- Modify: `habit.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_cli.py`:

```python
def test_rm_with_yes_removes_habit(run_cli, data_dir):
    run_cli("add", "water")
    result = run_cli("rm", "water", "--yes")
    assert result.returncode == 0
    assert _read_data(data_dir)["habits"] == []


def test_rm_unknown_exits_nonzero(run_cli):
    result = run_cli("rm", "ghost", "--yes")
    assert result.returncode == 1


def test_rm_prompts_and_cancels_on_no(run_cli, data_dir):
    run_cli("add", "water")
    result = run_cli("rm", "water", stdin="n\n")
    assert result.returncode == 0
    assert "cancel" in result.stdout.lower()
    assert len(_read_data(data_dir)["habits"]) == 1


def test_rm_prompts_and_confirms_on_y(run_cli, data_dir):
    run_cli("add", "water")
    result = run_cli("rm", "water", stdin="y\n")
    assert result.returncode == 0
    assert _read_data(data_dir)["habits"] == []
```

- [ ] **Step 2: Run them (will fail)**

Run: `.venv\Scripts\pytest tests/test_cli.py -k rm -v`
Expected: parser rejects `rm`.

- [ ] **Step 3: Implement `cmd_rm`**

Update imports:

```python
from habit_core import (
    DataStore,
    add_habit,
    completion_pct_30d,
    current_streak,
    find_habit,
    longest_streak,
    mark_done,
    remove_habit,
    unmark_today,
)
```

Add to `_build_parser`:

```python
    p_rm = sub.add_parser("rm", help="Remove a habit and its history")
    p_rm.add_argument("name")
    p_rm.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
```

Add the handler:

```python
def cmd_rm(
    store: DataStore, console: Console, err: Console, name: str, assume_yes: bool
) -> int:
    habits = store.load()
    habit = _resolve(habits, name, err)
    if habit is None:
        return 1

    if not assume_yes:
        console.print(f"Remove {habit.name!r} and all its history? [y/N] ", end="")
        answer = sys.stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            console.print("Cancelled.")
            return 0

    remove_habit(habits, habit.name)
    store.save(habits)
    console.print(f"Removed {habit.name!r}.")
    return 0
```

Add to dispatch:

```python
    if command == "rm":
        return cmd_rm(store, console, err, args.name, args.yes)
```

- [ ] **Step 4: Run all tests**

Run: `.venv\Scripts\pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```
git add habit.py tests/test_cli.py
git commit -m "feat: habit rm command with confirmation"
```

---

## Task 11: Final Smoke Run + README Polish

**Files:**
- Modify: `README.md` (only if usage drifted)

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -v`
Expected: every test passes. Note the count.

- [ ] **Step 2: Manual smoke test**

In a real shell (not a test), with a throwaway data dir:

```
$env:HABIT_DATA_DIR = "$env:TEMP\habit-smoke"
Remove-Item -Recurse -Force $env:HABIT_DATA_DIR -ErrorAction SilentlyContinue
.venv\Scripts\python habit.py add water
.venv\Scripts\python habit.py add read
.venv\Scripts\python habit.py done water
.venv\Scripts\python habit.py list
.venv\Scripts\python habit.py show water
.venv\Scripts\python habit.py rm read --yes
.venv\Scripts\python habit.py
```

Expected: each command behaves per spec. Output looks right (table is colored, heatmap renders).

- [ ] **Step 3: Verify README still matches behavior**

Read `README.md`. If any flag, command, or env var name has drifted, update it.

- [ ] **Step 4: Commit (only if README changed)**

```
git add README.md
git commit -m "docs: align README with final CLI"
```

- [ ] **Step 5: Tag**

```
git tag v0.1.0
```

---

## Self-Review

**Spec coverage:**
- All 7 commands (`add`, `done`, `undo`, `list`, `show`, `rm`, no-args) — Tasks 5–10. ✓
- Data model with `version` field — Task 2. ✓
- Streak rules (current with yesterday fallback, longest, 30-day %) — Task 3. ✓
- Error handling: unknown habit, duplicate, idempotent done, corrupt file recovery — Tasks 2, 6, 7. ✓
- Stderr for errors, stdout for success — wired in command handlers (Task 5+). ✓
- Out-of-scope items not implemented. ✓
- Test coverage: streak math, round-trips, end-to-end CLI, corrupt recovery — Tasks 2, 3, 4, 5–10. ✓

**Type/name consistency:** `Habit`, `DataStore`, `add_habit`, `find_habit`, `mark_done`, `unmark_today`, `remove_habit`, `current_streak`, `longest_streak`, `completion_pct_30d` — all referenced consistently across tasks.

**Placeholder scan:** No TBDs. Every code step shows full code, every command step shows the exact command and expected outcome.
