"""Pure logic for the time-blocking planner: storage, template, days, state."""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

DATA_FILENAME = "data.json"
SCHEMA_VERSION = 5
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
    id: str = ""


@dataclass
class DayBlock:
    """A rendered block for a given day (template fields + resolved state/label)."""
    start: str
    end: str
    label: str
    state: str = "pending"
    tag: str | None = None
    comment: str | None = None
    flagged: bool = False


@dataclass
class Override:
    """A per-day deviation for one block, keyed externally by start time."""
    state: str = "pending"
    label: str | None = None
    comment: str | None = None
    flagged: bool = False


@dataclass
class Note:
    """A day-level note. `id` is a stable handle for edit/dismiss/delete."""
    id: str
    text: str
    flagged: bool = False


@dataclass
class Outcome:
    id: str
    name: str
    description: str
    direction: str            # "increase" | "decrease"
    created: str              # ISO date
    status: str = "active"    # "active" | "archived"
    block_ids: list[str] = field(default_factory=list)


@dataclass
class OutcomeCheckin:
    rating: int               # 1..5, higher = better
    at: str                   # ISO-8601 timestamp


@dataclass
class Day:
    overrides: dict[str, Override] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)
    outcome_checkins: dict[str, OutcomeCheckin] = field(default_factory=dict)


@dataclass
class Reminder:
    """A flagged comment/note carried over from an earlier day."""
    origin_date: str
    kind: str               # "block" | "note"
    ref: str                # block start time, or note id
    text: str
    block_label: str | None = None
    block_time: str | None = None


@dataclass
class PlannerData:
    template: list[TemplateBlock] = field(default_factory=list)
    days: dict[str, Day] = field(default_factory=dict)
    outcomes: list[Outcome] = field(default_factory=list)


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


def _load_day(day: dict) -> Day:
    overrides = {start: Override(**ov) for start, ov in day["overrides"].items()}
    notes = [Note(**n) for n in day.get("notes", [])]
    checkins = {
        oid: OutcomeCheckin(**c) for oid, c in day.get("outcome_checkins", {}).items()
    }
    return Day(overrides=overrides, notes=notes, outcome_checkins=checkins)


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
            raw_template = raw["template"]
            template = [TemplateBlock(**b) for b in raw_template]
            for b, rb in zip(template, raw_template):
                if "id" not in rb:
                    b.id = uuid.uuid4().hex
            if version in (3, 4, 5):
                days = {d: _load_day(day) for d, day in raw["days"].items()}
            elif version == 2:
                days = _migrate_v2_days(raw["days"], template)
            else:
                raise ValueError(f"unsupported schema version: {version!r}")
            outcomes = [Outcome(**o) for o in raw.get("outcomes", [])]
            return PlannerData(template=template, days=days, outcomes=outcomes)
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            backup = self._backup_corrupt()
            if on_corrupt is not None:
                on_corrupt(backup)
            return PlannerData()

    def save(self, data: PlannerData) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        days_payload = {}
        for d, day in data.days.items():
            if not day.overrides and not day.notes and not day.outcome_checkins:
                continue  # don't persist empty days (defensive; _prune removes them)
            overrides = {}
            for start, ov in day.overrides.items():
                entry = {"state": ov.state}
                if ov.label is not None:
                    entry["label"] = ov.label
                if ov.comment is not None:
                    entry["comment"] = ov.comment
                if ov.flagged:
                    entry["flagged"] = True
                overrides[start] = entry
            day_payload = {"overrides": overrides}
            if day.notes:
                day_payload["notes"] = [
                    {"id": n.id, "text": n.text, **({"flagged": True} if n.flagged else {})}
                    for n in day.notes
                ]
            if day.outcome_checkins:
                day_payload["outcome_checkins"] = {
                    oid: asdict(c) for oid, c in day.outcome_checkins.items()
                }
            days_payload[d] = day_payload
        payload = {
            "version": SCHEMA_VERSION,
            "template": [asdict(b) for b in data.template],
            "days": days_payload,
            "outcomes": [asdict(o) for o in data.outcomes],
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
    block = TemplateBlock(start=start, end=end, label=label, tag=tag, id=uuid.uuid4().hex)
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
        comment = ov.comment if ov is not None else None
        flagged = ov.flagged if ov is not None else False
        blocks.append(DayBlock(start=tb.start, end=tb.end, label=label,
                               state=state, tag=tb.tag, comment=comment, flagged=flagged))
    return blocks


def get_reminders(data: PlannerData, date_iso: str) -> list[Reminder]:
    """Flagged block-comments and day-notes from days strictly before date_iso.

    Block label/time are resolved against the CURRENT template; an orphaned
    block (start no longer in the template) still surfaces with those fields None.
    """
    template_by_start = {b.start: b for b in data.template}
    out: list[Reminder] = []
    for origin, day in data.days.items():
        if origin >= date_iso:
            continue
        for start, ov in day.overrides.items():
            if ov.flagged and ov.comment:
                tb = template_by_start.get(start)
                out.append(Reminder(
                    origin_date=origin, kind="block", ref=start, text=ov.comment,
                    block_label=tb.label if tb is not None else None,
                    block_time=f"{tb.start}–{tb.end}" if tb is not None else None,
                ))
        for note in day.notes:
            if note.flagged:
                out.append(Reminder(origin_date=origin, kind="note", ref=note.id, text=note.text))
    out.sort(key=lambda r: (r.origin_date, r.kind, r.ref))
    return out


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
    if (
        ov is not None
        and ov.state == "pending"
        and ov.label is None
        and ov.comment is None
        and not ov.flagged
    ):
        del day.overrides[start]
    if not day.overrides and not day.notes and not day.outcome_checkins:
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


def set_block_comment(data: PlannerData, date_iso: str, start: str, comment: str) -> None:
    _require_template_start(data, start)
    ov = _override(data, date_iso, start)
    ov.comment = comment.strip() or None
    if ov.comment is None:
        ov.flagged = False  # a flag with no comment is meaningless
    _prune(data, date_iso, start)


def set_block_flag(data: PlannerData, date_iso: str, start: str, flagged: bool) -> None:
    _require_template_start(data, start)
    ov = _override(data, date_iso, start)
    if flagged and not ov.comment:
        raise ValidationError("cannot flag a block with no comment")
    ov.flagged = flagged
    _prune(data, date_iso, start)


def find_note(day: Day, note_id: str) -> Note | None:
    for note in day.notes:
        if note.id == note_id:
            return note
    return None


def add_note(data: PlannerData, date_iso: str, text: str, flagged: bool = False) -> Note:
    text = text.strip()
    if not text:
        raise ValidationError("note text must not be empty")
    note = Note(id=uuid.uuid4().hex, text=text, flagged=flagged)
    data.days.setdefault(date_iso, Day()).notes.append(note)
    return note


def edit_note(
    data: PlannerData, date_iso: str, note_id: str, *,
    text: str | None = None, flagged: bool | None = None,
) -> Note:
    day = data.days.get(date_iso)
    note = find_note(day, note_id) if day is not None else None
    if note is None:
        raise ValidationError(f"no note {note_id!r} on {date_iso}")
    if text is not None:
        text = text.strip()
        if not text:
            raise ValidationError("note text must not be empty")
        note.text = text
    if flagged is not None:
        note.flagged = flagged
    return note


def remove_note(data: PlannerData, date_iso: str, note_id: str) -> bool:
    day = data.days.get(date_iso)
    if day is None:
        return False
    note = find_note(day, note_id)
    if note is None:
        return False
    day.notes.remove(note)
    if not day.overrides and not day.notes and not day.outcome_checkins:
        data.days.pop(date_iso, None)
    return True


def dismiss_reminder(data: PlannerData, origin_date: str, kind: str, ref: str) -> None:
    """Clear the flag on the origin block-comment or note. Idempotent."""
    day = data.days.get(origin_date)
    if day is None:
        return
    if kind == "block":
        ov = day.overrides.get(ref)
        if ov is not None:
            ov.flagged = False
            _prune(data, origin_date, ref)
    elif kind == "note":
        note = find_note(day, ref)
        if note is not None:
            note.flagged = False


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


def _min_of(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


DIRECTIONS = ("increase", "decrease")
OUTCOME_STATUSES = ("active", "archived")


def validate_direction(direction: str) -> None:
    if direction not in DIRECTIONS:
        raise ValidationError(f"unknown direction {direction!r}; expected one of {DIRECTIONS}")


def validate_outcome_status(status: str) -> None:
    if status not in OUTCOME_STATUSES:
        raise ValidationError(f"unknown status {status!r}; expected one of {OUTCOME_STATUSES}")


def validate_rating(rating: int) -> None:
    if not isinstance(rating, int) or isinstance(rating, bool) or not (1 <= rating <= 5):
        raise ValidationError(f"rating must be an integer 1..5, got {rating!r}")


def find_outcome(data: PlannerData, outcome_id: str) -> Outcome | None:
    for o in data.outcomes:
        if o.id == outcome_id:
            return o
    return None


def find_template_block_by_id(data: PlannerData, block_id: str) -> TemplateBlock | None:
    for b in data.template:
        if b.id == block_id:
            return b
    return None


def _validate_block_ids(data: PlannerData, block_ids: list[str]) -> None:
    for bid in block_ids:
        if find_template_block_by_id(data, bid) is None:
            raise ValidationError(f"no template block with id {bid!r}")


def linked_blocks(data: PlannerData, outcome: Outcome) -> list[TemplateBlock]:
    """Template blocks linked to this outcome; dangling ids are filtered out."""
    wanted = set(outcome.block_ids)
    return [b for b in data.template if b.id in wanted]


def add_outcome(
    data: PlannerData, name: str, description: str, direction: str,
    *, block_ids: list[str] | tuple[str, ...] = (), created: str,
) -> Outcome:
    name = name.strip()
    if not name:
        raise ValidationError("outcome name must not be empty")
    validate_direction(direction)
    ids = list(block_ids)
    _validate_block_ids(data, ids)
    outcome = Outcome(
        id=uuid.uuid4().hex, name=name, description=description.strip(),
        direction=direction, created=created, status="active", block_ids=ids,
    )
    data.outcomes.append(outcome)
    return outcome


def edit_outcome(
    data: PlannerData, outcome_id: str, *,
    name: str | None = None, description: str | None = None,
    direction: str | None = None, status: str | None = None,
    block_ids: list[str] | None = None,
) -> Outcome:
    outcome = find_outcome(data, outcome_id)
    if outcome is None:
        raise ValidationError(f"no outcome {outcome_id!r}")
    if name is not None:
        name = name.strip()
        if not name:
            raise ValidationError("outcome name must not be empty")
        outcome.name = name
    if description is not None:
        outcome.description = description.strip()
    if direction is not None:
        validate_direction(direction)
        outcome.direction = direction
    if status is not None:
        validate_outcome_status(status)
        outcome.status = status
    if block_ids is not None:
        _validate_block_ids(data, block_ids)
        outcome.block_ids = list(block_ids)
    return outcome


def remove_outcome(data: PlannerData, outcome_id: str) -> bool:
    outcome = find_outcome(data, outcome_id)
    if outcome is None:
        return False
    data.outcomes.remove(outcome)
    for date_iso in list(data.days):
        day = data.days[date_iso]
        if outcome_id in day.outcome_checkins:
            del day.outcome_checkins[outcome_id]
            if not day.overrides and not day.notes and not day.outcome_checkins:
                data.days.pop(date_iso, None)
    return True


def active_block(blocks: list[DayBlock], now_min: int) -> DayBlock | None:
    """The block to prompt for at now_min: the first non-done block whose
    half-open interval [start, end) contains now_min. None if nothing is active.

    Mirrors the web app's activeStart() so the server and client agree.
    """
    for b in blocks:
        if b.state != "done" and _min_of(b.start) <= now_min < _min_of(b.end):
            return b
    return None
