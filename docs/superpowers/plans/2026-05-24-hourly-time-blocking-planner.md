# Hourly Time-Blocking Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the recurring-habit tracker with an hourly time-blocking planner: a reusable template of time blocks that auto-fills each day, marked Pending/Done/Skipped, exposed through a React/Vite web app plus a minimal CLI.

**Architecture:** A pure-Python `core.py` owns the template, per-day materialization, state transitions, validation, and storage (schema v2, snapshot-on-write days). A FastAPI `api.py` is a thin JSON layer over the core; a React/Vite SPA in `web/` is the primary UI; a minimal `cli.py` (`plan`) shares the same core. The core imports neither FastAPI nor React.

**Tech Stack:** Python 3.13, `rich` (CLI), `fastapi` + `uvicorn` (API), `pytest` + FastAPI `TestClient` (Python tests), React + Vite + Vitest + React Testing Library (web).

**Spec:** `docs/superpowers/specs/2026-05-24-hourly-time-blocking-planner-design.md`

**Conventions used throughout this plan:**
- Times are `"HH:MM"` 24-hour, zero-padded. Because they are zero-padded, plain string comparison (`"08:00" < "09:00"`) gives correct chronological ordering — the code relies on this.
- Block states: `"pending"`, `"done"`, `"skipped"`.
- Data dir comes from env var `PLAN_DATA_DIR`, default `~/.plan`. (Renamed from the old `HABIT_DATA_DIR` / `~/.habit-tracker` — clean break, no migration.)
- Run all Python commands from the repo root `D:\habit-tracker`.

---

## Phase 0: Project setup

### Task 0: Dependencies, module rename, and test fixtures

**Files:**
- Modify: `pyproject.toml`
- Delete: `habit.py`, `habit_core.py` (replaced by `cli.py` / `core.py` in later tasks)
- Delete: `tests/test_storage.py`, `tests/test_streaks.py`, `tests/test_cli.py`, `tests/test_habits.py` (old model; rewritten this plan)
- Modify: `tests/conftest.py`
- Modify: `README.md`

- [ ] **Step 1: Update `pyproject.toml`**

Replace the file contents with:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "habit-tracker"
version = "0.2.0"
description = "Single-user hourly time-blocking planner"
requires-python = ">=3.13"
dependencies = ["rich>=13.0", "fastapi>=0.110", "uvicorn>=0.27"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[project.scripts]
plan = "cli:main"

[tool.setuptools]
py-modules = ["cli", "core", "api"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

(`httpx` is required by FastAPI's `TestClient`.)

- [ ] **Step 2: Remove the old modules and tests**

```bash
git rm habit.py habit_core.py tests/test_storage.py tests/test_streaks.py
rm -f tests/test_cli.py tests/test_habits.py
```

(`test_cli.py` and `test_habits.py` are untracked, so `rm` not `git rm`.)

- [ ] **Step 3: Rewrite `tests/conftest.py`**

```python
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolated data directory for one test."""
    d = tmp_path / "plan-data"
    d.mkdir()
    monkeypatch.setenv("PLAN_DATA_DIR", str(d))
    return d


@pytest.fixture
def run_cli(data_dir):
    """Run cli.py as a subprocess with the isolated data dir."""
    repo_root = Path(__file__).resolve().parent.parent

    def _run(*args, stdin: str | None = None):
        env = {
            **os.environ,
            "PLAN_DATA_DIR": str(data_dir),
            "PYTHONIOENCODING": "utf-8",
        }
        return subprocess.run(
            [sys.executable, str(repo_root / "cli.py"), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            input=stdin,
            env=env,
            cwd=str(repo_root),
        )

    return _run
```

- [ ] **Step 4: Install dependencies**

Run: `pip install -e ".[dev]"`
Expected: installs `rich`, `fastapi`, `uvicorn`, `pytest`, `httpx` without error.

- [ ] **Step 5: Update `README.md`**

Replace the contents with:

```markdown
# habit-tracker

Single-user hourly time-blocking planner: a reusable template of time blocks that
auto-fills each day, marked Pending / Done / Skipped, via a web app or a minimal CLI.

## Install (dev)

    python -m venv .venv
    .venv\Scripts\activate    # Windows
    pip install -e ".[dev]"

## CLI

    plan today                # text view of today's blocks
    plan done 8               # mark the block starting at 08:00 done today
    plan done 08:00           # same, by explicit start time
    plan skip 9               # mark the 09:00 block skipped today
    plan template             # list the recurring template

Block references accept a start hour (`8`), an explicit start time (`08:00`), or the
row number shown in `plan today`.

## Web app

Backend:

    uvicorn api:app --reload      # serves the JSON API on http://127.0.0.1:8000

Frontend:

    cd web
    npm install
    npm run dev                   # Vite dev server, proxies /api to the backend

Data is stored at `~/.plan/data.json`. Override with the `PLAN_DATA_DIR` env var.
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: rename to planner, add web deps, reset tests"
```

---

## Phase 1: Core logic (`core.py`)

All of Phase 1 builds one file, `core.py`, and one test file, `tests/test_core.py`, test-first.

### Task 1: Data types and storage round-trip

**Files:**
- Create: `core.py`
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_core.py`:

```python
import json
from pathlib import Path

from core import (
    DataStore,
    Day,
    DayBlock,
    PlannerData,
    TemplateBlock,
)


def test_load_returns_empty_when_file_missing(data_dir: Path):
    assert DataStore(data_dir).load() == PlannerData()


def test_save_then_load_round_trips(data_dir: Path):
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="standup")],
        days={
            "2026-05-24": Day(
                blocks=[DayBlock(start="08:00", end="09:00", label="fixed bug", state="done")]
            )
        },
    )
    DataStore(data_dir).save(data)
    assert DataStore(data_dir).load() == data


def test_save_creates_parent_directory(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    DataStore(nested).save(PlannerData())
    assert (nested / "data.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core'`.

- [ ] **Step 3: Write minimal implementation**

Create `core.py`:

```python
"""Pure logic for the time-blocking planner: storage, template, days, state."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DATA_FILENAME = "data.json"
SCHEMA_VERSION = 2
STATES = ("pending", "done", "skipped")

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ValidationError(ValueError):
    """Raised when a block fails validation (format, ordering, overlap, duplicate)."""


@dataclass
class TemplateBlock:
    start: str
    end: str
    label: str


@dataclass
class DayBlock:
    start: str
    end: str
    label: str
    state: str = "pending"


@dataclass
class Day:
    blocks: list[DayBlock] = field(default_factory=list)


@dataclass
class PlannerData:
    template: list[TemplateBlock] = field(default_factory=list)
    days: dict[str, Day] = field(default_factory=dict)


class DataStore:
    """Reads and writes planner data to a JSON file in a fixed directory."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.path = self.directory / DATA_FILENAME

    def load(self, on_corrupt: Callable[[Path], None] | None = None) -> PlannerData:
        if not self.path.exists():
            return PlannerData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("root is not an object")
            if raw.get("version") != SCHEMA_VERSION:
                raise ValueError(f"unsupported schema version: {raw.get('version')!r}")
            template = [TemplateBlock(**b) for b in raw["template"]]
            days = {
                d: Day(blocks=[DayBlock(**blk) for blk in day["blocks"]])
                for d, day in raw["days"].items()
            }
            return PlannerData(template=template, days=days)
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            backup = self._backup_corrupt()
            if on_corrupt is not None:
                on_corrupt(backup)
            return PlannerData()

    def save(self, data: PlannerData) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": SCHEMA_VERSION,
            "template": [asdict(b) for b in data.template],
            "days": {
                d: {"blocks": [asdict(b) for b in day.blocks]}
                for d, day in data.days.items()
            },
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _backup_corrupt(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = self.path.with_name(f"{DATA_FILENAME}.corrupt-{timestamp}")
        self.path.rename(backup)
        return backup
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_core.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: core data types and storage round-trip"
```

### Task 2: Corrupt-file and v1 recovery

**Files:**
- Modify: `tests/test_core.py`
- (No `core.py` change needed — recovery already implemented; this task verifies it.)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_core.py`:

```python
def test_corrupt_file_is_backed_up_and_load_returns_empty(data_dir: Path):
    (data_dir / "data.json").write_text("{ this is not json", encoding="utf-8")
    seen = []
    result = DataStore(data_dir).load(on_corrupt=seen.append)
    assert result == PlannerData()
    backups = list(data_dir.glob("data.json.corrupt-*"))
    assert len(backups) == 1
    assert seen == backups


def test_v1_schema_is_rejected_as_corrupt(data_dir: Path):
    (data_dir / "data.json").write_text(
        json.dumps({"version": 1, "habits": []}), encoding="utf-8"
    )
    assert DataStore(data_dir).load() == PlannerData()
    assert list(data_dir.glob("data.json.corrupt-*"))
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (5 tests). If they fail, fix `core.py` before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_core.py
git commit -m "test: cover corrupt-file and v1 rejection recovery"
```

### Task 3: Block validation helpers

**Files:**
- Modify: `core.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_core.py`:

```python
import pytest

from core import ValidationError, validate_times


def test_validate_times_accepts_valid_range():
    validate_times("08:00", "09:30")  # no exception


@pytest.mark.parametrize("start,end", [
    ("8:00", "09:00"),    # not zero-padded
    ("24:00", "09:00"),   # hour out of range
    ("08:60", "09:00"),   # minute out of range
    ("0800", "09:00"),    # missing colon
])
def test_validate_times_rejects_bad_format(start, end):
    with pytest.raises(ValidationError):
        validate_times(start, end)


def test_validate_times_rejects_start_not_before_end():
    with pytest.raises(ValidationError):
        validate_times("09:00", "09:00")
    with pytest.raises(ValidationError):
        validate_times("10:00", "09:00")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py::test_validate_times_accepts_valid_range -v`
Expected: FAIL — `ImportError: cannot import name 'validate_times'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core.py` (after the `ValidationError` class):

```python
def validate_times(start: str, end: str) -> None:
    """Raise ValidationError unless start and end are HH:MM and start < end."""
    for value in (start, end):
        if not _TIME_RE.match(value):
            raise ValidationError(f"invalid time {value!r}; expected HH:MM (24h)")
    if start >= end:
        raise ValidationError(f"start {start!r} must be before end {end!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all validate_times cases).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: time validation helper"
```

### Task 4: Template operations (add/find/edit/remove)

**Files:**
- Modify: `core.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_core.py`:

```python
from core import (
    add_template_block,
    edit_template_block,
    find_template_block,
    remove_template_block,
)


def test_add_template_block_keeps_list_sorted_by_start():
    data = PlannerData()
    add_template_block(data, "09:00", "10:00", "code")
    add_template_block(data, "08:00", "09:00", "standup")
    assert [b.start for b in data.template] == ["08:00", "09:00"]


def test_add_template_block_rejects_duplicate_start():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    with pytest.raises(ValidationError):
        add_template_block(data, "08:00", "08:30", "other")


def test_add_template_block_rejects_overlap():
    data = PlannerData()
    add_template_block(data, "08:00", "10:00", "deep work")
    with pytest.raises(ValidationError):
        add_template_block(data, "09:00", "11:00", "overlap")


def test_adjacent_blocks_do_not_overlap():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "a")
    add_template_block(data, "09:00", "10:00", "b")  # touching is allowed
    assert len(data.template) == 2


def test_find_template_block():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    assert find_template_block(data, "08:00").label == "standup"
    assert find_template_block(data, "07:00") is None


def test_edit_template_block_updates_fields_and_resorts():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    add_template_block(data, "10:00", "11:00", "code")
    edit_template_block(data, "08:00", new_start="12:00", new_end="13:00", label="lunch")
    assert [b.start for b in data.template] == ["10:00", "12:00"]
    assert find_template_block(data, "12:00").label == "lunch"


def test_edit_template_block_rejects_collision_with_other_block():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "a")
    add_template_block(data, "10:00", "11:00", "b")
    with pytest.raises(ValidationError):
        edit_template_block(data, "08:00", new_start="10:00", new_end="10:30", label="x")


def test_edit_missing_template_block_raises():
    data = PlannerData()
    with pytest.raises(ValidationError):
        edit_template_block(data, "08:00", new_start="08:00", new_end="09:00", label="x")


def test_remove_template_block():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    assert remove_template_block(data, "08:00") is True
    assert data.template == []
    assert remove_template_block(data, "08:00") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py::test_add_template_block_keeps_list_sorted_by_start -v`
Expected: FAIL — `ImportError: cannot import name 'add_template_block'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core.py`:

```python
def _overlaps(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    # Half-open intervals [start, end): touching endpoints do not overlap.
    return a_start < b_end and b_start < a_end


def find_template_block(data: PlannerData, start: str) -> TemplateBlock | None:
    for block in data.template:
        if block.start == start:
            return block
    return None


def _check_template_slot(
    data: PlannerData, start: str, end: str, *, ignore_start: str | None = None
) -> None:
    validate_times(start, end)
    for block in data.template:
        if block.start == ignore_start:
            continue
        if block.start == start:
            raise ValidationError(f"a block already starts at {start!r}")
        if _overlaps(start, end, block.start, block.end):
            raise ValidationError(
                f"block {start}-{end} overlaps {block.start}-{block.end}"
            )


def add_template_block(data: PlannerData, start: str, end: str, label: str) -> TemplateBlock:
    _check_template_slot(data, start, end)
    block = TemplateBlock(start=start, end=end, label=label)
    data.template.append(block)
    data.template.sort(key=lambda b: b.start)
    return block


def edit_template_block(
    data: PlannerData, start: str, *, new_start: str, new_end: str, label: str
) -> TemplateBlock:
    block = find_template_block(data, start)
    if block is None:
        raise ValidationError(f"no template block starts at {start!r}")
    _check_template_slot(data, new_start, new_end, ignore_start=start)
    block.start, block.end, block.label = new_start, new_end, label
    data.template.sort(key=lambda b: b.start)
    return block


def remove_template_block(data: PlannerData, start: str) -> bool:
    block = find_template_block(data, start)
    if block is None:
        return False
    data.template.remove(block)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all template tests).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: template add/find/edit/remove with overlap validation"
```

### Task 5: Day materialization and state/label mutation

**Files:**
- Modify: `core.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_core.py`:

```python
from core import (
    get_day_blocks,
    history_dates,
    set_block_label,
    set_block_state,
)


def _template_data():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    add_template_block(data, "09:00", "10:00", "code")
    return data


def test_get_day_blocks_renders_untouched_day_from_template_as_pending():
    data = _template_data()
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00"]
    assert all(b.state == "pending" for b in blocks)
    assert "2026-05-24" not in data.days  # reading does not materialize


def test_set_block_state_materializes_day_and_persists_state():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")
    assert "2026-05-24" in data.days
    blocks = get_day_blocks(data, "2026-05-24")
    assert blocks[0].state == "done"
    assert blocks[1].state == "pending"


def test_set_block_state_rejects_unknown_state():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "08:00", "maybe")


def test_set_block_state_rejects_unknown_block():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "11:00", "done")


def test_set_block_label_overrides_for_that_day_only():
    data = _template_data()
    set_block_label(data, "2026-05-24", "08:00", "fixed login bug")
    assert get_day_blocks(data, "2026-05-24")[0].label == "fixed login bug"
    # A different, untouched day still shows the template default.
    assert get_day_blocks(data, "2026-05-25")[0].label == "standup"


def test_editing_template_does_not_touch_already_materialized_day():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")  # materialize the day
    edit_template_block(data, "08:00", new_start="08:00", new_end="09:00", label="renamed")
    remove_template_block(data, "09:00")
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00"]  # frozen copy unaffected
    assert blocks[0].label == "standup"
    assert blocks[0].state == "done"


def test_history_dates_sorted():
    data = _template_data()
    set_block_state(data, "2026-05-25", "08:00", "done")
    set_block_state(data, "2026-05-24", "08:00", "done")
    assert history_dates(data) == ["2026-05-24", "2026-05-25"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py::test_get_day_blocks_renders_untouched_day_from_template_as_pending -v`
Expected: FAIL — `ImportError: cannot import name 'get_day_blocks'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core.py`:

```python
def _blocks_from_template(data: PlannerData) -> list[DayBlock]:
    return [
        DayBlock(start=b.start, end=b.end, label=b.label, state="pending")
        for b in data.template
    ]


def get_day_blocks(data: PlannerData, date_iso: str) -> list[DayBlock]:
    """Return the day's blocks: the stored copy if touched, else a live template view."""
    day = data.days.get(date_iso)
    if day is not None:
        return day.blocks
    return _blocks_from_template(data)


def _materialize(data: PlannerData, date_iso: str) -> Day:
    day = data.days.get(date_iso)
    if day is None:
        day = Day(blocks=_blocks_from_template(data))
        data.days[date_iso] = day
    return day


def _find_day_block(day: Day, start: str) -> DayBlock | None:
    for block in day.blocks:
        if block.start == start:
            return block
    return None


def set_block_state(data: PlannerData, date_iso: str, start: str, state: str) -> None:
    if state not in STATES:
        raise ValidationError(f"unknown state {state!r}; expected one of {STATES}")
    day = _materialize(data, date_iso)
    block = _find_day_block(day, start)
    if block is None:
        raise ValidationError(f"no block starts at {start!r} on {date_iso}")
    block.state = state


def set_block_label(data: PlannerData, date_iso: str, start: str, label: str) -> None:
    day = _materialize(data, date_iso)
    block = _find_day_block(day, start)
    if block is None:
        raise ValidationError(f"no block starts at {start!r} on {date_iso}")
    block.label = label


def history_dates(data: PlannerData) -> list[str]:
    return sorted(data.days.keys())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all day tests, including the history-honesty test).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: day materialization, state and label mutation"
```

### Task 6: Block reference resolver (start hour / HH:MM / row number)

**Files:**
- Modify: `core.py`
- Modify: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_core.py`:

```python
from core import resolve_block_start


def test_resolve_block_start_by_explicit_hhmm():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    assert resolve_block_start(blocks, "09:00") == "09:00"


def test_resolve_block_start_by_bare_hour():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    assert resolve_block_start(blocks, "8") == "08:00"


def test_resolve_block_start_by_row_number_when_no_hour_match():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    # Row 2 is the 09:00 block; "2" is not a start hour here, so it means the row.
    assert resolve_block_start(blocks, "2") == "09:00"


def test_resolve_block_start_prefers_hour_over_row():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    # "8" matches the 08:00 start hour; it must NOT be read as row 8.
    assert resolve_block_start(blocks, "8") == "08:00"


def test_resolve_block_start_unknown_returns_none():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    assert resolve_block_start(blocks, "23:00") is None
    assert resolve_block_start(blocks, "99") is None
    assert resolve_block_start(blocks, "garbage") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_core.py::test_resolve_block_start_by_explicit_hhmm -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_block_start'`.

- [ ] **Step 3: Write minimal implementation**

Add to `core.py`:

```python
def resolve_block_start(blocks: list[DayBlock], ref: str) -> str | None:
    """Resolve a user reference to a block's start time.

    Resolution order (start time wins over row number):
      1. Exact HH:MM match against a block start.
      2. Bare hour (e.g. "8" -> "08:00") match against a block start.
      3. 1-based row number into the (already sorted) blocks list.
    Returns the matched start string, or None if nothing matches.
    """
    starts = [b.start for b in blocks]
    if ref in starts:
        return ref
    if ref.isdigit():
        hhmm = f"{int(ref):02d}:00"
        if hhmm in starts:
            return hhmm
        row = int(ref)
        if 1 <= row <= len(blocks):
            return blocks[row - 1].start
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_core.py -v`
Expected: PASS (all resolver tests).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: block reference resolver (hour/hhmm/row)"
```

---

## Phase 2: Minimal CLI (`cli.py`)

### Task 7: CLI scaffolding and `plan template`

**Files:**
- Create: `cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
def test_template_lists_blocks(run_cli):
    # Seed a block via a separate API/core call is overkill here; use `done` to
    # materialize is not it either — instead seed by writing through the store.
    import json
    from pathlib import Path

    import os
    data_dir = Path(os.environ["PLAN_DATA_DIR"])
    (data_dir / "data.json").write_text(
        json.dumps({
            "version": 2,
            "template": [{"start": "08:00", "end": "09:00", "label": "standup"}],
            "days": {},
        }),
        encoding="utf-8",
    )
    result = run_cli("template")
    assert result.returncode == 0
    assert "08:00" in result.stdout
    assert "standup" in result.stdout


def test_no_command_defaults_to_today(run_cli):
    result = run_cli()
    assert result.returncode == 0
    assert "No blocks" in result.stdout or "Today" in result.stdout
```

Note: the `data_dir` fixture sets `PLAN_DATA_DIR`; reading it back from `os.environ` inside the test keeps the seed self-contained.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `cli.py` does not exist, subprocess returns non-zero / file-not-found.

- [ ] **Step 3: Write minimal implementation**

Create `cli.py`:

```python
"""Minimal CLI for the time-blocking planner (`plan`)."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core import (
    DataStore,
    PlannerData,
    ValidationError,
    get_day_blocks,
    resolve_block_start,
    set_block_state,
)

DEFAULT_DATA_DIR = Path.home() / ".plan"
_STATE_GLYPH = {"pending": "·", "done": "[green]✓[/green]", "skipped": "[red]✗[/red]"}


def _data_dir() -> Path:
    override = os.environ.get("PLAN_DATA_DIR")
    return Path(override) if override else DEFAULT_DATA_DIR


def _load(store: DataStore, err: Console) -> PlannerData:
    def _warn(backup: Path) -> None:
        err.print(
            f"[yellow]Warning:[/yellow] data.json was corrupt; backed up to "
            f"{backup.name}. Starting empty."
        )
    return store.load(on_corrupt=_warn)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan", description="Hourly time-blocking planner")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("today", help="Show today's blocks")
    sub.add_parser("template", help="List the recurring template")
    p_done = sub.add_parser("done", help="Mark a block done today")
    p_done.add_argument("ref", help="start hour (8), start time (08:00), or row number")
    p_skip = sub.add_parser("skip", help="Mark a block skipped today")
    p_skip.add_argument("ref", help="start hour (8), start time (08:00), or row number")
    return parser


def cmd_template(store: DataStore, console: Console, err: Console) -> int:
    data = _load(store, err)
    if not data.template:
        console.print("No template blocks yet. Add them in the web app.")
        return 0
    table = Table(title="Template")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Label")
    for b in data.template:
        table.add_row(b.start, b.end, b.label)
    console.print(table)
    return 0


def cmd_today(store: DataStore, console: Console, err: Console) -> int:
    data = _load(store, err)
    blocks = get_day_blocks(data, date.today().isoformat())
    if not blocks:
        console.print("No blocks for today. Add template blocks in the web app.")
        return 0
    table = Table(title=f"Today ({date.today().isoformat()})")
    table.add_column("#", justify="right")
    table.add_column("Time")
    table.add_column("Block")
    table.add_column("State")
    for i, b in enumerate(blocks, start=1):
        table.add_row(str(i), f"{b.start}-{b.end}", b.label, _STATE_GLYPH[b.state])
    console.print(table)
    return 0


def _mark(store: DataStore, console: Console, err: Console, ref: str, state: str) -> int:
    data = _load(store, err)
    today = date.today().isoformat()
    start = resolve_block_start(get_day_blocks(data, today), ref)
    if start is None:
        err.print(f"No block matches {ref!r}. Run 'plan today' to see blocks.")
        return 1
    try:
        set_block_state(data, today, start, state)
    except ValidationError as e:
        err.print(str(e))
        return 1
    store.save(data)
    console.print(f"Marked {start} {state}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _build_parser().parse_args(argv)
    store = DataStore(_data_dir())
    console = Console()
    err = Console(stderr=True)

    command = args.command or "today"
    if command == "today":
        return cmd_today(store, console, err)
    if command == "template":
        return cmd_template(store, console, err)
    if command == "done":
        return _mark(store, console, err, args.ref, "done")
    if command == "skip":
        return _mark(store, console, err, args.ref, "skipped")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_cli.py
git commit -m "feat: minimal plan CLI with today and template"
```

### Task 8: CLI `done` / `skip` marking

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli.py`:

```python
import json
import os
from pathlib import Path


def _seed_template(block_label="standup"):
    data_dir = Path(os.environ["PLAN_DATA_DIR"])
    (data_dir / "data.json").write_text(
        json.dumps({
            "version": 2,
            "template": [
                {"start": "08:00", "end": "09:00", "label": block_label},
                {"start": "09:00", "end": "10:00", "label": "code"},
            ],
            "days": {},
        }),
        encoding="utf-8",
    )
    return data_dir


def test_done_by_bare_hour_marks_and_persists(run_cli):
    data_dir = _seed_template()
    result = run_cli("done", "8")
    assert result.returncode == 0
    saved = json.loads((data_dir / "data.json").read_text(encoding="utf-8"))
    block = saved["days"][__import__("datetime").date.today().isoformat()]["blocks"][0]
    assert block["state"] == "done"


def test_skip_by_row_number(run_cli):
    data_dir = _seed_template()
    result = run_cli("skip", "2")  # row 2 -> 09:00
    assert result.returncode == 0
    today = __import__("datetime").date.today().isoformat()
    saved = json.loads((data_dir / "data.json").read_text(encoding="utf-8"))
    states = {b["start"]: b["state"] for b in saved["days"][today]["blocks"]}
    assert states["09:00"] == "skipped"
    assert states["08:00"] == "pending"


def test_done_unknown_ref_errors(run_cli):
    _seed_template()
    result = run_cli("done", "23:00")
    assert result.returncode == 1
    assert "No block matches" in result.stderr
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (5 tests total). The marking logic already exists from Task 7.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "test: CLI done/skip by hour and row number"
```

---

## Phase 3: FastAPI backend (`api.py`)

### Task 9: API app, template read/create endpoints

**Files:**
- Create: `api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client(data_dir):
    # data_dir sets PLAN_DATA_DIR; api reads it per-request via the store dependency.
    return TestClient(app)


def test_template_starts_empty(client):
    resp = client.get("/api/template")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_template_block_then_list(client):
    resp = client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    assert resp.status_code == 201
    assert resp.json()["start"] == "08:00"

    listed = client.get("/api/template").json()
    assert [b["start"] for b in listed] == ["08:00"]


def test_create_overlapping_block_returns_400(client):
    client.post("/api/template", json={"start": "08:00", "end": "10:00", "label": "a"})
    resp = client.post("/api/template", json={"start": "09:00", "end": "11:00", "label": "b"})
    assert resp.status_code == 400
    assert "overlap" in resp.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'api'`.

- [ ] **Step 3: Write minimal implementation**

Create `api.py`:

```python
"""FastAPI JSON backend over the planner core."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import (
    DataStore,
    ValidationError,
    add_template_block,
    edit_template_block,
    get_day_blocks,
    history_dates,
    remove_template_block,
    set_block_label,
    set_block_state,
)

DEFAULT_DATA_DIR = Path.home() / ".plan"

app = FastAPI(title="Time-Blocking Planner")


def _store() -> DataStore:
    override = os.environ.get("PLAN_DATA_DIR")
    return DataStore(Path(override) if override else DEFAULT_DATA_DIR)


class BlockIn(BaseModel):
    start: str
    end: str
    label: str


class BlockEdit(BaseModel):
    new_start: str
    new_end: str
    label: str


class MarkIn(BaseModel):
    state: str | None = None
    label: str | None = None


@app.get("/api/template")
def list_template() -> list[dict]:
    return [asdict(b) for b in _store().load().template]


@app.post("/api/template", status_code=201)
def create_template_block(block: BlockIn) -> dict:
    store = _store()
    data = store.load()
    try:
        created = add_template_block(data, block.start, block.end, block.label)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return asdict(created)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat: FastAPI app with template list/create"
```

### Task 10: API template edit/delete endpoints

**Files:**
- Modify: `api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_edit_template_block(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.put(
        "/api/template/08:00",
        json={"new_start": "08:30", "new_end": "09:00", "label": "renamed"},
    )
    assert resp.status_code == 200
    starts = [b["start"] for b in client.get("/api/template").json()]
    assert starts == ["08:30"]


def test_edit_missing_block_returns_404(client):
    resp = client.put(
        "/api/template/08:00",
        json={"new_start": "08:00", "new_end": "09:00", "label": "x"},
    )
    assert resp.status_code == 404


def test_delete_template_block(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    assert client.delete("/api/template/08:00").status_code == 204
    assert client.get("/api/template").json() == []


def test_delete_missing_block_returns_404(client):
    assert client.delete("/api/template/08:00").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_edit_template_block -v`
Expected: FAIL — 405/404 (route not defined).

- [ ] **Step 3: Write minimal implementation**

Add to `api.py`:

```python
from fastapi import Response

from core import find_template_block


@app.put("/api/template/{start}")
def update_template_block(start: str, edit: BlockEdit) -> dict:
    store = _store()
    data = store.load()
    if find_template_block(data, start) is None:
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    try:
        updated = edit_template_block(
            data, start, new_start=edit.new_start, new_end=edit.new_end, label=edit.label
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return asdict(updated)


@app.delete("/api/template/{start}", status_code=204)
def delete_template_block(start: str) -> Response:
    store = _store()
    data = store.load()
    if not remove_template_block(data, start):
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    store.save(data)
    return Response(status_code=204)
```

Move the `find_template_block` import up into the existing `from core import (...)` block instead of a separate line if you prefer; either works.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat: API template edit/delete endpoints"
```

### Task 11: API day read/mark and history endpoints

**Files:**
- Modify: `api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_api.py`:

```python
def test_get_day_renders_from_template_as_pending(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.get("/api/days/2026-05-24")
    assert resp.status_code == 200
    blocks = resp.json()["blocks"]
    assert blocks[0]["state"] == "pending"
    assert blocks[0]["label"] == "standup"


def test_mark_block_state(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "done"})
    assert resp.status_code == 200
    blocks = client.get("/api/days/2026-05-24").json()["blocks"]
    assert blocks[0]["state"] == "done"


def test_mark_block_label_override(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    client.post("/api/days/2026-05-24/blocks/08:00", json={"label": "fixed bug"})
    blocks = client.get("/api/days/2026-05-24").json()["blocks"]
    assert blocks[0]["label"] == "fixed bug"


def test_mark_bad_state_returns_400(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "maybe"})
    assert resp.status_code == 400


def test_mark_unknown_block_returns_404(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/11:00", json={"state": "done"})
    assert resp.status_code == 404


def test_history_lists_touched_days(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "done"})
    assert client.get("/api/days").json() == ["2026-05-24"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_get_day_renders_from_template_as_pending -v`
Expected: FAIL — route not defined (404/405).

- [ ] **Step 3: Write minimal implementation**

Add to `api.py`. Import `get_day_blocks`, `history_dates`, `set_block_label`, `set_block_state` are already imported in Task 9.

```python
@app.get("/api/days")
def list_history() -> list[str]:
    return history_dates(_store().load())


@app.get("/api/days/{date_iso}")
def get_day(date_iso: str) -> dict:
    blocks = get_day_blocks(_store().load(), date_iso)
    return {"date": date_iso, "blocks": [asdict(b) for b in blocks]}


@app.post("/api/days/{date_iso}/blocks/{start}")
def mark_block(date_iso: str, start: str, mark: MarkIn) -> dict:
    store = _store()
    data = store.load()
    # Validate the block exists for this day before mutating.
    if all(b.start != start for b in get_day_blocks(data, date_iso)):
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    try:
        if mark.state is not None:
            set_block_state(data, date_iso, start, mark.state)
        if mark.label is not None:
            set_block_label(data, date_iso, start, mark.label)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    blocks = get_day_blocks(data, date_iso)
    return {"date": date_iso, "blocks": [asdict(b) for b in blocks]}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS (13 tests).

- [ ] **Step 5: Run the full Python suite**

Run: `pytest -v`
Expected: PASS — all of `test_core.py`, `test_cli.py`, `test_api.py`.

- [ ] **Step 6: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat: API day read/mark/history endpoints"
```

### Task 12: CORS for the Vite dev server

**Files:**
- Modify: `api.py`

- [ ] **Step 1: Add CORS middleware**

Add near the top of `api.py`, right after `app = FastAPI(...)`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

(5173 is Vite's default dev port. The production build is served same-origin, but the dev server needs this.)

- [ ] **Step 2: Verify the app still imports and tests pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS (still 13 tests).

- [ ] **Step 3: Commit**

```bash
git add api.py
git commit -m "feat: enable CORS for the Vite dev server"
```

---

## Phase 4: React/Vite SPA (`web/`)

Frontend lives in `web/` with its own `package.json`. Vite proxies `/api` to the backend in dev, so the client always calls relative `/api/...` URLs.

### Task 13: Scaffold the Vite React app

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.js`
- Create: `web/index.html`
- Create: `web/src/main.jsx`
- Create: `web/.gitignore`

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "planner-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^15.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    "jsdom": "^24.0.0",
    "vite": "^5.2.0",
    "vitest": "^1.5.0"
  }
}
```

- [ ] **Step 2: Create `web/vite.config.js`**

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
  },
});
```

- [ ] **Step 3: Create `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Time-Blocking Planner</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Create `web/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5: Create `web/.gitignore`**

```
node_modules/
dist/
```

- [ ] **Step 6: Install and verify the toolchain**

Run: `cd web && npm install`
Expected: installs without error, creates `web/node_modules`.

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/vite.config.js web/index.html web/src/main.jsx web/.gitignore
git commit -m "chore: scaffold Vite React web app"
```

### Task 14: API client module

**Files:**
- Create: `web/src/api.js`
- Create: `web/src/test-setup.js`
- Test: `web/src/api.test.js`

- [ ] **Step 1: Write the failing test**

Create `web/src/test-setup.js`:

```javascript
import "@testing-library/jest-dom";
```

Create `web/src/api.test.js`:

```javascript
import { afterEach, expect, test, vi } from "vitest";
import { getDay, markBlock } from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("getDay fetches the day endpoint", async () => {
  const payload = { date: "2026-05-24", blocks: [] };
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(payload),
  });
  const result = await getDay("2026-05-24");
  expect(global.fetch).toHaveBeenCalledWith("/api/days/2026-05-24");
  expect(result).toEqual(payload);
});

test("markBlock POSTs state to the block endpoint", async () => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ date: "2026-05-24", blocks: [] }),
  });
  await markBlock("2026-05-24", "08:00", { state: "done" });
  expect(global.fetch).toHaveBeenCalledWith(
    "/api/days/2026-05-24/blocks/08:00",
    expect.objectContaining({ method: "POST" })
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot resolve `./api.js`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/api.js`:

```javascript
async function request(url, options) {
  const resp = await fetch(url, options);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      detail = (await resp.json()).detail ?? detail;
    } catch {
      // non-JSON error body; keep statusText
    }
    throw new Error(detail);
  }
  if (resp.status === 204) return null;
  return resp.json();
}

const jsonPost = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getTemplate = () => request("/api/template");

export const addTemplateBlock = (block) =>
  request("/api/template", jsonPost(block));

export const editTemplateBlock = (start, edit) =>
  request(`/api/template/${start}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edit),
  });

export const deleteTemplateBlock = (start) =>
  request(`/api/template/${start}`, { method: "DELETE" });

export const getDay = (date) => request(`/api/days/${date}`);

export const getHistory = () => request("/api/days");

export const markBlock = (date, start, mark) =>
  request(`/api/days/${date}/blocks/${start}`, jsonPost(mark));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/api.js web/src/api.test.js web/src/test-setup.js
git commit -m "feat: web API client with tests"
```

### Task 15: Day view components and state toggles

**Files:**
- Create: `web/src/BlockRow.jsx`
- Create: `web/src/DayView.jsx`
- Create: `web/src/styles.css`
- Test: `web/src/BlockRow.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/BlockRow.test.jsx`:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import BlockRow from "./BlockRow.jsx";

const block = { start: "08:00", end: "09:00", label: "standup", state: "pending" };

test("renders time range and label", () => {
  render(<BlockRow block={block} onMark={() => {}} />);
  expect(screen.getByText("08:00–09:00")).toBeInTheDocument();
  expect(screen.getByText("standup")).toBeInTheDocument();
});

test("Done button calls onMark with done state", () => {
  const onMark = vi.fn();
  render(<BlockRow block={block} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "done" });
});

test("clicking Done on an already-done block resets it to pending", () => {
  const onMark = vi.fn();
  render(<BlockRow block={{ ...block, state: "done" }} onMark={onMark} />);
  fireEvent.click(screen.getByRole("button", { name: /done/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { state: "pending" });
});
```

(This encodes the decision: clicking the current state toggles back to pending.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot resolve `./BlockRow.jsx`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/BlockRow.jsx`:

```jsx
import { useState } from "react";

export default function BlockRow({ block, onMark }) {
  const [editing, setEditing] = useState(false);
  const [label, setLabel] = useState(block.label);

  const toggle = (target) =>
    onMark(block.start, { state: block.state === target ? "pending" : target });

  const submitLabel = () => {
    setEditing(false);
    if (label !== block.label) onMark(block.start, { label });
  };

  return (
    <div className={`block block--${block.state}`}>
      <span className="block__time">
        {block.start}–{block.end}
      </span>
      {editing ? (
        <input
          className="block__label-input"
          value={label}
          autoFocus
          onChange={(e) => setLabel(e.target.value)}
          onBlur={submitLabel}
          onKeyDown={(e) => e.key === "Enter" && submitLabel()}
        />
      ) : (
        <span className="block__label" onClick={() => setEditing(true)}>
          {block.label}
        </span>
      )}
      <span className="block__actions">
        <button
          aria-pressed={block.state === "done"}
          onClick={() => toggle("done")}
        >
          Done
        </button>
        <button
          aria-pressed={block.state === "skipped"}
          onClick={() => toggle("skipped")}
        >
          Skip
        </button>
      </span>
    </div>
  );
}
```

Create `web/src/DayView.jsx`:

```jsx
import { useEffect, useState } from "react";
import { getDay, markBlock } from "./api.js";
import BlockRow from "./BlockRow.jsx";

function shiftDate(iso, days) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function DayView() {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState(today);
  const [blocks, setBlocks] = useState([]);
  const [error, setError] = useState(null);

  const refresh = (d) =>
    getDay(d)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => setError(e.message));

  useEffect(() => {
    refresh(date);
  }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark)
      .then((day) => setBlocks(day.blocks))
      .catch((e) => setError(e.message));

  return (
    <section className="day">
      <header className="day__nav">
        <button onClick={() => setDate(shiftDate(date, -1))}>←</button>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
        <button onClick={() => setDate(shiftDate(date, 1))}>→</button>
      </header>
      {error && <p className="error">{error}</p>}
      {blocks.length === 0 ? (
        <p>No blocks. Add some in the Template tab.</p>
      ) : (
        blocks.map((b) => <BlockRow key={b.start} block={b} onMark={onMark} />)
      )}
    </section>
  );
}
```

Create `web/src/styles.css`:

```css
body { font-family: system-ui, sans-serif; margin: 0; background: #f6f7f9; }
.app { max-width: 720px; margin: 0 auto; padding: 1.5rem; }
.app__tabs button { margin-right: .5rem; padding: .4rem .8rem; }
.app__tabs button.active { font-weight: 700; }
.day__nav { display: flex; gap: .5rem; align-items: center; margin: 1rem 0; }
.block {
  display: flex; align-items: center; gap: 1rem;
  padding: .6rem .8rem; margin-bottom: .4rem; border-radius: 8px;
  border-left: 6px solid #bbb; background: #fff;
}
.block--done { border-left-color: #2e9e4f; }
.block--skipped { border-left-color: #d23b3b; }
.block--pending { border-left-color: #bbb; }
.block__time { font-variant-numeric: tabular-nums; color: #555; min-width: 110px; }
.block__label { flex: 1; cursor: text; }
.block__actions button { margin-left: .4rem; }
.block__actions button[aria-pressed="true"] { background: #222; color: #fff; }
.error { color: #d23b3b; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS (BlockRow + api tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/BlockRow.jsx web/src/DayView.jsx web/src/styles.css web/src/BlockRow.test.jsx
git commit -m "feat: day view with done/skip toggles and label override"
```

### Task 16: Template editor component

**Files:**
- Create: `web/src/TemplateEditor.jsx`
- Test: `web/src/TemplateEditor.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/TemplateEditor.test.jsx`:

```jsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import TemplateEditor from "./TemplateEditor.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("lists existing template blocks", async () => {
  vi.spyOn(api, "getTemplate").mockResolvedValue([
    { start: "08:00", end: "09:00", label: "standup" },
  ]);
  render(<TemplateEditor />);
  await waitFor(() => expect(screen.getByText("standup")).toBeInTheDocument());
  expect(screen.getByText(/08:00/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot resolve `./TemplateEditor.jsx`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/TemplateEditor.jsx`:

```jsx
import { useEffect, useState } from "react";
import {
  addTemplateBlock,
  deleteTemplateBlock,
  getTemplate,
} from "./api.js";

export default function TemplateEditor() {
  const [blocks, setBlocks] = useState([]);
  const [form, setForm] = useState({ start: "", end: "", label: "" });
  const [error, setError] = useState(null);

  const refresh = () =>
    getTemplate()
      .then(setBlocks)
      .catch((e) => setError(e.message));

  useEffect(() => {
    refresh();
  }, []);

  const submit = (e) => {
    e.preventDefault();
    setError(null);
    addTemplateBlock(form)
      .then(() => {
        setForm({ start: "", end: "", label: "" });
        refresh();
      })
      .catch((err) => setError(err.message));
  };

  const remove = (start) =>
    deleteTemplateBlock(start)
      .then(refresh)
      .catch((e) => setError(e.message));

  return (
    <section className="template">
      <h2>Template</h2>
      {error && <p className="error">{error}</p>}
      <ul className="template__list">
        {blocks.map((b) => (
          <li key={b.start}>
            <span>
              {b.start}–{b.end} · {b.label}
            </span>
            <button onClick={() => remove(b.start)}>Remove</button>
          </li>
        ))}
      </ul>
      <form onSubmit={submit} className="template__form">
        <input
          type="time"
          aria-label="start"
          value={form.start}
          onChange={(e) => setForm({ ...form, start: e.target.value })}
          required
        />
        <input
          type="time"
          aria-label="end"
          value={form.end}
          onChange={(e) => setForm({ ...form, end: e.target.value })}
          required
        />
        <input
          type="text"
          aria-label="label"
          placeholder="label"
          value={form.label}
          onChange={(e) => setForm({ ...form, label: e.target.value })}
          required
        />
        <button type="submit">Add</button>
      </form>
    </section>
  );
}
```

Note: `<input type="time">` yields `HH:MM` (zero-padded), matching the core's format.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/TemplateEditor.jsx web/src/TemplateEditor.test.jsx
git commit -m "feat: template editor component"
```

### Task 17: App shell with tab navigation

**Files:**
- Create: `web/src/App.jsx`
- Test: `web/src/App.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/App.test.jsx`:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "./App.jsx";
import * as api from "./api.js";

afterEach(() => vi.restoreAllMocks());

test("shows the day view by default and switches to template", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({ date: "2026-05-24", blocks: [] });
  vi.spyOn(api, "getTemplate").mockResolvedValue([]);
  render(<App />);
  expect(screen.getByRole("button", { name: /day/i })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /template/i }));
  expect(screen.getByRole("heading", { name: /template/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`
Expected: FAIL — cannot resolve `./App.jsx`.

- [ ] **Step 3: Write minimal implementation**

Create `web/src/App.jsx`:

```jsx
import { useState } from "react";
import DayView from "./DayView.jsx";
import TemplateEditor from "./TemplateEditor.jsx";

export default function App() {
  const [tab, setTab] = useState("day");
  return (
    <div className="app">
      <h1>Time-Blocking Planner</h1>
      <nav className="app__tabs">
        <button
          className={tab === "day" ? "active" : ""}
          onClick={() => setTab("day")}
        >
          Day
        </button>
        <button
          className={tab === "template" ? "active" : ""}
          onClick={() => setTab("template")}
        >
          Template
        </button>
      </nav>
      {tab === "day" ? <DayView /> : <TemplateEditor />}
    </div>
  );
}
```

- [ ] **Step 4: Run the full web suite**

Run: `cd web && npm test`
Expected: PASS — `api.test.js`, `BlockRow.test.jsx`, `TemplateEditor.test.jsx`, `App.test.jsx`.

- [ ] **Step 5: Verify the production build compiles**

Run: `cd web && npm run build`
Expected: Vite build completes, writes `web/dist/` without errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/App.jsx web/src/App.test.jsx
git commit -m "feat: app shell with day/template tabs"
```

---

## Phase 5: End-to-end verification

### Task 18: Manual smoke test and README check

**Files:** none (verification only)

- [ ] **Step 1: Run the entire Python test suite**

Run: `pytest -v`
Expected: PASS — all core, CLI, and API tests.

- [ ] **Step 2: Run the entire web test suite**

Run: `cd web && npm test`
Expected: PASS — all component and client tests.

- [ ] **Step 3: Manual end-to-end smoke test**

In one terminal: `uvicorn api:app --reload`
In another: `cd web && npm run dev`, then open `http://localhost:5173`.

Verify by hand:
1. Template tab → add a block `08:00`–`09:00` "standup". It appears in the list.
2. Adding an overlapping block `08:30`–`09:30` shows the error message (no crash).
3. Day tab → the `08:00` block shows as pending. Click **Done** → turns green. Click **Done** again → back to pending. Click **Skip** → turns red.
4. Click the label, edit it, press Enter → the override persists after navigating away and back via the date arrows.
5. In a terminal: `plan today` shows the block with its state; `plan done 8` marks it; reloading the web Day view reflects it.

- [ ] **Step 4: Confirm the data file location**

Run: `plan template`
Expected: lists the block you added in the web app, proving CLI and web share `~/.plan/data.json` (or `$PLAN_DATA_DIR`).

- [ ] **Step 5: Final commit (if any docs tweaks were needed)**

```bash
git add -A
git commit -m "docs: verify end-to-end planner workflow"
```
