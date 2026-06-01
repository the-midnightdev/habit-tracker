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


import base64

from push import load_or_create_vapid


def test_vapid_created_and_persisted(tmp_path):
    k1 = load_or_create_vapid(tmp_path)
    assert "BEGIN PRIVATE KEY" in k1.private_pem
    assert k1.public_key
    k2 = load_or_create_vapid(tmp_path)  # reload returns the same keys
    assert k2.public_key == k1.public_key
    assert k2.private_pem == k1.private_pem


def test_vapid_public_key_is_uncompressed_p256_point(tmp_path):
    k = load_or_create_vapid(tmp_path)
    b64 = k.public_key
    raw = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
    assert len(raw) == 65 and raw[0] == 0x04


def test_vapid_regenerates_on_corrupt_file(tmp_path):
    (tmp_path / "vapid.json").write_text("not json", encoding="utf-8")
    k = load_or_create_vapid(tmp_path)
    assert k.public_key
