import json
from pathlib import Path

import pytest

from core import (
    DataStore,
    Day,
    DayBlock,
    Override,
    PlannerData,
    Reminder,
    TemplateBlock,
    ValidationError,
    validate_times,
    add_note,
    dismiss_reminder,
    edit_note,
    remove_note,
    find_note,
    get_reminders,
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
    set_block_comment,
    set_block_flag,
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
    assert "2026-05-24" not in data.days  # reading never writes


def test_set_block_state_stores_override_and_renders():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")
    blocks = get_day_blocks(data, "2026-05-24")
    assert blocks[0].state == "done"
    assert blocks[1].state == "pending"


def test_set_block_state_rejects_unknown_state():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "08:00", "maybe")


def test_set_block_state_rejects_block_not_in_template():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_state(data, "2026-05-24", "11:00", "done")


def test_set_block_label_overrides_for_that_day_only():
    data = _template_data()
    set_block_label(data, "2026-05-24", "08:00", "fixed login bug")
    assert get_day_blocks(data, "2026-05-24")[0].label == "fixed login bug"
    assert get_day_blocks(data, "2026-05-25")[0].label == "standup"


def test_set_block_label_rejects_block_not_in_template():
    data = _template_data()
    with pytest.raises(ValidationError):
        set_block_label(data, "2026-05-24", "11:00", "nope")


def test_adding_template_block_appears_on_a_day_with_existing_marks():
    # THE BUG FIX: a day with overrides still reflects later template additions.
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")  # day now has an override
    add_template_block(data, "10:00", "11:00", "review")
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00", "09:00", "10:00"]
    assert blocks[0].state == "done"      # existing mark preserved
    assert blocks[2].state == "pending"   # new block shows up, pending


def test_removing_template_block_makes_its_override_inert():
    data = _template_data()
    set_block_state(data, "2026-05-24", "09:00", "skipped")
    remove_template_block(data, "09:00")
    blocks = get_day_blocks(data, "2026-05-24")
    assert [b.start for b in blocks] == ["08:00"]  # 09:00 gone everywhere


def test_setting_state_back_to_pending_clears_override():
    data = _template_data()
    set_block_state(data, "2026-05-24", "08:00", "done")
    set_block_state(data, "2026-05-24", "08:00", "pending")
    assert "2026-05-24" not in data.days  # tidy: empty day removed


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


def test_label_override_survives_state_reset_to_pending():
    data = _template_data()
    set_block_label(data, "2026-05-24", "08:00", "fixed bug")
    set_block_state(data, "2026-05-24", "08:00", "done")
    set_block_state(data, "2026-05-24", "08:00", "pending")
    # State reset to pending, but the custom label must survive.
    blocks = get_day_blocks(data, "2026-05-24")
    assert blocks[0].state == "pending"
    assert blocks[0].label == "fixed bug"


def test_empty_day_is_not_persisted(data_dir: Path):
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="standup")],
        days={"2026-05-24": Day(overrides={})},  # empty day constructed by hand
    )
    store = DataStore(data_dir)
    store.save(data)
    assert store.load().days == {}  # empty day dropped on save


from core import TAGS


def test_add_template_block_with_tag_round_trips(data_dir: Path):
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup", tag="Deep work")
    DataStore(data_dir).save(data)
    loaded = DataStore(data_dir).load()
    assert loaded.template[0].tag == "Deep work"


def test_template_block_defaults_to_no_tag():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    assert data.template[0].tag is None


def test_v3_file_without_tag_loads_as_none(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({
        "version": 3,
        "template": [{"start": "08:00", "end": "09:00", "label": "standup"}],
        "days": {},
    }), encoding="utf-8")
    loaded = DataStore(data_dir).load()
    assert loaded.template[0].tag is None


def test_add_template_block_rejects_unknown_tag():
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_template_block(data, "08:00", "09:00", "standup", tag="Nonsense")


def test_edit_template_block_sets_tag():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup")
    edit_template_block(data, "08:00", new_start="08:00", new_end="09:00",
                        label="standup", tag="Break")
    assert data.template[0].tag == "Break"


def test_get_day_blocks_includes_tag():
    data = PlannerData()
    add_template_block(data, "08:00", "09:00", "standup", tag="Shallow")
    assert get_day_blocks(data, "2026-05-24")[0].tag == "Shallow"


def test_known_tags():
    assert TAGS == ("Deep work", "Break", "Shallow")


def test_save_then_load_round_trips_comments_and_notes(data_dir: Path):
    from core import Note
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="standup")],
        days={
            "2026-05-24": Day(
                overrides={"08:00": Override(state="done", comment="ran long", flagged=True)},
                notes=[Note(id="abc123", text="call Sam", flagged=True)],
            )
        },
    )
    DataStore(data_dir).save(data)
    assert DataStore(data_dir).load() == data


def test_v3_file_loads_with_v4_defaults(data_dir: Path):
    v3 = {
        "version": 3,
        "template": [{"start": "08:00", "end": "09:00", "label": "standup", "tag": None}],
        "days": {"2026-05-24": {"overrides": {"08:00": {"state": "done"}}}},
    }
    (data_dir / "data.json").write_text(json.dumps(v3), encoding="utf-8")
    loaded = DataStore(data_dir).load()
    ov = loaded.days["2026-05-24"].overrides["08:00"]
    assert ov.state == "done"
    assert ov.comment is None and ov.flagged is False
    assert loaded.days["2026-05-24"].notes == []


def _data_with_block():
    return PlannerData(template=[TemplateBlock(start="08:00", end="09:00", label="standup")])


def test_set_block_comment_then_clear_prunes_override():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ran long")
    assert data.days["2026-05-24"].overrides["08:00"].comment == "ran long"
    set_block_comment(data, "2026-05-24", "08:00", "")
    assert "2026-05-24" not in data.days  # pruned: pending, no label/comment/flag


def test_flag_requires_comment():
    data = _data_with_block()
    with pytest.raises(ValidationError):
        set_block_flag(data, "2026-05-24", "08:00", True)


def test_set_flag_keeps_override_when_pending():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    ov = data.days["2026-05-24"].overrides["08:00"]
    assert ov.flagged is True and ov.state == "pending"


def test_clearing_comment_also_clears_flag():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    set_block_comment(data, "2026-05-24", "08:00", "")
    assert "2026-05-24" not in data.days


def test_whitespace_only_comment_treated_as_empty():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "   ")
    assert "2026-05-24" not in data.days  # whitespace == empty, override pruned
    with pytest.raises(ValidationError):
        set_block_flag(data, "2026-05-24", "08:00", True)  # no real comment to flag


def test_get_day_blocks_includes_comment_and_flag():
    from core import get_day_blocks
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    block = get_day_blocks(data, "2026-05-24")[0]
    assert block.comment == "ping Sam" and block.flagged is True


def test_get_day_blocks_defaults_when_no_override():
    from core import get_day_blocks
    data = _data_with_block()
    block = get_day_blocks(data, "2026-05-24")[0]
    assert block.comment is None and block.flagged is False


def test_add_note_generates_id_and_stores():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "call Sam")
    assert note.id and note.text == "call Sam" and note.flagged is False
    assert data.days["2026-05-24"].notes == [note]


def test_add_empty_note_rejected():
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_note(data, "2026-05-24", "")


def test_edit_note_updates_fields():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "draft")
    edit_note(data, "2026-05-24", note.id, text="final", flagged=True)
    assert note.text == "final" and note.flagged is True


def test_edit_unknown_note_raises():
    data = PlannerData()
    add_note(data, "2026-05-24", "x")
    with pytest.raises(ValidationError):
        edit_note(data, "2026-05-24", "nope", text="y")


def test_remove_note_and_prune_day():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "x")
    assert remove_note(data, "2026-05-24", note.id) is True
    assert "2026-05-24" not in data.days  # day pruned when no overrides/notes left
    assert remove_note(data, "2026-05-24", note.id) is False


def test_get_reminders_returns_prior_day_flags_only():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    add_note(data, "2026-05-24", "buy milk", flagged=True)
    add_note(data, "2026-05-24", "unflagged note", flagged=False)

    # Viewed on the SAME day: no reminders (carryover is strictly earlier days).
    assert get_reminders(data, "2026-05-24") == []

    # Viewed the NEXT day: both flagged items surface, unflagged excluded.
    rem = get_reminders(data, "2026-05-25")
    kinds = {(r.kind, r.text) for r in rem}
    assert ("block", "ping Sam") in kinds
    assert ("note", "buy milk") in kinds
    assert all(r.text != "unflagged note" for r in rem)

    block_rem = next(r for r in rem if r.kind == "block")
    assert block_rem.block_label == "standup"
    assert block_rem.block_time == "08:00–09:00"


def test_get_reminders_excludes_dismissed_and_orphans_survive():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    # Orphan the block by removing it from the template; reminder still surfaces.
    data.template.clear()
    rem = get_reminders(data, "2026-05-25")
    assert len(rem) == 1
    assert rem[0].text == "ping Sam"
    assert rem[0].block_label is None and rem[0].block_time is None


def test_get_reminders_sorted_oldest_origin_first():
    data = _data_with_block()
    # Flag a block comment on an earlier day and a note on a later day.
    set_block_comment(data, "2026-05-20", "08:00", "older")
    set_block_flag(data, "2026-05-20", "08:00", True)
    add_note(data, "2026-05-23", "newer", flagged=True)
    rem = get_reminders(data, "2026-05-25")
    assert [r.origin_date for r in rem] == ["2026-05-20", "2026-05-23"]
    assert [r.text for r in rem] == ["older", "newer"]


def test_get_reminders_excludes_unflagged_block_comment():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "noted but not flagged")
    # No set_block_flag call -> override has a comment but is not flagged.
    assert get_reminders(data, "2026-05-25") == []


def test_dismiss_block_reminder_clears_flag_keeps_text():
    data = _data_with_block()
    set_block_comment(data, "2026-05-24", "08:00", "ping Sam")
    set_block_flag(data, "2026-05-24", "08:00", True)
    dismiss_reminder(data, "2026-05-24", "block", "08:00")
    ov = data.days["2026-05-24"].overrides["08:00"]
    assert ov.flagged is False and ov.comment == "ping Sam"  # text kept
    assert get_reminders(data, "2026-05-25") == []


def test_dismiss_note_reminder_clears_flag():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "buy milk", flagged=True)
    dismiss_reminder(data, "2026-05-24", "note", note.id)
    assert note.flagged is False and note.text == "buy milk"


def test_dismiss_is_idempotent_for_missing_target():
    data = PlannerData()
    dismiss_reminder(data, "2026-05-24", "block", "08:00")  # no raise
    dismiss_reminder(data, "2026-05-24", "note", "nope")    # no raise


def test_add_whitespace_only_note_rejected():
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_note(data, "2026-05-24", "   ")


def test_add_note_trims_text():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "  call Sam  ")
    assert note.text == "call Sam"


def test_edit_note_whitespace_text_rejected():
    data = PlannerData()
    note = add_note(data, "2026-05-24", "x")
    with pytest.raises(ValidationError):
        edit_note(data, "2026-05-24", note.id, text="   ")


def test_active_block_returns_block_containing_now():
    from core import active_block
    blocks = [DayBlock("08:00", "09:00", "a"), DayBlock("09:00", "10:00", "b")]
    assert active_block(blocks, 9 * 60 + 30).start == "09:00"


def test_active_block_excludes_done():
    from core import active_block
    blocks = [DayBlock("09:00", "10:00", "b", state="done")]
    assert active_block(blocks, 9 * 60 + 30) is None


def test_active_block_none_before_first_block():
    from core import active_block
    blocks = [DayBlock("09:00", "10:00", "b")]
    assert active_block(blocks, 8 * 60) is None


def test_active_block_end_is_exclusive():
    from core import active_block
    blocks = [DayBlock("09:00", "10:00", "b")]
    assert active_block(blocks, 10 * 60) is None


from core import Outcome, OutcomeCheckin
from core import (
    add_outcome, edit_outcome, remove_outcome, find_outcome,
    find_template_block_by_id, linked_blocks,
)
from core import set_outcome_rating


def test_add_template_block_assigns_stable_id(data_dir: Path):
    data = PlannerData()
    block = add_template_block(data, "08:00", "09:00", "standup")
    assert block.id  # non-empty
    assert find_template_block(data, "08:00").id == block.id


def test_v4_file_migrates_assigning_block_ids_and_outcomes(data_dir: Path):
    (data_dir / "data.json").write_text(json.dumps({
        "version": 4,
        "template": [{"start": "08:00", "end": "09:00", "label": "standup", "tag": None}],
        "days": {},
    }), encoding="utf-8")
    data = DataStore(data_dir).load()
    assert len(data.template) == 1
    assert data.template[0].id          # id backfilled
    assert data.outcomes == []          # initialised


def test_outcomes_and_checkins_round_trip(data_dir: Path):
    data = PlannerData(
        template=[TemplateBlock(start="08:00", end="09:00", label="walk", id="b1")],
        outcomes=[Outcome(id="o1", name="More energy", description="",
                          direction="increase", created="2026-06-01",
                          status="active", block_ids=["b1"])],
        days={"2026-06-02": Day(
            outcome_checkins={"o1": OutcomeCheckin(rating=4, at="2026-06-02T20:00:00")}
        )},
    )
    DataStore(data_dir).save(data)
    assert DataStore(data_dir).load() == data


def _seed_block(data, start="08:00", end="09:00", label="walk"):
    return add_template_block(data, start, end, label)


def test_add_outcome_links_existing_block(data_dir: Path):
    data = PlannerData()
    b = _seed_block(data)
    o = add_outcome(data, "More energy", "", "increase",
                    block_ids=[b.id], created="2026-06-01")
    assert find_outcome(data, o.id) is o
    assert [lb.id for lb in linked_blocks(data, o)] == [b.id]


def test_add_outcome_rejects_unknown_block(data_dir: Path):
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_outcome(data, "x", "", "increase", block_ids=["nope"], created="2026-06-01")


def test_add_outcome_rejects_bad_direction(data_dir: Path):
    data = PlannerData()
    with pytest.raises(ValidationError):
        add_outcome(data, "x", "", "sideways", created="2026-06-01")


def test_edit_outcome_archives_and_relinks(data_dir: Path):
    data = PlannerData()
    b = _seed_block(data)
    o = add_outcome(data, "x", "", "increase", created="2026-06-01")
    edit_outcome(data, o.id, status="archived", block_ids=[b.id])
    assert o.status == "archived"
    assert o.block_ids == [b.id]


def test_remove_outcome_drops_it_and_its_checkins(data_dir: Path):
    data = PlannerData()
    o = add_outcome(data, "x", "", "increase", created="2026-06-01")
    data.days["2026-06-02"] = Day(
        outcome_checkins={o.id: OutcomeCheckin(rating=3, at="t")})
    assert remove_outcome(data, o.id) is True
    assert find_outcome(data, o.id) is None
    assert "2026-06-02" not in data.days  # pruned: day had only that checkin


def test_linked_blocks_ignores_orphaned_ids(data_dir: Path):
    data = PlannerData()
    b = _seed_block(data)
    o = add_outcome(data, "x", "", "increase", block_ids=[b.id], created="2026-06-01")
    remove_template_block(data, b.start)         # block gone, link dangling
    assert linked_blocks(data, o) == []          # filtered at read


def test_set_outcome_rating_upserts_one_per_day(data_dir: Path):
    data = PlannerData()
    o = add_outcome(data, "x", "", "increase", created="2026-06-01")
    set_outcome_rating(data, "2026-06-02", o.id, 4, "2026-06-02T20:00:00")
    set_outcome_rating(data, "2026-06-02", o.id, 2, "2026-06-02T21:00:00")  # overwrite
    ci = data.days["2026-06-02"].outcome_checkins[o.id]
    assert ci.rating == 2 and ci.at == "2026-06-02T21:00:00"


@pytest.mark.parametrize("bad", [0, 6, -1, True])
def test_set_outcome_rating_rejects_out_of_range(data_dir: Path, bad):
    data = PlannerData()
    o = add_outcome(data, "x", "", "increase", created="2026-06-01")
    with pytest.raises(ValidationError):
        set_outcome_rating(data, "2026-06-02", o.id, bad, "t")


def test_set_outcome_rating_rejects_archived(data_dir: Path):
    data = PlannerData()
    o = add_outcome(data, "x", "", "increase", created="2026-06-01")
    edit_outcome(data, o.id, status="archived")
    with pytest.raises(ValidationError):
        set_outcome_rating(data, "2026-06-02", o.id, 3, "t")
