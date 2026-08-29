"""Bausteine fuer echte Gmail-Antworten und ein Doppel des Clients."""

from __future__ import annotations

import base64
from typing import Any


def b64(text: str) -> str:
    """base64url ohne Auffuellung -- genau wie Gmail es liefert."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")


def part(mime: str, text: str = "", *, filename: str = "", size: int = 0) -> dict:
    return {
        "mimeType": mime,
        "filename": filename,
        "body": {"data": b64(text) if text else "", "size": size or len(text)},
    }


def message(
    *,
    mid: str = "m1",
    thread: str = "t1",
    labels: tuple[str, ...] = ("INBOX", "UNREAD"),
    headers: dict[str, str] | None = None,
    payload: dict | None = None,
    snippet: str = "",
) -> dict:
    kopf = {"From": "absender@example.com", "To": "ich@example.com", "Subject": "Betreff"}
    kopf.update(headers or {})
    if payload is None:
        payload = part("text/plain", "Nachrichtentext")
    payload = dict(payload)
    payload["headers"] = [{"name": k, "value": v} for k, v in kopf.items()]
    return {
        "id": mid,
        "threadId": thread,
        "labelIds": list(labels),
        "internalDate": "1740000000000",
        "snippet": snippet,
        "payload": payload,
    }


def multipart(*teile: dict, mime: str = "multipart/alternative") -> dict:
    return {"mimeType": mime, "filename": "", "body": {}, "parts": list(teile)}


class FakeGmailClient:
    """Ersetzt den echten Client. Zeichnet auf, was aufgerufen wurde."""

    def __init__(
        self,
        messages: list[dict] | None = None,
        *,
        address: str = "ich@example.com",
        labels: list[dict] | None = None,
    ) -> None:
        self._messages = {m["id"]: m for m in messages or []}
        self._address = address
        self._labels = list(labels or [])
        self._naechste_id = 1
        self.modified: list[tuple[str, list[str]]] = []
        self.created: list[str] = []
        self.queries: list[tuple[str, int]] = []

    def address(self) -> str:
        return self._address

    def list_message_ids(self, query: str, limit: int) -> list[str]:
        self.queries.append((query, limit))
        return list(self._messages)[:limit]

    def get_message(self, message_id: str) -> dict:
        return self._messages[message_id]

    def modify_labels(
        self, message_id: str, *, add: list[str] | None = None, remove: list[str] | None = None
    ) -> dict:
        self.modified.append((message_id, list(add or [])))
        return {"id": message_id}

    def list_labels(self) -> list[dict]:
        return list(self._labels)

    def create_label(self, name: str) -> dict[str, Any]:
        self.created.append(name)
        neu = {"id": f"Label_{self._naechste_id}", "name": name}
        self._naechste_id += 1
        self._labels.append(neu)
        return neu
