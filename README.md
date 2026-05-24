# habit-tracker

Single-user hourly time-blocking planner: a reusable template of time blocks that
auto-fills each day, marked Pending / Done / Skipped, via a web app or a minimal CLI.

## Install (dev)

    python -m venv .venv
    .venv\Scripts\activate    # Windows
    pip install -e ".[dev]"

## CLI

    plan today                # text view of today's blocks
    plan done 8               # mark the block starting at 08:00 done today
    plan done 08:00           # same, by explicit start time
    plan skip 9               # mark the 09:00 block skipped today
    plan template             # list the recurring template

Block references accept a start hour (`8`), an explicit start time (`08:00`), or the
row number shown in `plan today`.

## Web app

Backend:

    uvicorn api:app --reload      # serves the JSON API on http://127.0.0.1:8000

Frontend:

    cd web
    npm install
    npm run dev                   # Vite dev server, proxies /api to the backend

Data is stored at `~/.plan/data.json`. Override with the `PLAN_DATA_DIR` env var.
