"""Pure, on-demand insights engine for Outcomes. No IO, no globals mutated."""
from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class Signal:
    kind: str            # block_daily | late_end_daily | duration_daily | dow_daily
                         # | block_weekly | morning_weekly | afternoon_weekly | evening_weekly
    label: str
    lag: int
    threshold: float     # group-split boundary used for phrasing
    mean_delta: float    # mean(rating | high group) - mean(rating | low group)
    strength: float      # |pearson r|
    n: int
    block_id: str | None


def _split_delta(pairs: list[tuple[float, float]]) -> tuple[float, float] | None:
    """Split pairs at mean(x); return (mean_delta, min-x-of-high-group)."""
    mx = _mean([x for x, _ in pairs])
    high = [y for x, y in pairs if x > mx]
    low = [y for x, y in pairs if x <= mx]
    if not high or not low:
        return None
    threshold = min(x for x, _ in pairs if x > mx)
    return _mean(high) - _mean(low), threshold


def _signal(kind, label, lag, block_id, pairs) -> Signal | None:
    r = pearson([x for x, _ in pairs], [y for _, y in pairs])
    if r is None:
        return None
    if abs(r) < MIN_STRENGTH:
        return None
    sd = _split_delta(pairs)
    if sd is None:
        return None
    delta, threshold = sd
    return Signal(kind=kind, label=label, lag=lag, threshold=threshold,
                  mean_delta=delta, strength=abs(r), n=len(pairs), block_id=block_id)


def _latest_end(data: PlannerData, date_iso: str, blocks) -> float:
    ends = [_min_of(b.end) for b in blocks if block_done(data, date_iso, b.start)]
    return float(max(ends)) if ends else 0.0


def _iso_week(date_iso: str):
    return date.fromisoformat(date_iso).isocalendar()[:2]


WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _weekday(date_iso: str) -> int:
    return date.fromisoformat(date_iso).weekday()


def _duration_done(data: PlannerData, date_iso: str, blocks) -> float:
    return float(sum(_min_of(b.end) - _min_of(b.start)
                     for b in blocks if block_done(data, date_iso, b.start)))


def _weekly_pairs(dates, ratings, counter) -> list[tuple[float, float]]:
    weeks: dict = {}
    for d in dates:
        w = weeks.setdefault(_iso_week(d), {"ratings": [], "count": 0})
        if d in ratings:
            w["ratings"].append(ratings[d])
        w["count"] += counter(d)
    return [(float(w["count"]), _mean(w["ratings"])) for w in weeks.values() if w["ratings"]]


def candidate_signals(data: PlannerData, outcome: Outcome, today: date) -> list[Signal]:
    start, end = trailing_window(today)
    ratings = _ratings_by_date(data, outcome, start, end)
    rating_days = sorted(ratings)
    if not rating_days:
        return []
    blocks = linked_blocks(data, outcome)
    all_dates = list(_dates_in(start, end))
    signals: list[Signal] = []

    # Daily: per-block adherence at lags 0/1/2.
    for b in blocks:
        for lag in LAGS:
            pairs = [
                (1.0 if block_done(data, _shift(d, -lag), b.start) else 0.0, float(ratings[d]))
                for d in rating_days
            ]
            s = _signal("block_daily", b.label, lag, b.id, pairs)
            if s:
                signals.append(s)

    # Daily: latest honored end-time at lags 0/1/2.
    for lag in LAGS:
        pairs = [(_latest_end(data, _shift(d, -lag), blocks), float(ratings[d])) for d in rating_days]
        s = _signal("late_end_daily", "blocks ending late", lag, None, pairs)
        if s:
            signals.append(s)

    # Weekly: per-block completion frequency vs weekly mean rating.
    for b in blocks:
        pairs = _weekly_pairs(all_dates, ratings, lambda d, b=b: 1 if block_done(data, d, b.start) else 0)
        s = _signal("block_weekly", b.label, 0, b.id, pairs)
        if s:
            signals.append(s)

    # Weekly: morning linked-block completions vs weekly mean rating.
    morning = [b for b in blocks if _min_of(b.start) < 12 * 60]
    if morning:
        pairs = _weekly_pairs(
            all_dates, ratings,
            lambda d: sum(1 for b in morning if block_done(data, d, b.start)),
        )
        s = _signal("morning_weekly", "morning blocks", 0, None, pairs)
        if s:
            signals.append(s)

    # Weekly: afternoon / evening linked-block completions vs weekly mean rating.
    for bucket_name, lo, hi in (("afternoon", 12 * 60, 17 * 60), ("evening", 17 * 60, 24 * 60)):
        bucket = [b for b in blocks if lo <= _min_of(b.start) < hi]
        if bucket:
            pairs = _weekly_pairs(
                all_dates, ratings,
                lambda d, bucket=bucket: sum(1 for b in bucket if block_done(data, d, b.start)),
            )
            s = _signal(f"{bucket_name}_weekly", f"{bucket_name} blocks", 0, None, pairs)
            if s:
                signals.append(s)

    # Daily: total honored block-duration (minutes) at lags 0/1/2.
    for lag in LAGS:
        pairs = [(_duration_done(data, _shift(d, -lag), blocks), float(ratings[d])) for d in rating_days]
        s = _signal("duration_daily", "block time", lag, None, pairs)
        if s:
            signals.append(s)

    # Daily: day-of-week effect (one binary feature per weekday present in the data).
    for wd in sorted({_weekday(d) for d in rating_days}):
        pairs = [(1.0 if _weekday(d) == wd else 0.0, float(ratings[d])) for d in rating_days]
        s = _signal("dow_daily", WEEKDAYS[wd], 0, None, pairs)
        if s:
            signals.append(s)

    return signals


def select_signal(signals: list[Signal]) -> Signal | None:
    eligible = [s for s in signals if s.strength >= MIN_STRENGTH and s.n >= 3]
    if not eligible:
        return None
    return max(eligible, key=lambda s: (s.strength, s.n))


def _when(s: Signal) -> str:
    if s.kind == "block_daily":
        return (f"on days you completed {s.label}" if s.lag == 0
                else f"the day after you completed {s.label}")
    if s.kind == "block_weekly":
        return f"on weeks with {int(s.threshold)}+ {s.label}"
    if s.kind == "morning_weekly":
        return f"on weeks with {int(s.threshold)}+ morning blocks"
    if s.kind == "late_end_daily":
        hh = int(s.threshold) // 60
        return f"on days with blocks ending after {hh:02d}:00"
    if s.kind in ("afternoon_weekly", "evening_weekly"):
        return f"on weeks with {int(s.threshold)}+ {s.label}"
    if s.kind == "dow_daily":
        return f"on {s.label}s"
    if s.kind == "duration_daily":
        return f"on days with over {s.threshold / 60:.1f}h of your blocks"
    return ""


def phrase(s: Signal, outcome: Outcome) -> dict:
    delta = round(s.mean_delta, 1)
    sign = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
    when = _when(s)
    if delta >= 0:
        headline = f"{outcome.name} averaged {sign} {when}."
        suggestion = {"action": "keep", "blockId": s.block_id,
                      "text": "These seem to go together — worth keeping."}
    else:
        headline = f"{outcome.name} ran lower {when} — a signal worth watching."
        if s.kind == "late_end_daily":
            suggestion = {"action": "tweak", "blockId": None,
                          "text": "Try moving these earlier and watch for two weeks."}
        else:
            suggestion = {"action": "tweak", "blockId": s.block_id,
                          "text": "Try tweaking or dropping this one and watch for two weeks."}
    return {"headline": headline, "meanDelta": delta, "tone": "signal", "suggestion": suggestion}


def build_insight(data: PlannerData, outcome: Outcome, today: date) -> dict:
    conf = confidence(data, outcome, today)
    if not conf["ready"]:
        return {**conf, "headline": None, "meanDelta": None, "tone": "building", "suggestion": None}
    best = select_signal(candidate_signals(data, outcome, today))
    if best is None:
        first_block = outcome.block_ids[0] if outcome.block_ids else None
        return {
            **conf, "headline": "No clear pattern yet.", "meanDelta": None, "tone": "none",
            "suggestion": {"action": "tweak", "blockId": first_block,
                           "text": "No clear pattern yet — want to try moving a block "
                                   "earlier and watch for another two weeks?"},
        }
    return {**conf, **phrase(best, outcome)}
