"""Pure logic for the habit tracker: storage, streaks, mutations."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
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
