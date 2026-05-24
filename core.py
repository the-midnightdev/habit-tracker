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
