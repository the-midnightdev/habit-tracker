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
