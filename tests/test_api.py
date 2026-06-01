import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client(data_dir):
    # data_dir sets PLAN_DATA_DIR; api reads it per-request via the store dependency.
    return TestClient(app)


def test_template_starts_empty(client):
    resp = client.get("/api/template")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_template_block_then_list(client):
    resp = client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    assert resp.status_code == 201
    assert resp.json()["start"] == "08:00"

    listed = client.get("/api/template").json()
    assert [b["start"] for b in listed] == ["08:00"]


def test_create_overlapping_block_returns_400(client):
    client.post("/api/template", json={"start": "08:00", "end": "10:00", "label": "a"})
    resp = client.post("/api/template", json={"start": "09:00", "end": "11:00", "label": "b"})
    assert resp.status_code == 400
    assert "overlap" in resp.json()["detail"]


def test_edit_template_block(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.put(
        "/api/template/08:00",
        json={"new_start": "08:30", "new_end": "09:00", "label": "renamed"},
    )
    assert resp.status_code == 200
    assert resp.json()["label"] == "renamed"  # PUT returns the updated block
    starts = [b["start"] for b in client.get("/api/template").json()]
    assert starts == ["08:30"]


def test_edit_template_block_collision_returns_400(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "a"})
    client.post("/api/template", json={"start": "10:00", "end": "11:00", "label": "b"})
    resp = client.put(
        "/api/template/08:00",
        json={"new_start": "10:00", "new_end": "10:30", "label": "x"},
    )
    assert resp.status_code == 400


def test_edit_missing_block_returns_404(client):
    resp = client.put(
        "/api/template/08:00",
        json={"new_start": "08:00", "new_end": "09:00", "label": "x"},
    )
    assert resp.status_code == 404


def test_delete_template_block(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    assert client.delete("/api/template/08:00").status_code == 204
    assert client.get("/api/template").json() == []


def test_delete_missing_block_returns_404(client):
    assert client.delete("/api/template/08:00").status_code == 404


def test_get_day_renders_from_template_as_pending(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.get("/api/days/2026-05-24")
    assert resp.status_code == 200
    blocks = resp.json()["blocks"]
    assert blocks[0]["state"] == "pending"
    assert blocks[0]["label"] == "standup"


def test_mark_block_state(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "done"})
    assert resp.status_code == 200
    blocks = client.get("/api/days/2026-05-24").json()["blocks"]
    assert blocks[0]["state"] == "done"


def test_mark_block_label_override(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"label": "fixed bug"})
    assert resp.status_code == 200
    blocks = client.get("/api/days/2026-05-24").json()["blocks"]
    assert blocks[0]["label"] == "fixed bug"


def test_mark_block_state_and_label_together(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post(
        "/api/days/2026-05-24/blocks/08:00",
        json={"state": "done", "label": "fixed bug"},
    )
    assert resp.status_code == 200
    block = client.get("/api/days/2026-05-24").json()["blocks"][0]
    assert block["state"] == "done"
    assert block["label"] == "fixed bug"


def test_mark_bad_state_returns_400(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "maybe"})
    assert resp.status_code == 400


def test_mark_unknown_block_returns_404(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    resp = client.post("/api/days/2026-05-24/blocks/11:00", json={"state": "done"})
    assert resp.status_code == 404


def test_history_lists_touched_days(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "done"})
    assert client.get("/api/days").json() == ["2026-05-24"]


def test_added_template_block_shows_on_a_day_with_existing_marks(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "standup"})
    client.post("/api/days/2026-05-24/blocks/08:00", json={"state": "done"})
    client.post("/api/template", json={"start": "10:00", "end": "11:00", "label": "review"})
    blocks = client.get("/api/days/2026-05-24").json()["blocks"]
    assert [b["start"] for b in blocks] == ["08:00", "10:00"]
    assert blocks[0]["state"] == "done"
    assert blocks[1]["state"] == "pending"


def test_create_block_with_tag(client):
    resp = client.post("/api/template",
                       json={"start": "08:00", "end": "09:00", "label": "x", "tag": "Deep work"})
    assert resp.status_code == 201
    assert resp.json()["tag"] == "Deep work"
    assert client.get("/api/template").json()[0]["tag"] == "Deep work"


def test_create_block_with_bad_tag_returns_400(client):
    resp = client.post("/api/template",
                       json={"start": "08:00", "end": "09:00", "label": "x", "tag": "Bogus"})
    assert resp.status_code == 400


def test_day_blocks_include_tag(client):
    client.post("/api/template",
                json={"start": "08:00", "end": "09:00", "label": "x", "tag": "Break"})
    assert client.get("/api/days/2026-05-24").json()["blocks"][0]["tag"] == "Break"


def test_edit_block_sets_tag(client):
    client.post("/api/template", json={"start": "08:00", "end": "09:00", "label": "x"})
    resp = client.put("/api/template/08:00",
                      json={"new_start": "08:00", "new_end": "09:00", "label": "x", "tag": "Shallow"})
    assert resp.status_code == 200
    assert resp.json()["tag"] == "Shallow"


def _add_block(client, start="08:00", end="09:00", label="standup"):
    client.post("/api/template", json={"start": start, "end": end, "label": label})


def test_get_day_returns_notes_and_reminders_keys(client):
    _add_block(client)
    body = client.get("/api/days/2026-05-24").json()
    assert body["blocks"][0]["comment"] is None
    assert body["blocks"][0]["flagged"] is False
    assert body["notes"] == []
    assert body["reminders"] == []


def test_flagged_block_comment_becomes_reminder_next_day(client):
    _add_block(client)
    resp = client.post("/api/days/2026-05-24/blocks/08:00",
                       json={"comment": "ping Sam", "flagged": True})
    assert resp.status_code == 200
    assert resp.json()["blocks"][0]["flagged"] is True
    assert client.get("/api/days/2026-05-24").json()["reminders"] == []
    rem = client.get("/api/days/2026-05-25").json()["reminders"]
    assert len(rem) == 1 and rem[0]["text"] == "ping Sam" and rem[0]["kind"] == "block"


def test_flagging_block_without_comment_returns_400(client):
    _add_block(client)
    resp = client.post("/api/days/2026-05-24/blocks/08:00", json={"flagged": True})
    assert resp.status_code == 400


def test_create_edit_delete_note(client):
    created = client.post("/api/days/2026-05-24/notes",
                          json={"text": "call Sam", "flagged": False})
    assert created.status_code == 201
    body = created.json()
    assert body["notes"][0]["text"] == "call Sam"
    note_id = body["notes"][0]["id"]

    edited = client.put(f"/api/days/2026-05-24/notes/{note_id}",
                        json={"text": "call Sam at 3", "flagged": True})
    assert edited.status_code == 200
    assert edited.json()["notes"][0]["text"] == "call Sam at 3"
    assert edited.json()["notes"][0]["flagged"] is True

    deleted = client.delete(f"/api/days/2026-05-24/notes/{note_id}")
    assert deleted.status_code == 204
    assert client.get("/api/days/2026-05-24").json()["notes"] == []


def test_edit_unknown_note_returns_404(client):
    resp = client.put("/api/days/2026-05-24/notes/nope", json={"text": "x"})
    assert resp.status_code == 404


def test_delete_unknown_note_returns_404(client):
    resp = client.delete("/api/days/2026-05-24/notes/nope")
    assert resp.status_code == 404


def test_create_empty_note_returns_400(client):
    resp = client.post("/api/days/2026-05-24/notes", json={"text": ""})
    assert resp.status_code == 400


def test_edit_existing_note_empty_text_returns_400(client):
    created = client.post("/api/days/2026-05-24/notes", json={"text": "real"})
    note_id = created.json()["notes"][0]["id"]
    resp = client.put(f"/api/days/2026-05-24/notes/{note_id}", json={"text": "   "})
    assert resp.status_code == 400


def test_dismiss_reminder_endpoint(client):
    _add_block(client)
    client.post("/api/days/2026-05-24/blocks/08:00",
                json={"comment": "ping Sam", "flagged": True})
    assert len(client.get("/api/days/2026-05-25").json()["reminders"]) == 1

    resp = client.post("/api/reminders/dismiss",
                       json={"origin_date": "2026-05-24", "kind": "block", "ref": "08:00"})
    assert resp.status_code == 204
    assert client.get("/api/days/2026-05-25").json()["reminders"] == []


def test_dismiss_missing_reminder_is_noop_204(client):
    resp = client.post("/api/reminders/dismiss",
                       json={"origin_date": "2026-05-24", "kind": "note", "ref": "nope"})
    assert resp.status_code == 204


def test_push_key_returns_public_key(client):
    resp = client.get("/api/push/key")
    assert resp.status_code == 200
    assert resp.json()["key"]


def test_subscribe_then_unsubscribe(client, data_dir):
    from push import SubscriptionStore

    sub = {"endpoint": "https://push/abc", "keys": {"p256dh": "p", "auth": "a"}}
    assert client.post("/api/push/subscribe", json=sub).status_code == 201
    assert any(s["endpoint"] == "https://push/abc" for s in SubscriptionStore(data_dir).all())

    assert client.post("/api/push/unsubscribe", json={"endpoint": "https://push/abc"}).status_code == 204
    assert SubscriptionStore(data_dir).all() == []
