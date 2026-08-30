"""Was JARVIS ueber Termine weiss.

Wie bei Mail: schmal und mit Zustand. Gespeichert wird der bereits
normalisierte Titel -- der Rohtext bleibt im Kalender, wo er hingehoert.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime

from jarvis.core.db import transaction
from jarvis.skills.mail.store import (
    FINAL_STATES,
    MAIL_STATES,
    STATE_SEEN,
)

__all__ = ["CalendarStore", "EventRecord"]


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    calendar_id: str
    starts_at: str | None
    ends_at: str | None
    all_day: bool
    summary: str
    state: str
    finding: str | None
    first_seen: str
    last_seen: str


class CalendarStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def remember(
        self,
        *,
        event_id: str,
        calendar_id: str,
        starts_at: str | None = None,
        ends_at: str | None = None,
        all_day: bool = False,
        summary: str = "",
        state: str = STATE_SEEN,
        finding: str | None = None,
    ) -> None:
        if state not in MAIL_STATES:
            raise ValueError(f"Unbekannter Zustand: {state!r}")
        jetzt = datetime.now(UTC).isoformat(timespec="seconds")
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO calendar_events
                    (event_id, calendar_id, starts_at, ends_at, all_day, summary,
                     state, finding, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (event_id) DO UPDATE SET
                    calendar_id = excluded.calendar_id,
                    starts_at   = excluded.starts_at,
                    ends_at     = excluded.ends_at,
                    all_day     = excluded.all_day,
                    summary     = excluded.summary,
                    last_seen   = excluded.last_seen,
                    finding     = COALESCE(excluded.finding, calendar_events.finding),
                    state       = CASE
                        WHEN calendar_events.state IN ('acted', 'skipped')
                            THEN calendar_events.state
                        ELSE excluded.state
                    END
                """,
                (
                    event_id,
                    calendar_id,
                    starts_at,
                    ends_at,
                    int(bool(all_day)),
                    summary[:300],
                    state,
                    finding,
                    jetzt,
                    jetzt,
                ),
            )

    def record_finding(self, event_id: str, finding: str) -> None:
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE calendar_events SET finding = ? WHERE event_id = ?",
                (finding[:300], event_id),
            )

    def clear_findings(self, keep: Collection[str]) -> int:
        """Loescht Befunde zu Terminen, die nicht mehr in `keep` stehen.

        Ein Konflikt kann verschwinden, weil jemand einen Termin verschiebt.
        Bliebe der Befund stehen, warnte das Briefing morgen vor etwas, das es
        nicht mehr gibt. Mit dem Befund faellt auch `acted` weg: was nicht
        gemeldet ist, gilt nicht als gemeldet -- kehrt der Konflikt zurueck,
        wird er wieder aufgegriffen.
        """
        ids = list(keep)
        platzhalter = ",".join("?" * len(ids))
        bedingung = f" AND event_id NOT IN ({platzhalter})" if ids else ""
        with transaction(self._conn):
            cur = self._conn.execute(
                "UPDATE calendar_events SET finding = NULL, "
                "state = CASE WHEN state = 'acted' THEN 'analysed' ELSE state END "
                f"WHERE finding IS NOT NULL{bedingung}",
                ids,
            )
            return int(cur.rowcount)

    def handled(self, event_ids: Collection[str]) -> set[str]:
        if not event_ids:
            return set()
        ids = list(event_ids)
        platzhalter = ",".join("?" * len(ids))
        zeilen = self._conn.execute(
            f"SELECT event_id FROM calendar_events "
            f"WHERE event_id IN ({platzhalter}) AND state IN (?, ?)",
            [*ids, *FINAL_STATES],
        ).fetchall()
        return {z["event_id"] for z in zeilen}

    def get(self, event_id: str) -> EventRecord | None:
        zeile = self._conn.execute(
            "SELECT * FROM calendar_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return self._record(zeile) if zeile else None

    def between(self, *, von: str, bis: str, limit: int = 100) -> list[EventRecord]:
        zeilen = self._conn.execute(
            "SELECT * FROM calendar_events WHERE starts_at >= ? AND starts_at < ? "
            "ORDER BY starts_at ASC LIMIT ?",
            (von, bis, limit),
        ).fetchall()
        return [self._record(z) for z in zeilen]

    def findings(self, *, von: str, bis: str) -> list[EventRecord]:
        zeilen = self._conn.execute(
            "SELECT * FROM calendar_events WHERE finding IS NOT NULL "
            "AND starts_at >= ? AND starts_at < ? ORDER BY starts_at ASC",
            (von, bis),
        ).fetchall()
        return [self._record(z) for z in zeilen]

    def total(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0])

    def counts_by_state(self) -> dict[str, int]:
        zeilen = self._conn.execute(
            "SELECT state, COUNT(*) AS anzahl FROM calendar_events GROUP BY state"
        ).fetchall()
        return {z["state"]: z["anzahl"] for z in zeilen}

    @staticmethod
    def _record(zeile: sqlite3.Row) -> EventRecord:
        return EventRecord(
            event_id=zeile["event_id"],
            calendar_id=zeile["calendar_id"],
            starts_at=zeile["starts_at"],
            ends_at=zeile["ends_at"],
            all_day=bool(zeile["all_day"]),
            summary=zeile["summary"],
            state=zeile["state"],
            finding=zeile["finding"],
            first_seen=zeile["first_seen"],
            last_seen=zeile["last_seen"],
        )
