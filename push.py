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
