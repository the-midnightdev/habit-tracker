# Background Push Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the hourly check-in notification via Web Push so it fires even when the planner tab is discarded or its window is closed (backend + Chrome background process must be alive).

**Architecture:** A new backend module `push.py` owns VAPID keys, a subscription store, payload composition, and sending via `pywebpush`. An asyncio task in the FastAPI process pushes to all subscriptions at the top of each hour. A Service Worker (`web/public/sw.js`) shows the desktop notification with Skip/Open actions; `web/src/lib/push.js` handles registration/subscription; the existing sidebar toggle is rewired to subscribe/unsubscribe.

**Tech Stack:** Python 3.13, FastAPI, pywebpush (+cryptography/py-vapid), pytest; React 18, Vite, Vitest, the Web Push + Service Worker browser APIs.

Backend commands run from `D:\habit-tracker` using the venv Python: `./.venv/Scripts/python.exe -m pytest ...`. Frontend commands run from `D:\habit-tracker\web`: `npm test -- <path>`.

---

### Task 1: `active_block` server-side helper

**Files:**
- Modify: `core.py` (add a helper near `resolve_block_start`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_core.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_core.py -k active_block -v`
Expected: FAIL with `ImportError: cannot import name 'active_block'`.

- [ ] **Step 3: Write minimal implementation** — add to `core.py` (after `resolve_block_start`):

```python
def _min_of(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def active_block(blocks: list[DayBlock], now_min: int) -> DayBlock | None:
    """The block to prompt for at now_min: the first non-done block whose
    half-open interval [start, end) contains now_min. None if nothing is active.

    Mirrors the web app's activeStart() so the server and client agree.
    """
    for b in blocks:
        if b.state != "done" and _min_of(b.start) <= now_min < _min_of(b.end):
            return b
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_core.py -k active_block -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core.py tests/test_core.py
git commit -m "feat: server-side active_block helper"
```

---

### Task 2: Add the `pywebpush` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency** — in `pyproject.toml`, change the `dependencies` line:

```toml
dependencies = ["rich>=13.0", "fastapi>=0.110", "uvicorn>=0.27"]
```
to:
```toml
dependencies = ["rich>=13.0", "fastapi>=0.110", "uvicorn>=0.27", "pywebpush>=1.14"]
```

- [ ] **Step 2: Install it into the venv**

Run: `./.venv/Scripts/python.exe -m pip install "pywebpush>=1.14"`
Expected: installs `pywebpush`, `cryptography`, `http-ece`, `py-vapid` (and deps) successfully.

- [ ] **Step 3: Verify the imports resolve**

Run: `./.venv/Scripts/python.exe -c "import pywebpush, cryptography; from cryptography.hazmat.primitives.asymmetric import ec; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pywebpush dependency"
```

---

### Task 3: Payload composition (`compose_checkin`, `build_payload`)

**Files:**
- Create: `push.py`
- Test: `tests/test_push.py`

- [ ] **Step 1: Write the failing test** — create `tests/test_push.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'push'`.

- [ ] **Step 3: Write minimal implementation** — create `push.py`:

```python
"""Web Push for the hourly check-in: payloads, VAPID keys, subscriptions, sending.

Pure helpers do not import pywebpush at module load; the network send imports it
lazily so the rest of the module (and its tests) work without a push backend.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core import DayBlock


def compose_checkin(block: DayBlock) -> dict:
    """Notification content for a block. Mirrors the JS composeCheckIn()."""
    return {
        "title": f"{block.start} — new hour",
        "question": "What are you working on this hour?",
        "default_label": block.label,
    }


def build_payload(date_iso: str, block: DayBlock) -> dict:
    """The JSON payload pushed to the Service Worker."""
    content = compose_checkin(block)
    return {
        "date": date_iso,
        "start": block.start,
        "end": block.end,
        "label": block.label,
        "tag": block.tag,
        "title": content["title"],
        "question": content["question"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add push.py tests/test_push.py
git commit -m "feat: push payload composition"
```

---

### Task 4: VAPID key generation and persistence

**Files:**
- Modify: `push.py`
- Test: `tests/test_push.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_push.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -k vapid -v`
Expected: FAIL with `ImportError: cannot import name 'load_or_create_vapid'`.

- [ ] **Step 3: Write minimal implementation** — add to `push.py` (after `build_payload`, with the new imports at the top of the file):

Add these imports below the existing `import json` line:
```python
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
```

Add this code:
```python
VAPID_FILENAME = "vapid.json"


@dataclass
class VapidKeys:
    private_pem: str  # PKCS8 PEM, passed to pywebpush as vapid_private_key
    public_key: str   # base64url uncompressed point, the browser applicationServerKey


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def load_or_create_vapid(directory: Path) -> VapidKeys:
    """Load the VAPID keypair from <directory>/vapid.json, generating and
    persisting a new P-256 keypair if the file is missing or corrupt."""
    directory = Path(directory)
    path = directory / VAPID_FILENAME
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return VapidKeys(private_pem=raw["private_pem"], public_key=raw["public_key"])
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            pass  # fall through and regenerate

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")
    point = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    keys = VapidKeys(private_pem=private_pem, public_key=_b64url(point))
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"private_pem": keys.private_pem, "public_key": keys.public_key}),
        encoding="utf-8",
    )
    return keys
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -k vapid -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add push.py tests/test_push.py
git commit -m "feat: VAPID key generation and persistence"
```

---

### Task 5: Subscription store

**Files:**
- Modify: `push.py`
- Test: `tests/test_push.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_push.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -k subscription -v`
Expected: FAIL with `ImportError: cannot import name 'SubscriptionStore'`.

- [ ] **Step 3: Write minimal implementation** — add to `push.py`:

```python
SUBSCRIPTIONS_FILENAME = "push_subscriptions.json"


class SubscriptionStore:
    """Persists browser push subscriptions to a JSON list, keyed by endpoint."""

    def __init__(self, directory: Path):
        self.path = Path(directory) / SUBSCRIPTIONS_FILENAME

    def all(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (json.JSONDecodeError, ValueError):
            return []

    def _save(self, subs: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(subs, indent=2), encoding="utf-8")

    def add(self, subscription: dict) -> None:
        endpoint = subscription.get("endpoint")
        subs = [s for s in self.all() if s.get("endpoint") != endpoint]
        subs.append(subscription)
        self._save(subs)

    def remove(self, endpoint: str) -> None:
        self._save([s for s in self.all() if s.get("endpoint") != endpoint])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -k subscription -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add push.py tests/test_push.py
git commit -m "feat: push subscription store"
```

---

### Task 6: Sending + the per-hour tick (`send_push`, `push_active_block`)

**Files:**
- Modify: `push.py`
- Test: `tests/test_push.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_push.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -k push_active_block -v`
Expected: FAIL with `ImportError: cannot import name 'push_active_block'`.

- [ ] **Step 3: Write minimal implementation** — add to `push.py` (add `from datetime import datetime` and `from core import DataStore, active_block, get_day_blocks` to the imports; `from core import DayBlock` already exists — extend that line):

Change the existing import line:
```python
from core import DayBlock
```
to:
```python
from datetime import datetime

from core import DataStore, DayBlock, active_block, get_day_blocks
```

Add this code:
```python
def send_push(subscription: dict, payload: dict, vapid: VapidKeys,
              *, claims_email: str = "admin@example.com") -> int:
    """Send one web-push. Returns the HTTP status code. Raises (via pywebpush)
    on failure; callers handle pruning by inspecting exc.response.status_code."""
    from pywebpush import webpush

    resp = webpush(
        subscription_info=subscription,
        data=json.dumps(payload),
        vapid_private_key=vapid.private_pem,
        vapid_claims={"sub": f"mailto:{claims_email}"},
    )
    return resp.status_code


def push_active_block(store: DataStore, subs: SubscriptionStore, vapid: VapidKeys,
                      now: datetime, *, send=send_push) -> int:
    """One scheduler tick: if a block is active today, push to all subscriptions.
    Subscriptions that fail with 404/410 are pruned. Returns the number sent."""
    data = store.load()
    date_iso = now.strftime("%Y-%m-%d")
    now_min = now.hour * 60 + now.minute
    block = active_block(get_day_blocks(data, date_iso), now_min)
    if block is None:
        return 0
    payload = build_payload(date_iso, block)
    sent = 0
    for sub in subs.all():
        try:
            send(sub, payload, vapid)
            sent += 1
        except Exception as exc:  # noqa: BLE001 - prune gone subs, ignore the rest
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                subs.remove(sub.get("endpoint", ""))
    return sent
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -k push_active_block -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the whole push module test file**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_push.py -v`
Expected: PASS (all push tests).

- [ ] **Step 6: Commit**

```bash
git add push.py tests/test_push.py
git commit -m "feat: web-push send and per-hour tick"
```

---

### Task 7: Push API endpoints

**Files:**
- Modify: `api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k push -v`
Expected: FAIL — 404 responses (routes not defined yet), assertions fail.

- [ ] **Step 3: Write minimal implementation** — in `api.py`:

Add to the imports near the top (after the `from core import (...)` block):
```python
from push import SubscriptionStore, VapidKeys, load_or_create_vapid
```

Replace the existing `_store` helper:
```python
def _store() -> DataStore:
    override = os.environ.get("PLAN_DATA_DIR")
    return DataStore(Path(override) if override else DEFAULT_DATA_DIR)
```
with:
```python
def _data_dir() -> Path:
    override = os.environ.get("PLAN_DATA_DIR")
    return Path(override) if override else DEFAULT_DATA_DIR


def _store() -> DataStore:
    return DataStore(_data_dir())


def _subs() -> SubscriptionStore:
    return SubscriptionStore(_data_dir())


def _vapid() -> VapidKeys:
    return load_or_create_vapid(_data_dir())
```

Add these models near the other `BaseModel` classes:
```python
class SubscribeIn(BaseModel):
    endpoint: str
    keys: dict
    expirationTime: float | None = None


class UnsubscribeIn(BaseModel):
    endpoint: str
```

Add these endpoints at the end of the file:
```python
@app.get("/api/push/key")
def push_key() -> dict:
    return {"key": _vapid().public_key}


@app.post("/api/push/subscribe", status_code=201)
def push_subscribe(sub: SubscribeIn) -> dict:
    _subs().add(sub.model_dump())
    return {"ok": True}


@app.post("/api/push/unsubscribe", status_code=204)
def push_unsubscribe(payload: UnsubscribeIn) -> Response:
    _subs().remove(payload.endpoint)
    return Response(status_code=204)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k push -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat: push subscription API endpoints"
```

---

### Task 8: Hourly scheduler task

**Files:**
- Modify: `api.py`
- Test: `tests/test_api.py`

The loop and startup/shutdown hooks are verified manually (Task 13); only the pure `seconds_to_next_hour` helper is unit-tested. The existing API tests use `TestClient(app)` **without** a `with` block, so FastAPI startup events do not fire during tests and the scheduler stays dormant there.

- [ ] **Step 1: Write the failing test** — append to `tests/test_api.py`:

```python
def test_seconds_to_next_hour():
    from datetime import datetime
    from api import seconds_to_next_hour

    assert seconds_to_next_hour(datetime(2026, 6, 1, 9, 0, 0)) == 3600
    assert seconds_to_next_hour(datetime(2026, 6, 1, 9, 59, 0)) == 60
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k next_hour -v`
Expected: FAIL with `ImportError: cannot import name 'seconds_to_next_hour'`.

- [ ] **Step 3: Write minimal implementation** — in `api.py`:

Add to the imports at the top:
```python
import asyncio
from datetime import datetime, timedelta
```

Add to the `from push import ...` line so it reads:
```python
from push import SubscriptionStore, VapidKeys, load_or_create_vapid, push_active_block
```

Add this code at the end of the file:
```python
def seconds_to_next_hour(now: datetime) -> float:
    """Seconds from `now` until the next top-of-hour (xx:00:00)."""
    nxt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return (nxt - now).total_seconds()


async def _scheduler_loop() -> None:
    while True:
        await asyncio.sleep(seconds_to_next_hour(datetime.now()))
        try:
            push_active_block(_store(), _subs(), _vapid(), datetime.now())
        except Exception:  # noqa: BLE001 - a bad tick must not kill the loop
            pass


@app.on_event("startup")
async def _start_scheduler() -> None:
    app.state.scheduler = asyncio.create_task(_scheduler_loop())


@app.on_event("shutdown")
async def _stop_scheduler() -> None:
    task = getattr(app.state, "scheduler", None)
    if task is not None:
        task.cancel()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_api.py -k next_hour -v`
Expected: PASS (1 test).

- [ ] **Step 5: Run the full backend suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — all backend tests green (core, api, cli, push).

- [ ] **Step 6: Commit**

```bash
git add api.py tests/test_api.py
git commit -m "feat: hourly push scheduler task"
```

---

### Task 9: Frontend API client functions

**Files:**
- Modify: `web/src/api.js`
- Test: `web/src/api.test.js`

- [ ] **Step 1: Write the failing test** — append to `web/src/api.test.js`:

```js
import { getPushKey, subscribePush, unsubscribePush } from "./api.js";

function mockFetch(status, body) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: async () => body,
  }));
}

test("getPushKey GETs the key endpoint", async () => {
  mockFetch(200, { key: "abc" });
  await expect(getPushKey()).resolves.toEqual({ key: "abc" });
  expect(fetch).toHaveBeenCalledWith("/api/push/key");
});

test("subscribePush POSTs the subscription body", async () => {
  mockFetch(201, { ok: true });
  const sub = { endpoint: "https://push/1", keys: { p256dh: "p", auth: "a" } };
  await subscribePush(sub);
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("/api/push/subscribe");
  expect(opts.method).toBe("POST");
  expect(JSON.parse(opts.body)).toEqual(sub);
});

test("unsubscribePush POSTs the endpoint and handles 204", async () => {
  mockFetch(204, null);
  await expect(unsubscribePush("https://push/1")).resolves.toBeNull();
  const [url, opts] = fetch.mock.calls[0];
  expect(url).toBe("/api/push/unsubscribe");
  expect(JSON.parse(opts.body)).toEqual({ endpoint: "https://push/1" });
});
```

Note: if `web/src/api.test.js` does not already restore globals between tests, add `import { afterEach, vi } from "vitest";` usage — but the existing file already imports the vitest globals it needs; only add an `afterEach(() => vi.unstubAllGlobals());` line if one is not already present.

- [ ] **Step 2: Run test to verify it fails**

Run (from `D:\habit-tracker\web`): `npm test -- src/api.test.js`
Expected: FAIL — `getPushKey`/`subscribePush`/`unsubscribePush` are not exported.

- [ ] **Step 3: Write minimal implementation** — append to `web/src/api.js`:

```js
export const getPushKey = () => request("/api/push/key");

export const subscribePush = (subscription) =>
  request("/api/push/subscribe", jsonPost(subscription));

export const unsubscribePush = (endpoint) =>
  request("/api/push/unsubscribe", jsonPost({ endpoint }));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/api.test.js`
Expected: PASS — the three new tests pass alongside the existing api tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/api.js web/src/api.test.js
git commit -m "feat(web): push API client functions"
```

---

### Task 10: Frontend push registration module

**Files:**
- Create: `web/src/lib/push.js`
- Test: `web/src/lib/push.test.js`

- [ ] **Step 1: Write the failing test** — create `web/src/lib/push.test.js`:

```js
import { afterEach, expect, test, vi } from "vitest";

vi.mock("../api.js", () => ({
  getPushKey: vi.fn().mockResolvedValue({ key: "QUJDRA" }), // base64url of "ABCD"
  subscribePush: vi.fn().mockResolvedValue({ ok: true }),
  unsubscribePush: vi.fn().mockResolvedValue(null),
}));

import * as api from "../api.js";
import { isPushSupported, subscribeToPush, unsubscribeFromPush } from "./push.js";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

test("isPushSupported is true when serviceWorker and PushManager exist", () => {
  Object.defineProperty(navigator, "serviceWorker", { value: {}, configurable: true });
  Object.defineProperty(window, "PushManager", { value: function () {}, configurable: true });
  expect(isPushSupported()).toBe(true);
});

test("subscribeToPush subscribes and posts the subscription JSON", async () => {
  const fakeSub = {
    endpoint: "https://push/1",
    toJSON: () => ({ endpoint: "https://push/1", keys: { p256dh: "p", auth: "a" } }),
  };
  const reg = { pushManager: { subscribe: vi.fn().mockResolvedValue(fakeSub) } };
  vi.stubGlobal("navigator", { serviceWorker: { ready: Promise.resolve(reg) } });

  const sub = await subscribeToPush();
  expect(reg.pushManager.subscribe).toHaveBeenCalledWith(
    expect.objectContaining({ userVisibleOnly: true })
  );
  expect(api.subscribePush).toHaveBeenCalledWith({
    endpoint: "https://push/1",
    keys: { p256dh: "p", auth: "a" },
  });
  expect(sub).toBe(fakeSub);
});

test("unsubscribeFromPush unsubscribes and tells the backend", async () => {
  const fakeSub = { endpoint: "https://push/1", unsubscribe: vi.fn().mockResolvedValue(true) };
  const reg = { pushManager: { getSubscription: vi.fn().mockResolvedValue(fakeSub) } };
  vi.stubGlobal("navigator", { serviceWorker: { ready: Promise.resolve(reg) } });

  await unsubscribeFromPush();
  expect(api.unsubscribePush).toHaveBeenCalledWith("https://push/1");
  expect(fakeSub.unsubscribe).toHaveBeenCalled();
});

test("unsubscribeFromPush is a no-op when there is no subscription", async () => {
  const reg = { pushManager: { getSubscription: vi.fn().mockResolvedValue(null) } };
  vi.stubGlobal("navigator", { serviceWorker: { ready: Promise.resolve(reg) } });

  await unsubscribeFromPush();
  expect(api.unsubscribePush).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- src/lib/push.test.js`
Expected: FAIL with `Failed to resolve import "./push.js"`.

- [ ] **Step 3: Write minimal implementation** — create `web/src/lib/push.js`:

```js
import { getPushKey, subscribePush, unsubscribePush } from "../api.js";

export function isPushSupported() {
  return (
    typeof navigator !== "undefined" &&
    "serviceWorker" in navigator &&
    typeof window !== "undefined" &&
    "PushManager" in window
  );
}

// base64url VAPID public key -> Uint8Array, as pushManager.subscribe requires.
function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function registerServiceWorker() {
  return navigator.serviceWorker.register("/sw.js");
}

export async function subscribeToPush() {
  const reg = await navigator.serviceWorker.ready;
  const { key } = await getPushKey();
  const subscription = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(key),
  });
  await subscribePush(subscription.toJSON());
  return subscription;
}

export async function unsubscribeFromPush() {
  const reg = await navigator.serviceWorker.ready;
  const subscription = await reg.pushManager.getSubscription();
  if (!subscription) return;
  await unsubscribePush(subscription.endpoint);
  await subscription.unsubscribe();
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- src/lib/push.test.js`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/push.js web/src/lib/push.test.js
git commit -m "feat(web): push registration module"
```

---

### Task 11: The Service Worker

**Files:**
- Create: `web/public/sw.js`

No unit test — jsdom cannot run a real Service Worker. It is verified manually in Task 13. Keep the logic minimal.

- [ ] **Step 1: Create the Service Worker** — create `web/public/sw.js`:

```js
/* Service Worker for hourly check-in push notifications. */

self.addEventListener("push", (event) => {
  const payload = event.data ? event.data.json() : {};
  const title = payload.title || "Time to check in";
  const body = payload.question || "What are you working on this hour?";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: "hourly-checkin",
      data: payload,
      actions: [
        { action: "skip", title: "Skip this hour" },
        { action: "open", title: "Open" },
      ],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  const data = event.notification.data || {};
  event.notification.close();

  if (event.action === "skip") {
    event.waitUntil(
      fetch(`/api/days/${data.date}/blocks/${encodeURIComponent(data.start)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ state: "skipped" }),
      })
    );
    return;
  }

  const message = { type: "checkin-open", block: data };
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        for (const client of clients) {
          if ("focus" in client) {
            client.postMessage(message);
            return client.focus();
          }
        }
        return self.clients.openWindow("/").then((c) => c && c.postMessage(message));
      })
  );
});
```

- [ ] **Step 2: Verify it is served at the origin root**

Ensure the Vite dev server is running (`npm run dev` from `web`), then run:
`curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/sw.js`
Expected: `200` (files in `web/public/` are served at the root, giving the SW root scope).

- [ ] **Step 3: Commit**

```bash
git add web/public/sw.js
git commit -m "feat(web): service worker for push notifications"
```

---

### Task 12: Rewire the toggle and listen for SW messages

**Files:**
- Modify: `web/src/DayView.jsx`

No new unit test (push/SW flows need a real browser; covered by Tasks 9–11 + manual Task 13). The existing full suite must stay green. In jsdom, `"serviceWorker" in navigator` is false, so the new message-listener effect is a no-op there, and `toggleCheckIn` is never invoked by the existing tests.

- [ ] **Step 1: Update imports** — in `web/src/DayView.jsx`:

Change:
```jsx
import { notify, requestPermission } from "./lib/notify.js";
```
to:
```jsx
import { requestPermission } from "./lib/notify.js";
import {
  isPushSupported, registerServiceWorker, subscribeToPush, unsubscribeFromPush,
} from "./lib/push.js";
```

- [ ] **Step 2: Replace `toggleCheckIn`** — change the existing handler:

```jsx
  const toggleCheckIn = async () => {
    const next = !checkInOn;
    if (next) await requestPermission();
    localStorage.setItem("checkInOn", next ? "1" : "0");
    setCheckInOn(next);
  };
```
to:
```jsx
  const toggleCheckIn = async () => {
    const next = !checkInOn;
    try {
      if (next) {
        if (!isPushSupported()) {
          toast.error("Notifications aren't supported in this browser.");
          return;
        }
        if ((await requestPermission()) !== "granted") {
          toast.error("Notification permission denied.");
          return;
        }
        await registerServiceWorker();
        await subscribeToPush();
      } else {
        await unsubscribeFromPush();
      }
    } catch (e) {
      toast.error(e.message);
      return;
    }
    localStorage?.setItem("checkInOn", next ? "1" : "0");
    setCheckInOn(next);
  };
```

- [ ] **Step 3: Remove the page-level OS notification** — in the existing firing effect, delete this single line (push now owns OS notifications):

```jsx
      notify(content.title, content.question);
```

The effect keeps composing `content` and calling `setCheckIn({ block: active, content })` — only the `notify(...)` line is removed.

- [ ] **Step 4: Add the Service Worker message listener** — add this effect immediately after the existing firing effect (the one containing `shouldCheckIn`):

```jsx
  // A notification "Open" click (handled by the Service Worker) posts a message
  // to open the in-app modal for that block.
  useEffect(() => {
    if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return;
    const onMessage = (event) => {
      const d = event.data;
      if (d && d.type === "checkin-open" && d.block) {
        setCheckIn({
          block: d.block,
          content: {
            title: d.block.title,
            question: d.block.question,
            defaultLabel: d.block.label,
          },
        });
      }
    };
    navigator.serviceWorker.addEventListener("message", onMessage);
    return () => navigator.serviceWorker.removeEventListener("message", onMessage);
  }, []);
```

- [ ] **Step 5: Run the full frontend suite**

Run (from `web`): `npm test`
Expected: PASS — all test files green (the existing DayView tests still pass; the message effect is inert in jsdom).

- [ ] **Step 6: Commit**

```bash
git add web/src/DayView.jsx
git commit -m "feat(web): drive push subscribe/unsubscribe from the check-in toggle"
```

---

### Task 13: Manual end-to-end verification

**Files:** none (verification only). Run from `D:\habit-tracker` unless noted.

- [ ] **Step 1: Restart the backend with the new code**

Stop any running uvicorn, then start it (so the scheduler task and new endpoints load):
`./.venv/Scripts/uvicorn.exe api:app --host 127.0.0.1 --port 8000`
Expected: "Application startup complete."

- [ ] **Step 2: Confirm the key endpoint works**

Run: `curl -s http://localhost:8000/api/push/key`
Expected: a JSON object like `{"key":"B...."}` (a long base64url string).

- [ ] **Step 3: Enable check-ins in a real browser**

Open `http://localhost:5173/` in Chrome. Click the **Hourly check-ins** card and **Allow** the notification permission prompt. Confirm:
- the card switches to "On — asked at the top of each hour";
- `~/.plan/push_subscriptions.json` now contains one subscription (`Get-Content $HOME\.plan\push_subscriptions.json`);
- Chrome DevTools → Application → Service Workers shows `sw.js` activated.

- [ ] **Step 4: Fire a push immediately (don't wait for xx:00)**

With check-ins enabled and the browser still open (the tab may be backgrounded), run:
```
./.venv/Scripts/python.exe -c "from pathlib import Path; from datetime import datetime; from core import DataStore; from push import SubscriptionStore, load_or_create_vapid, push_active_block; d=Path.home()/'.plan'; print('sent', push_active_block(DataStore(d), SubscriptionStore(d), load_or_create_vapid(d), datetime.now()))"
```
Expected: prints `sent 1` (or more) **and** a desktop notification appears titled like "11:00 — new hour" with **Skip this hour** and **Open** buttons. (Requires the current local time to fall inside an active block and outbound internet to the push service. If `sent 0`, no block is active at this clock time — temporarily widen the day's template or re-run during working hours.)

- [ ] **Step 5: Verify the action buttons**

- Click **Skip this hour** on the notification → confirm the active block becomes *skipped* in the app (reload the planner; the block shows skip styling). Verify via `curl -s http://localhost:8000/api/days/$(date +%Y-%m-%d) | python -m json.tool` that the block's state is `skipped`.
- Fire another push (repeat Step 4), click **Open** → Chrome focuses/opens the planner and the in-app check-in modal appears for that block.

- [ ] **Step 6: Verify background delivery**

Switch to a different application (or minimize Chrome, leaving it running), fire a push (Step 4), and confirm the desktop notification still appears while the planner tab is not focused.

- [ ] **Step 7: Confirm both test suites are green and the tree is clean**

Run: `./.venv/Scripts/python.exe -m pytest -q`  → all backend tests pass.
Run (from `web`): `npm test`  → all frontend tests pass.
Run: `git status` → no unintended changes.

---

## Notes for the implementer

- **No data-model changes.** Skips and label edits reuse the existing `set_block_state` / `set_block_label` via the existing `POST /api/days/{date}/blocks/{start}` endpoint.
- **The AI seam still lives in `compose_checkin`** — now in `push.py` (server) mirroring the JS `composeCheckIn`. If you later make check-in content AI-generated, change `compose_checkin` and the payload flows through unchanged.
- **`notify.js` stays** (its `requestPermission` is still used by the toggle); only the page-level `notify(...)` *call* is removed so push is the single source of OS notifications.
- **Dev vs prod serving:** in dev, the SW's `/api/...` fetch is proxied to the backend by Vite. In a production build, `web/public/sw.js` is emitted at the dist root and `/api` must be served by (or proxied to) the same origin as the app.
