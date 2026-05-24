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
    add_template_block,
    edit_template_block,
    find_template_block,
    get_day_blocks,
    history_dates,
    remove_template_block,
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


class BlockIn(BaseModel):
    start: str
    end: str
    label: str


class BlockEdit(BaseModel):
    new_start: str
    new_end: str
    label: str


class MarkIn(BaseModel):
    state: str | None = None
    label: str | None = None


@app.get("/api/template")
def list_template() -> list[dict]:
    return [asdict(b) for b in _store().load().template]


@app.post("/api/template", status_code=201)
def create_template_block(block: BlockIn) -> dict:
    store = _store()
    data = store.load()
    try:
        created = add_template_block(data, block.start, block.end, block.label)
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
            data, start, new_start=edit.new_start, new_end=edit.new_end, label=edit.label
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
    blocks = get_day_blocks(_store().load(), date_iso)
    return {"date": date_iso, "blocks": [asdict(b) for b in blocks]}


@app.post("/api/days/{date_iso}/blocks/{start}")
def mark_block(date_iso: str, start: str, mark: MarkIn) -> dict:
    store = _store()
    data = store.load()
    # Validate the block exists for this day before mutating.
    if all(b.start != start for b in get_day_blocks(data, date_iso)):
        raise HTTPException(status_code=404, detail=f"no block starts at {start!r}")
    try:
        if mark.state is not None:
            set_block_state(data, date_iso, start, mark.state)
        if mark.label is not None:
            set_block_label(data, date_iso, start, mark.label)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(data)
    blocks = get_day_blocks(data, date_iso)
    return {"date": date_iso, "blocks": [asdict(b) for b in blocks]}
