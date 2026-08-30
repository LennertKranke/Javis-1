"""Terminkonflikte finden. Arithmetik, kein Modell.

Ob sich zwei Zeitfenster ueberschneiden, ist eine Rechnung. Ein Modell dafuer
zu fragen waere teurer, langsamer und unzuverlaessiger -- und es waere von
aussen beeinflussbar, weil Titel und Beschreibung vom Einladenden stammen.
Deshalb stuetzt sich hier nichts auf Text: nur auf Zeiten, Status und
Antwortzustaende.

Zwei Arten von Befund:

  ueberschneidung  zwei Termine liegen zeitlich uebereinander
  kein_puffer      der naechste beginnt zu knapp nach dem vorigen

Was JARVIS daraus macht -- erwaehnen, warnen, ignorieren -- entscheidet die
Faehigkeit. Hier entstehen nur die Tatsachen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from jarvis.skills.calendar.event import CalendarEvent

__all__ = ["Finding", "find_conflicts"]

UEBERSCHNEIDUNG = "ueberschneidung"
KEIN_PUFFER = "kein_puffer"


@dataclass(frozen=True)
class Finding:
    kind: str
    event_ids: tuple[str, ...]
    minutes: int = 0

    def describe(self, titel: dict[str, str] | None = None) -> str:
        """Beschreibung mit bereits normalisierten Titeln.

        Die Titel kommen von aussen; der Aufrufer reicht sie durch `sanitize`,
        bevor er sie hier hineingibt.
        """
        namen = titel or {}
        eins, zwei = (namen.get(k, k) for k in self.event_ids[:2])
        if self.kind == UEBERSCHNEIDUNG:
            return f"{eins} ueberschneidet sich mit {zwei}"
        return f"Nur {self.minutes} Minuten zwischen {eins} und {zwei}"


def find_conflicts(events: list[CalendarEvent], *, min_gap_minutes: int = 15) -> list[Finding]:
    """Alle Ueberschneidungen und zu knappen Uebergaenge in einer Terminliste."""
    belegend = sorted(
        (e for e in events if e.blocks_time),
        key=lambda e: (e.starts_at, e.ends_at),  # type: ignore[arg-type,return-value]
    )
    puffer = timedelta(minutes=max(0, min_gap_minutes))
    befunde: list[Finding] = []

    for i, erster in enumerate(belegend):
        for zweiter in belegend[i + 1 :]:
            assert erster.ends_at and zweiter.starts_at
            # Sortiert: sobald der naechste nach dem Puffer beginnt, koennen
            # auch alle folgenden nicht mehr kollidieren.
            if zweiter.starts_at >= erster.ends_at + puffer:
                break
            if erster.overlaps(zweiter):
                befunde.append(
                    Finding(kind=UEBERSCHNEIDUNG, event_ids=(erster.event_id, zweiter.event_id))
                )
            else:
                luecke = int((zweiter.starts_at - erster.ends_at).total_seconds() // 60)
                befunde.append(
                    Finding(
                        kind=KEIN_PUFFER,
                        event_ids=(erster.event_id, zweiter.event_id),
                        minutes=max(0, luecke),
                    )
                )
    return befunde
