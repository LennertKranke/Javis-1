"""Die eine Stelle, an der "darf ich nach aussen handeln" beantwortet wird.

Drei Pruefungen gehoeren zusammen und werden hier zusammen gestellt:
Stoppschalter, Autonomiestufe, Ratenbegrenzung. Waeren sie ueber die
Faehigkeiten verstreut, wuerde die vierte Faehigkeit irgendwann eine davon
vergessen -- und zwar unbemerkt, weil das Vergessen aussieht wie Erfolg.

Die Reihenfolge ist Absicht. Der Stoppschalter kommt vor der Ratenbegrenzung,
damit ein angehaltenes System keine Kontingente aufbraucht. Die Begrenzung wird
auch im Trockenlauf ausgewertet, aber nicht verbraucht: so zeigt der
Schattenbetrieb, wann sie gegriffen haette.

Jeder Aufruf hinterlaesst einen Protokolleintrag. Auch der abgelehnte.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from jarvis.core.audit import KIND_ACTION, AuditLog
from jarvis.core.config import Config
from jarvis.core.ratelimit import RateLimiter, RateVerdict

__all__ = ["Disposition", "Gate", "GateVerdict"]


class Disposition(StrEnum):
    ACT = "act"
    DRY_RUN = "dry_run"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GateVerdict:
    capability: str
    disposition: Disposition
    reason: str
    granted_level: int
    required_level: int
    rate: RateVerdict | None = None
    audit_id: int | None = None

    @property
    def may_act(self) -> bool:
        """Nur hier darf die Aktion tatsaechlich ausgefuehrt werden."""
        return self.disposition is Disposition.ACT


class Gate:
    def __init__(self, config: Config, audit: AuditLog, limiter: RateLimiter) -> None:
        self._config = config
        self._audit = audit
        self._limiter = limiter

    def evaluate(
        self,
        capability: str,
        *,
        required_level: int,
        subject: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> GateVerdict:
        cap = self._config.capability(capability)
        granted = int(cap.autonomy_level)

        if not cap.enabled:
            return self._record(
                capability,
                Disposition.BLOCKED,
                "Faehigkeit abgeschaltet",
                granted,
                required_level,
                None,
                subject,
                detail,
            )

        stop = self._config.stop_switch
        if stop.engaged():
            reason = stop.reason() or "ohne Angabe"
            return self._record(
                capability,
                Disposition.BLOCKED,
                f"Stoppschalter aktiv ({reason})",
                granted,
                required_level,
                None,
                subject,
                detail,
            )

        # Trockenlauf, wenn global so eingestellt oder die Stufe nicht reicht.
        dry = self._config.dry_run or not self._config.permits(capability, required_level)

        rate = self._limiter.acquire(capability, dry_run=dry)
        if not rate.allowed:
            return self._record(
                capability,
                Disposition.BLOCKED,
                rate.reason or "Obergrenze erreicht",
                granted,
                required_level,
                rate,
                subject,
                detail,
            )

        if dry:
            why = (
                "Trockenlauf global aktiv"
                if self._config.dry_run
                else f"Stufe {granted} reicht nicht fuer Stufe {required_level}"
            )
            return self._record(
                capability,
                Disposition.DRY_RUN,
                why,
                granted,
                required_level,
                rate,
                subject,
                detail,
            )

        return self._record(
            capability,
            Disposition.ACT,
            "freigegeben",
            granted,
            required_level,
            rate,
            subject,
            detail,
        )

    def _record(
        self,
        capability: str,
        disposition: Disposition,
        reason: str,
        granted: int,
        required: int,
        rate: RateVerdict | None,
        subject: str | None,
        detail: dict[str, Any] | None,
    ) -> GateVerdict:
        payload: dict[str, Any] = dict(detail or {})
        payload["reason"] = reason
        payload["granted_level"] = granted
        payload["required_level"] = required
        if rate is not None:
            payload["windows"] = {w.window: f"{w.used}/{w.limit}" for w in rate.windows}

        entry = self._audit.record(
            capability=capability,
            kind=KIND_ACTION,
            outcome=str(disposition),
            subject=subject,
            detail=payload,
            dry_run=disposition is Disposition.DRY_RUN,
        )
        if rate is not None and rate.event_id is not None:
            self._limiter.link_audit(rate.event_id, entry.id)

        return GateVerdict(
            capability=capability,
            disposition=disposition,
            reason=reason,
            granted_level=granted,
            required_level=required,
            rate=rate,
            audit_id=entry.id,
        )
