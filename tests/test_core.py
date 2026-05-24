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


from core import (
    add_template_block,
    edit_template_block,
    find_template_block,
    remove_template_block,
)


def test_add_template_block_keeps_list_sorted_by_start():
    data = PlannerData()
    add_template_block(data, "09:00", "10:00", "code")
    add_template_block(data, "08:00", "09:00", "standup")
    assert [b.start for b in data.template] == ["08:00", "09:00"]


def test_add_template_block_rejects_duplicate_start():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    with pytest.raises(ValidationError):
        add_template_block(data, "08:00", "08:30", "other")


def test_add_template_block_rejects_overlap():
    data = PlannerData()
    add_template_block(data, "08:00", "10:00", "deep work")
    with pytest.raises(ValidationError):
        add_template_block(data, "09:00", "11:00", "overlap")


def test_adjacent_blocks_do_not_overlap():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "a")
    add_template_block(data, "09:00", "10:00", "b")  # touching is allowed
    assert len(data.template) == 2


def test_find_template_block():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    assert find_template_block(data, "08:00").label == "standup"
    assert find_template_block(data, "07:00") is None


def test_edit_template_block_updates_fields_and_resorts():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    add_template_block(data, "10:00", "11:00", "code")
    edit_template_block(data, "08:00", new_start="12:00", new_end="13:00", label="lunch")
    assert [b.start for b in data.template] == ["10:00", "12:00"]
    assert find_template_block(data, "12:00").label == "lunch"


def test_edit_template_block_rejects_collision_with_other_block():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "a")
    add_template_block(data, "10:00", "11:00", "b")
    with pytest.raises(ValidationError):
        edit_template_block(data, "08:00", new_start="10:00", new_end="10:30", label="x")


def test_edit_missing_template_block_raises():
    data = PlannerData()
    with pytest.raises(ValidationError):
        edit_template_block(data, "08:00", new_start="08:00", new_end="09:00", label="x")


def test_remove_template_block():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    assert remove_template_block(data, "08:00") is True
    assert data.template == []
    assert remove_template_block(data, "08:00") is False
