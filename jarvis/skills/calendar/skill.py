"""Die Kalenderfaehigkeit: sieht voraus, ohne zu raten.

Sie ruft kein Modell. Ob sich zwei Termine ueberschneiden, ist eine Rechnung;
ein Modell dafuer zu fragen waere teurer, langsamer und -- weil Titel und
Beschreibung vom Einladenden stammen -- von aussen beeinflussbar.

Trotzdem laeuft alles durch denselben Weg wie bei Mail: poll, decide, Gatter,
act, Protokoll. Ein Hinweis ist eine Aktion, auch wenn er niemanden erreicht:
er aendert, was JARVIS morgen frueh sagt. Im Trockenlauf entsteht er deshalb
nicht, sondern wird nur festgehalten.

Titel und Ort gehen durch `sanitize`, bevor sie irgendwo landen. Ein
Kalendereintrag ist ein bequemer Weg, fremden Text in ein System zu bekommen.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, time, timedelta, tzinfo
from typing import Any

from jarvis.core.config import Config, ConfigError
from jarvis.core.sanitize import sanitize
from jarvis.skills.base import (
    Decision,
    Event,
    Result,
    Skill,
    TargetMismatch,
    register_skill,
)
from jarvis.skills.calendar.conflicts import Finding, find_conflicts
from jarvis.skills.calendar.event import CalendarEvent, as_utc_text, parse_event
from jarvis.skills.calendar.google import CalendarClient
from jarvis.skills.calendar.store import CalendarStore
from jarvis.skills.mail.store import STATE_ACTED, STATE_ANALYSED

__all__ = ["CalendarOptions", "CalendarSkill"]

DEFAULTS: dict[str, Any] = {
    "calendar_ids": ["primary"],
    "window_days": 7,
    "min_gap_minutes": 15,
    "max_per_run": 100,
}


class CalendarOptions:
    """Prueft [skills.calendar] selbst."""

    ERLAUBT = frozenset(DEFAULTS)

    def __init__(self, roh: dict[str, Any]) -> None:
        unbekannt = sorted(set(roh) - self.ERLAUBT)
        if unbekannt:
            raise ConfigError(f"skills.calendar: unbekannte Schluessel {', '.join(unbekannt)}")

        kalender = roh.get("calendar_ids", DEFAULTS["calendar_ids"])
        if not isinstance(kalender, list) or not kalender:
            raise ConfigError("skills.calendar.calendar_ids: erwartet eine nicht leere Liste")
        if not all(isinstance(k, str) and k.strip() for k in kalender):
            raise ConfigError("skills.calendar.calendar_ids: erwartet Zeichenketten")
        self.calendar_ids = [k.strip() for k in kalender]

        self.window_days = self._zahl(roh, "window_days", 1, 60)
        self.min_gap_minutes = self._zahl(roh, "min_gap_minutes", 0, 240)
        self.max_per_run = self._zahl(roh, "max_per_run", 1, 250)

    @staticmethod
    def _zahl(roh: dict[str, Any], name: str, min_wert: int, max_wert: int) -> int:
        wert = roh.get(name, DEFAULTS[name])
        if isinstance(wert, bool) or not isinstance(wert, int):
            raise ConfigError(f"skills.calendar.{name}: erwartet eine ganze Zahl")
        if not min_wert <= wert <= max_wert:
            raise ConfigError(
                f"skills.calendar.{name}: muss zwischen {min_wert} und {max_wert} liegen"
            )
        return wert


@register_skill
class CalendarSkill(Skill):
    name = "calendar"
    autonomy_level = 0  # Ein Hinweis erreicht niemanden
    requires_outbound = False

    def __init__(
        self,
        *,
        options: CalendarOptions,
        client: CalendarClient,
        store: CalendarStore,
        sanitize_max_chars: int = 2000,
        timezone: tzinfo = UTC,
        now: Any = None,
    ) -> None:
        self._options = options
        self._client = client
        self._store = store
        self._max_chars = sanitize_max_chars
        self._zone = timezone
        self._now = now or (lambda: datetime.now(UTC))
        self._fenster: list[CalendarEvent] = []

    @classmethod
    def from_config(
        cls, config: Config, *, client: CalendarClient, store: CalendarStore
    ) -> CalendarSkill:
        return cls(
            options=CalendarOptions(config.skill_options("calendar")),
            client=client,
            store=store,
            sanitize_max_chars=min(config.sanitize_max_chars, 2000),
            timezone=config.timezone,
        )

    @property
    def options(self) -> CalendarOptions:
        return self._options

    @property
    def client(self) -> CalendarClient:
        return self._client

    # ------------------------------------------------------------------ #

    def _titel(self, event: CalendarEvent) -> str:
        """Normalisierter Titel. Nie der Rohtext."""
        sauber = sanitize(event.summary or "(ohne Titel)", max_chars=self._max_chars)
        return sauber.text[:120] or "(ohne Titel)"

    def _beginn(self, termin: CalendarEvent) -> str | None:
        """Die Speicherform des Beginns, in UTC.

        Ein ganztaegiger Termin hat ein Datum, keinen Zeitpunkt. `parse_event`
        verankert ihn mangels Zone auf UTC-Mitternacht -- oestlich von
        Greenwich faellt das nicht auf, westlich schon: dort beginnt der
        oertliche Tag erst spaeter, und der Feiertag laege vor seinem eigenen
        Tag. Hier ist die Zone bekannt, also wird er auf oertliche Mitternacht
        gesetzt und liegt damit in jeder Zone im richtigen Tag.
        """
        if termin.starts_at is None:
            return None
        if termin.all_day:
            return as_utc_text(
                datetime.combine(termin.starts_at.date(), time.min, tzinfo=self._zone)
            )
        return as_utc_text(termin.starts_at)

    def _ende(self, termin: CalendarEvent) -> str | None:
        if termin.all_day and termin.ends_at is not None:
            return as_utc_text(datetime.combine(termin.ends_at.date(), time.min, tzinfo=self._zone))
        return as_utc_text(termin.ends_at)

    def _befunde(self) -> dict[str, tuple[Finding, str]]:
        """Der jetzt gueltige Befund je Termin, mit fertigem Satz dazu.

        Eine einzige Stelle fuer poll, decide und verify_targets. Faenden die
        drei ihre Befunde jeweils selbst, koennten sie auseinanderlaufen -- und
        genau der Vergleich "gilt der gespeicherte Satz noch?" haenge dann in
        der Luft. Steckt ein Termin in mehreren Konflikten, gewinnt der erste;
        `find_conflicts` liefert sie in stabiler Reihenfolge.

        Alles kommt aus dieser einen Rechnung zurueck, nichts wird nebenher
        gemerkt: ein zwischengespeicherter Rest waere derselbe Fehler noch
        einmal, nur eine Ebene tiefer.
        """
        titel = {t.event_id: self._titel(t) for t in self._fenster}
        erste: dict[str, tuple[Finding, str]] = {}
        for befund in find_conflicts(self._fenster, min_gap_minutes=self._options.min_gap_minutes):
            satz = befund.describe(titel)
            for eid in befund.event_ids:
                erste.setdefault(eid, (befund, satz))
        return erste

    def poll(self) -> list[Event]:
        jetzt = self._now()
        bis = jetzt + timedelta(days=self._options.window_days)

        gesammelt: list[CalendarEvent] = []
        for kalender in self._options.calendar_ids:
            roh = self._client.list_events(
                kalender,
                time_min=jetzt.isoformat(),
                time_max=bis.isoformat(),
                limit=self._options.max_per_run,
            )
            gesammelt.extend(parse_event(e, calendar_id=kalender) for e in roh)

        # Das ganze Fenster wird gebraucht, um Konflikte zu erkennen -- auch
        # Termine, die selbst schon erledigt sind.
        self._fenster = gesammelt
        for termin in gesammelt:
            self._store.remember(
                event_id=termin.event_id,
                calendar_id=termin.calendar_id,
                starts_at=self._beginn(termin),
                ends_at=self._ende(termin),
                all_day=termin.all_day,
                summary=self._titel(termin),
            )

        # Was nicht mehr genau so gilt, verschwindet aus dem Speicher. Der
        # Vergleich laeuft ueber den Befund selbst: ein Termin kann von einem
        # Konflikt in einen anderen wechseln, ohne je konfliktfrei zu sein.
        self._store.clear_stale_findings(
            {eid: satz for eid, (_befund, satz) in self._befunde().items()}
        )

        erledigt = self._store.handled([t.event_id for t in gesammelt])
        return [
            Event(
                skill=self.name,
                key=termin.event_id,
                summary=f"{self._zeitangabe(termin)} {self._titel(termin)}",
                payload=termin,
            )
            for termin in gesammelt
            if termin.event_id not in erledigt
        ]

    def _zeitangabe(self, termin: CalendarEvent) -> str:
        """Was auf der Uhr steht, nicht was in der Datenbank liegt."""
        if termin.starts_at is None:
            return "ohne Zeit"
        if termin.all_day:
            # Ein Datum, kein Zeitpunkt -- also auch nicht umzurechnen.
            return f"{termin.starts_at.date().isoformat()} ganztags"
        return termin.starts_at.astimezone(self._zone).strftime("%d.%m. %H:%M")

    def decide(self, event: Event) -> Decision:
        """Deterministisch. Kein Modell, keine Textauswertung."""
        termin: CalendarEvent = event.payload
        befunde = self._befunde()

        if termin.event_id not in befunde:
            return Decision(
                skill=self.name,
                event_key=event.key,
                action="none",
                reason="kein Konflikt",
                decided_by="rule",
                targets={"event_id": termin.event_id},
            )

        befund, satz = befunde[termin.event_id]
        return Decision(
            skill=self.name,
            event_key=event.key,
            action="notice",
            reason=satz,
            decided_by="rule",
            fields={"art": befund.kind, "minuten": befund.minutes},
            targets={"event_id": termin.event_id, "finding": satz, "kind": befund.kind},
        )

    def verify_targets(self, decision: Decision) -> Decision:
        """Rechnet den Befund aus dem aktuellen Kalender neu."""
        if decision.is_noop:
            return decision

        event_id = str(decision.targets.get("event_id") or "")
        if self._store.get(event_id) is None:
            raise TargetMismatch(f"Termin {event_id!r} ist nicht bekannt")

        befunde = self._befunde()
        if event_id not in befunde:
            raise TargetMismatch(f"Termin {event_id!r} hat keinen Konflikt mehr")

        befund, satz = befunde[event_id]
        return replace(
            decision,
            targets={"event_id": event_id, "finding": satz, "kind": befund.kind},
        )

    def act(self, decision: Decision) -> Result:
        if decision.is_noop:
            return Result(skill=self.name, event_key=decision.event_key, performed=False)
        self._store.record_finding(
            str(decision.targets["event_id"]), str(decision.targets["finding"])
        )
        return Result(
            skill=self.name,
            event_key=decision.event_key,
            performed=True,
            detail={"kind": decision.targets.get("kind")},
        )

    def after(
        self, event: Event, decision: Decision, disposition: str, result: Result | None
    ) -> None:
        termin: CalendarEvent = event.payload
        # Kein Konflikt heisst nicht "erledigt": ein neuer Termin kann morgen
        # einen erzeugen. Nur ein festgehaltener Befund ist endgueltig.
        if decision.is_noop:
            zustand = STATE_ANALYSED
        elif result is not None and result.performed:
            zustand = STATE_ACTED
        else:
            zustand = STATE_ANALYSED
        self._store.remember(
            event_id=decision.event_key,
            calendar_id=termin.calendar_id,
            starts_at=self._beginn(termin),
            ends_at=self._ende(termin),
            all_day=termin.all_day,
            summary=self._titel(termin),
            state=zustand,
        )
