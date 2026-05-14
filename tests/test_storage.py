import json
from pathlib import Path

from habit_core import DataStore, Habit


def test_load_returns_empty_when_file_missing(data_dir: Path):
    store = DataStore(data_dir)
    assert store.load() == []


def test_save_then_load_round_trips(data_dir: Path):
    store = DataStore(data_dir)
    habits = [Habit(name="water", created="2026-05-01", completions=["2026-05-01"])]
    store.save(habits)

    again = DataStore(data_dir).load()
    assert again == habits


def test_save_creates_parent_directory(tmp_path: Path, monkeypatch):
    nested = tmp_path / "a" / "b"
    monkeypatch.setenv("HABIT_DATA_DIR", str(nested))
    store = DataStore(nested)
    store.save([Habit(name="x", created="2026-05-01", completions=[])])
    assert (nested / "data.json").exists()


def test_corrupt_file_is_backed_up_and_load_returns_empty(data_dir: Path):
    (data_dir / "data.json").write_text("{ this is not json")

    store = DataStore(data_dir)
    assert store.load() == []

    backups = list(data_dir.glob("data.json.corrupt-*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "{ this is not json"


def test_unknown_version_is_treated_as_corrupt(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({"version": 999, "habits": []}))

    store = DataStore(data_dir)
    assert store.load() == []
    assert list(data_dir.glob("data.json.corrupt-*"))
