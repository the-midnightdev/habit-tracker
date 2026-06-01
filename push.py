"""Web Push for the hourly check-in: payloads, VAPID keys, subscriptions, sending.

Pure helpers do not import pywebpush at module load; the network send imports it
lazily so the rest of the module (and its tests) work without a push backend.
"""
from __future__ import annotations

import base64
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from dataclasses import dataclass
from pathlib import Path

from datetime import datetime

from core import DataStore, DayBlock, active_block, get_day_blocks


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
