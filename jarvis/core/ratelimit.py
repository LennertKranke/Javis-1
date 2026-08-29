"""Harte Obergrenzen pro Faehigkeit und Zeitfenster (Prinzip 2.4).

Die Fenster rollen: "zehn pro Stunde" heisst zehn in den letzten 3600 Sekunden,
nicht zehn seit der vollen Stunde. Ein Kalenderfenster erlaubt sonst zwanzig
Aktionen in zwei Minuten, wenn man den Uebergang trifft.

Der Zaehlerstand steht in der Datenbank, nicht im Arbeitsspeicher. Ein Neustart
des Daemons setzt die Begrenzung damit nicht zurueck -- sonst waere ein
Absturzkreislauf der bequemste Weg, sie zu umgehen.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Mapping
from dataclasses import dataclass

from jarvis.core.config import Capability, ConfigError
from jarvis.core.db import transaction

__all__ = ["RateLimiter", "RateVerdict", "WindowUsage"]


@dataclass(frozen=True)
class WindowUsage:
    window: str
    seconds: int
    limit: int
    used: int

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @property
    def exceeded(self) -> bool:
        return self.used >= self.limit


@dataclass(frozen=True)
class RateVerdict:
    capability: str
    allowed: bool
    consumed: bool
    windows: tuple[WindowUsage, ...] = ()
    blocking: WindowUsage | None = None
    event_id: int | None = None

    @property
    def reason(self) -> str | None:
        if self.allowed or self.blocking is None:
            return None
        b = self.blocking
        return f"Obergrenze erreicht: {b.used}/{b.limit} pro {b.window}"


class RateLimiter:
    def __init__(
        self,
        conn: sqlite3.Connection,
        capabilities: Mapping[str, Capability],
        *,
        clock: object = None,
    ) -> None:
        self._conn = conn
        self._capabilities = capabilities
        self._clock = clock or time.time

    def _now(self) -> float:
        return float(self._clock())  # type: ignore[operator]

    def _capability(self, name: str) -> Capability:
        try:
            return self._capabilities[name]
        except KeyError:
            raise ConfigError(f"Unbekannte Faehigkeit: {name!r}") from None

    def _usage(self, cap: Capability, now: float) -> tuple[WindowUsage, ...]:
        usage = []
        for limit in cap.rate_limits:
            used = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM rate_events WHERE capability = ? AND ts_epoch > ?",
                    (cap.name, now - limit.seconds),
                ).fetchone()[0]
            )
            usage.append(
                WindowUsage(
                    window=limit.window, seconds=limit.seconds, limit=limit.limit, used=used
                )
            )
        return tuple(usage)

    def usage(self, capability: str) -> tuple[WindowUsage, ...]:
        """Aktueller Stand, ohne etwas zu veraendern. Fuer `jarvis status`."""
        return self._usage(self._capability(capability), self._now())

    def check(self, capability: str) -> RateVerdict:
        """Wuerde eine Aktion jetzt durchgehen? Verbraucht nichts."""
        cap = self._capability(capability)
        windows = self._usage(cap, self._now())
        blocking = next((w for w in windows if w.exceeded), None)
        return RateVerdict(
            capability=capability,
            allowed=blocking is None,
            consumed=False,
            windows=windows,
            blocking=blocking,
        )

    def acquire(self, capability: str, *, dry_run: bool = False) -> RateVerdict:
        """Prueft und verbraucht in einem Zug.

        Im Trockenlauf wird geprueft, aber nicht verbraucht: das Urteil landet
        trotzdem im Protokoll, sodass der Schattenbetrieb zeigt, wann die
        Begrenzung gegriffen haette. Verbrauchen wuerde die Zaehler verfaelschen,
        obwohl nichts hinausgegangen ist.
        """
        cap = self._capability(capability)
        if not cap.rate_limits:
            return RateVerdict(capability=capability, allowed=True, consumed=False)

        now = self._now()
        # Zaehlen und Eintragen unter derselben Schreibsperre. Getrennt koennten
        # zwei Prozesse beide den vorletzten Platz sehen und beide senden.
        with transaction(self._conn):
            windows = self._usage(cap, now)
            blocking = next((w for w in windows if w.exceeded), None)
            event_id = None
            if blocking is None and not dry_run:
                cur = self._conn.execute(
                    "INSERT INTO rate_events (capability, ts_epoch) VALUES (?, ?)",
                    (capability, now),
                )
                event_id = int(cur.lastrowid or 0)
        return RateVerdict(
            capability=capability,
            allowed=blocking is None,
            consumed=event_id is not None,
            windows=windows,
            blocking=blocking,
            event_id=event_id,
        )

    def link_audit(self, event_id: int, audit_id: int) -> None:
        """Verbindet einen verbrauchten Platz mit seinem Protokolleintrag."""
        with transaction(self._conn):
            self._conn.execute(
                "UPDATE rate_events SET audit_id = ? WHERE id = ?", (audit_id, event_id)
            )

    def prune(self, *, keep_seconds: int | None = None) -> int:
        """Raeumt Zaehlereintraege ab, die kein Fenster mehr sehen kann."""
        if keep_seconds is None:
            spans = [lim.seconds for cap in self._capabilities.values() for lim in cap.rate_limits]
            keep_seconds = max(spans) if spans else 0
        cutoff = self._now() - keep_seconds
        with transaction(self._conn):
            cur = self._conn.execute("DELETE FROM rate_events WHERE ts_epoch <= ?", (cutoff,))
        return cur.rowcount or 0
