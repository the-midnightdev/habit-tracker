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
