"""Anstehende Entscheidungen -- was auf einen Menschen wartet.

Wenn eine Faehigkeit etwas tun wollte, aber nicht durfte, war das bisher ein
Protokolleintrag und sonst nichts. Ab Phase 4 wird daraus ein Vorgang, den man
im Dashboard einzeln freigeben oder verwerfen kann.

Gespeichert werden beide Haelften der urspruenglichen Entscheidung getrennt:
`fields` vom Modell, `targets` aus deterministischer Rechnung. Beim Freigeben
wird daraus wieder eine `Decision` gebaut -- und die prueft beim Anlegen
erneut, dass in der Modellhaelfte kein Ziel steckt. Eine Freigabe kann Prinzip
2.1 also nicht umgehen, auch nicht durch eine von Hand veraenderte Zeile in der
Datenbank.

Ein Vorgang steht hoechstens einmal offen; dafuer sorgt ein Teilindex in der
Datenbank, nicht eine Pruefung im Code.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from jarvis.core.db import transaction

__all__ = ["STATES", "Approval", "ApprovalStore"]

PENDING = "pending"
EXECUTED = "executed"
REJECTED = "rejected"
FAILED = "failed"
STATES = frozenset({PENDING, EXECUTED, REJECTED, FAILED})

MAX_JSON = 8000


@dataclass(frozen=True)
class Approval:
    id: int
    skill: str
    event_key: str
    action: str
    reason: str
    decided_by: str
    summary: str
    fields: dict[str, Any]
    targets: dict[str, Any]
    model: str | None
    state: str
    created_at: str
    settled_at: str | None = None
    note: str | None = None

    @property
    def pending(self) -> bool:
        return self.state == PENDING


def _dump(wert: Mapping[str, Any]) -> str:
    text = json.dumps(dict(wert), ensure_ascii=False, sort_keys=True)
    if len(text) > MAX_JSON:
        raise ValueError("Entscheidung zu gross fuer die Warteschlange")
    return text


class ApprovalStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def enqueue(
        self,
        *,
        skill: str,
        event_key: str,
        action: str,
        reason: str = "",
        decided_by: str = "",
        summary: str = "",
        fields: Mapping[str, Any] | None = None,
        targets: Mapping[str, Any] | None = None,
        model: str | None = None,
        audit_id: int | None = None,
    ) -> Approval | None:
        """Stellt einen Vorgang ein. Gibt None zurueck, wenn er schon offen ist."""
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            vorhanden = self._conn.execute(
                "SELECT id FROM approvals WHERE skill = ? AND event_key = ? AND state = ?",
                (skill, event_key, PENDING),
            ).fetchone()
            if vorhanden is not None:
                return None
            cursor = self._conn.execute(
                """
                INSERT INTO approvals
                    (skill, event_key, action, reason, decided_by, summary,
                     fields, targets, model, state, created_at, audit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill,
                    event_key,
                    action,
                    reason[:500],
                    decided_by,
                    summary[:500],
                    _dump(fields or {}),
                    _dump(targets or {}),
                    model,
                    PENDING,
                    jetzt,
                    audit_id,
                ),
            )
            neue_id = int(cursor.lastrowid or 0)
        return self.get(neue_id)

    def get(self, approval_id: int) -> Approval | None:
        zeile = self._conn.execute(
            "SELECT * FROM approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        return self._approval(zeile) if zeile else None

    def pending(self, *, limit: int = 50, skill: str | None = None) -> list[Approval]:
        if skill:
            zeilen = self._conn.execute(
                "SELECT * FROM approvals WHERE state = ? AND skill = ? "
                "ORDER BY created_at ASC, id ASC LIMIT ?",
                (PENDING, skill, limit),
            ).fetchall()
        else:
            zeilen = self._conn.execute(
                "SELECT * FROM approvals WHERE state = ? ORDER BY created_at ASC, id ASC LIMIT ?",
                (PENDING, limit),
            ).fetchall()
        return [self._approval(z) for z in zeilen]

    def recent(self, *, limit: int = 30) -> list[Approval]:
        zeilen = self._conn.execute(
            "SELECT * FROM approvals ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._approval(z) for z in zeilen]

    def count_pending(self, *, skill: str | None = None) -> int:
        if skill:
            zeile = self._conn.execute(
                "SELECT COUNT(*) FROM approvals WHERE state = ? AND skill = ?", (PENDING, skill)
            ).fetchone()
        else:
            zeile = self._conn.execute(
                "SELECT COUNT(*) FROM approvals WHERE state = ?", (PENDING,)
            ).fetchone()
        return int(zeile[0])

    def counts_by_state(self) -> dict[str, int]:
        zeilen = self._conn.execute(
            "SELECT state, COUNT(*) AS anzahl FROM approvals GROUP BY state"
        ).fetchall()
        return {z["state"]: z["anzahl"] for z in zeilen}

    def settle(self, approval_id: int, state: str, *, note: str | None = None) -> bool:
        """Schliesst einen Vorgang ab. Nur ein offener laesst sich abschliessen."""
        if state not in STATES or state == PENDING:
            raise ValueError(f"Unbrauchbarer Endzustand: {state!r}")
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            cursor = self._conn.execute(
                "UPDATE approvals SET state = ?, settled_at = ?, note = ? "
                "WHERE id = ? AND state = ?",
                (state, jetzt, (note or "")[:500] or None, approval_id, PENDING),
            )
        return (cursor.rowcount or 0) > 0

    def note(self, approval_id: int, note: str) -> None:
        """Haelt fest, warum eine Freigabe nicht ausgefuehrt wurde. Bleibt offen."""
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE approvals SET note = ? WHERE id = ? AND state = ?",
                (note[:500], approval_id, PENDING),
            )

    @staticmethod
    def _approval(zeile: sqlite3.Row) -> Approval:
        return Approval(
            id=zeile["id"],
            skill=zeile["skill"],
            event_key=zeile["event_key"],
            action=zeile["action"],
            reason=zeile["reason"],
            decided_by=zeile["decided_by"],
            summary=zeile["summary"],
            fields=json.loads(zeile["fields"]),
            targets=json.loads(zeile["targets"]),
            model=zeile["model"],
            state=zeile["state"],
            created_at=zeile["created_at"],
            settled_at=zeile["settled_at"],
            note=zeile["note"],
        )
