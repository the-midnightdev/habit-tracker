import json
from pathlib import Path

import pytest

from core import (
    DataStore,
    Day,
    DayBlock,
    PlannerData,
    TemplateBlock,
    ValidationError,
    validate_times,
)


def test_load_returns_empty_when_file_missing(data_dir: Path):
    assert DataStore(data_dir).load() == PlannerData()


def test_save_then_load_round_trips(data_dir: Path):
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="standup")],
        days={
            "2026-05-24": Day(
                blocks=[DayBlock(start="08:00", end="09:00", label="fixed bug", state="done")]
            )
        },
    )
    DataStore(data_dir).save(data)
    assert DataStore(data_dir).load() == data


def test_save_creates_parent_directory(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    DataStore(nested).save(PlannerData())
    assert (nested / "data.json").exists()


def test_corrupt_file_is_backed_up_and_load_returns_empty(data_dir: Path):
    (data_dir / "data.json").write_text("{ this is not json", encoding="utf-8")
    seen = []
    result = DataStore(data_dir).load(on_corrupt=seen.append)
    assert result == PlannerData()
    backups = list(data_dir.glob("data.json.corrupt-*"))
    assert len(backups) == 1
    assert seen == backups


def test_v1_schema_is_rejected_as_corrupt(data_dir: Path):
    (data_dir / "data.json").write_text(
        json.dumps({"version": 1, "habits": []}), encoding="utf-8"
    )
    assert DataStore(data_dir).load() == PlannerData()
    assert list(data_dir.glob("data.json.corrupt-*"))


def test_validate_times_accepts_valid_range():
    validate_times("08:00", "09:30")  # no exception


@pytest.mark.parametrize("start,end", [
    ("8:00", "09:00"),    # not zero-padded
    ("24:00", "09:00"),   # hour out of range
    ("08:60", "09:00"),   # minute out of range
    ("0800", "09:00"),    # missing colon
])
def test_validate_times_rejects_bad_format(start, end):
    with pytest.raises(ValidationError):
        validate_times(start, end)


def test_validate_times_rejects_start_not_before_end():
    with pytest.raises(ValidationError):
        validate_times("09:00", "09:00")
    with pytest.raises(ValidationError):
        validate_times("10:00", "09:00")
