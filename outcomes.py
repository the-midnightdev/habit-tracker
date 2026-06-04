"""Pure, on-demand insights engine for Outcomes. No IO, no globals mutated."""
from __future__ import annotations

from datetime import date, timedelta

from core import PlannerData, Outcome, linked_blocks

WEEKS = 6
MIN_DAYS = 14
MIN_COMPLETIONS = 10
MIN_STRENGTH = 0.3       # |pearson r| needed to surface a signal
LAGS = (0, 1, 2)


def trailing_window(today: date, weeks: int = WEEKS) -> tuple[date, date]:
    return today - timedelta(days=weeks * 7 - 1), today


def _dates_in(start: date, end: date):
    d = start
    while d <= end:
        yield d.isoformat()
        d += timedelta(days=1)


def _shift(date_iso: str, days: int) -> str:
    return (date.fromisoformat(date_iso) + timedelta(days=days)).isoformat()


def _min_of(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def block_done(data: PlannerData, date_iso: str, start: str) -> bool:
    day = data.days.get(date_iso)
    if day is None:
        return False
    ov = day.overrides.get(start)
    return ov is not None and ov.state == "done"


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = _mean(xs), _mean(ys)
    sx = sum((x - mx) ** 2 for x in xs)
    sy = sum((y - my) ** 2 for y in ys)
    if sx == 0 or sy == 0:        # zero variance -> no signal
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / ((sx ** 0.5) * (sy ** 0.5))


def _ratings_by_date(data: PlannerData, outcome: Outcome, start: date, end: date) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in _dates_in(start, end):
        day = data.days.get(d)
        if day is not None:
            ci = day.outcome_checkins.get(outcome.id)
            if ci is not None:
                out[d] = ci.rating
    return out


def confidence(data: PlannerData, outcome: Outcome, today: date) -> dict:
    start, end = trailing_window(today)
    ratings = _ratings_by_date(data, outcome, start, end)
    blocks = linked_blocks(data, outcome)
    completions = sum(
        1 for d in _dates_in(start, end) for b in blocks if block_done(data, d, b.start)
    )
    days_checked = len(ratings)
    return {
        "daysChecked": days_checked,
        "completions": completions,
        "ready": days_checked >= MIN_DAYS and completions >= MIN_COMPLETIONS,
    }
