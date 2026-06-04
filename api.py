"""FastAPI JSON backend over the planner core."""
from __future__ import annotations

import asyncio
import os
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import (
    DataStore,
    ValidationError,
    add_note,
    add_outcome,
    add_template_block,
    dismiss_reminder,
    edit_note,
    edit_outcome,
    edit_template_block,
    find_note,
    find_outcome,
    find_template_block,
    get_day_blocks,
    get_reminders,
    history_dates,
    remove_note,
    remove_outcome,
    remove_template_block,
    set_block_comment,
    set_block_flag,
    set_block_label,
    set_block_state,
    set_outcome_rating,
)
from outcomes import build_insight
from push import SubscriptionStore, VapidKeys, load_or_create_vapid, push_active_block

DEFAULT_DATA_DIR = Path.home() / ".plan"

app = FastAPI(title="Time-Blocking Planner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _data_dir() -> Path:
    override = os.environ.get("PLAN_DATA_DIR")
    return Path(override) if override else DEFAULT_DATA_DIR


def _store() -> DataStore:
    return DataStore(_data_dir())


def _subs() -> SubscriptionStore:
    return SubscriptionStore(_data_dir())


def _vapid() -> VapidKeys:
    return load_or_create_vapid(_data_dir())


def _day_payload(data, date_iso: str) -> dict:
    notes = data.days[date_iso].notes if date_iso in data.days else []
    return {
        "date": date_iso,
        "blocks": [asdict(b) for b in get_day_blocks(data, date_iso)],
        "notes": [asdict(n) for n in notes],
        "reminders": [asdict(r) for r in get_reminders(data, date_iso)],
    }


class BlockIn(BaseModel):
    start: str
    end: str
    label: str
    tag: str | None = None


class BlockEdit(BaseModel):
    new_start: str
    new_end: str
    label: str
    tag: str | None = None


class MarkIn(BaseModel):
    state: str | None = None
    label: str | None = None
    comment: str | None = None
    flagged: bool | None = None


class NoteIn(BaseModel):
    text: str
    flagged: bool = False


class NoteEdit(BaseModel):
    text: str | None = None
    flagged: bool | None = None


class DismissIn(BaseModel):
    origin_date: str
    kind: str
    ref: str


class SubscribeIn(BaseModel):
    endpoint: str
    keys: dict
    expirationTime: float | None = None


class UnsubscribeIn(BaseModel):
    endpoint: str


class OutcomeIn(BaseModel):
    name: str
    description: str = ""
    direction: str
    block_ids: list[str] = []


class OutcomeEdit(BaseModel):
    name: str | None = None
    description: str | None = None
    direction: str | None = None
    status: str | None = None
    block_ids: list[str] | None = None


class RatingIn(BaseModel):
    rating: int


@app.get("/api/template")
def list_template() -> list[dict]:
    return [asdict(b) for b in _store().load().template]


@app.post("/api/template", status_code=201)
def create_template_block(block: BlockIn) -> dict:
    store = _store()
    data = store.load()
    try:
        created = add_template_block(data, block.start, block.end, block.label, tag=block.tag)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return asdict(created)


@app.put("/api/template/{start}")
def update_template_block(start: str, edit: BlockEdit) -> dict:
    store = _store()
    data = store.load()
    if find_template_block(data, start) is None:
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    try:
        updated = edit_template_block(
            data, start, new_start=edit.new_start, new_end=edit.new_end, label=edit.label, tag=edit.tag
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return asdict(updated)


@app.delete("/api/template/{start}", status_code=204)
def delete_template_block(start: str) -> Response:
    store = _store()
    data = store.load()
    if not remove_template_block(data, start):
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    store.save(data)
    return Response(status_code=204)


@app.get("/api/days")
def list_history() -> list[str]:
    return history_dates(_store().load())


@app.get("/api/days/{date_iso}")
def get_day(date_iso: str) -> dict:
    return _day_payload(_store().load(), date_iso)


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


@app.post("/api/reminders/dismiss", status_code=204)
def dismiss(payload: DismissIn) -> Response:
    store = _store()
    data = store.load()
    dismiss_reminder(data, payload.origin_date, payload.kind, payload.ref)
    store.save(data)
    return Response(status_code=204)


@app.get("/api/outcomes")
def list_outcomes() -> list[dict]:
    data = _store().load()
    today = date.today().isoformat()
    day = data.days.get(today)
    out = []
    for o in data.outcomes:
        ci = day.outcome_checkins.get(o.id) if day else None
        out.append({**asdict(o),
                    "checkedToday": ci is not None,
                    "todayRating": ci.rating if ci else None})
    return out


@app.post("/api/outcomes", status_code=201)
def create_outcome(payload: OutcomeIn) -> dict:
    store = _store()
    data = store.load()
    try:
        created = add_outcome(data, payload.name, payload.description, payload.direction,
                              block_ids=payload.block_ids, created=date.today().isoformat())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return asdict(created)


@app.put("/api/outcomes/{outcome_id}")
def update_outcome(outcome_id: str, edit: OutcomeEdit) -> dict:
    store = _store()
    data = store.load()
    if find_outcome(data, outcome_id) is None:
        raise HTTPException(status_code=404, detail=f"no outcome {outcome_id!r}")
    try:
        updated = edit_outcome(data, outcome_id, name=edit.name, description=edit.description,
                               direction=edit.direction, status=edit.status, block_ids=edit.block_ids)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return asdict(updated)


@app.delete("/api/outcomes/{outcome_id}", status_code=204)
def delete_outcome(outcome_id: str) -> Response:
    store = _store()
    data = store.load()
    if not remove_outcome(data, outcome_id):
        raise HTTPException(status_code=404, detail=f"no outcome {outcome_id!r}")
    store.save(data)
    return Response(status_code=204)


@app.post("/api/days/{date_iso}/outcomes/{outcome_id}")
def rate_outcome(date_iso: str, outcome_id: str, body: RatingIn) -> dict:
    store = _store()
    data = store.load()
    if find_outcome(data, outcome_id) is None:
        raise HTTPException(status_code=404, detail=f"no outcome {outcome_id!r}")
    try:
        ci = set_outcome_rating(data, date_iso, outcome_id, body.rating, datetime.now().isoformat())
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    return {"rating": ci.rating, "at": ci.at}


@app.get("/api/outcomes/{outcome_id}/insights")
def outcome_insights(outcome_id: str) -> dict:
    data = _store().load()
    o = find_outcome(data, outcome_id)
    if o is None:
        raise HTTPException(status_code=404, detail=f"no outcome {outcome_id!r}")
    return build_insight(data, o, date.today())


@app.get("/api/push/key")
def push_key() -> dict:
    return {"key": _vapid().public_key}


@app.post("/api/push/subscribe", status_code=201)
def push_subscribe(sub: SubscribeIn) -> dict:
    _subs().add(sub.model_dump())
    return {"ok": True}


@app.post("/api/push/unsubscribe", status_code=204)
def push_unsubscribe(payload: UnsubscribeIn) -> Response:
    _subs().remove(payload.endpoint)
    return Response(status_code=204)


def seconds_to_next_hour(now: datetime) -> float:
    """Seconds from `now` until the next top-of-hour (xx:00:00)."""
    nxt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return (nxt - now).total_seconds()


async def _scheduler_loop() -> None:
    while True:
        await asyncio.sleep(seconds_to_next_hour(datetime.now()))
        try:
            push_active_block(_store(), _subs(), _vapid(), datetime.now())
        except Exception:  # noqa: BLE001 - a bad tick must not kill the loop
            pass


@app.on_event("startup")
async def _start_scheduler() -> None:
    app.state.scheduler = asyncio.create_task(_scheduler_loop())


@app.on_event("shutdown")
async def _stop_scheduler() -> None:
    task = getattr(app.state, "scheduler", None)
    if task is not None:
        task.cancel()
