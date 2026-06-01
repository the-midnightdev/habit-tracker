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
