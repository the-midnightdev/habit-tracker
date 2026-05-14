import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolated data directory for one test."""
    d = tmp_path / "habit-data"
    d.mkdir()
    monkeypatch.setenv("HABIT_DATA_DIR", str(d))
    return d


@pytest.fixture
def run_cli(data_dir):
    """Run habit.py as a subprocess with the isolated data dir."""
    repo_root = Path(__file__).resolve().parent.parent

    def _run(*args, stdin: str | None = None):
        env = {**os.environ, "HABIT_DATA_DIR": str(data_dir)}
        return subprocess.run(
            [sys.executable, str(repo_root / "habit.py"), *args],
            capture_output=True,
            text=True,
            input=stdin,
            env=env,
            cwd=str(repo_root),
        )

    return _run
