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
        sent: list[dict] | None = None,
        capabilities: frozenset[str] | set[str] | None = None,
    ) -> None:
        self._messages = {m["id"]: m for m in messages or []}
        self._sent = {m["id"]: m for m in sent or []}
        self._address = address
        self._labels = list(labels or [])
        self._naechste_id = 1
        self._capabilities = frozenset(capabilities or {"read", "label", "draft", "send"})
        self.modified: list[tuple[str, list[str]]] = []
        self.created: list[str] = []
        self.queries: list[tuple[str, int]] = []
        self.drafts: dict[str, dict] = {}
        self.sent_drafts: list[str] = []

    def can(self, capability: str) -> bool:
        return capability in self._capabilities

    def _verlangt(self, capability: str) -> None:
        if capability not in self._capabilities:
            from jarvis.skills.mail.gmail import GmailError

            raise GmailError(f"nicht freigeschaltet: {capability}")

    def address(self) -> str:
        return self._address

    def list_message_ids(self, query: str, limit: int) -> list[str]:
        self.queries.append((query, limit))
        quelle = self._sent if "in:sent" in query else self._messages
        return list(quelle)[:limit]

    def get_message(self, message_id: str, *, fmt: str = "full", headers=None) -> dict:
        if message_id in self._messages:
            return self._messages[message_id]
        return self._sent[message_id]

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

    # --- Entwuerfe ------------------------------------------------------- #

    def create_draft(self, raw: str, *, thread_id: str | None = None) -> dict:
        """Legt den Entwurf wirklich ab -- als das, was Gmail zurueckgeben wuerde.

        Ohne das liesse sich die Abnahmebedingung aus Abschnitt 6 nicht pruefen:
        der Vergleich braucht einen echten Entwurf zum Nachrechnen.
        """
        self._verlangt("draft")
        draft_id = f"Draft_{self._naechste_id}"
        self._naechste_id += 1
        self.drafts[draft_id] = {
            "id": draft_id,
            "message": _gmail_form(raw, thread_id or ""),
        }
        return {"id": draft_id, "message": {"id": f"Msg_{draft_id}"}}

    def get_draft(self, draft_id: str) -> dict:
        self._verlangt("draft")
        return self.drafts[draft_id]

    def send_draft(self, draft_id: str) -> dict:
        self._verlangt("send")
        self.sent_drafts.append(draft_id)
        return {"id": draft_id}


def _gmail_form(raw: str, thread_id: str) -> dict:
    """Wandelt eine RFC-5322-Nachricht in die Form, die Gmail liefert."""
    import base64 as _b64
    from email import message_from_bytes
    from email.policy import SMTP as _SMTP

    roh = _b64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    nachricht = message_from_bytes(roh, policy=_SMTP)
    koerper = nachricht.get_content()
    return {
        "threadId": thread_id,
        "payload": {
            "mimeType": "text/plain",
            "filename": "",
            "headers": [{"name": k, "value": v} for k, v in nachricht.items()],
            "body": {"data": b64(koerper), "size": len(koerper)},
        },
    }
