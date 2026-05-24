import json
from pathlib import Path

import pytest

from core import (
    DataStore,
    Day,
    DayBlock,
    Override,
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
                overrides={"08:00": Override(state="done", label="fixed bug")}
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


from core import (
    get_day_blocks,
    history_dates,
    set_block_label,
    set_block_state,
)


def _template_data():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    add_template_block(data, "09:00", "10:00", "code")
    return data


def test_get_day_blocks_renders_untouched_day_from_template_as_pending():
    data = _template_data()
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00"]
    assert all(b.state == "pending" for b in blocks)
    assert "2026-05-24" not in data.days  # reading does not materialize


def test_set_block_state_materializes_day_and_persists_state():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")
    assert "2026-05-24" in data.days
    blocks = get_day_blocks(data, "2026-05-24")
    assert blocks[0].state == "done"
    assert blocks[1].state == "pending"


def test_set_block_state_rejects_unknown_state():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "08:00", "maybe")


def test_set_block_state_rejects_unknown_block():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "11:00", "done")


def test_set_block_label_rejects_unknown_block():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_label(data, "2026-05-24", "11:00", "nope")


def test_set_block_label_overrides_for_that_day_only():
    data = _template_data()
    set_block_label(data, "2026-05-24", "08:00", "fixed login bug")
    assert get_day_blocks(data, "2026-05-24")[0].label == "fixed login bug"
    # A different, untouched day still shows the template default.
    assert get_day_blocks(data, "2026-05-25")[0].label == "standup"


def test_editing_template_does_not_touch_already_materialized_day():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")  # materialize the day
    edit_template_block(data, "08:00", new_start="08:00", new_end="09:00", label="renamed")
    remove_template_block(data, "09:00")
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00"]  # frozen copy unaffected
    assert blocks[0].label == "standup"
    assert blocks[0].state == "done"


def test_history_dates_sorted():
    data = _template_data()
    set_block_state(data, "2026-05-25", "08:00", "done")
    set_block_state(data, "2026-05-24", "08:00", "done")
    assert history_dates(data) == ["2026-05-24", "2026-05-25"]


from core import resolve_block_start


def test_resolve_block_start_by_explicit_hhmm():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    assert resolve_block_start(blocks, "09:00") == "09:00"


def test_resolve_block_start_by_bare_hour():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    assert resolve_block_start(blocks, "8") == "08:00"


def test_resolve_block_start_by_row_number_when_no_hour_match():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    # Row 2 is the 09:00 block; "2" is not a start hour here, so it means the row.
    assert resolve_block_start(blocks, "2") == "09:00"


def test_resolve_block_start_prefers_hour_over_row():
    # Genuine ambiguity: "2" is both a valid start hour (02:00) and a valid row
    # number (row 2 is 05:00). The start hour must win.
    data = PlannerData()
    add_template_block(data, "02:00", "03:00", "early")
    add_template_block(data, "05:00", "06:00", "late")
    blocks = get_day_blocks(data, "2026-05-24")
    assert blocks[1].start == "05:00"  # row 2, the value we must NOT pick
    assert resolve_block_start(blocks, "2") == "02:00"


def test_resolve_block_start_unknown_returns_none():
    blocks = get_day_blocks(_template_data(), "2026-05-24")
    assert resolve_block_start(blocks, "23:00") is None
    assert resolve_block_start(blocks, "99") is None
    assert resolve_block_start(blocks, "garbage") is None


def test_v2_file_is_migrated_to_overrides(data_dir: Path):
    # A v2 file with a done block and a stale (no-longer-in-template) pending block.
    (data_dir / "data.json").write_text(json.dumps({
        "version": 2,
        "template": [{"start": "13:00", "end": "14:00", "label": "break"}],
        "days": {
            "2026-05-24": {"blocks": [
                {"start": "13:00", "end": "14:00", "label": "break", "state": "done"},
                {"start": "11:55", "end": "13:00", "label": "work", "state": "pending"},
            ]},
        },
    }), encoding="utf-8")
    data = DataStore(data_dir).load()
    # Done block kept as an override; stale pending block dropped.
    assert data.days["2026-05-24"].overrides == {"13:00": Override(state="done")}


def test_v2_migration_keeps_custom_label_override(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({
        "version": 2,
        "template": [{"start": "13:00", "end": "14:00", "label": "break"}],
        "days": {
            "2026-05-24": {"blocks": [
                {"start": "13:00", "end": "14:00", "label": "long lunch", "state": "pending"},
            ]},
        },
    }), encoding="utf-8")
    data = DataStore(data_dir).load()
    assert data.days["2026-05-24"].overrides == {
        "13:00": Override(state="pending", label="long lunch")
    }
