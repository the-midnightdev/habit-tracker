"""Minimal CLI for the time-blocking planner (`plan`)."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from rich.console import Console
from rich.table import Table

from core import (
    DataStore,
    PlannerData,
    ValidationError,
    get_day_blocks,
    resolve_block_start,
    set_block_state,
)

DEFAULT_DATA_DIR = Path.home() / ".plan"
_STATE_GLYPH = {"pending": "·", "done": "[green]✓[/green]", "skipped": "[red]✗[/red]"}


def _data_dir() -> Path:
    override = os.environ.get("PLAN_DATA_DIR")
    return Path(override) if override else DEFAULT_DATA_DIR


def _load(store: DataStore, err: Console) -> PlannerData:
    def _warn(backup: Path) -> None:
        err.print(
            f"[yellow]Warning:[/yellow] data.json was corrupt; backed up to "
            f"{backup.name}. Starting empty."
        )
    return store.load(on_corrupt=_warn)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan", description="Hourly time-blocking planner")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("today", help="Show today's blocks")
    sub.add_parser("template", help="List the recurring template")
    p_done = sub.add_parser("done", help="Mark a block done today")
    p_done.add_argument("ref", help="start hour (8), start time (08:00), or row number")
    p_skip = sub.add_parser("skip", help="Mark a block skipped today")
    p_skip.add_argument("ref", help="start hour (8), start time (08:00), or row number")
    return parser


def cmd_template(store: DataStore, console: Console, err: Console) -> int:
    data = _load(store, err)
    if not data.template:
        console.print("No template blocks yet. Add them in the web app.")
        return 0
    table = Table(title="Template")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Label")
    for b in data.template:
        table.add_row(b.start, b.end, b.label)
    console.print(table)
    return 0


def cmd_today(store: DataStore, console: Console, err: Console) -> int:
    data = _load(store, err)
    blocks = get_day_blocks(data, date.today().isoformat())
    if not blocks:
        console.print("No blocks for today. Add template blocks in the web app.")
        return 0
    table = Table(title=f"Today ({date.today().isoformat()})")
    table.add_column("#", justify="right")
    table.add_column("Time")
    table.add_column("Block")
    table.add_column("State")
    for i, b in enumerate(blocks, start=1):
        table.add_row(str(i), f"{b.start}-{b.end}", b.label, _STATE_GLYPH[b.state])
    console.print(table)
    return 0


def _mark(store: DataStore, console: Console, err: Console, ref: str, state: str) -> int:
    data = _load(store, err)
    today = date.today().isoformat()
    start = resolve_block_start(get_day_blocks(data, today), ref)
    if start is None:
        err.print(f"No block matches {ref!r}. Run 'plan today' to see blocks.")
        return 1
    try:
        set_block_state(data, today, start, state)
    except ValidationError as e:
        err.print(str(e))
        return 1
    store.save(data)
    console.print(f"Marked {start} {state}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = _build_parser().parse_args(argv)
    store = DataStore(_data_dir())
    console = Console()
    err = Console(stderr=True)

    command = args.command or "today"
    if command == "today":
        return cmd_today(store, console, err)
    if command == "template":
        return cmd_template(store, console, err)
    if command == "done":
        return _mark(store, console, err, args.ref, "done")
    if command == "skip":
        return _mark(store, console, err, args.ref, "skipped")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
