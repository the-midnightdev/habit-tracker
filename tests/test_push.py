from core import DayBlock
from push import compose_checkin, build_payload


def test_compose_checkin_content():
    c = compose_checkin(DayBlock("09:00", "10:00", "work", tag="Deep work"))
    assert c["title"] == "09:00 — new hour"
    assert "working on" in c["question"]
    assert c["default_label"] == "work"


def test_build_payload_carries_block_fields():
    p = build_payload("2026-06-01", DayBlock("09:00", "10:00", "work", tag="Deep work"))
    assert p["date"] == "2026-06-01"
    assert p["start"] == "09:00"
    assert p["end"] == "10:00"
    assert p["label"] == "work"
    assert p["tag"] == "Deep work"
    assert p["title"] == "09:00 — new hour"
    assert p["question"].startswith("What")
