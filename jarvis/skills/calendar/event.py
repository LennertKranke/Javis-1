"""Einen Google-Kalendertermin in seine zwei Haelften zerlegen.

Dieselbe Trennung wie bei E-Mail, aus demselben Grund. Wer einen Termin
verschickt, bestimmt seinen Titel, seinen Ort und seine Beschreibung -- ein
Kalendereintrag ist ein Weg, fremden Text in ein System zu bekommen, und ein
sehr bequemer dazu.

  vertrauenswuerdig   Kennungen, Zeiten, Status, Adressen der Teilnehmer
  unvertrauenswuerdig Titel, Ort, Beschreibung, Anzeigenamen

Zeiten sind immer zeitzonenbewusst. Ein ganztaegiger Termin hat kein
Zeitfenster im eigentlichen Sinn und wird deshalb gesondert gefuehrt -- er
kollidiert nicht mit einer Besprechung.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, tzinfo

__all__ = ["Attendee", "CalendarEvent", "as_utc_text", "local_moment", "parse_event"]

DECLINED = "declined"


def _zeitpunkt(roh: dict | None) -> tuple[datetime | None, bool]:
    """(Zeitpunkt, ganztaegig). Gibt (None, False) wenn nichts brauchbar ist."""
    if not roh:
        return None, False
    if wert := roh.get("dateTime"):
        try:
            gelesen = datetime.fromisoformat(str(wert))
        except ValueError:
            return None, False
        if gelesen.tzinfo is None:
            gelesen = gelesen.replace(tzinfo=UTC)
        return gelesen, False
    if wert := roh.get("date"):
        try:
            tag = date.fromisoformat(str(wert))
        except ValueError:
            return None, False
        return datetime.combine(tag, time.min, tzinfo=UTC), True
    return None, False


def as_utc_text(moment: datetime | None) -> str | None:
    """Die Speicherform: immer UTC.

    Google liefert Ortszeit mit Versatz (`09:00+02:00`). Solche Texte lassen
    sich nicht vergleichen: `09:00+02:00` steht vor `23:00+00:00`, ist aber
    spaeter. Genau so vergleicht SQLite sie aber, wenn ein Zeitfenster
    abgefragt wird. Auf UTC normalisiert stimmt die Textreihenfolge wieder mit
    der zeitlichen ueberein.
    """
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat()


def local_moment(gespeichert: str | None, zone: tzinfo) -> datetime | None:
    """Aus der Speicherform zurueck in die Zeit, die auf der Uhr steht."""
    if not gespeichert:
        return None
    try:
        gelesen = datetime.fromisoformat(gespeichert)
    except ValueError:
        return None
    if gelesen.tzinfo is None:
        gelesen = gelesen.replace(tzinfo=UTC)
    return gelesen.astimezone(zone)


@dataclass(frozen=True)
class Attendee:
    email: str
    response: str = ""
    is_self: bool = False


@dataclass(frozen=True)
class CalendarEvent:
    # --- vertrauenswuerdig --------------------------------------------------
    event_id: str
    calendar_id: str
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool = False
    status: str = "confirmed"
    organizer: str = ""
    attendees: tuple[Attendee, ...] = field(default_factory=tuple)
    recurring: bool = False
    # --- unvertrauenswuerdig ------------------------------------------------
    summary: str = ""
    location: str = ""
    description: str = ""

    @property
    def cancelled(self) -> bool:
        return self.status == "cancelled"

    @property
    def declined_by_me(self) -> bool:
        return any(t.is_self and t.response == DECLINED for t in self.attendees)

    @property
    def blocks_time(self) -> bool:
        """Belegt der Termin wirklich Zeit im Kalender?

        Abgesagte, abgelehnte und ganztaegige Eintraege nicht -- sonst meldet
        JARVIS jeden Feiertag als Konflikt mit jeder Besprechung.
        """
        return (
            not self.cancelled
            and not self.declined_by_me
            and not self.all_day
            and self.starts_at is not None
            and self.ends_at is not None
        )

    @property
    def untrusted_text(self) -> str:
        """Alles, was der Einladende bestimmt."""
        teile = [self.summary, self.location, self.description]
        return "\n".join(t for t in teile if t).strip()

    def overlaps(self, other: CalendarEvent) -> bool:
        if not (self.blocks_time and other.blocks_time):
            return False
        assert self.starts_at and self.ends_at and other.starts_at and other.ends_at
        return self.starts_at < other.ends_at and other.starts_at < self.ends_at


def parse_event(roh: dict, *, calendar_id: str, own_address: str = "") -> CalendarEvent:
    beginn, ganztags = _zeitpunkt(roh.get("start"))
    ende, _ = _zeitpunkt(roh.get("end"))

    eigen = own_address.lower()
    teilnehmer = tuple(
        Attendee(
            email=str(t.get("email", "")).lower(),
            response=str(t.get("responseStatus", "")).lower(),
            is_self=bool(t.get("self")) or str(t.get("email", "")).lower() == eigen,
        )
        for t in roh.get("attendees") or []
        if t.get("email")
    )

    return CalendarEvent(
        event_id=str(roh.get("id", "")),
        calendar_id=calendar_id,
        starts_at=beginn,
        ends_at=ende,
        all_day=ganztags,
        status=str(roh.get("status", "confirmed")).lower(),
        organizer=str((roh.get("organizer") or {}).get("email", "")).lower(),
        attendees=teilnehmer,
        recurring=bool(roh.get("recurringEventId")),
        summary=str(roh.get("summary", "")),
        location=str(roh.get("location", "")),
        description=str(roh.get("description", "")),
    )
