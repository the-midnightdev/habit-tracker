"""FastAPI JSON backend over the planner core."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

DEFAULT_DATA_DIR = Path.home() / ".plan"

app = FastAPI(title="Time-Blocking Planner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _store() -> DataStore:
    override = os.environ.get("PLAN_DATA_DIR")
    return DataStore(Path(override) if override else DEFAULT_DATA_DIR)


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
