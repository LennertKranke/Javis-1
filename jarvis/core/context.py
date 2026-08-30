"""Kurzzeitkontext und der Bauplan fuer das, was ins Modell geht.

Zwei Dinge werden hier streng getrennt, und diese Trennung ist der Grund,
warum es die Datei gibt:

  Speicherung   Was JARVIS aufbewahrt: Protokoll, Antwortvorgaenge,
                Gedaechtnis, Logdateien. Waechst mit der Nutzungsdauer.
  Kontext       Was bei einer einzelnen Anfrage tatsaechlich ans Modell geht.
                Ist beschraenkt und bleibt es.

Ohne diese Trennung waechst der Kontext mit der Speicherung: nach einem Jahr
Betrieb ginge die gesamte Geschichte bei jeder Klassifizierung mit, und der
Assistent waere langsam, teuer und irgendwann unbrauchbar.

Der `ContextBuilder` ist die einzige Stelle, die entscheidet was mitgeht. Er
kennt drei Quellen -- eine Praeambel, das Langzeitgedaechtnis und den
Kurzzeitkontext -- und er kennt eine Obergrenze. Was nicht hineinpasst, faellt
heraus und wird gezaehlt, damit es auffaellt.

Das Protokoll ist ausdruecklich keine Quelle. Es ist der Nachweis, was
geschehen ist, und gehoert nicht in einen Prompt. Dasselbe gilt fuer die
technischen Logs.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.core.db import transaction
from jarvis.core.memory import LongTermMemory, MemoryFact

__all__ = [
    "BuiltContext",
    "ContextBudget",
    "ContextBuilder",
    "ContextEntry",
    "ShortTermContext",
]

MAX_ENTRY_CHARS = 1000


@dataclass(frozen=True)
class ContextEntry:
    id: int
    scope: str
    kind: str
    text: str
    created_at: str

    def as_line(self) -> str:
        return f"- {self.kind}: {self.text}"


class ShortTermContext:
    """Ein knapper, selbst beschneidender Verlauf je Bereich.

    "Bereich" ist zum Beispiel ein Mail-Thread oder eine Unterhaltung. Aeltere
    Eintraege fallen beim Schreiben heraus -- die Tabelle kann also nicht
    unbemerkt wachsen, und niemand muss sie spaeter aufraeumen.
    """

    def __init__(self, conn: sqlite3.Connection, *, scope: str, max_entries: int = 20) -> None:
        self._conn = conn
        self._scope = scope
        self._max_entries = max(1, max_entries)

    @property
    def scope(self) -> str:
        return self._scope

    def append(self, kind: str, text: str) -> ContextEntry:
        inhalt = " ".join(text.split())[:MAX_ENTRY_CHARS]
        if not inhalt:
            raise ValueError("Leerer Eintrag")
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            cursor = self._conn.execute(
                "INSERT INTO context_entries (scope, kind, text, created_at) VALUES (?, ?, ?, ?)",
                (self._scope, kind, inhalt, jetzt),
            )
            neue_id = int(cursor.lastrowid or 0)
            # Beim Schreiben beschneiden. Sonst waechst der Verlauf still.
            self._conn.execute(
                """
                DELETE FROM context_entries
                WHERE scope = ? AND id NOT IN (
                    SELECT id FROM context_entries WHERE scope = ?
                    ORDER BY id DESC LIMIT ?
                )
                """,
                (self._scope, self._scope, self._max_entries),
            )
        return ContextEntry(id=neue_id, scope=self._scope, kind=kind, text=inhalt, created_at=jetzt)

    def recent(self, limit: int | None = None) -> list[ContextEntry]:
        zeilen = self._conn.execute(
            "SELECT * FROM context_entries WHERE scope = ? ORDER BY id DESC LIMIT ?",
            (self._scope, limit or self._max_entries),
        ).fetchall()
        return [
            ContextEntry(
                id=z["id"],
                scope=z["scope"],
                kind=z["kind"],
                text=z["text"],
                created_at=z["created_at"],
            )
            for z in reversed(zeilen)
        ]

    def clear(self) -> int:
        with transaction(self._conn):
            cursor = self._conn.execute(
                "DELETE FROM context_entries WHERE scope = ?", (self._scope,)
            )
        return cursor.rowcount or 0

    def count(self) -> int:
        return int(
            self._conn.execute(
                "SELECT COUNT(*) FROM context_entries WHERE scope = ?", (self._scope,)
            ).fetchone()[0]
        )


@dataclass(frozen=True)
class ContextBudget:
    """Die Obergrenze. Sie ist eine Zusicherung, keine Empfehlung."""

    max_chars: int = 4000
    max_facts: int = 12
    max_entries: int = 8


@dataclass(frozen=True)
class BuiltContext:
    text: str
    facts: tuple[MemoryFact, ...] = ()
    entries: tuple[ContextEntry, ...] = ()
    dropped_facts: int = 0
    dropped_entries: int = 0

    @property
    def chars(self) -> int:
        return len(self.text)

    @property
    def truncated(self) -> bool:
        return bool(self.dropped_facts or self.dropped_entries)


class ContextBuilder:
    """Entscheidet pro Anfrage, was tatsaechlich mitgeht.

    Quellen sind eine Praeambel (etwa eine Stilbeschreibung), das
    Langzeitgedaechtnis und der Kurzzeitkontext. Mehr nicht -- insbesondere
    kein Protokoll, keine Logdateien, keine Nachrichtentexte.

    Die Praeambel hat Vorrang: sie stammt vom aufrufenden Code und ist die
    Anweisung selbst. Danach kommen Tatsachen, dann der Verlauf. Was die
    Obergrenze sprengt, faellt heraus und wird gezaehlt.
    """

    def __init__(
        self,
        *,
        memory: LongTermMemory | None = None,
        short_term: ShortTermContext | None = None,
        budget: ContextBudget | None = None,
    ) -> None:
        self._memory = memory
        self._short_term = short_term
        self._budget = budget or ContextBudget()

    @property
    def budget(self) -> ContextBudget:
        return self._budget

    def build(self, *, preamble: str = "", terms: str = "") -> BuiltContext:
        teile: list[str] = []
        verbleibend = self._budget.max_chars

        kopf = preamble.strip()
        if kopf:
            kopf = kopf[:verbleibend]
            teile.append(kopf)
            verbleibend -= len(kopf)

        fakten: list[MemoryFact] = []
        verworfene_fakten = 0
        if self._memory is not None and verbleibend > 0:
            kandidaten = self._memory.relevant(terms, limit=self._budget.max_facts)
            zeilen: list[str] = []
            for fakt in kandidaten:
                zeile = fakt.as_line()
                if len(zeile) + 1 > verbleibend:
                    verworfene_fakten += 1
                    continue
                zeilen.append(zeile)
                fakten.append(fakt)
                verbleibend -= len(zeile) + 1
            if zeilen:
                teile.append("Dauerhaft bekannt:\n" + "\n".join(zeilen))

        eintraege: list[ContextEntry] = []
        verworfene_eintraege = 0
        if self._short_term is not None and verbleibend > 0:
            kandidaten_e = self._short_term.recent(self._budget.max_entries)
            zeilen = []
            for eintrag in kandidaten_e:
                zeile = eintrag.as_line()
                if len(zeile) + 1 > verbleibend:
                    verworfene_eintraege += 1
                    continue
                zeilen.append(zeile)
                eintraege.append(eintrag)
                verbleibend -= len(zeile) + 1
            if zeilen:
                teile.append("Zuletzt:\n" + "\n".join(zeilen))

        text = "\n\n".join(t for t in teile if t)
        # Letzte Sicherung. Die Rechnung oben sollte reichen; falls nicht,
        # gilt trotzdem die Obergrenze.
        text = text[: self._budget.max_chars]
        return BuiltContext(
            text=text,
            facts=tuple(fakten),
            entries=tuple(eintraege),
            dropped_facts=verworfene_fakten,
            dropped_entries=verworfene_eintraege,
        )
