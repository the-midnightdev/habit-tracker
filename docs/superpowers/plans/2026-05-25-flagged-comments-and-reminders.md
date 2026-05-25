# Flagged Comments & Next-Day Reminders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-block and day-level comments that can be flagged, with flagged comments surfacing as an in-app "Reminders" card on every following day until dismissed.

**Architecture:** Comments live on the day they belong to (per-block `comment`/`flagged` on the existing `Override`; a new `Note` list on `Day`). The reminders list is *computed on read* by scanning earlier days for still-flagged items — no copying or background jobs. Dismiss clears the flag in place; text is kept. On-disk schema bumps v3→v4 with automatic migration.

**Tech Stack:** Python 3 + FastAPI + dataclasses (backend); React 18 + Vite + Radix UI + Tailwind (frontend); pytest (backend tests); vitest + React Testing Library (frontend tests).

**Spec:** `docs/superpowers/specs/2026-05-25-flagged-comments-and-reminders-design.md`

---

## File Structure

**Backend**
- Modify `core.py` — data model (`Override`, `Note`, `Day`, `DayBlock`, `Reminder`), save/load v4 + migration, pruning, block-comment/flag mutations, note CRUD, `get_reminders`, `dismiss_reminder`.
- Modify `api.py` — extend `MarkIn`, day payload helper, notes endpoints, dismiss endpoint.
- Modify `tests/test_core.py`, `tests/test_api.py` — new tests.

**Frontend** (all under `web/`)
- Modify `web/package.json` (+`@radix-ui/react-popover`).
- Create `web/src/components/ui/popover.jsx` — Radix popover wrapper.
- Create `web/src/RemindersCard.jsx`, `web/src/NotesCard.jsx`.
- Modify `web/src/TimelineBlock.jsx` — comment popover + indicators.
- Modify `web/src/DaySidebar.jsx` — compose new cards.
- Modify `web/src/DayView.jsx` — hold notes/reminders state + handlers.
- Modify `web/src/api.js` — note/dismiss calls.
- Create/Modify tests: `web/src/RemindersCard.test.jsx`, `web/src/NotesCard.test.jsx`, `web/src/TimelineBlock.test.jsx`, `web/src/DayView.test.jsx`, `web/src/test-setup.js`.

> **Commands:** backend tests run from repo root `D:\habit-tracker`; frontend tests/build run from `web/` (`cd web` first, or `npm --prefix web ...`).

---

## PHASE 1 — Backend core (`core.py`)

### Task 1: Data model fields + v4 save/load round trip

**Files:**
- Modify: `core.py:11-13` (constants), `core.py:45-70` (dataclasses), `core.py:129-149` (`save`), `core.py:102-127` (`load`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
def test_save_then_load_round_trips_comments_and_notes(data_dir: Path):
    from core import Note
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="standup")],
        days={
            "2026-05-24": Day(
                overrides={"08:00": Override(state="done", comment="ran long", flagged=True)},
                notes=[Note(id="abc123", text="call Sam", flagged=True)],
            )
        },
    )
    DataStore(data_dir).save(data)
    assert DataStore(data_dir).load() == data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py::test_save_then_load_round_trips_comments_and_notes -v`
Expected: FAIL (`ImportError: cannot import name 'Note'` or `TypeError` on unexpected kwargs).

- [ ] **Step 3: Write minimal implementation**

In `core.py` bump the version constant:

```python
SCHEMA_VERSION = 4
```

Replace the `Override` dataclass and add `Note`, extend `Day` and `DayBlock`:

```python
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
class Day:
    overrides: dict[str, Override] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)
```

Add a module-level helper above `class DataStore`:

```python
def _load_day(day: dict) -> Day:
    overrides = {start: Override(**ov) for start, ov in day["overrides"].items()}
    notes = [Note(**n) for n in day.get("notes", [])]
    return Day(overrides=overrides, notes=notes)
```

Replace the version-dispatch block inside `DataStore.load` (the `if version == SCHEMA_VERSION ... elif version == 2 ...` section) with:

```python
            if version in (3, 4):
                days = {d: _load_day(day) for d, day in raw["days"].items()}
            elif version == 2:
                days = _migrate_v2_days(raw["days"], template)
            else:
                raise ValueError(f"unsupported schema version: {version!r}")
```

Replace the body of `DataStore.save` with:

```python
    def save(self, data: PlannerData) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        days_payload = {}
        for d, day in data.days.items():
            if not day.overrides and not day.notes:
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
            days_payload[d] = day_payload
        payload = {
            "version": SCHEMA_VERSION,
            "template": [asdict(b) for b in data.template],
            "days": days_payload,
        }
        self.path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py::test_save_then_load_round_trips_comments_and_notes -v`
Expected: PASS

- [ ] **Step 5: Run the full core suite (guard against regressions)**

Run: `python -m pytest tests/test_core.py -v`
Expected: all PASS (the existing `test_save_then_load_round_trips` still passes — empty notes lists round-trip).

- [ ] **Step 6: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat(core): comment/flag fields + day notes, schema v4"
```

---

### Task 2: v3 → v4 migration on load

**Files:**
- Modify: `core.py` (no code change expected — verify v3 loads via `_load_day`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
def test_v3_file_loads_with_v4_defaults(data_dir: Path):
    v3 = {
        "version": 3,
        "template": [{"start": "08:00", "end": "09:00", "label": "standup", "tag": None}],
        "days": {"2026-05-24": {"overrides": {"08:00": {"state": "done"}}}},
    }
    (data_dir / "data.json").write_text(json.dumps(v3), encoding="utf-8")
    loaded = DataStore(data_dir).load()
    ov = loaded.days["2026-05-24"].overrides["08:00"]
    assert ov.state == "done"
    assert ov.comment is None and ov.flagged is False
    assert loaded.days["2026-05-24"].notes == []
```

- [ ] **Step 2: Run test to verify it passes (migration is implicit)**

Run: `python -m pytest tests/test_core.py::test_v3_file_loads_with_v4_defaults -v`
Expected: PASS — `_load_day` reads v3 override dicts (`{"state": "done"}`) into `Override` with the new fields defaulting, and `day.get("notes", [])` yields `[]`.

> If this FAILS, the v3 branch was not wired to `_load_day` in Task 1 — fix `load` so `version in (3, 4)` both call `_load_day`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_core.py
git commit -m "test(core): v3->v4 migration loads with defaults"
```

---

### Task 3: Pruning + block comment/flag mutations

**Files:**
- Modify: `core.py:245-266` (`_prune`, and add `set_block_comment`/`set_block_flag` near `set_block_state`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
from core import set_block_comment, set_block_flag  # add to existing import block


def _data_with_block():
    return PlannerData(template=[TemplateBlock(start="08:00", end="09:00", label="standup")])


def test_set_block_comment_then_clear_prunes_override():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ran long")
    assert data.days["2026-05-24"].overrides["08:00"].comment == "ran long"
    set_block_comment(data, "2026-05-24", "08:00", "")
    assert "2026-05-24" not in data.days  # pruned: pending, no label/comment/flag


def test_flag_requires_comment():
    data = _data_with_block()
    with pytest.raises(ValidationError):
        set_block_flag(data, "2026-05-24", "08:00", True)


def test_set_flag_keeps_override_when_pending():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    ov = data.days["2026-05-24"].overrides["08:00"]
    assert ov.flagged is True and ov.state == "pending"


def test_clearing_comment_also_clears_flag():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    set_block_comment(data, "2026-05-24", "08:00", "")
    assert "2026-05-24" not in data.days
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py -k "block_comment or flag" -v`
Expected: FAIL (`ImportError` for the new functions).

- [ ] **Step 3: Write minimal implementation**

Replace `_prune` in `core.py`:

```python
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
    if not day.overrides and not day.notes:
        data.days.pop(date_iso, None)
```

Add after `set_block_label`:

```python
def set_block_comment(data: PlannerData, date_iso: str, start: str, comment: str) -> None:
    _require_template_start(data, start)
    ov = _override(data, date_iso, start)
    ov.comment = comment or None
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -k "block_comment or flag" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat(core): block comment/flag mutations + prune rule"
```

---

### Task 4: Render comment/flag into day blocks

**Files:**
- Modify: `core.py:218-232` (`get_day_blocks`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
def test_get_day_blocks_includes_comment_and_flag():
    from core import get_day_blocks
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    block = get_day_blocks(data, "2026-05-24")[0]
    assert block.comment == "ping Sam" and block.flagged is True


def test_get_day_blocks_defaults_when_no_override():
    from core import get_day_blocks
    data = _data_with_block()
    block = get_day_blocks(data, "2026-05-24")[0]
    assert block.comment is None and block.flagged is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py -k "get_day_blocks_includes or get_day_blocks_defaults" -v`
Expected: FAIL (`DayBlock` built without comment/flag → both default; `includes` test fails).

- [ ] **Step 3: Write minimal implementation**

Replace the loop body in `get_day_blocks`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -k "get_day_blocks" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat(core): surface comment/flag on rendered day blocks"
```

---

### Task 5: Day-level note CRUD

**Files:**
- Modify: `core.py` (add `import uuid` at top; add `add_note`, `find_note`, `edit_note`, `remove_note`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
from core import add_note, edit_note, remove_note, find_note  # add to import block


def test_add_note_generates_id_and_stores():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "call Sam")
    assert note.id and note.text == "call Sam" and note.flagged is False
    assert data.days["2026-05-24"].notes == [note]


def test_add_empty_note_rejected():
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_note(data, "2026-05-24", "")


def test_edit_note_updates_fields():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "draft")
    edit_note(data, "2026-05-24", note.id, text="final", flagged=True)
    assert note.text == "final" and note.flagged is True


def test_edit_unknown_note_raises():
    data = PlannerData()
    add_note(data, "2026-05-24", "x")
    with pytest.raises(ValidationError):
        edit_note(data, "2026-05-24", "nope", text="y")


def test_remove_note_and_prune_day():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "x")
    assert remove_note(data, "2026-05-24", note.id) is True
    assert "2026-05-24" not in data.days  # day pruned when no overrides/notes left
    assert remove_note(data, "2026-05-24", note.id) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py -k "note" -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Write minimal implementation**

At the top of `core.py`, add to the imports:

```python
import uuid
```

Add these functions (place them after `set_block_flag`):

```python
def find_note(day: Day, note_id: str) -> Note | None:
    for note in day.notes:
        if note.id == note_id:
            return note
    return None


def add_note(data: PlannerData, date_iso: str, text: str, flagged: bool = False) -> Note:
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
    if not day.overrides and not day.notes:
        data.days.pop(date_iso, None)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -k "note" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat(core): day-level note CRUD"
```

---

### Task 6: `get_reminders` (computed carryover)

**Files:**
- Modify: `core.py` (add `Reminder` dataclass + `get_reminders`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
from core import Reminder, get_reminders  # add to import block


def test_get_reminders_returns_prior_day_flags_only():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    add_note(data, "2026-05-24", "buy milk", flagged=True)
    add_note(data, "2026-05-24", "unflagged note", flagged=False)

    # Viewed on the SAME day: no reminders (carryover is strictly earlier days).
    assert get_reminders(data, "2026-05-24") == []

    # Viewed the NEXT day: both flagged items surface, unflagged excluded.
    rem = get_reminders(data, "2026-05-25")
    kinds = {(r.kind, r.text) for r in rem}
    assert ("block", "ping Sam") in kinds
    assert ("note", "buy milk") in kinds
    assert all(r.text != "unflagged note" for r in rem)

    block_rem = next(r for r in rem if r.kind == "block")
    assert block_rem.block_label == "standup"
    assert block_rem.block_time == "08:00–09:00"


def test_get_reminders_excludes_dismissed_and_orphans_survive():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    # Orphan the block by removing it from the template; reminder still surfaces.
    data.template.clear()
    rem = get_reminders(data, "2026-05-25")
    assert len(rem) == 1
    assert rem[0].text == "ping Sam"
    assert rem[0].block_label is None and rem[0].block_time is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py -k "reminders" -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Write minimal implementation**

Add the dataclass near the other dataclasses (after `Day`):

```python
@dataclass
class Reminder:
    """A flagged comment/note carried over from an earlier day."""
    origin_date: str
    kind: str               # "block" | "note"
    ref: str                # block start time, or note id
    text: str
    block_label: str | None = None
    block_time: str | None = None
```

Add the function (after `get_day_blocks`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -k "reminders" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat(core): compute carried-over reminders on read"
```

---

### Task 7: `dismiss_reminder`

**Files:**
- Modify: `core.py` (add `dismiss_reminder`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_core.py`:

```python
from core import dismiss_reminder  # add to import block


def test_dismiss_block_reminder_clears_flag_keeps_text():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    dismiss_reminder(data, "2026-05-24", "block", "08:00")
    ov = data.days["2026-05-24"].overrides["08:00"]
    assert ov.flagged is False and ov.comment == "ping Sam"  # text kept
    assert get_reminders(data, "2026-05-25") == []


def test_dismiss_note_reminder_clears_flag():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "buy milk", flagged=True)
    dismiss_reminder(data, "2026-05-24", "note", note.id)
    assert note.flagged is False and note.text == "buy milk"


def test_dismiss_is_idempotent_for_missing_target():
    data = PlannerData()
    dismiss_reminder(data, "2026-05-24", "block", "08:00")  # no raise
    dismiss_reminder(data, "2026-05-24", "note", "nope")    # no raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_core.py -k "dismiss" -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Write minimal implementation**

Add (after `remove_note`):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_core.py -k "dismiss" -v`
Expected: PASS

- [ ] **Step 5: Run full backend suite**

Run: `python -m pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat(core): dismiss reminder clears flag, keeps text"
```

---

## PHASE 2 — API (`api.py`)

### Task 8: Day payload (notes + reminders) + comment/flag on mark

**Files:**
- Modify: `api.py:12-23` (imports), `api.py:56-59` (`MarkIn`), `api.py:104-133` (`get_day`, `mark_block`)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def _add_block(client, start="08:00", end="09:00", label="standup"):
    client.post("/api/template", json={"start": start, "end": end, "label": label})


def test_get_day_returns_notes_and_reminders_keys(client):
    _add_block(client)
    body = client.get("/api/days/2026-05-24").json()
    assert body["blocks"][0]["comment"] is None
    assert body["blocks"][0]["flagged"] is False
    assert body["notes"] == []
    assert body["reminders"] == []


def test_flagged_block_comment_becomes_reminder_next_day(client):
    _add_block(client)
    resp = client.post("/api/days/2026-05-24/blocks/08:00",
                       json={"comment": "ping Sam", "flagged": True})
    assert resp.status_code == 200
    assert resp.json()["blocks"][0]["flagged"] is True
    # Same day: no reminder. Next day: reminder present.
    assert client.get("/api/days/2026-05-24").json()["reminders"] == []
    rem = client.get("/api/days/2026-05-25").json()["reminders"]
    assert len(rem) == 1 and rem[0]["text"] == "ping Sam" and rem[0]["kind"] == "block"


def test_flagging_block_without_comment_returns_400(client):
    _add_block(client)
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"flagged": True})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -k "notes_and_reminders or reminder_next_day or without_comment" -v`
Expected: FAIL (`KeyError: 'notes'` / missing comment field / flag accepted).

- [ ] **Step 3: Write minimal implementation**

Update the import from `core` in `api.py` to add the new names:

```python
from core import (
    DataStore,
    ValidationError,
    add_note,
    add_template_block,
    dismiss_reminder,
    edit_note,
    edit_template_block,
    find_note,
    find_template_block,
    get_day_blocks,
    get_reminders,
    history_dates,
    remove_note,
    remove_template_block,
    set_block_comment,
    set_block_flag,
    set_block_label,
    set_block_state,
)
```

Extend `MarkIn`:

```python
class MarkIn(BaseModel):
    state: str | None = None
    label: str | None = None
    comment: str | None = None
    flagged: bool | None = None
```

Add a payload helper just above `list_template` (after `_store`):

```python
def _day_payload(data, date_iso: str) -> dict:
    notes = data.days[date_iso].notes if date_iso in data.days else []
    return {
        "date": date_iso,
        "blocks": [asdict(b) for b in get_day_blocks(data, date_iso)],
        "notes": [asdict(n) for n in notes],
        "reminders": [asdict(r) for r in get_reminders(data, date_iso)],
    }
```

Replace `get_day`:

```python
@app.get("/api/days/{date_iso}")
def get_day(date_iso: str) -> dict:
    return _day_payload(_store().load(), date_iso)
```

Replace the body of `mark_block` (keep the existing 404 existence check) with:

```python
@app.post("/api/days/{date_iso}/blocks/{start}")
def mark_block(date_iso: str, start: str, mark: MarkIn) -> dict:
    store = _store()
    data = store.load()
    if all(b.start != start for b in get_day_blocks(data, date_iso)):
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    try:
        if mark.state is not None:
            set_block_state(data, date_iso, start, mark.state)
        if mark.label is not None:
            set_block_label(data, date_iso, start, mark.label)
        if mark.comment is not None:
            set_block_comment(data, date_iso, start, mark.comment)
        if mark.flagged is not None:
            set_block_flag(data, date_iso, start, mark.flagged)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return _day_payload(data, date_iso)
```

> Order matters: `comment` is applied before `flagged`, so a single request carrying both `{comment, flagged: true}` works.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py -k "notes_and_reminders or reminder_next_day or without_comment" -v`
Expected: PASS

- [ ] **Step 5: Run full api suite (existing mark/day tests must still pass)**

Run: `python -m pytest tests/test_api.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat(api): day payload with notes+reminders, comment/flag on mark"
```

---

### Task 9: Notes endpoints (create / edit / delete)

**Files:**
- Modify: `api.py` (add `NoteIn`, `NoteEdit` models + three endpoints)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_create_edit_delete_note(client):
    created = client.post("/api/days/2026-05-24/notes",
                          json={"text": "call Sam", "flagged": False})
    assert created.status_code == 201
    body = created.json()
    assert body["notes"][0]["text"] == "call Sam"
    note_id = body["notes"][0]["id"]

    edited = client.put(f"/api/days/2026-05-24/notes/{note_id}",
                        json={"text": "call Sam at 3", "flagged": True})
    assert edited.status_code == 200
    assert edited.json()["notes"][0]["text"] == "call Sam at 3"
    assert edited.json()["notes"][0]["flagged"] is True

    deleted = client.delete(f"/api/days/2026-05-24/notes/{note_id}")
    assert deleted.status_code == 204
    assert client.get("/api/days/2026-05-24").json()["notes"] == []


def test_edit_unknown_note_returns_404(client):
    resp = client.put("/api/days/2026-05-24/notes/nope", json={"text": "x"})
    assert resp.status_code == 404


def test_delete_unknown_note_returns_404(client):
    resp = client.delete("/api/days/2026-05-24/notes/nope")
    assert resp.status_code == 404


def test_create_empty_note_returns_400(client):
    resp = client.post("/api/days/2026-05-24/notes", json={"text": ""})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -k "note" -v`
Expected: FAIL (404 from FastAPI for undefined routes).

- [ ] **Step 3: Write minimal implementation**

Add models near `MarkIn`:

```python
class NoteIn(BaseModel):
    text: str
    flagged: bool = False


class NoteEdit(BaseModel):
    text: str | None = None
    flagged: bool | None = None
```

Add endpoints (after `mark_block`):

```python
@app.post("/api/days/{date_iso}/notes", status_code=201)
def create_note(date_iso: str, note: NoteIn) -> dict:
    store = _store()
    data = store.load()
    try:
        add_note(data, date_iso, note.text, flagged=note.flagged)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return _day_payload(data, date_iso)


@app.put("/api/days/{date_iso}/notes/{note_id}")
def update_note(date_iso: str, note_id: str, edit: NoteEdit) -> dict:
    store = _store()
    data = store.load()
    day = data.days.get(date_iso)
    if day is None or find_note(day, note_id) is None:
        raise HTTPException(status_code=404, detail=f"no note {note_id!r} on {date_iso}")
    try:
        edit_note(data, date_iso, note_id, text=edit.text, flagged=edit.flagged)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return _day_payload(data, date_iso)


@app.delete("/api/days/{date_iso}/notes/{note_id}", status_code=204)
def delete_note(date_iso: str, note_id: str) -> Response:
    store = _store()
    data = store.load()
    if not remove_note(data, date_iso, note_id):
        raise HTTPException(status_code=404, detail=f"no note {note_id!r} on {date_iso}")
    store.save(data)
    return Response(status_code=204)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py -k "note" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat(api): day note create/edit/delete endpoints"
```

---

### Task 10: Dismiss-reminder endpoint

**Files:**
- Modify: `api.py` (add `DismissIn` + endpoint)
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
def test_dismiss_reminder_endpoint(client):
    _add_block(client)
    client.post("/api/days/2026-05-24/blocks/08:00",
                json={"comment": "ping Sam", "flagged": True})
    assert len(client.get("/api/days/2026-05-25").json()["reminders"]) == 1

    resp = client.post("/api/reminders/dismiss",
                       json={"origin_date": "2026-05-24", "kind": "block", "ref": "08:00"})
    assert resp.status_code == 204
    assert client.get("/api/days/2026-05-25").json()["reminders"] == []


def test_dismiss_missing_reminder_is_noop_204(client):
    resp = client.post("/api/reminders/dismiss",
                       json={"origin_date": "2026-05-24", "kind": "note", "ref": "nope"})
    assert resp.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api.py -k "dismiss" -v`
Expected: FAIL (404 — route undefined).

- [ ] **Step 3: Write minimal implementation**

Add model near `MarkIn`:

```python
class DismissIn(BaseModel):
    origin_date: str
    kind: str
    ref: str
```

Add endpoint (after `delete_note`):

```python
@app.post("/api/reminders/dismiss", status_code=204)
def dismiss(payload: DismissIn) -> Response:
    store = _store()
    data = store.load()
    dismiss_reminder(data, payload.origin_date, payload.kind, payload.ref)
    store.save(data)
    return Response(status_code=204)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api.py -k "dismiss" -v`
Expected: PASS

- [ ] **Step 5: Run full backend suite**

Run: `python -m pytest -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat(api): dismiss-reminder endpoint"
```

---

## PHASE 3 — Frontend (`web/`)

### Task 11: API client calls

**Files:**
- Modify: `web/src/api.js`
- Test: `web/src/api.test.js`

- [ ] **Step 1: Write the failing test**

Append to `web/src/api.test.js`:

```js
import { addNote, editNote, deleteNote, dismissReminder } from "./api.js";

test("addNote POSTs to the day notes endpoint", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ date: "2026-05-24", notes: [] }), { status: 201 })
  );
  await addNote("2026-05-24", { text: "hi", flagged: false });
  expect(fetchMock).toHaveBeenCalledWith("/api/days/2026-05-24/notes", expect.objectContaining({ method: "POST" }));
});

test("dismissReminder POSTs to the dismiss endpoint", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await dismissReminder({ origin_date: "2026-05-24", kind: "note", ref: "x" });
  expect(fetchMock).toHaveBeenCalledWith("/api/reminders/dismiss", expect.objectContaining({ method: "POST" }));
});

test("deleteNote issues a DELETE", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  await deleteNote("2026-05-24", "abc");
  expect(fetchMock).toHaveBeenCalledWith("/api/days/2026-05-24/notes/abc", { method: "DELETE" });
});
```

> Check the top of `web/src/api.test.js` — if `vi` is not already imported there, add `import { test, expect, vi } from "vitest";` (or extend the existing import).

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix web test -- src/api.test.js`
Expected: FAIL (`addNote` etc. are not exported).

- [ ] **Step 3: Write minimal implementation**

Append to `web/src/api.js`:

```js
export const addNote = (date, note) =>
  request(`/api/days/${date}/notes`, jsonPost(note));

export const editNote = (date, id, edit) =>
  request(`/api/days/${date}/notes/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edit),
  });

export const deleteNote = (date, id) =>
  request(`/api/days/${date}/notes/${id}`, { method: "DELETE" });

export const dismissReminder = (payload) =>
  request("/api/reminders/dismiss", jsonPost(payload));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix web test -- src/api.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/api.js web/src/api.test.js
git commit -m "feat(web): api client for notes + dismiss"
```

---

### Task 12: Install Radix popover + ui wrapper + jsdom polyfills

**Files:**
- Modify: `web/package.json` (dependency added by npm)
- Create: `web/src/components/ui/popover.jsx`
- Modify: `web/src/test-setup.js`

- [ ] **Step 1: Install the dependency**

Run: `npm --prefix web install @radix-ui/react-popover`
Expected: `@radix-ui/react-popover` appears in `web/package.json` dependencies; `package-lock.json` updated.

- [ ] **Step 2: Create the popover wrapper**

Create `web/src/components/ui/popover.jsx`:

```jsx
import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { cn } from "@/lib/utils";

const Popover = PopoverPrimitive.Root;
const PopoverTrigger = PopoverPrimitive.Trigger;

const PopoverContent = React.forwardRef(
  ({ className, align = "center", sideOffset = 6, ...props }, ref) => (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        ref={ref}
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 w-72 rounded-xl border bg-white p-3 shadow-md outline-none",
          className
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  )
);
PopoverContent.displayName = "PopoverContent";

export { Popover, PopoverTrigger, PopoverContent };
```

- [ ] **Step 3: Add jsdom polyfills Radix needs**

Append to `web/src/test-setup.js` (Radix popovers call pointer-capture / scroll APIs jsdom lacks):

```js
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
```

- [ ] **Step 4: Verify the suite still loads**

Run: `npm --prefix web test`
Expected: all existing tests PASS (no behavior change yet).

- [ ] **Step 5: Commit**

```bash
git add web/package.json web/package-lock.json web/src/components/ui/popover.jsx web/src/test-setup.js
git commit -m "chore(web): add radix popover + jsdom pointer polyfills"
```

---

### Task 13: TimelineBlock comment popover + indicators

**Files:**
- Modify: `web/src/TimelineBlock.jsx`
- Test: `web/src/TimelineBlock.test.jsx`

- [ ] **Step 1: Write the failing test**

Append to `web/src/TimelineBlock.test.jsx`:

```jsx
test("shows a flag indicator when the block is flagged", () => {
  renderBlock({ comment: "ping Sam", flagged: true });
  expect(screen.getByLabelText("flagged")).toBeInTheDocument();
});

test("saving the comment popover calls onMark with comment and flag", async () => {
  const onMark = vi.fn();
  renderBlock({}, onMark);
  fireEvent.click(screen.getByRole("button", { name: /comment/i }));
  const textarea = await screen.findByLabelText("comment text");
  fireEvent.change(textarea, { target: { value: "ping Sam" } });
  fireEvent.click(screen.getByRole("button", { name: /flag for tomorrow/i }));
  fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
  expect(onMark).toHaveBeenCalledWith("08:00", { comment: "ping Sam", flagged: true });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix web test -- src/TimelineBlock.test.jsx`
Expected: FAIL (no comment button / flagged label).

- [ ] **Step 3: Write minimal implementation**

In `web/src/TimelineBlock.jsx`, update the imports:

```jsx
import { useEffect, useState } from "react";
import { Check, X, MessageSquare, Flag } from "lucide-react";
import { cn } from "@/lib/utils";
import { PAL } from "./lib/palette.js";
import { tagIcon } from "./lib/tags.js";
import { minOf } from "./lib/schedule.js";
import { Popover, PopoverTrigger, PopoverContent } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
```

Inside the component, after the existing `submitLabel` definition, add popover state and a save handler:

```jsx
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState(block.comment ?? "");
  const [noteFlag, setNoteFlag] = useState(block.flagged ?? false);
  useEffect(() => {
    setNoteText(block.comment ?? "");
    setNoteFlag(block.flagged ?? false);
  }, [block.comment, block.flagged]);
  const saveNote = () => {
    onMark(block.start, { comment: noteText.trim(), flagged: noteText.trim() ? noteFlag : false });
    setNoteOpen(false);
  };
```

Add an indicator next to the pill. Replace the pill row (`<div className="flex items-center gap-2"> ... </div>` containing the time span + pill) with this version that appends indicators:

```jsx
          <div className="flex items-center gap-2">
            <span className="flex-shrink-0 font-mono text-[11px]" style={{ color: PAL.muted }}>{block.start}–{block.end}</span>
            {!compact && (
              <span className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                style={pillStyle(isActive, isDone)}>
                {isActive ? "Now" : isDone ? "Done" : block.tag || "Block"}
              </span>
            )}
            {block.flagged ? (
              <Flag aria-label="flagged" className="h-3 w-3 flex-shrink-0" style={{ color: PAL.accent, fill: PAL.accent }} />
            ) : block.comment ? (
              <span aria-label="has comment" className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ background: PAL.hairline2 }} />
            ) : null}
          </div>
```

Add the comment button to the action cluster — insert it before the `done` button inside the `<div className={cn("flex flex-shrink-0 items-center gap-1 transition", ...)}>`:

```jsx
          <Popover open={noteOpen} onOpenChange={setNoteOpen}>
            <PopoverTrigger asChild>
              <button aria-label="comment"
                className="flex h-7 w-7 items-center justify-center rounded-md border" style={{ borderColor: PAL.hairline2 }}>
                <MessageSquare className="h-3.5 w-3.5" />
              </button>
            </PopoverTrigger>
            <PopoverContent align="end">
              <textarea aria-label="comment text" value={noteText} rows={3}
                onChange={(e) => setNoteText(e.target.value)} placeholder="Add a comment…"
                className="w-full resize-none rounded-md border bg-transparent p-2 text-sm outline-none"
                style={{ borderColor: PAL.hairline2 }} />
              <label className="mt-2 flex items-center gap-2 text-xs" style={{ color: PAL.ink2 }}>
                <input type="checkbox" checked={noteFlag} aria-label="flag for tomorrow"
                  onChange={(e) => setNoteFlag(e.target.checked)} />
                Flag for tomorrow
              </label>
              <Button size="sm" className="mt-3 w-full" onClick={saveNote}>Save</Button>
            </PopoverContent>
          </Popover>
```

> The action cluster keeps `opacity-0 group-hover:opacity-100` from the existing code; the comment button inherits that hover reveal. The flag/dot indicator in the title row is always visible.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix web test -- src/TimelineBlock.test.jsx`
Expected: PASS (including the 3 pre-existing tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/TimelineBlock.jsx web/src/TimelineBlock.test.jsx
git commit -m "feat(web): per-block comment popover + flag/comment indicators"
```

---

### Task 14: RemindersCard component

**Files:**
- Create: `web/src/RemindersCard.jsx`
- Test: `web/src/RemindersCard.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/RemindersCard.test.jsx`:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import RemindersCard from "./RemindersCard.jsx";

const reminder = {
  origin_date: "2026-05-24", kind: "block", ref: "08:00",
  text: "ping Sam", block_label: "standup", block_time: "08:00–09:00",
};

test("renders nothing when there are no reminders", () => {
  const { container } = render(<RemindersCard reminders={[]} onDismiss={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

test("renders a reminder and dismiss calls back with it", () => {
  const onDismiss = vi.fn();
  render(<RemindersCard reminders={[reminder]} onDismiss={onDismiss} />);
  expect(screen.getByText("ping Sam")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /dismiss reminder/i }));
  expect(onDismiss).toHaveBeenCalledWith(reminder);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix web test -- src/RemindersCard.test.jsx`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `web/src/RemindersCard.jsx`:

```jsx
import { Check } from "lucide-react";
import { PAL } from "./lib/palette.js";

const prettyOrigin = (iso) =>
  new Date(iso + "T00:00:00").toLocaleDateString(undefined, {
    weekday: "short", month: "short", day: "numeric",
  });

export default function RemindersCard({ reminders, onDismiss }) {
  if (!reminders.length) return null;
  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
        Reminders
      </div>
      <ul className="flex flex-col gap-2">
        {reminders.map((r) => (
          <li key={`${r.origin_date}-${r.kind}-${r.ref}`}
            className="flex items-start gap-2 rounded-lg border p-2"
            style={{ borderColor: PAL.hairline2, background: "#FBF8F2" }}>
            <div className="min-w-0 flex-1">
              <div className="text-sm" style={{ color: PAL.ink }}>{r.text}</div>
              <div className="mt-0.5 font-mono text-[10px]" style={{ color: PAL.muted }}>
                from {prettyOrigin(r.origin_date)}
                {r.block_time ? ` · ${r.block_time}${r.block_label ? ` ${r.block_label}` : ""}` : ""}
              </div>
            </div>
            <button aria-label="dismiss reminder" onClick={() => onDismiss(r)}
              className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-md border"
              style={{ borderColor: PAL.hairline2 }}>
              <Check className="h-3.5 w-3.5" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix web test -- src/RemindersCard.test.jsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/RemindersCard.jsx web/src/RemindersCard.test.jsx
git commit -m "feat(web): RemindersCard with dismiss"
```

---

### Task 15: NotesCard component

**Files:**
- Create: `web/src/NotesCard.jsx`
- Test: `web/src/NotesCard.test.jsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/NotesCard.test.jsx`:

```jsx
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import NotesCard from "./NotesCard.jsx";

const note = { id: "n1", text: "call Sam", flagged: false };

test("adding a note calls onAdd with text and flag, then clears input", () => {
  const onAdd = vi.fn();
  render(<NotesCard notes={[]} onAdd={onAdd} onToggleFlag={() => {}} onDelete={() => {}} />);
  fireEvent.change(screen.getByLabelText("new note"), { target: { value: "buy milk" } });
  fireEvent.click(screen.getByRole("button", { name: /flag for tomorrow/i }));
  fireEvent.click(screen.getByRole("button", { name: /add note/i }));
  expect(onAdd).toHaveBeenCalledWith({ text: "buy milk", flagged: true });
});

test("toggle and delete call back with the note", () => {
  const onToggleFlag = vi.fn();
  const onDelete = vi.fn();
  render(<NotesCard notes={[note]} onAdd={() => {}} onToggleFlag={onToggleFlag} onDelete={onDelete} />);
  fireEvent.click(screen.getByRole("button", { name: /flag note/i }));
  expect(onToggleFlag).toHaveBeenCalledWith(note);
  fireEvent.click(screen.getByRole("button", { name: /delete note/i }));
  expect(onDelete).toHaveBeenCalledWith(note);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix web test -- src/NotesCard.test.jsx`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write minimal implementation**

Create `web/src/NotesCard.jsx`:

```jsx
import { useState } from "react";
import { Flag, Trash2, Plus } from "lucide-react";
import { PAL } from "./lib/palette.js";

export default function NotesCard({ notes, onAdd, onToggleFlag, onDelete }) {
  const [text, setText] = useState("");
  const [flag, setFlag] = useState(false);
  const submit = () => {
    const t = text.trim();
    if (!t) return;
    onAdd({ text: t, flagged: flag });
    setText("");
    setFlag(false);
  };
  const flagStyle = (on) => ({ color: on ? PAL.accent : PAL.hairline2, fill: on ? PAL.accent : "none" });

  return (
    <div className="rounded-2xl border bg-white p-4" style={{ borderColor: PAL.hairline }}>
      <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-widest" style={{ color: PAL.muted }}>
        Notes
      </div>
      {notes.length > 0 && (
        <ul className="mb-3 flex flex-col gap-2">
          {notes.map((n) => (
            <li key={n.id} className="flex items-start gap-2">
              <button aria-label={n.flagged ? "unflag note" : "flag note"} onClick={() => onToggleFlag(n)} className="mt-0.5 flex-shrink-0">
                <Flag className="h-3.5 w-3.5" style={flagStyle(n.flagged)} />
              </button>
              <span className="min-w-0 flex-1 text-sm" style={{ color: PAL.ink }}>{n.text}</span>
              <button aria-label="delete note" onClick={() => onDelete(n)} className="flex-shrink-0">
                <Trash2 className="h-3.5 w-3.5" style={{ color: PAL.muted }} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex items-center gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          placeholder="Add a note…" aria-label="new note"
          className="min-w-0 flex-1 rounded-md border bg-transparent px-2 py-1 text-sm outline-none"
          style={{ borderColor: PAL.hairline2 }} />
        <button aria-label="flag for tomorrow" onClick={() => setFlag((f) => !f)} className="flex-shrink-0">
          <Flag className="h-4 w-4" style={flagStyle(flag)} />
        </button>
        <button aria-label="add note" onClick={submit}
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border" style={{ borderColor: PAL.hairline2 }}>
          <Plus className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix web test -- src/NotesCard.test.jsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/NotesCard.jsx web/src/NotesCard.test.jsx
git commit -m "feat(web): NotesCard for day-level notes"
```

---

### Task 16: Wire cards into DaySidebar + DayView

**Files:**
- Modify: `web/src/DaySidebar.jsx`, `web/src/DayView.jsx`
- Test: `web/src/DayView.test.jsx`

- [ ] **Step 1: Write the failing test**

Append to `web/src/DayView.test.jsx`:

```jsx
test("renders reminders and notes from the day payload", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({
    date: "2026-05-24",
    blocks: [{ start: "09:00", end: "10:00", label: "work", state: "pending", tag: "Deep work", comment: null, flagged: false }],
    notes: [{ id: "n1", text: "call Sam", flagged: false }],
    reminders: [{ origin_date: "2026-05-23", kind: "note", ref: "old", text: "from yesterday" }],
  });
  render(<DayView now={FIXED_NOW} />);
  expect(await screen.findByText("from yesterday")).toBeInTheDocument();
  expect(screen.getByText("call Sam")).toBeInTheDocument();
});

test("dismissing a reminder calls the API and reloads", async () => {
  vi.spyOn(api, "getDay").mockResolvedValue({
    date: "2026-05-24",
    blocks: [],
    notes: [],
    reminders: [{ origin_date: "2026-05-23", kind: "note", ref: "old", text: "from yesterday" }],
  });
  const dismiss = vi.spyOn(api, "dismissReminder").mockResolvedValue(null);
  render(<DayView now={FIXED_NOW} />);
  fireEvent.click(await screen.findByRole("button", { name: /dismiss reminder/i }));
  await waitFor(() =>
    expect(dismiss).toHaveBeenCalledWith({ origin_date: "2026-05-23", kind: "note", ref: "old" })
  );
});
```

> The existing `mockDay` helper returns objects without `notes`/`reminders`; older tests still pass because the sidebar treats missing arrays as empty (see Step 3 defaults).

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix web test -- src/DayView.test.jsx`
Expected: FAIL (reminders/notes not rendered).

- [ ] **Step 3: Write minimal implementation**

**`web/src/DaySidebar.jsx`** — import the two cards and accept new props. Update the imports at the top:

```jsx
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { PAL } from "./lib/palette.js";
import { countdown, focusedMinutes, remainingMinutes, minOf } from "./lib/schedule.js";
import RemindersCard from "./RemindersCard.jsx";
import NotesCard from "./NotesCard.jsx";
```

Change the component signature and add the cards. Replace the function signature line and the opening wrapper `<div>` so RemindersCard is first and NotesCard is last:

```jsx
export default function DaySidebar({
  blocks, active, nowMin, onComplete,
  reminders = [], notes = [],
  onDismissReminder, onAddNote, onToggleNoteFlag, onDeleteNote,
}) {
  const done = blocks.filter((b) => b.state === "done").length;
  const total = blocks.length;
  const pct = total ? done / total : 0;
  const size = 96, r = 38, c = 2 * Math.PI * r;

  return (
    <div className="flex flex-col gap-4 border-l p-5" style={{ borderColor: PAL.hairline }}>
      <RemindersCard reminders={reminders} onDismiss={onDismissReminder} />
```

Then, immediately before the final closing `</div>` of the returned tree (after the existing NOW card block), add:

```jsx
      <NotesCard notes={notes} onAdd={onAddNote} onToggleFlag={onToggleNoteFlag} onDelete={onDeleteNote} />
```

**`web/src/DayView.jsx`** — hold the new state and thread handlers. Update the api import line:

```jsx
import { getDay, markBlock, addTemplateBlock, addNote, editNote, deleteNote, dismissReminder } from "./api.js";
```

Replace the blocks state + loaders. Find:

```jsx
  const [blocks, setBlocks] = useState([]);

  const load = (d) => getDay(d).then((day) => setBlocks(day.blocks)).catch((e) => toast.error(e.message));
  useEffect(() => { load(date); }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark).then((day) => setBlocks(day.blocks)).catch((e) => toast.error(e.message));
```

Replace with:

```jsx
  const [blocks, setBlocks] = useState([]);
  const [notes, setNotes] = useState([]);
  const [reminders, setReminders] = useState([]);

  const applyDay = (day) => {
    setBlocks(day.blocks);
    setNotes(day.notes ?? []);
    setReminders(day.reminders ?? []);
  };
  const load = (d) => getDay(d).then(applyDay).catch((e) => toast.error(e.message));
  useEffect(() => { load(date); }, [date]);

  const onMark = (start, mark) =>
    markBlock(date, start, mark).then(applyDay).catch((e) => toast.error(e.message));
  const onAddNote = (note) => addNote(date, note).then(applyDay).catch((e) => toast.error(e.message));
  const onToggleNoteFlag = (n) =>
    editNote(date, n.id, { flagged: !n.flagged }).then(applyDay).catch((e) => toast.error(e.message));
  const onDeleteNote = (n) => deleteNote(date, n.id).then(applyDay).catch((e) => toast.error(e.message));
  const onDismissReminder = (r) =>
    dismissReminder({ origin_date: r.origin_date, kind: r.kind, ref: r.ref })
      .then(() => load(date)).catch((e) => toast.error(e.message));
```

Update the `<DaySidebar ... />` usage (near the end of the returned JSX) to pass the new props:

```jsx
        <DaySidebar blocks={blocks} active={active} nowMin={nowMin}
          onComplete={(start) => onMark(start, { state: "done" })}
          reminders={reminders} notes={notes}
          onDismissReminder={onDismissReminder} onAddNote={onAddNote}
          onToggleNoteFlag={onToggleNoteFlag} onDeleteNote={onDeleteNote} />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix web test -- src/DayView.test.jsx`
Expected: PASS (including the existing 4 DayView tests).

- [ ] **Step 5: Run the full frontend suite**

Run: `npm --prefix web test`
Expected: all PASS.

- [ ] **Step 6: Build to catch import/JSX errors**

Run: `npm --prefix web run build`
Expected: build succeeds.

- [ ] **Step 7: Commit**

```bash
git add web/src/DaySidebar.jsx web/src/DayView.jsx web/src/DayView.test.jsx
git commit -m "feat(web): wire reminders + notes into day view sidebar"
```

---

## PHASE 4 — Manual verification

### Task 17: End-to-end smoke test

- [ ] **Step 1: Run the full backend + frontend suites**

Run: `python -m pytest -v`
Run: `npm --prefix web test`
Expected: all green.

- [ ] **Step 2: Start both servers**

Run (background): `python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload`
Run (background, from `web/`): `npm run dev`

- [ ] **Step 3: Drive the feature in the browser at http://localhost:5173**

Verify:
1. Hover a block → 💬 button → type a comment, check "Flag for tomorrow", Save. Block shows a ⚑ indicator.
2. Add a day-level note in the Notes card with the flag toggle on.
3. Click the next-day arrow → the Reminders card appears at the top of the sidebar showing both flagged items, each tagged "from <origin day>".
4. Click a reminder's ✓ → it disappears; navigate back to the origin day → the comment/note text is still there, just unflagged.
5. Confirm same-day flagged items do NOT appear in the Reminders card.

- [ ] **Step 4: Final commit (if any tweaks were needed)**

```bash
git add -A
git commit -m "test: manual verification of flagged comments & reminders"
```

---

## Self-Review Notes

- **Spec coverage:** data model (T1), v3→v4 migration (T2), pruning (T3), block render fields (T4), note CRUD (T5), `get_reminders` incl. origin<viewed, dismissed exclusion, orphan survival (T6), dismiss keeps text (T7), day payload + comment/flag on mark + flag-requires-comment 400 (T8), note endpoints with 404/400 (T9), dismiss endpoint incl. idempotent 204 (T10), api.js (T11), Radix popover dependency (T12), per-block popover + dot/⚑ indicators (T13), RemindersCard top-of-sidebar dismiss-only (T14), NotesCard add/flag/delete (T15), DaySidebar composition + DayView wiring (T16), manual E2E (T17). All spec sections map to a task.
- **Type/name consistency:** `Reminder` fields (`origin_date`, `kind`, `ref`, `text`, `block_label`, `block_time`) are used identically in core, `asdict` serialization, RemindersCard, and the dismiss payload `{origin_date, kind, ref}`. `Note` fields (`id`, `text`, `flagged`) match across core/api/NotesCard. The mark request shape `{comment, flagged}` matches `MarkIn` and `set_block_comment`/`set_block_flag` order.
- **No placeholders:** every code step contains complete code; every run step states the expected result.
