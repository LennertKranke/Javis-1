"""Fuehrt eine Faehigkeit einmal durch.

Der Ausfuehrer ist bewusst duenn und kennt keine einzelne Faehigkeit. Er sorgt
nur dafuer, dass die Reihenfolge stimmt und keiner der Schritte uebersprungen
wird: beurteilen, protokollieren, durchs Gatter, erst dann handeln.

Ein Fehler bei einer Nachricht beendet den Durchlauf nicht. Eine kaputte Mail
im Posteingang darf nicht dazu fuehren, dass die restlichen dreissig liegen
bleiben -- sie wird protokolliert und uebersprungen.

Seit Phase 4 kommt ein zweiter Weg dazu: was nicht von selbst durchging, kann
als anstehende Entscheidung in die Warteschlange wandern und spaeter von Hand
freigegeben werden. `execute_approval` baut die urspruengliche Entscheidung
dafuer wieder auf -- und laesst sie noch einmal durchs Gatter, nur eben mit der
Freigabe anstelle der Autonomiestufe.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from jarvis.core.approvals import EXECUTED, FAILED, REJECTED, Approval, ApprovalStore
from jarvis.core.audit import KIND_ACTION, KIND_DECISION, KIND_SYSTEM, AuditLog
from jarvis.core.gate import Disposition, Gate
from jarvis.skills.base import Decision, Result, Skill, TargetMismatch

__all__ = ["RunReport", "execute_approval", "reject_approval", "run_skill"]


@dataclass
class RunReport:
    skill: str
    polled: int = 0
    skipped: int = 0
    acted: int = 0
    dry_run: int = 0
    blocked: int = 0
    failed: int = 0
    queued: int = 0
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
    approvals: ApprovalStore | None = None,
    collect_approvals: bool = False,
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

        if decision.is_noop:
            report.skipped += 1
            skill.after(event, decision, decision.action, None)
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
            # Eine Faehigkeit meldet Erwartbares als `Result(performed=False)`.
            # Was hier durchschlaegt, ist das Unerwartete -- und das darf den
            # Durchlauf nicht beenden: sonst nimmt ein einziger kaputter
            # Vorgang alle folgenden mit, und der Daemon merkt beim naechsten
            # Tick dasselbe noch einmal. Abschnitt 6, Dauerbetrieb: Fehler
            # ueberleben. Der Vorgang gilt als fehlgeschlagen, nichts geht
            # hinaus, und der naechste ist an der Reihe.
            try:
                result = skill.act(decision)
            except Exception as exc:
                audit.record(
                    capability=skill.name,
                    kind=KIND_ACTION,
                    outcome="failed",
                    subject=event.key,
                    detail={"error": f"{type(exc).__name__}: {exc}"},
                )
                report.failed += 1
                report.errors.append(f"{event.key}: {type(exc).__name__}: {exc}")
                log.exception(
                    "Ausfuehrung fehlgeschlagen",
                    extra={"skill": skill.name, "event": event.key},
                )
                skill.after(event, decision, str(verdict.disposition), None)
                continue

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

        # Nur was am Stoppschalter vorbeikam, ist eine offene Frage: `rate` ist
        # gesetzt, sobald die Begrenzung ueberhaupt geprueft wurde. Ist das
        # System angehalten, steht die Antwort schon fest -- dann bliebe die
        # Warteschlange voller Vorgaenge, die niemand gemeint hat.
        sammelbar = approvals is not None and collect_approvals and verdict.rate is not None
        if sammelbar and not verdict.may_act:
            eingestellt = approvals.enqueue(
                skill=skill.name,
                event_key=event.key,
                action=decision.action,
                reason=verdict.reason,
                decided_by=decision.decided_by,
                summary=event.summary,
                fields=decision.fields,
                targets=decision.targets,
                model=decision.model,
                audit_id=verdict.audit_id,
            )
            if eingestellt is not None:
                report.queued += 1

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


def _decision_from(approval: Approval) -> Decision:
    """Baut die urspruengliche Entscheidung wieder auf.

    Ueber den regulaeren Weg, nicht per Umgehung: `Decision` prueft beim
    Anlegen erneut, dass in der Modellhaelfte kein Ziel steckt. Eine von Hand
    veraenderte Zeile in der Datenbank kommt damit nicht an Prinzip 2.1 vorbei.
    """
    return Decision(
        skill=approval.skill,
        event_key=approval.event_key,
        action=approval.action,
        reason=approval.reason,
        decided_by=approval.decided_by,
        fields=approval.fields,
        targets=approval.targets,
        model=approval.model,
    )


def execute_approval(
    approval: Approval,
    *,
    skill: Skill,
    gate: Gate,
    audit: AuditLog,
    approvals: ApprovalStore,
    logger: logging.Logger | None = None,
) -> Result | None:
    """Fuehrt eine freigegebene Entscheidung aus.

    Die Freigabe ersetzt die Autonomiestufe, sonst nichts. Stoppschalter,
    Ein-Aus-Schalter und Obergrenze gelten weiter; greift eine davon, bleibt
    der Vorgang offen und traegt den Grund als Vermerk. Erneut klicken kostet
    dann nichts, und niemand muss raten, warum nichts geschah.
    """
    log = logger or logging.getLogger("jarvis.runner")
    if not approval.pending:
        return None

    decision = _decision_from(approval)

    # Erst die Ziele gegen die Quelle pruefen, dann das Gatter fragen. Umgekehrt
    # wuerde ein Kontingent fuer eine Entscheidung verbraucht, die gar nicht
    # mehr ausfuehrbar ist.
    try:
        decision = skill.verify_targets(decision)
    except (TargetMismatch, NotImplementedError) as exc:
        audit.record(
            capability=skill.name,
            kind=KIND_ACTION,
            outcome="refused",
            subject=approval.event_key,
            detail={"approval_id": approval.id, "reason": str(exc)[:400]},
        )
        approvals.settle(approval.id, FAILED, note=str(exc)[:400])
        log.warning(
            "Freigabe verweigert: Ziele stimmen nicht mehr",
            extra={"skill": skill.name, "approval": approval.id, "error": str(exc)},
        )
        return None

    verdict = gate.evaluate(
        skill.name,
        required_level=skill.autonomy_level,
        subject=approval.event_key,
        detail={"action": decision.action, "approval_id": approval.id, "approved": True},
        approved=True,
    )

    if not verdict.may_act:
        approvals.note(approval.id, verdict.reason)
        log.info(
            "Freigabe nicht ausgefuehrt",
            extra={"skill": skill.name, "approval": approval.id, "reason": verdict.reason},
        )
        return None

    # Wie im Durchlauf: Unerwartetes beendet hier nichts. Dieser Weg kommt aus
    # dem Dashboard, und eine Ausnahme waere dort eine leere Fehlerseite mit
    # einem Vorgang, der weiter als offen dasteht.
    try:
        result = skill.act(decision)
    except Exception as exc:
        audit.record(
            capability=skill.name,
            kind=KIND_ACTION,
            outcome="failed",
            subject=approval.event_key,
            detail={"approval_id": approval.id, "error": f"{type(exc).__name__}: {exc}"},
        )
        approvals.settle(approval.id, FAILED, note=f"{type(exc).__name__}: {exc}"[:400])
        log.exception(
            "Freigabe fehlgeschlagen",
            extra={"skill": skill.name, "approval": approval.id},
        )
        return None

    audit.record(
        capability=skill.name,
        kind=KIND_ACTION,
        outcome="performed" if result.performed else "failed",
        subject=approval.event_key,
        detail=dict(result.detail)
        | {"approval_id": approval.id, "approved": True}
        | ({"error": result.error} if result.error else {}),
    )
    # Nachbereitung, bevor der Vorgang abgeschlossen wird. Ohne sie war der
    # Freigabeweg eine Sackgasse: `act()` legte den Entwurf an, aber der
    # Antwortspeicher erfuhr nichts davon -- der Entwurf lag im Postfach, und
    # `mail_send` sah ihn nie. Ein Fehler beim Nachtragen darf die bereits
    # ausgefuehrte Aktion nicht als gescheitert erscheinen lassen.
    try:
        skill.after_approval(decision, result)
    except Exception as exc:
        log.exception(
            "Nachbereitung der Freigabe fehlgeschlagen",
            extra={"skill": skill.name, "approval": approval.id},
        )
        audit.record(
            capability=skill.name,
            kind=KIND_ACTION,
            outcome="failed",
            subject=approval.event_key,
            detail={
                "approval_id": approval.id,
                "phase": "after_approval",
                "error": f"{type(exc).__name__}: {exc}",
            },
        )

    approvals.settle(
        approval.id,
        EXECUTED if result.performed else FAILED,
        note=result.error,
    )
    log.info(
        "Freigabe ausgefuehrt",
        extra={
            "skill": skill.name,
            "approval": approval.id,
            "performed": result.performed,
        },
    )
    return result


def reject_approval(
    approval: Approval,
    *,
    audit: AuditLog,
    approvals: ApprovalStore,
    note: str = "von Hand verworfen",
) -> bool:
    """Verwirft eine Entscheidung. Es geschieht nichts ausser einem Vermerk."""
    if not approvals.settle(approval.id, REJECTED, note=note):
        return False
    audit.record(
        capability=approval.skill,
        kind=KIND_SYSTEM,
        outcome="rejected",
        subject=approval.event_key,
        detail={"approval_id": approval.id, "note": note},
    )
    return True
