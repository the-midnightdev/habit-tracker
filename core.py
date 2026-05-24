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
TAGS = ("Deep work", "Break", "Shallow")

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


def validate_tag(tag: str | None) -> None:
    if tag is not None and tag not in TAGS:
        raise ValidationError(f"unknown tag {tag!r}; expected one of {TAGS} or null")


@dataclass
class TemplateBlock:
    start: str
    end: str
    label: str
    tag: str | None = None


@dataclass
class DayBlock:
    """A rendered block for a given day (template fields + resolved state/label)."""
    start: str
    end: str
    label: str
    state: str = "pending"
    tag: str | None = None


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
            if not day.overrides:
                continue  # don't persist empty days (defensive; _prune removes them)
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


def add_template_block(
    data: PlannerData, start: str, end: str, label: str, tag: str | None = None
) -> TemplateBlock:
    _check_template_slot(data, start, end)
    validate_tag(tag)
    block = TemplateBlock(start=start, end=end, label=label, tag=tag)
    data.template.append(block)
    data.template.sort(key=lambda b: b.start)
    return block


def edit_template_block(
    data: PlannerData, start: str, *, new_start: str, new_end: str,
    label: str, tag: str | None = None
) -> TemplateBlock:
    block = find_template_block(data, start)
    if block is None:
        raise ValidationError(f"no template block starts at {start!r}")
    _check_template_slot(data, new_start, new_end, ignore_start=start)
    validate_tag(tag)
    block.start, block.end, block.label, block.tag = new_start, new_end, label, tag
    data.template.sort(key=lambda b: b.start)
    return block


def remove_template_block(data: PlannerData, start: str) -> bool:
    block = find_template_block(data, start)
    if block is None:
        return False
    data.template.remove(block)
    return True


def get_day_blocks(data: PlannerData, date_iso: str) -> list[DayBlock]:
    """Render a day from the CURRENT template, applying that day's overrides.

    Overrides whose start is no longer in the template are inert (ignored).
    Reading never mutates `data`.
    """
    overrides = data.days[date_iso].overrides if date_iso in data.days else {}
    blocks = []
    for tb in data.template:
        ov = overrides.get(tb.start)
        state = ov.state if ov is not None else "pending"
        label = ov.label if (ov is not None and ov.label is not None) else tb.label
        blocks.append(DayBlock(start=tb.start, end=tb.end, label=label,
                               state=state, tag=tb.tag))
    return blocks


def _require_template_start(data: PlannerData, start: str) -> None:
    if find_template_block(data, start) is None:
        raise ValidationError(f"no template block starts at {start!r}")


def _override(data: PlannerData, date_iso: str, start: str) -> Override:
    day = data.days.setdefault(date_iso, Day())
    return day.overrides.setdefault(start, Override())


def _prune(data: PlannerData, date_iso: str, start: str) -> None:
    day = data.days.get(date_iso)
    if day is None:
        return
    ov = day.overrides.get(start)
    if ov is not None and ov.state == "pending" and ov.label is None:
        del day.overrides[start]
    if not day.overrides:
        data.days.pop(date_iso, None)


def set_block_state(data: PlannerData, date_iso: str, start: str, state: str) -> None:
    if state not in STATES:
        raise ValidationError(f"unknown state {state!r}; expected one of {STATES}")
    _require_template_start(data, start)
    _override(data, date_iso, start).state = state
    _prune(data, date_iso, start)


def set_block_label(data: PlannerData, date_iso: str, start: str, label: str) -> None:
    _require_template_start(data, start)
    _override(data, date_iso, start).label = label


def history_dates(data: PlannerData) -> list[str]:
    return sorted(d for d, day in data.days.items() if day.overrides)


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
