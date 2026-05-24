import json
import os
from pathlib import Path


def test_template_lists_blocks(run_cli):
    import json
    import os
    from pathlib import Path

    data_dir = Path(os.environ["PLAN_DATA_DIR"])
    (data_dir / "data.json").write_text(
        json.dumps({
            "version": 2,
            "template": [{"start": "08:00", "end": "09:00", "label": "standup"}],
            "days": {},
        }),
        encoding="utf-8",
    )
    result = run_cli("template")
    assert result.returncode == 0
    assert "08:00" in result.stdout
    assert "standup" in result.stdout


def test_no_command_defaults_to_today(run_cli):
    result = run_cli()
    assert result.returncode == 0
    assert "No blocks" in result.stdout or "Today" in result.stdout


def _seed_template(block_label="standup"):
    data_dir = Path(os.environ["PLAN_DATA_DIR"])
    (data_dir / "data.json").write_text(
        json.dumps({
            "version": 2,
            "template": [
                {"start": "08:00", "end": "09:00", "label": block_label},
                {"start": "09:00", "end": "10:00", "label": "code"},
            ],
            "days": {},
        }),
        encoding="utf-8",
    )
    return data_dir


def test_done_by_bare_hour_marks_and_persists(run_cli):
    data_dir = _seed_template()
    result = run_cli("done", "8")
    assert result.returncode == 0
    saved = json.loads((data_dir / "data.json").read_text(encoding="utf-8"))
    block = saved["days"][__import__("datetime").date.today().isoformat()]["blocks"][0]
    assert block["state"] == "done"


def test_skip_by_row_number(run_cli):
    data_dir = _seed_template()
    result = run_cli("skip", "2")  # row 2 -> 09:00
    assert result.returncode == 0
    today = __import__("datetime").date.today().isoformat()
    saved = json.loads((data_dir / "data.json").read_text(encoding="utf-8"))
    states = {b["start"]: b["state"] for b in saved["days"][today]["blocks"]}
    assert states["09:00"] == "skipped"
    assert states["08:00"] == "pending"


def test_done_unknown_ref_errors(run_cli):
    _seed_template()
    result = run_cli("done", "23:00")
    assert result.returncode == 1
    assert "No block matches" in result.stderr
