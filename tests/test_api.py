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
    starts = [b["start"] for b in client.get("/api/template").json()]
    assert starts == ["08:30"]


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
