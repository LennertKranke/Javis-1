"""Wer eine automatisch gesendete Antwort bekommen darf.

Die Liste fuellt sich aus den eigenen gesendeten Nachrichten: wer oft genug
von dir gehoert hat, gilt als bekannter Kontakt. Das ist bequem, hat aber eine
Schwaeche, die man kennen sollte -- die Liste ist damit eine Statistik und
keine Entscheidung. Drei Bremsen halten dagegen:

  Mindestzahl   Ein einzelner Hoeflichkeitsgruss genuegt nicht. Erst ab
                `threshold` eigenen Nachrichten zaehlt jemand als Kontakt.
  Sperrliste    Eintraege aus der Konfiguration gewinnen immer, auch gegen
                hundert gesendete Nachrichten. Ganze Domains sind moeglich.
  Auf Befehl    Die Liste aendert sich nur bei `jarvis mail allowlist refresh`,
                nie beiläufig waehrend eines Durchlaufs. Wer sie aendert, sieht
                dabei zu.

Jeder Eintrag traegt seinen Beleg -- wie oft, zuletzt wann. Ohne den waere die
Liste eine Behauptung.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import getaddresses

from jarvis.core.db import transaction

__all__ = ["AllowEntry", "AllowVerdict", "Allowlist"]

DEFAULT_THRESHOLD = 3
SENT_QUERY = "in:sent"


@dataclass(frozen=True)
class AllowEntry:
    address: str
    sent_count: int
    first_seen: str | None
    last_seen: str | None
    source: str


@dataclass(frozen=True)
class AllowVerdict:
    address: str
    allowed: bool
    reason: str
    source: str


def _normalise(address: str) -> str:
    return address.strip().lower()


def _domain(address: str) -> str:
    _, _, domain = address.rpartition("@")
    return domain


class Allowlist:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        manual: Collection[str] = (),
        blocked: Collection[str] = (),
        threshold: int = DEFAULT_THRESHOLD,
    ) -> None:
        self._conn = conn
        self._manual = {_normalise(a) for a in manual}
        self._blocked = {_normalise(a) for a in blocked}
        self._threshold = max(1, threshold)

    @property
    def threshold(self) -> int:
        return self._threshold

    # ------------------------------------------------------------------ #

    def _is_blocked(self, address: str) -> bool:
        if address in self._blocked:
            return True
        domain = _domain(address)
        return any(eintrag in (f"@{domain}", f"*@{domain}", domain) for eintrag in self._blocked)

    def permits(self, address: str) -> AllowVerdict:
        """Darf an diese Adresse gesendet werden? Sperrliste gewinnt immer."""
        ziel = _normalise(address)
        if not ziel or "@" not in ziel:
            return AllowVerdict(ziel, False, "keine brauchbare Adresse", "ungueltig")

        if self._is_blocked(ziel):
            return AllowVerdict(ziel, False, "steht auf der Sperrliste", "blocked")

        if ziel in self._manual:
            return AllowVerdict(ziel, True, "von Hand freigegeben", "manual")

        eintrag = self.get(ziel)
        if eintrag is None:
            return AllowVerdict(ziel, False, "nicht auf der Allowlist", "unbekannt")
        if eintrag.sent_count < self._threshold:
            return AllowVerdict(
                ziel,
                False,
                f"erst {eintrag.sent_count} von {self._threshold} eigenen Nachrichten",
                "zu_wenig",
            )
        return AllowVerdict(
            ziel, True, f"{eintrag.sent_count} eigene Nachrichten an diese Adresse", "sent"
        )

    # ------------------------------------------------------------------ #

    def get(self, address: str) -> AllowEntry | None:
        zeile = self._conn.execute(
            "SELECT * FROM mail_allowlist WHERE address = ?", (_normalise(address),)
        ).fetchone()
        return self._entry(zeile) if zeile else None

    @staticmethod
    def _entry(zeile: sqlite3.Row) -> AllowEntry:
        return AllowEntry(
            address=zeile["address"],
            sent_count=zeile["sent_count"],
            first_seen=zeile["first_seen"],
            last_seen=zeile["last_seen"],
            source=zeile["source"],
        )

    def entries(self, *, limit: int = 100, only_permitted: bool = False) -> list[AllowEntry]:
        bedingung = "WHERE sent_count >= ?" if only_permitted else ""
        parameter: tuple = (self._threshold, limit) if only_permitted else (limit,)
        zeilen = self._conn.execute(
            f"SELECT * FROM mail_allowlist {bedingung} "
            f"ORDER BY sent_count DESC, address ASC LIMIT ?",
            parameter,
        ).fetchall()
        return [self._entry(z) for z in zeilen]

    def count(self, *, only_permitted: bool = False) -> int:
        if only_permitted:
            zeile = self._conn.execute(
                "SELECT COUNT(*) FROM mail_allowlist WHERE sent_count >= ?", (self._threshold,)
            ).fetchone()
        else:
            zeile = self._conn.execute("SELECT COUNT(*) FROM mail_allowlist").fetchone()
        return int(zeile[0])

    # ------------------------------------------------------------------ #

    def refresh_from_sent(
        self,
        client: object,
        *,
        max_messages: int = 300,
        own_address: str | None = None,
    ) -> dict[str, int]:
        """Zaehlt die Empfaenger der eigenen gesendeten Nachrichten neu durch.

        Holt bewusst nur Kopffelder, nicht die ganzen Nachrichten: fuer das
        Zaehlen von Adressen braucht niemand den Inhalt alter Korrespondenz,
        und dreihundert vollstaendige Mails zu laden waere ausserdem langsam.
        """
        ids = client.list_message_ids(SENT_QUERY, max_messages)  # type: ignore[attr-defined]
        eigen = _normalise(own_address or "")
        gezaehlt: dict[str, int] = {}
        zeitpunkte: dict[str, str] = {}

        for message_id in ids:
            roh = client.get_message(  # type: ignore[attr-defined]
                message_id, fmt="metadata", headers=["To", "Cc"]
            )
            kopf = {
                str(h.get("name", "")).lower(): str(h.get("value", ""))
                for h in (roh.get("payload") or {}).get("headers") or []
            }
            wann = _zeitpunkt(roh.get("internalDate"))
            for _, adresse in getaddresses([kopf.get("to", ""), kopf.get("cc", "")]):
                ziel = _normalise(adresse)
                if not ziel or "@" not in ziel or ziel == eigen:
                    continue
                gezaehlt[ziel] = gezaehlt.get(ziel, 0) + 1
                if wann and (ziel not in zeitpunkte or wann > zeitpunkte[ziel]):
                    zeitpunkte[ziel] = wann

        with transaction(self._conn):
            for adresse, anzahl in gezaehlt.items():
                self._conn.execute(
                    """
                    INSERT INTO mail_allowlist
                        (address, sent_count, first_seen, last_seen, source)
                    VALUES (?, ?, ?, ?, 'sent')
                    ON CONFLICT (address) DO UPDATE SET
                        sent_count = excluded.sent_count,
                        last_seen  = excluded.last_seen,
                        source     = 'sent'
                    """,
                    (adresse, anzahl, zeitpunkte.get(adresse), zeitpunkte.get(adresse)),
                )
        return gezaehlt


def _zeitpunkt(internal_date: object) -> str | None:
    try:
        millisekunden = int(str(internal_date))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millisekunden / 1000, UTC).isoformat(timespec="seconds")
