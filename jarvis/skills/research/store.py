"""Was JARVIS recherchieren soll, und was dabei herauskam.

Zwei Tabellen, dasselbe Zustandsmodell wie bei Mail und Kalender: eine Frage
ist `seen`, `analysed`, `acted` oder `skipped`. Ein Trockenlauf verbraucht
eine Frage nicht -- sie bleibt offen, bis wirklich recherchiert wurde.

Die Frage wird normalisiert abgelegt. Sie kann aus einer Mail stammen und ist
damit Fremdtext; wer sie speichert, speichert bereits Gesaeubertes.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.core.db import transaction
from jarvis.skills.mail.store import (
    FINAL_STATES,
    MAIL_STATES,
    STATE_SEEN,
)

__all__ = ["Frage", "Fund", "ResearchStore"]

MAX_FRAGE = 400


@dataclass(frozen=True)
class Frage:
    id: int
    question: str
    asked_at: str
    state: str
    category: str | None
    keywords: str
    origin: str


@dataclass(frozen=True)
class Fund:
    id: int
    question_id: int
    source: str
    title: str
    snippet: str
    reference: str
    found_at: str


class ResearchStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    # --- Fragen -------------------------------------------------------- #

    def ask(self, question: str, *, origin: str = "cli") -> Frage:
        """Legt eine Frage an. Doppelte Fragen werden nicht doppelt gefuehrt."""
        sauber = " ".join(question.split())[:MAX_FRAGE]
        if not sauber:
            raise ValueError("Leere Frage")
        vorhanden = self._conn.execute(
            "SELECT * FROM research_questions WHERE question = ? AND state NOT IN (?, ?)",
            (sauber, *FINAL_STATES),
        ).fetchone()
        if vorhanden is not None:
            return self._frage(vorhanden)

        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            cur = self._conn.execute(
                "INSERT INTO research_questions (question, asked_at, state, origin) "
                "VALUES (?, ?, ?, ?)",
                (sauber, jetzt, STATE_SEEN, origin),
            )
            kennung = int(cur.lastrowid or 0)
        gelesen = self.get(kennung)
        assert gelesen is not None
        return gelesen

    def get(self, question_id: int) -> Frage | None:
        zeile = self._conn.execute(
            "SELECT * FROM research_questions WHERE id = ?", (question_id,)
        ).fetchone()
        return self._frage(zeile) if zeile else None

    def open_questions(self, *, limit: int = 25) -> list[Frage]:
        zeilen = self._conn.execute(
            "SELECT * FROM research_questions WHERE state NOT IN (?, ?) ORDER BY id ASC LIMIT ?",
            (*FINAL_STATES, limit),
        ).fetchall()
        return [self._frage(z) for z in zeilen]

    def set_state(
        self, question_id: int, state: str, *, category: str | None = None, keywords: str = ""
    ) -> None:
        if state not in MAIL_STATES:
            raise ValueError(f"Unbekannter Zustand: {state!r}")
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE research_questions SET state = ?, "
                "category = COALESCE(?, category), "
                "keywords = CASE WHEN ? = '' THEN keywords ELSE ? END "
                "WHERE id = ?",
                (state, category, keywords, keywords, question_id),
            )

    def counts_by_state(self) -> dict[str, int]:
        zeilen = self._conn.execute(
            "SELECT state, COUNT(*) AS anzahl FROM research_questions GROUP BY state"
        ).fetchall()
        return {z["state"]: z["anzahl"] for z in zeilen}

    # --- Funde --------------------------------------------------------- #

    def record(
        self, question_id: int, *, source: str, title: str, snippet: str, reference: str = ""
    ) -> None:
        with transaction(self._conn):
            self._conn.execute(
                "INSERT INTO research_findings "
                "(question_id, source, title, snippet, reference, found_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    question_id,
                    source,
                    title[:200],
                    snippet[:2000],
                    reference[:300],
                    datetime.now(UTC).isoformat(timespec="seconds"),
                ),
            )

    def findings(self, question_id: int, *, limit: int = 50) -> list[Fund]:
        zeilen = self._conn.execute(
            "SELECT * FROM research_findings WHERE question_id = ? ORDER BY id ASC LIMIT ?",
            (question_id, limit),
        ).fetchall()
        return [self._fund(z) for z in zeilen]

    def count_findings(self, question_id: int) -> int:
        zeile = self._conn.execute(
            "SELECT COUNT(*) FROM research_findings WHERE question_id = ?", (question_id,)
        ).fetchone()
        return int(zeile[0])

    # ------------------------------------------------------------------ #

    @staticmethod
    def _frage(zeile: sqlite3.Row) -> Frage:
        return Frage(
            id=zeile["id"],
            question=zeile["question"],
            asked_at=zeile["asked_at"],
            state=zeile["state"],
            category=zeile["category"],
            keywords=zeile["keywords"],
            origin=zeile["origin"],
        )

    @staticmethod
    def _fund(zeile: sqlite3.Row) -> Fund:
        return Fund(
            id=zeile["id"],
            question_id=zeile["question_id"],
            source=zeile["source"],
            title=zeile["title"],
            snippet=zeile["snippet"],
            reference=zeile["reference"],
            found_at=zeile["found_at"],
        )
