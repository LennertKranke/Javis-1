"""Ein Briefing je Tag."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from jarvis.core.db import transaction

__all__ = ["Briefing", "BriefingStore"]


@dataclass(frozen=True)
class Briefing:
    day: str
    created_at: str
    text: str
    facts: dict[str, Any]
    model: str | None


class BriefingStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(
        self, *, day: str, text: str, facts: dict[str, Any] | None = None, model: str | None = None
    ) -> None:
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO briefings (day, created_at, text, facts, model)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (day) DO UPDATE SET
                    created_at = excluded.created_at,
                    text       = excluded.text,
                    facts      = excluded.facts,
                    model      = excluded.model
                """,
                (
                    day,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    text[:8000],
                    json.dumps(facts or {}, ensure_ascii=False)[:8000],
                    model,
                ),
            )

    def get(self, day: str) -> Briefing | None:
        zeile = self._conn.execute("SELECT * FROM briefings WHERE day = ?", (day,)).fetchone()
        return self._briefing(zeile) if zeile else None

    def recent(self, limit: int = 7) -> list[Briefing]:
        zeilen = self._conn.execute(
            "SELECT * FROM briefings ORDER BY day DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._briefing(z) for z in zeilen]

    @staticmethod
    def _briefing(zeile: sqlite3.Row) -> Briefing:
        return Briefing(
            day=zeile["day"],
            created_at=zeile["created_at"],
            text=zeile["text"],
            facts=json.loads(zeile["facts"]),
            model=zeile["model"],
        )
