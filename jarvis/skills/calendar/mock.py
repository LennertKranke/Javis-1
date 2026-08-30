"""Ein Kalender ohne Google. Fuer den Betrieb, nicht fuer Tests.

Gleicher Gedanke wie beim Postfach-Mock: ein festes, plausibles Fenster, mit
dem sich Konflikterkennung und Briefing einmal ansehen lassen, ohne einen
Google-Account. Es schreibt nie `merke_kontakt` -- ein Mock ist kein Nachweis.

Die Beispieltermine sind so gelegt, dass beide Befundarten vorkommen: eine
echte Ueberschneidung und ein zu knapper Uebergang. Sonst saehe die
Konflikterkennung im Mock immer ruhig aus, und man merkte nie, ob sie laeuft.
Die Zeiten haengen an *heute*, damit das Briefing etwas zu sagen hat.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jarvis.skills.calendar.google import CALENDAR_READ
from jarvis.skills.mail.gmail import GmailError

__all__ = ["MockCalendarClient", "beispiel_kalender"]


def _termin(
    *,
    eid: str,
    titel: str,
    beginn: datetime,
    dauer_minuten: int = 60,
    ganztags: bool = False,
    ort: str = "",
) -> dict[str, Any]:
    ende = beginn + timedelta(minutes=dauer_minuten)
    if ganztags:
        zeiten = {
            "start": {"date": beginn.date().isoformat()},
            "end": {"date": (beginn + timedelta(days=1)).date().isoformat()},
        }
    else:
        zeiten = {
            "start": {"dateTime": beginn.isoformat()},
            "end": {"dateTime": ende.isoformat()},
        }
    return {
        "id": eid,
        "status": "confirmed",
        "summary": titel,
        "location": ort,
        "description": "",
        "organizer": {"email": "ich@example.com"},
        **zeiten,
    }


def beispiel_kalender(*, jetzt: datetime | None = None) -> list[dict[str, Any]]:
    """Die naechsten Stunden und Tage, mit beiden Befundarten.

    Die Termine haengen an *jetzt plus zwei Stunden*, nicht an einer festen
    Uhrzeit. Ein Beispielkalender, dessen Konflikte am Nachmittag schon
    vorbei sind, zeigt eine Konflikterkennung, die nichts findet -- und man
    haelt sie fuer kaputt oder, schlimmer, fuer in Ordnung.
    """
    basis = (jetzt or datetime.now(UTC)).replace(minute=0, second=0, microsecond=0)
    heute = basis + timedelta(hours=2)
    return [
        _termin(eid="c1", titel="Zahnarzt", beginn=heute, dauer_minuten=60),
        # Ueberschneidung mit c1.
        _termin(
            eid="c2",
            titel="Standup",
            beginn=heute + timedelta(minutes=30),
            dauer_minuten=30,
        ),
        # Zu knapper Uebergang nach c2: fuenf Minuten.
        _termin(
            eid="c3",
            titel="Kundengespraech",
            beginn=heute + timedelta(minutes=65),
            dauer_minuten=60,
        ),
        _termin(
            eid="c4",
            titel="Mittagessen",
            beginn=heute + timedelta(hours=4),
            dauer_minuten=60,
        ),
        _termin(
            eid="c5",
            titel="Feiertag",
            beginn=basis + timedelta(days=2),
            ganztags=True,
        ),
    ]


class MockCalendarClient:
    """Dieselbe Oberflaeche wie `CalendarClient`, ohne Netz.

    Auch hier bleibt die Faehigkeitspruefung, und auch hier gibt es keinen
    Schreibpfad -- der echte Client hat ebenfalls keinen.
    """

    name = "mock"

    def __init__(
        self,
        *,
        capabilities: frozenset[str] | set[str] = CALENDAR_READ,
        events: list[dict] | None = None,
        fixtures: Path | None = None,
    ) -> None:
        self._capabilities = frozenset(capabilities)
        self._events = list(events if events is not None else beispiel_kalender())
        if fixtures is not None:
            self._events = _lade_fixtures(fixtures)

    @property
    def capabilities(self) -> frozenset[str]:
        return self._capabilities

    def can(self, capability: str) -> bool:
        return capability in self._capabilities

    def list_calendars(self) -> list[dict]:
        if not self.can("read"):
            raise GmailError("'read' steht nicht auf der Liste der erlaubten Faehigkeiten")
        return [{"id": "primary", "summary": "Mock-Kalender"}]

    def list_events(
        self, calendar_id: str, *, time_min: str, time_max: str, limit: int = 100
    ) -> list[dict]:
        if not self.can("read"):
            raise GmailError("'read' steht nicht auf der Liste der erlaubten Faehigkeiten")
        von = _lese_zeit(time_min)
        bis = _lese_zeit(time_max)
        im_fenster = [e for e in self._events if _im_fenster(e, von, bis)]
        return im_fenster[: max(0, limit)]


def _lese_zeit(text: str) -> datetime | None:
    try:
        gelesen = datetime.fromisoformat(text)
    except ValueError:
        return None
    return gelesen if gelesen.tzinfo else gelesen.replace(tzinfo=UTC)


def _im_fenster(eintrag: dict, von: datetime | None, bis: datetime | None) -> bool:
    roh = eintrag.get("start") or {}
    wert = roh.get("dateTime") or roh.get("date")
    if not wert:
        return False
    beginn = _lese_zeit(wert if "T" in str(wert) else f"{wert}T00:00:00+00:00")
    if beginn is None:
        return False
    if von is not None and beginn < von:
        return False
    return not (bis is not None and beginn >= bis)


def _lade_fixtures(ordner: Path) -> list[dict]:
    if not ordner.is_dir():
        raise GmailError(f"Kein Beispielverzeichnis: {ordner}")
    termine: list[dict] = []
    for datei in sorted(ordner.glob("*.json")):
        try:
            inhalt = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GmailError(f"{datei.name}: unlesbar ({exc})") from exc
        termine.extend(inhalt if isinstance(inhalt, list) else [inhalt])
    return termine
