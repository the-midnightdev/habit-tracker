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


from push import SubscriptionStore


def test_subscription_store_add_and_all(tmp_path):
    store = SubscriptionStore(tmp_path)
    assert store.all() == []
    store.add({"endpoint": "https://push/1", "keys": {}})
    assert [s["endpoint"] for s in store.all()] == ["https://push/1"]


def test_subscription_store_dedupes_by_endpoint(tmp_path):
    store = SubscriptionStore(tmp_path)
    store.add({"endpoint": "https://push/1", "keys": {"a": 1}})
    store.add({"endpoint": "https://push/1", "keys": {"a": 2}})
    subs = store.all()
    assert len(subs) == 1 and subs[0]["keys"] == {"a": 2}


def test_subscription_store_remove(tmp_path):
    store = SubscriptionStore(tmp_path)
    store.add({"endpoint": "https://push/1"})
    store.add({"endpoint": "https://push/2"})
    store.remove("https://push/1")
    assert [s["endpoint"] for s in store.all()] == ["https://push/2"]


def test_subscription_store_tolerates_corrupt_file(tmp_path):
    (tmp_path / "push_subscriptions.json").write_text("nope", encoding="utf-8")
    assert SubscriptionStore(tmp_path).all() == []


from datetime import datetime

from core import DataStore, PlannerData, TemplateBlock
from push import push_active_block, VapidKeys


def _fake_vapid():
    return VapidKeys(private_pem="x", public_key="y")


def _store_with_template(tmp_path):
    store = DataStore(tmp_path)
    store.save(PlannerData(template=[TemplateBlock("09:00", "10:00", "work", "Deep work")]))
    return store


def test_push_active_block_sends_to_each_subscription(tmp_path):
    store = _store_with_template(tmp_path)
    subs = SubscriptionStore(tmp_path)
    subs.add({"endpoint": "https://push/1"})
    subs.add({"endpoint": "https://push/2"})
    calls = []

    def fake_send(sub, payload, vapid):
        calls.append((sub["endpoint"], payload))

    sent = push_active_block(store, subs, _fake_vapid(), datetime(2026, 6, 1, 9, 30), send=fake_send)
    assert sent == 2
    assert {c[0] for c in calls} == {"https://push/1", "https://push/2"}
    assert calls[0][1]["start"] == "09:00"


def test_push_active_block_no_active_block_sends_nothing(tmp_path):
    store = _store_with_template(tmp_path)
    subs = SubscriptionStore(tmp_path)
    subs.add({"endpoint": "https://push/1"})
    calls = []
    sent = push_active_block(
        store, subs, _fake_vapid(), datetime(2026, 6, 1, 7, 0),
        send=lambda *a: calls.append(1),
    )
    assert sent == 0 and calls == []


def test_push_active_block_prunes_gone_subscription(tmp_path):
    store = _store_with_template(tmp_path)
    subs = SubscriptionStore(tmp_path)
    subs.add({"endpoint": "https://push/gone"})

    class Gone(Exception):
        class response:  # noqa: N801 - mimics WebPushException.response.status_code
            status_code = 410

    def fake_send(sub, payload, vapid):
        raise Gone()

    push_active_block(store, subs, _fake_vapid(), datetime(2026, 6, 1, 9, 30), send=fake_send)
    assert subs.all() == []
