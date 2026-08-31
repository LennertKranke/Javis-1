"""Die eine Stelle, an der "darf ich nach aussen handeln" beantwortet wird.

Drei Pruefungen gehoeren zusammen und werden hier zusammen gestellt:
Stoppschalter, Autonomiestufe, Ratenbegrenzung. Waeren sie ueber die
Faehigkeiten verstreut, wuerde die vierte Faehigkeit irgendwann eine davon
vergessen -- und zwar unbemerkt, weil das Vergessen aussieht wie Erfolg.

Seit Phase 4 gibt es einen zweiten Weg hindurch: eine ausdrueckliche Freigabe
durch einen Menschen. Sie ersetzt die Autonomiestufe -- mehr nicht. Der
Stoppschalter, der Ein-Aus-Schalter der Faehigkeit und die Obergrenze gelten
weiter. Ein angehaltenes System bleibt angehalten, auch wenn jemand klickt;
sonst waere der Stoppschalter nur eine Bitte.

Die Reihenfolge ist Absicht. Der Stoppschalter kommt vor der Ratenbegrenzung,
damit ein angehaltenes System keine Kontingente aufbraucht.

Die Begrenzung wird auch im Trockenlauf ausgewertet, aber nicht verbraucht --
ein Schattenbetrieb soll kein echtes Kontingent aufessen. Hier stand frueher,
der Schattenbetrieb zeige damit, *wann* die Grenze gegriffen haette. Das tut er
nicht: was nichts verbraucht, laesst den Zaehler stehen, und die Grenze wird im
Trockenlauf nie erreicht. Nachgemessen im End-to-End-Review; die Zusage ist
gestrichen, nicht das Verhalten.

Jeder Aufruf hinterlaesst einen Protokolleintrag. Auch der abgelehnte.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from jarvis.core.audit import KIND_ACTION, AuditLog
from jarvis.core.config import Config
from jarvis.core.ratelimit import RateLimiter, RateVerdict

__all__ = ["Disposition", "Gate", "GatePreview", "GateStep", "GateVerdict"]


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


@dataclass(frozen=True)
class GateStep:
    """Eine Sprosse der Leiter, wie die Oberflaeche sie zeigt.

    `outcome` ist bewusst kein `Disposition`: eine Sprosse hat mehr Zustaende
    als der Vorgang als Ganzes. `offen` heisst "nicht ausgewertet" -- und das
    ist etwas anderes als "bestanden".
    """

    name: str
    value: str
    outcome: str  # weiter | blockiert | trocken | act | offen


@dataclass(frozen=True)
class GatePreview:
    capability: str
    disposition: Disposition
    reason: str
    granted_level: int
    required_level: int
    steps: tuple[GateStep, ...]


#: Die Reihenfolge aus Abschnitt 4.2. Sie wird nie umsortiert.
SPROSSEN = (
    "Faehigkeit aktiv",
    "Stoppschalter",
    "Stufe / Freigabe",
    "Obergrenze",
    "Ausfuehrung",
)


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
        approved: bool = False,
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
        # Eine Freigabe von Hand ersetzt die Stufe, nicht den Trockenlauf:
        # dry_run heisst "nichts geht hinaus", und das soll es auch heissen,
        # wenn jemand klickt.
        stufe_reicht = self._config.permits(capability, required_level, approved=approved)
        dry = self._config.dry_run or not stufe_reicht

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
            "von Hand freigegeben" if approved else "freigegeben",
            granted,
            required_level,
            rate,
            subject,
            detail,
        )

    def preview(
        self,
        capability: str,
        *,
        required_level: int,
        approved: bool = False,
    ) -> GatePreview:
        """Woran haengt es gerade -- ohne etwas zu entscheiden.

        Fuer die Oberflaeche. `evaluate` beantwortet "darf gehandelt werden"
        und schreibt dabei ins Protokoll und verbraucht Kontingent; das darf
        eine Anzeige nicht tun. Deshalb hier dieselbe Reihenfolge, aber
        lesend: `limiter.check` statt `limiter.acquire`, kein Protokolleintrag.

        Dass die Reihenfolge damit ein zweites Mal im Code steht, ist der Preis.
        Er wird durch einen Test bezahlt, der Vorschau und Auswertung ueber
        alle Lagen gegeneinander haelt -- eine Oberflaeche, die etwas anderes
        anzeigt als das Gatter tut, waere schlimmer als eine, die nichts zeigt.
        """
        cap = self._config.capability(capability)
        granted = int(cap.autonomy_level)
        schritte: list[GateStep] = []

        def fertig(disposition: Disposition, reason: str) -> GatePreview:
            # Was nach der haltenden Sprosse kommt, wurde nicht ausgewertet.
            # Es als "bestanden" zu zeigen waere gelogen.
            for name in SPROSSEN[len(schritte) :]:
                schritte.append(GateStep(name, "nicht ausgewertet", "offen"))
            return GatePreview(
                capability=capability,
                disposition=disposition,
                reason=reason,
                granted_level=granted,
                required_level=int(required_level),
                steps=tuple(schritte),
            )

        if not cap.enabled:
            schritte.append(GateStep(SPROSSEN[0], "abgeschaltet", "blockiert"))
            return fertig(Disposition.BLOCKED, "Faehigkeit abgeschaltet")
        schritte.append(GateStep(SPROSSEN[0], "ja", "weiter"))

        stop = self._config.stop_switch
        if stop.engaged():
            grund = stop.reason() or "ohne Angabe"
            schritte.append(GateStep(SPROSSEN[1], f"gesetzt: {grund}", "blockiert"))
            return fertig(Disposition.BLOCKED, f"Stoppschalter aktiv ({grund})")
        schritte.append(GateStep(SPROSSEN[1], "nicht gesetzt", "weiter"))

        stufe_reicht = self._config.permits(capability, required_level, approved=approved)
        if not stufe_reicht:
            schritte.append(
                GateStep(
                    SPROSSEN[2],
                    f"gewaehrt {granted} reicht nicht fuer verlangt {required_level}",
                    "trocken",
                )
            )
        elif approved and granted < int(required_level):
            schritte.append(
                GateStep(
                    SPROSSEN[2],
                    f"von Hand freigegeben -- gewaehrt {granted}, verlangt {required_level}",
                    "weiter",
                )
            )
        else:
            schritte.append(
                GateStep(SPROSSEN[2], f"gewaehrt {granted}, verlangt {required_level}", "weiter")
            )

        rate = self._limiter.check(capability)
        stand = "  ".join(f"{w.used}/{w.limit} {w.window}" for w in rate.windows)
        if not rate.allowed:
            schritte.append(GateStep(SPROSSEN[3], rate.reason or "erreicht", "blockiert"))
            return fertig(Disposition.BLOCKED, rate.reason or "Obergrenze erreicht")
        schritte.append(GateStep(SPROSSEN[3], stand or "keine Obergrenze", "weiter"))

        if self._config.dry_run or not stufe_reicht:
            why = (
                "Trockenlauf global aktiv"
                if self._config.dry_run
                else f"Stufe {granted} reicht nicht fuer Stufe {required_level}"
            )
            schritte.append(GateStep(SPROSSEN[4], why, "trocken"))
            return fertig(Disposition.DRY_RUN, why)

        grund = "von Hand freigegeben" if approved else "freigegeben"
        schritte.append(GateStep(SPROSSEN[4], "geht nach aussen", "act"))
        return fertig(Disposition.ACT, grund)

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
