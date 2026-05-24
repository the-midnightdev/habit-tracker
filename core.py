"""Pure logic for the time-blocking planner: storage, template, days, state."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DATA_FILENAME = "data.json"
SCHEMA_VERSION = 3
STATES = ("pending", "done", "skipped")

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ValidationError(ValueError):
    """Raised when a block fails validation (format, ordering, overlap, duplicate)."""


def validate_times(start: str, end: str) -> None:
    """Raise ValidationError unless start and end are HH:MM and start < end."""
    for value in (start, end):
        if not _TIME_RE.match(value):
            raise ValidationError(f"invalid time {value!r}; expected HH:MM (24h)")
    if start >= end:
        raise ValidationError(f"start {start!r} must be before end {end!r}")


@dataclass
class TemplateBlock:
    start: str
    end: str
    label: str


@dataclass
class DayBlock:
    """A rendered block for a given day (template fields + resolved state/label)."""
    start: str
    end: str
    label: str
    state: str = "pending"


@dataclass
class Override:
    """A per-day deviation for one block, keyed externally by start time."""
    state: str = "pending"
    label: str | None = None


@dataclass
class Day:
    overrides: dict[str, Override] = field(default_factory=dict)


@dataclass
class PlannerData:
    template: list[TemplateBlock] = field(default_factory=list)
    days: dict[str, Day] = field(default_factory=dict)


def _migrate_v2_days(raw_days: dict, template: list[TemplateBlock]) -> dict[str, Day]:
    """Convert v2 day snapshots to v3 overrides: keep a block only if it has a
    non-pending state or a label that differs from the current template default."""
    template_by_start = {b.start: b for b in template}
    days: dict[str, Day] = {}
    for date_iso, day in raw_days.items():
        overrides: dict[str, Override] = {}
        for blk in day.get("blocks", []):
            start = blk["start"]
            state = blk.get("state", "pending")
            label = blk.get("label")
            tb = template_by_start.get(start)
            keep_label = tb is not None and label is not None and label != tb.label
            if state != "pending" or keep_label:
                overrides[start] = Override(
                    state=state, label=label if keep_label else None
                )
        if overrides:
            days[date_iso] = Day(overrides=overrides)
    return days


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
            version = raw.get("version")
            template = [TemplateBlock(**b) for b in raw["template"]]
            if version == SCHEMA_VERSION:
                days = {
                    d: Day(overrides={
                        start: Override(**ov) for start, ov in day["overrides"].items()
                    })
                    for d, day in raw["days"].items()
                }
            elif version == 2:
                days = _migrate_v2_days(raw["days"], template)
            else:
                raise ValueError(f"unsupported schema version: {version!r}")
            return PlannerData(template=template, days=days)
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            backup = self._backup_corrupt()
            if on_corrupt is not None:
                on_corrupt(backup)
            return PlannerData()

    def save(self, data: PlannerData) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        days_payload = {}
        for d, day in data.days.items():
            overrides = {}
            for start, ov in day.overrides.items():
                entry = {"state": ov.state}
                if ov.label is not None:
                    entry["label"] = ov.label
                overrides[start] = entry
            days_payload[d] = {"overrides": overrides}
        payload = {
            "version": SCHEMA_VERSION,
            "template": [asdict(b) for b in data.template],
            "days": days_payload,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _backup_corrupt(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = self.path.with_name(f"{DATA_FILENAME}.corrupt-{timestamp}")
        self.path.rename(backup)
        return backup


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


def _blocks_from_template(data: PlannerData) -> list[DayBlock]:
    return [
        DayBlock(start=b.start, end=b.end, label=b.label, state="pending")
        for b in data.template
    ]


def get_day_blocks(data: PlannerData, date_iso: str) -> list[DayBlock]:
    """Return the day's blocks: the stored copy if touched, else a live template view."""
    day = data.days.get(date_iso)
    if day is not None:
        # Return a copy so callers can't mutate the stored ("frozen") day in place,
        # matching the fresh-list behaviour of the untouched-day path below.
        return list(day.blocks)
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
