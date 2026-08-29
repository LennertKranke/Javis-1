"""Merkt sich, welche Nachricht schon beurteilt wurde.

Ohne das klassifiziert jeder Durchlauf denselben Posteingang erneut: teuer in
Modellaufrufen und unbrauchbar im Protokoll, weil dieselbe Nachricht dort
dutzendfach auftaucht. Der Speicher ist bewusst schmal -- Kennung, Kategorie,
Zeitpunkt. Kein Betreff, kein Text: das Postfach ist die Quelle, nicht diese
Tabelle.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.core.db import transaction

__all__ = ["MailRecord", "MailStore"]


@dataclass(frozen=True)
class MailRecord:
    message_id: str
    thread_id: str
    first_seen: str
    last_seen: str
    category: str | None
    decided_by: str | None
    labelled: bool
    audit_id: int | None


class MailStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def seen(self, message_ids: Collection[str]) -> set[str]:
        if not message_ids:
            return set()
        ids = list(message_ids)
        platzhalter = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT message_id FROM mail_messages WHERE message_id IN ({platzhalter})", ids
        ).fetchall()
        return {row["message_id"] for row in rows}

    def remember(
        self,
        *,
        message_id: str,
        thread_id: str = "",
        category: str | None = None,
        decided_by: str | None = None,
        labelled: bool = False,
        audit_id: int | None = None,
    ) -> None:
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO mail_messages
                    (message_id, thread_id, first_seen, last_seen, category,
                     decided_by, labelled, audit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (message_id) DO UPDATE SET
                    last_seen  = excluded.last_seen,
                    category   = excluded.category,
                    decided_by = excluded.decided_by,
                    labelled   = excluded.labelled,
                    audit_id   = excluded.audit_id
                """,
                (
                    message_id,
                    thread_id,
                    jetzt,
                    jetzt,
                    category,
                    decided_by,
                    int(bool(labelled)),
                    audit_id,
                ),
            )

    def counts_by_category(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT category, COUNT(*) AS anzahl FROM mail_messages "
            "WHERE category IS NOT NULL GROUP BY category ORDER BY anzahl DESC"
        ).fetchall()
        return {row["category"]: row["anzahl"] for row in rows}

    def total(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM mail_messages").fetchone()[0])

    def labelled_count(self) -> int:
        return int(
            self._conn.execute("SELECT COUNT(*) FROM mail_messages WHERE labelled = 1").fetchone()[
                0
            ]
        )

    def recent(self, limit: int = 20) -> list[MailRecord]:
        rows = self._conn.execute(
            "SELECT * FROM mail_messages ORDER BY last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            MailRecord(
                message_id=row["message_id"],
                thread_id=row["thread_id"] or "",
                first_seen=row["first_seen"],
                last_seen=row["last_seen"],
                category=row["category"],
                decided_by=row["decided_by"],
                labelled=bool(row["labelled"]),
                audit_id=row["audit_id"],
            )
            for row in rows
        ]
