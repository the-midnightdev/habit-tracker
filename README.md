# habit-tracker

Single-user CLI habit tracker.

## Install (dev)

    python -m venv .venv
    .venv\Scripts\activate    # Windows
    pip install -e ".[dev]"

## Use

    habit add water
    habit done water
    habit list
    habit show water

Data is stored at `~/.habit-tracker/data.json`. Override with the
`HABIT_DATA_DIR` environment variable.
