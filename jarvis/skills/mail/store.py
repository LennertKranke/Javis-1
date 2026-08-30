"""Merkt sich, welche Nachricht schon beurteilt wurde.

Ohne das klassifiziert jeder Durchlauf denselben Posteingang erneut: teuer in
Modellaufrufen und unbrauchbar im Protokoll, weil dieselbe Nachricht dort
dutzendfach auftaucht. Der Speicher ist bewusst schmal -- Kennung, Kategorie,
Zeitpunkt. Kein Betreff, kein Text: das Postfach ist die Quelle, nicht diese
Tabelle.

Entscheidend ist der Zustand. Frueher galt eine Nachricht als erledigt, sobald
eine Zeile existierte -- auch wenn nur ein Trockenlauf sie angesehen hatte.
Der naechste echte Durchlauf hat sie dann uebersprungen, und die Beobachtungs-
woche hat still den Posteingang verbrannt. Vier Zustaende trennen das:

  seen      geholt, noch nicht beurteilt
  analysed  beurteilt, aber nichts getan -- Trockenlauf, Stufe zu niedrig,
            Gatter zu. Wird wieder aufgegriffen.
  acted     tatsaechlich gehandelt. Schliesst aus, und darauf beruht die
            Wiederholbarkeit eines echten Laufs.
  skipped   endgueltig nichts zu tun (eigene Post, schon eingeordnet).

`handled()` liefert nur acted und skipped. Alles andere kommt wieder.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jarvis.core.db import transaction

__all__ = [
    "STATE_ACTED",
    "STATE_ANALYSED",
    "STATE_SEEN",
    "STATE_SKIPPED",
    "MailRecord",
    "MailStore",
    "ReplyRecord",
    "ReplyStore",
]

STATE_SEEN = "seen"
STATE_ANALYSED = "analysed"
STATE_ACTED = "acted"
STATE_SKIPPED = "skipped"
MAIL_STATES = frozenset({STATE_SEEN, STATE_ANALYSED, STATE_ACTED, STATE_SKIPPED})

# Nur diese beiden schliessen eine Nachricht von weiteren Durchlaeufen aus.
FINAL_STATES = (STATE_ACTED, STATE_SKIPPED)


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
    needs_reply: bool = False
    state: str = STATE_SEEN


class MailStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def seen(self, message_ids: Collection[str]) -> set[str]:
        """Wovon ueberhaupt eine Zeile existiert -- ohne Aussage ueber den Zustand."""
        if not message_ids:
            return set()
        ids = list(message_ids)
        platzhalter = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT message_id FROM mail_messages WHERE message_id IN ({platzhalter})", ids
        ).fetchall()
        return {row["message_id"] for row in rows}

    def handled(self, message_ids: Collection[str]) -> set[str]:
        """Was endgueltig erledigt ist: gehandelt oder bewusst uebersprungen.

        Das und nur das schliesst eine Nachricht aus. Ein Trockenlauf setzt
        `analysed` und faellt damit nicht hierunter -- sonst waere sie fuer den
        spaeteren echten Lauf verloren.
        """
        if not message_ids:
            return set()
        ids = list(message_ids)
        platzhalter = ",".join("?" * len(ids))
        rows = self._conn.execute(
            f"SELECT message_id FROM mail_messages "
            f"WHERE message_id IN ({platzhalter}) AND state IN (?, ?)",
            [*ids, *FINAL_STATES],
        ).fetchall()
        return {row["message_id"] for row in rows}

    def cached_analysis(self, message_id: str) -> MailRecord | None:
        """Eine bereits gefaellte Beurteilung, die noch auf ihre Aktion wartet.

        Damit die Beobachtungswoche nicht bei jedem Durchlauf dieselben
        Nachrichten erneut ans Modell gibt. Der Zustand bleibt `analysed`, die
        Nachricht also weiterhin offen -- gespart wird nur der Modellaufruf.
        """
        zeile = self._conn.execute(
            "SELECT * FROM mail_messages WHERE message_id = ? AND state = ? "
            "AND category IS NOT NULL",
            (message_id, STATE_ANALYSED),
        ).fetchone()
        return self._record(zeile) if zeile else None

    def remember(
        self,
        *,
        message_id: str,
        thread_id: str = "",
        category: str | None = None,
        decided_by: str | None = None,
        labelled: bool = False,
        needs_reply: bool = False,
        state: str = STATE_SEEN,
        audit_id: int | None = None,
    ) -> None:
        if state not in MAIL_STATES:
            raise ValueError(f"Unbekannter Zustand: {state!r}")
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO mail_messages
                    (message_id, thread_id, first_seen, last_seen, category,
                     decided_by, labelled, needs_reply, state, audit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (message_id) DO UPDATE SET
                    last_seen   = excluded.last_seen,
                    category    = excluded.category,
                    decided_by  = excluded.decided_by,
                    needs_reply = excluded.needs_reply,
                    audit_id    = excluded.audit_id,
                    -- Einmal gehandelt bleibt gehandelt. Ein spaeterer
                    -- Trockenlauf darf einen echten Lauf nicht zuruecknehmen.
                    labelled    = MAX(mail_messages.labelled, excluded.labelled),
                    state       = CASE
                        WHEN mail_messages.state IN ('acted', 'skipped')
                            THEN mail_messages.state
                        ELSE excluded.state
                    END
                """,
                (
                    message_id,
                    thread_id,
                    jetzt,
                    jetzt,
                    category,
                    decided_by,
                    int(bool(labelled)),
                    int(bool(needs_reply)),
                    state,
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

    @staticmethod
    def _record(row: sqlite3.Row) -> MailRecord:
        return MailRecord(
            message_id=row["message_id"],
            thread_id=row["thread_id"] or "",
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            category=row["category"],
            decided_by=row["decided_by"],
            labelled=bool(row["labelled"]),
            audit_id=row["audit_id"],
            needs_reply=bool(row["needs_reply"]),
            state=row["state"],
        )

    def get(self, message_id: str) -> MailRecord | None:
        zeile = self._conn.execute(
            "SELECT * FROM mail_messages WHERE message_id = ?", (message_id,)
        ).fetchone()
        return self._record(zeile) if zeile else None

    def counts_by_state(self) -> dict[str, int]:
        zeilen = self._conn.execute(
            "SELECT state, COUNT(*) AS anzahl FROM mail_messages GROUP BY state"
        ).fetchall()
        return {z["state"]: z["anzahl"] for z in zeilen}

    def recent(self, limit: int = 20) -> list[MailRecord]:
        rows = self._conn.execute(
            "SELECT * FROM mail_messages ORDER BY last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._record(row) for row in rows]

    def awaiting_reply(self, categories: Collection[str], *, limit: int = 25) -> list[str]:
        """Nachrichten, die eine Antwort brauchen und noch keine geplant haben."""
        if not categories:
            return []
        platzhalter = ",".join("?" * len(categories))
        zeilen = self._conn.execute(
            f"""
            SELECT m.message_id FROM mail_messages AS m
            LEFT JOIN mail_replies AS r ON r.message_id = m.message_id
            WHERE m.needs_reply = 1
              AND m.category IN ({platzhalter})
              AND m.state IN ('analysed', 'acted')
              AND r.message_id IS NULL
            ORDER BY m.last_seen ASC
            LIMIT ?
            """,
            (*categories, limit),
        ).fetchall()
        return [z["message_id"] for z in zeilen]

    def overdue(self, categories: Collection[str], *, days: int = 3) -> int:
        """Wie viele davon schon laenger liegen als `days`.

        Eine Frist, die sich ohne Textdeutung feststellen laesst: eine Anfrage,
        die seit Tagen unbeantwortet im Postfach steht. Gerechnet wird auf
        `first_seen`, nicht auf `last_seen` -- sonst setzte jeder Durchlauf die
        Uhr zurueck.
        """
        if not categories:
            return 0
        platzhalter = ",".join("?" * len(categories))
        grenze = (datetime.now(UTC) - timedelta(days=max(0, days))).isoformat(timespec="seconds")
        zeile = self._conn.execute(
            f"""
            SELECT COUNT(*) AS anzahl FROM mail_messages AS m
            LEFT JOIN mail_replies AS r ON r.message_id = m.message_id
            WHERE m.needs_reply = 1
              AND m.category IN ({platzhalter})
              AND m.state IN ('analysed', 'acted')
              AND m.first_seen < ?
              AND (r.message_id IS NULL OR r.sent_at IS NULL)
            """,
            (*categories, grenze),
        ).fetchone()
        return int(zeile["anzahl"])


@dataclass(frozen=True)
class ReplyRecord:
    message_id: str
    thread_id: str
    recipient: str
    subject: str
    fingerprint: str
    planned_at: str
    disposition: str
    needs_human: bool
    draft_id: str | None = None
    drafted_at: str | None = None
    draft_fingerprint: str | None = None
    sent_at: str | None = None


class ReplyStore:
    """Was geantwortet werden sollte, und was tatsaechlich daraus wurde.

    `fingerprint` haelt fest, wie die Antwort im Moment der Entscheidung
    aussah. `draft_fingerprint` haelt fest, was spaeter wirklich im Postfach
    lag. Stimmen beide ueberein, ist der Entwurf der angekuendigte -- das ist
    die Abnahmebedingung aus Abschnitt 6.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def plan(
        self,
        *,
        message_id: str,
        thread_id: str,
        recipient: str,
        subject: str,
        fingerprint: str,
        disposition: str,
        needs_human: bool = False,
        draft_id: str | None = None,
        draft_fingerprint: str | None = None,
        audit_id: int | None = None,
    ) -> None:
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        gezeichnet = jetzt if draft_id else None
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO mail_replies
                    (message_id, thread_id, recipient, subject, fingerprint, planned_at,
                     disposition, needs_human, draft_id, drafted_at, draft_fingerprint,
                     audit_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (message_id) DO UPDATE SET
                    disposition       = excluded.disposition,
                    needs_human       = excluded.needs_human,
                    draft_id          = COALESCE(excluded.draft_id, mail_replies.draft_id),
                    drafted_at        = COALESCE(excluded.drafted_at, mail_replies.drafted_at),
                    draft_fingerprint = COALESCE(
                        excluded.draft_fingerprint, mail_replies.draft_fingerprint
                    )
                """,
                (
                    message_id,
                    thread_id,
                    recipient,
                    subject,
                    fingerprint,
                    jetzt,
                    disposition,
                    int(bool(needs_human)),
                    draft_id,
                    gezeichnet,
                    draft_fingerprint,
                    audit_id,
                ),
            )

    def mark_sent(self, message_id: str) -> None:
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE mail_replies SET disposition = 'sent', sent_at = ? WHERE message_id = ?",
                (jetzt, message_id),
            )

    def mark(self, message_id: str, disposition: str) -> None:
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE mail_replies SET disposition = ? WHERE message_id = ?",
                (disposition, message_id),
            )

    def get(self, message_id: str) -> ReplyRecord | None:
        zeile = self._conn.execute(
            "SELECT * FROM mail_replies WHERE message_id = ?", (message_id,)
        ).fetchone()
        return self._record(zeile) if zeile else None

    def pending_for_send(self, *, limit: int = 25) -> list[ReplyRecord]:
        """Fertige Entwuerfe, die niemand zurueckhaelt."""
        zeilen = self._conn.execute(
            """
            SELECT * FROM mail_replies
            WHERE disposition = 'drafted' AND needs_human = 0
              AND draft_id IS NOT NULL AND sent_at IS NULL
            ORDER BY planned_at ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [self._record(z) for z in zeilen]

    def with_drafts(self, *, limit: int = 200) -> list[ReplyRecord]:
        zeilen = self._conn.execute(
            "SELECT * FROM mail_replies WHERE draft_id IS NOT NULL "
            "ORDER BY planned_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._record(z) for z in zeilen]

    def recent(self, limit: int = 20) -> list[ReplyRecord]:
        zeilen = self._conn.execute(
            "SELECT * FROM mail_replies ORDER BY planned_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._record(z) for z in zeilen]

    def counts_by_disposition(self) -> dict[str, int]:
        zeilen = self._conn.execute(
            "SELECT disposition, COUNT(*) AS anzahl FROM mail_replies "
            "GROUP BY disposition ORDER BY anzahl DESC"
        ).fetchall()
        return {z["disposition"]: z["anzahl"] for z in zeilen}

    def total(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM mail_replies").fetchone()[0])

    @staticmethod
    def _record(zeile: sqlite3.Row) -> ReplyRecord:
        return ReplyRecord(
            message_id=zeile["message_id"],
            thread_id=zeile["thread_id"] or "",
            recipient=zeile["recipient"],
            subject=zeile["subject"],
            fingerprint=zeile["fingerprint"],
            planned_at=zeile["planned_at"],
            disposition=zeile["disposition"],
            needs_human=bool(zeile["needs_human"]),
            draft_id=zeile["draft_id"],
            drafted_at=zeile["drafted_at"],
            draft_fingerprint=zeile["draft_fingerprint"],
            sent_at=zeile["sent_at"],
        )
