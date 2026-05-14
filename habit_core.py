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
