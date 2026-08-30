"""Langzeitgedaechtnis: wenige Tatsachen, ausdruecklich abgelegt.

Der Unterschied zum Protokoll ist der Zweck. Das Protokoll haelt fest, was
geschehen ist -- vollstaendig, unveraenderlich, fuer den Nachweis. Das
Gedaechtnis haelt fest, was dauerhaft gilt: eine Vorliebe, eine Adresse, eine
Absprache. Es ist klein, es wird von Hand oder von einer Faehigkeit
ausdruecklich beschrieben, und es waechst nicht von selbst mit.

Das ist die entscheidende Eigenschaft. Ein Assistent, der jede Unterhaltung
aufbewahrt und beim naechsten Aufruf mitschickt, wird mit jeder Woche teurer
und langsamer, bis er im eigenen Verlauf erstickt. Hier landet nur, was jemand
bewusst abgelegt hat -- und auch das geht nur ueber den `ContextBuilder` ins
Modell, der eine Obergrenze durchsetzt.

Was hier ausdruecklich nicht hineingehoert: Gespraechsverlaeufe, Werkzeug-
ergebnisse, Protokolleintraege, Logzeilen, Nachrichtentexte.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.core.db import transaction

__all__ = ["CATEGORIES", "LongTermMemory", "MemoryFact"]

MAX_KEY = 80
MAX_VALUE = 500

#: Obergrenze fuer dauerhaft abgelegte Tatsachen.
#:
#: Ohne sie waechst der Speicher unbegrenzt. Das faellt lange nicht auf, weil
#: der Kontextbauer ohnehin nur wenige Tatsachen mitgibt -- aber `relevant()`
#: bewertet bis zu 500 Eintraege bei jeder Anfrage, und die Datenbank waechst
#: mit jeder je gemerkten Kleinigkeit weiter.
#:
#: Verdraengt wird die unwichtigste, bei gleichem Gewicht die aelteste. Wer
#: etwas dauerhaft behalten will, gibt ihm ein hoeheres Gewicht.
MAX_FAKTEN = 500

CATEGORIES = frozenset({"praeferenz", "person", "termin", "entscheidung", "zugang", "sonstiges"})

_KEY_RE = re.compile(r"[^a-z0-9_.:-]+")
_WORT_RE = re.compile(r"[a-z0-9]{3,}")


def normalise_key(key: str) -> str:
    sauber = _KEY_RE.sub("_", key.strip().lower()).strip("_")
    if not sauber:
        raise ValueError("Leerer Schluessel")
    return sauber[:MAX_KEY]


@dataclass(frozen=True)
class MemoryFact:
    key: str
    value: str
    category: str
    source: str
    weight: float
    created_at: str
    updated_at: str

    def as_line(self) -> str:
        return f"- {self.key}: {self.value}"


class LongTermMemory:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def remember(
        self,
        key: str,
        value: str,
        *,
        category: str = "sonstiges",
        source: str = "",
        weight: float = 1.0,
    ) -> MemoryFact:
        """Legt eine Tatsache ab oder ersetzt sie. Immer ein bewusster Schritt."""
        schluessel = normalise_key(key)
        inhalt = " ".join(value.split())[:MAX_VALUE]
        if not inhalt:
            raise ValueError("Leerer Wert")
        if category not in CATEGORIES:
            bekannt = ", ".join(sorted(CATEGORIES))
            raise ValueError(f"Unbekannte Kategorie {category!r} (bekannt: {bekannt})")

        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO memory_facts
                    (key, value, category, source, weight, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (key) DO UPDATE SET
                    value      = excluded.value,
                    category   = excluded.category,
                    source     = excluded.source,
                    weight     = excluded.weight,
                    updated_at = excluded.updated_at
                """,
                (schluessel, inhalt, category, source, float(weight), jetzt, jetzt),
            )
        self._verdraenge()
        gemerkt = self.get(schluessel)
        assert gemerkt is not None
        return gemerkt

    def forget(self, key: str) -> bool:
        with transaction(self._conn):
            cursor = self._conn.execute(
                "DELETE FROM memory_facts WHERE key = ?", (normalise_key(key),)
            )
        return (cursor.rowcount or 0) > 0

    def get(self, key: str) -> MemoryFact | None:
        zeile = self._conn.execute(
            "SELECT * FROM memory_facts WHERE key = ?", (normalise_key(key),)
        ).fetchone()
        return self._fact(zeile) if zeile else None

    def _verdraenge(self, *, obergrenze: int = MAX_FAKTEN) -> int:
        """Haelt den Bestand unter der Obergrenze.

        Nicht die aeltesten fliegen, sondern die unwichtigsten: `weight` ist
        die Angabe, wie sehr etwas behalten werden soll. Bei gleichem Gewicht
        entscheidet das Alter. Was gerade geschrieben wurde, ueberlebt damit
        nicht automatisch -- sonst verdraengte ein Schwall Belangloses alles
        Wichtige.
        """
        anzahl = self.count()
        if anzahl <= obergrenze:
            return 0
        with transaction(self._conn):
            cur = self._conn.execute(
                """
                DELETE FROM memory_facts WHERE key IN (
                    SELECT key FROM memory_facts
                    ORDER BY weight ASC, updated_at ASC, key ASC
                    LIMIT ?
                )
                """,
                (anzahl - obergrenze,),
            )
            return int(cur.rowcount)

    def all(self, *, limit: int = 100, category: str | None = None) -> list[MemoryFact]:
        if category:
            zeilen = self._conn.execute(
                "SELECT * FROM memory_facts WHERE category = ? "
                "ORDER BY weight DESC, key ASC LIMIT ?",
                (category, limit),
            ).fetchall()
        else:
            zeilen = self._conn.execute(
                "SELECT * FROM memory_facts ORDER BY weight DESC, key ASC LIMIT ?", (limit,)
            ).fetchall()
        return [self._fact(z) for z in zeilen]

    def relevant(self, terms: str, *, limit: int = 10) -> list[MemoryFact]:
        """Passende Tatsachen zu einem Text.

        Bewusst schlicht: Wortueberschneidung mal Gewicht. Kein Einbettungs-
        modell, keine Aehnlichkeitssuche -- bei einigen Dutzend Tatsachen
        waere das Aufwand ohne Nutzen. Wenn das Gedaechtnis je gross wird, ist
        das die Stelle, die ersetzt wird, und nur sie.
        """
        gesucht = set(_WORT_RE.findall(terms.lower()))
        if not gesucht:
            return self.all(limit=limit)

        bewertet: list[tuple[float, MemoryFact]] = []
        for fakt in self.all(limit=500):
            worte = set(_WORT_RE.findall(f"{fakt.key} {fakt.value}".lower()))
            treffer = len(worte & gesucht)
            if treffer:
                bewertet.append((treffer * max(fakt.weight, 0.1), fakt))
        bewertet.sort(key=lambda paar: (-paar[0], paar[1].key))
        return [fakt for _, fakt in bewertet[:limit]]

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM memory_facts").fetchone()[0])

    @staticmethod
    def _fact(zeile: sqlite3.Row) -> MemoryFact:
        return MemoryFact(
            key=zeile["key"],
            value=zeile["value"],
            category=zeile["category"],
            source=zeile["source"],
            weight=zeile["weight"],
            created_at=zeile["created_at"],
            updated_at=zeile["updated_at"],
        )
