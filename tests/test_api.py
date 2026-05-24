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
