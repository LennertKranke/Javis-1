"""Fuehrt eine Faehigkeit einmal durch.

Der Ausfuehrer ist bewusst duenn und kennt keine einzelne Faehigkeit. Er sorgt
nur dafuer, dass die Reihenfolge stimmt und keiner der Schritte uebersprungen
wird: beurteilen, protokollieren, durchs Gatter, erst dann handeln.

Ein Fehler bei einer Nachricht beendet den Durchlauf nicht. Eine kaputte Mail
im Posteingang darf nicht dazu fuehren, dass die restlichen dreissig liegen
bleiben -- sie wird protokolliert und uebersprungen.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from jarvis.core.audit import KIND_ACTION, KIND_DECISION, AuditLog
from jarvis.core.gate import Disposition, Gate
from jarvis.skills.base import Skill

__all__ = ["RunReport", "run_skill"]


@dataclass
class RunReport:
    skill: str
    polled: int = 0
    skipped: int = 0
    acted: int = 0
    dry_run: int = 0
    blocked: int = 0
    failed: int = 0
    by_category: Counter[str] = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    @property
    def decided(self) -> int:
        return self.acted + self.dry_run + self.blocked + self.skipped


def run_skill(
    skill: Skill,
    *,
    gate: Gate,
    audit: AuditLog,
    logger: logging.Logger | None = None,
) -> RunReport:
    log = logger or logging.getLogger("jarvis.runner")
    report = RunReport(skill=skill.name)

    events = skill.poll()
    report.polled = len(events)
    log.info("Durchlauf begonnen", extra={"skill": skill.name, "events": len(events)})

    for event in events:
        try:
            decision = skill.decide(event)
        except Exception as exc:  # eine schlechte Nachricht kippt nicht den Lauf
            report.failed += 1
            report.errors.append(f"{event.key}: {exc}")
            audit.record(
                capability=skill.name,
                kind=KIND_DECISION,
                outcome="failed",
                subject=event.key,
                detail={"error": str(exc), "summary": event.summary},
            )
            log.warning(
                "Beurteilung fehlgeschlagen",
                extra={"skill": skill.name, "event": event.key, "error": str(exc)},
            )
            continue

        detail = decision.audit_detail | {"summary": event.summary}
        audit.record(
            capability=skill.name,
            kind=KIND_DECISION,
            outcome=decision.action,
            subject=event.key,
            detail=detail,
        )

        if decision.action == "skip":
            report.skipped += 1
            skill.after(event, decision, "skip", None)
            continue

        kategorie = decision.targets.get("category")
        if kategorie:
            report.by_category[str(kategorie)] += 1

        verdict = gate.evaluate(
            skill.name,
            required_level=skill.autonomy_level,
            subject=event.key,
            detail={"action": decision.action, "decided_by": decision.decided_by},
        )

        result = None
        if verdict.may_act:
            result = skill.act(decision)
            audit.record(
                capability=skill.name,
                kind=KIND_ACTION,
                outcome="performed" if result.performed else "failed",
                subject=event.key,
                detail=dict(result.detail) | ({"error": result.error} if result.error else {}),
            )
            if result.performed:
                report.acted += 1
            else:
                report.failed += 1
                if result.error:
                    report.errors.append(f"{event.key}: {result.error}")
        elif verdict.disposition is Disposition.DRY_RUN:
            report.dry_run += 1
        else:
            report.blocked += 1

        skill.after(event, decision, str(verdict.disposition), result)

    log.info(
        "Durchlauf beendet",
        extra={
            "skill": skill.name,
            "acted": report.acted,
            "dry_run": report.dry_run,
            "blocked": report.blocked,
            "skipped": report.skipped,
            "failed": report.failed,
        },
    )
    return report
