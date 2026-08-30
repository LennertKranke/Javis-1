"""Bausteine fuer Google-Kalenderantworten und ein Doppel des Clients."""

from __future__ import annotations

from typing import Any


def termin(
    *,
    eid: str = "e1",
    start: str | None = "2026-03-02T09:00:00+00:00",
    ende: str | None = "2026-03-02T10:00:00+00:00",
    titel: str = "Besprechung",
    ganztags: bool = False,
    status: str = "confirmed",
    ort: str = "",
    beschreibung: str = "",
    teilnehmer: list[dict] | None = None,
    wiederkehrend: bool = False,
) -> dict:
    """Ein Rohtermin, wie ihn die Google-API liefert."""
    roh: dict[str, Any] = {
        "id": eid,
        "status": status,
        "summary": titel,
        "location": ort,
        "description": beschreibung,
    }
    if ganztags:
        roh["start"] = {"date": (start or "")[:10]}
        roh["end"] = {"date": (ende or start or "")[:10]}
    else:
        roh["start"] = {"dateTime": start} if start else {}
        roh["end"] = {"dateTime": ende} if ende else {}
    if teilnehmer:
        roh["attendees"] = teilnehmer
    if wiederkehrend:
        roh["recurringEventId"] = "serie1"
    return roh


class FakeCalendarClient:
    """Ersetzt den echten Client. Zeichnet auf, was abgefragt wurde."""

    def __init__(self, events: dict[str, list[dict]] | list[dict] | None = None) -> None:
        if isinstance(events, list) or events is None:
            self._events = {"primary": list(events or [])}
        else:
            self._events = {k: list(v) for k, v in events.items()}
        self.calls: list[tuple[str, str, str, int]] = []

    def list_events(
        self, calendar_id: str, *, time_min: str, time_max: str, limit: int = 100
    ) -> list[dict]:
        self.calls.append((calendar_id, time_min, time_max, limit))
        return list(self._events.get(calendar_id, []))

    def set_events(self, calendar_id: str, events: list[dict]) -> None:
        self._events[calendar_id] = list(events)
