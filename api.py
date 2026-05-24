"""FastAPI JSON backend over the planner core."""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core import (
    DataStore,
    ValidationError,
    add_template_block,
    edit_template_block,
    get_day_blocks,
    history_dates,
    remove_template_block,
    set_block_label,
    set_block_state,
)

DEFAULT_DATA_DIR = Path.home() / ".plan"

app = FastAPI(title="Time-Blocking Planner")


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
