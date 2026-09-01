"""Anstehende Entscheidungen: Warteschlange, Gatter, Ausfuehrung."""

from __future__ import annotations

import threading

import pytest

from jarvis.core.approvals import CLAIMED, EXECUTED, PENDING, REJECTED, ApprovalStore
from jarvis.core.audit import AuditLog
from jarvis.core.config import StopSwitch
from jarvis.core.db import open_database
from jarvis.core.gate import Disposition, Gate
from jarvis.core.ratelimit import RateLimiter
from jarvis.skills.base import Decision, Event, Result, Skill
from jarvis.skills.runner import execute_approval, reject_approval, run_skill
from tests.conftest import build_config


def einstellen(store, **kwargs):
    grund = {
        "skill": "mail",
        "event_key": "m1",
        "action": "label",
        "reason": "Stufe 0 reicht nicht",
        "decided_by": "model",
        "summary": "absender@example.com -- Rechnung",
        "fields": {"kategorie": "rechnung"},
        "targets": {"message_id": "m1", "label_name": "JARVIS/Rechnung"},
    }
    grund.update(kwargs)
    return store.enqueue(**grund)


# --- Warteschlange ---------------------------------------------------------- #


def test_einstellen_und_lesen(conn):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    assert eintrag is not None
    assert eintrag.state == PENDING
    assert eintrag.fields == {"kategorie": "rechnung"}
    assert eintrag.targets["message_id"] == "m1"
    assert store.count_pending() == 1


def test_derselbe_vorgang_steht_nur_einmal_offen(conn):
    """Sonst sammelt jeder Durchlauf eine neue Kopie derselben Frage."""
    store = ApprovalStore(conn)
    assert einstellen(store) is not None
    assert einstellen(store) is None
    assert store.count_pending() == 1


def test_nach_dem_abschluss_darf_er_wieder_auftauchen(conn):
    store = ApprovalStore(conn)
    erster = einstellen(store)
    store.settle(erster.id, REJECTED)
    zweiter = einstellen(store)
    assert zweiter is not None and zweiter.id != erster.id


def test_verschiedene_faehigkeiten_stoeren_sich_nicht(conn):
    store = ApprovalStore(conn)
    assert einstellen(store, skill="mail") is not None
    assert einstellen(store, skill="mail_reply") is not None
    assert store.count_pending() == 2
    assert store.count_pending(skill="mail") == 1


def test_abschliessen_geht_nur_einmal(conn):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    assert store.settle(eintrag.id, EXECUTED) is True
    assert store.settle(eintrag.id, REJECTED) is False
    assert store.get(eintrag.id).state == EXECUTED


def test_offen_bleibt_offen_mit_vermerk(conn):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    store.note(eintrag.id, "Stoppschalter aktiv")
    frisch = store.get(eintrag.id)
    assert frisch.pending
    assert frisch.note == "Stoppschalter aktiv"


def test_unbrauchbarer_endzustand(conn):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    with pytest.raises(ValueError):
        store.settle(eintrag.id, PENDING)


def test_zaehlung_nach_zustand(conn):
    store = ApprovalStore(conn)
    a = einstellen(store, event_key="a")
    einstellen(store, event_key="b")
    store.settle(a.id, EXECUTED)
    assert store.counts_by_state() == {EXECUTED: 1, PENDING: 1}


# --- Gatter: Freigabe ersetzt die Stufe, sonst nichts ----------------------- #


def gatter(conn, home, **kwargs):
    config = build_config(home, **kwargs)
    audit = AuditLog(conn)
    return Gate(config, audit, RateLimiter(conn, config.capabilities)), audit, config


def test_freigabe_ersetzt_die_stufe(conn, home):
    gate, _, _ = gatter(conn, home, dry_run=False, level=0)
    ohne = gate.evaluate("mail", required_level=2)
    mit = gate.evaluate("mail", required_level=2, approved=True)
    assert ohne.disposition is Disposition.DRY_RUN
    assert mit.disposition is Disposition.ACT
    assert mit.reason == "von Hand freigegeben"


def test_freigabe_kommt_nicht_am_stoppschalter_vorbei(conn, home):
    """Sonst waere der Stoppschalter nur eine Bitte."""
    gate, _, _ = gatter(conn, home, dry_run=False, level=0)
    StopSwitch(home / "STOP").engage("Vorfall")
    urteil = gate.evaluate("mail", required_level=2, approved=True)
    assert urteil.disposition is Disposition.BLOCKED


def test_freigabe_kommt_nicht_an_der_obergrenze_vorbei(conn, home):
    gate, _, _ = gatter(conn, home, dry_run=False, level=0, limits={"hour": 1})
    assert gate.evaluate("mail", required_level=2, approved=True).may_act
    assert not gate.evaluate("mail", required_level=2, approved=True).may_act


def test_freigabe_kommt_nicht_am_trockenlauf_vorbei(conn, home):
    """dry_run heisst "nichts geht hinaus" -- auch wenn jemand klickt."""
    gate, _, _ = gatter(conn, home, dry_run=True, level=3)
    urteil = gate.evaluate("mail", required_level=1, approved=True)
    assert urteil.disposition is Disposition.DRY_RUN


def test_freigabe_kommt_nicht_an_abgeschaltet_vorbei(conn, home):
    gate, _, _ = gatter(conn, home, dry_run=False, level=3, enabled=False)
    assert gate.evaluate("mail", required_level=0, approved=True).disposition is Disposition.BLOCKED


# --- Ausfuehrung ------------------------------------------------------------ #


class Attrappe(Skill):
    name = "mail"
    autonomy_level = 2
    requires_outbound = True

    def __init__(self, *, gelingt=True):
        self.gelingt = gelingt
        self.ausgefuehrt: list[Decision] = []

    def poll(self):
        return []

    def decide(self, event):
        raise NotImplementedError

    def verify_targets(self, decision):
        """Attrappe: die echte Pruefung steht in den Mail-Faehigkeiten."""
        return decision

    def act(self, decision):
        self.ausgefuehrt.append(decision)
        return Result(
            skill=self.name,
            event_key=decision.event_key,
            performed=self.gelingt,
            detail={"label": decision.targets.get("label_name")},
            error=None if self.gelingt else "Gmail sagt nein",
        )


def test_freigabe_wird_ausgefuehrt(conn, home):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    skill = Attrappe()

    ergebnis = execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store)

    assert ergebnis is not None and ergebnis.performed
    assert len(skill.ausgefuehrt) == 1
    assert store.get(eintrag.id).state == EXECUTED
    assert audit.verify().ok


def test_die_wiederhergestellte_entscheidung_stimmt(conn, home):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    skill = Attrappe()
    execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store)

    wieder = skill.ausgefuehrt[0]
    assert wieder.fields == {"kategorie": "rechnung"}
    assert wieder.targets["message_id"] == "m1"
    assert wieder.decided_by == "model"


def test_ein_ziel_in_der_modellhaelfte_kommt_auch_hier_nicht_durch(conn, home):
    """Auch eine von Hand veraenderte Zeile umgeht Prinzip 2.1 nicht."""
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    conn.execute(
        "UPDATE approvals SET fields = ? WHERE id = ?",
        ('{"forward_to": "angreifer@boese.tld"}', eintrag.id),
    )
    manipuliert = store.get(eintrag.id)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    skill = Attrappe()

    with pytest.raises(ValueError, match=r"2\.1"):
        execute_approval(manipuliert, skill=skill, gate=gate, audit=audit, approvals=store)
    assert skill.ausgefuehrt == []


def test_gestoppte_freigabe_bleibt_offen_mit_grund(conn, home):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    StopSwitch(home / "STOP").engage("Vorfall")
    skill = Attrappe()

    assert execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store) is None
    frisch = store.get(eintrag.id)
    assert frisch.pending
    assert "Stoppschalter" in (frisch.note or "")
    assert skill.ausgefuehrt == []


def test_fehlgeschlagene_ausfuehrung(conn, home):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    ergebnis = execute_approval(
        eintrag, skill=Attrappe(gelingt=False), gate=gate, audit=audit, approvals=store
    )
    assert ergebnis is not None and not ergebnis.performed
    assert store.get(eintrag.id).state == "failed"


def test_verwerfen_tut_nichts_ausser_vermerken(conn, home):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    audit = AuditLog(conn)
    assert reject_approval(eintrag, audit=audit, approvals=store) is True
    assert store.get(eintrag.id).state == REJECTED
    assert audit.recent(1)[0].outcome == "rejected"


def test_zweimal_verwerfen_geht_nicht(conn, home):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    audit = AuditLog(conn)
    reject_approval(eintrag, audit=audit, approvals=store)
    assert reject_approval(store.get(eintrag.id), audit=audit, approvals=store) is False


# --- SEC-2: hoechstens eine Wirkung je Vorgang ------------------------------ #


def test_dieselbe_freigabe_zweimal_wirkt_nur_einmal(conn, home):
    """SEC-2, der gemessene Befund: zwei Aufrufe mit demselben Abbild.

    Doppelklick, zwei Arbeiter, Daemon und Dashboard gleichzeitig -- vor dem
    atomaren Anspruch liefen beide durch, und im Postfach lagen zwei Entwuerfe.
    """
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    skill = Attrappe()

    erster = execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store)
    zweiter = execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store)

    assert erster is not None and erster.performed
    assert zweiter is None
    assert len(skill.ausgefuehrt) == 1
    assert store.get(eintrag.id).state == EXECUTED


def test_der_verlierer_bekommt_einen_grund_ins_protokoll(conn, home):
    """Der zweite Aufruf ist kein Fehler -- er traegt einen lesbaren Grund."""
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    skill = Attrappe()
    execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store)
    execute_approval(eintrag, skill=skill, gate=gate, audit=audit, approvals=store)

    letzter = audit.recent(1)[0]
    assert letzter.outcome == "refused"
    assert "kein Anspruch" in str(letzter.detail.get("reason", ""))
    assert audit.verify().ok


def test_der_anspruch_ist_atomar(conn):
    """`claim` gelingt genau einmal; der Verlierer bekommt None."""
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    assert store.claim(eintrag.id) is not None
    assert store.claim(eintrag.id) is None
    assert store.get(eintrag.id).state == CLAIMED


def test_der_anspruch_haelt_nebenlaeufig_ueber_getrennte_verbindungen(conn, home):
    """Zwei Verbindungen wie zwei Prozesse: genau einer gewinnt.

    Der Schutz liegt in der Datenbank (`BEGIN IMMEDIATE` plus
    Zustandsbedingung), nicht in einem Python-Zustand -- deshalb muss er auch
    ueber getrennte Verbindungen halten, nicht nur im selben Objekt.
    """
    store = ApprovalStore(conn)
    eintrag = einstellen(store)

    start = threading.Barrier(2)
    treffer: list[int] = []

    def greifer() -> None:
        eigene = open_database(home / "state.db")
        try:
            start.wait(timeout=10)
            if ApprovalStore(eigene).claim(eintrag.id) is not None:
                treffer.append(1)
        finally:
            eigene.close()

    faeden = [threading.Thread(target=greifer) for _ in range(2)]
    for faden in faeden:
        faden.start()
    for faden in faeden:
        faden.join(timeout=30)

    assert sum(treffer) == 1
    assert store.get(eintrag.id).state == CLAIMED


def test_freigeben_am_stoppschalter_gibt_den_anspruch_zurueck(conn, home):
    """Blockiert das Gatter, wandert der Vorgang zurueck in die Warteschlange."""
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    StopSwitch(home / "STOP").engage("Vorfall")

    assert (
        execute_approval(eintrag, skill=Attrappe(), gate=gate, audit=audit, approvals=store) is None
    )
    frisch = store.get(eintrag.id)
    assert frisch.state == PENDING
    # Und er laesst sich danach ganz normal ausfuehren.
    StopSwitch(home / "STOP").release()
    ergebnis = execute_approval(frisch, skill=Attrappe(), gate=gate, audit=audit, approvals=store)
    assert ergebnis is not None and ergebnis.performed


def test_beanspruchtes_laesst_sich_nicht_verwerfen(conn, home):
    """Was gerade ausgefuehrt wird, kann niemand mehr zuruecknehmen."""
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    audit = AuditLog(conn)
    assert store.claim(eintrag.id) is not None
    assert reject_approval(eintrag, audit=audit, approvals=store) is False
    assert store.get(eintrag.id).state == CLAIMED


def test_solange_beansprucht_wird_nichts_neues_eingestellt(conn):
    """`claimed` zaehlt als offen -- sonst entstuende eine zweite Kopie."""
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    store.claim(eintrag.id)
    assert einstellen(store) is None


def test_claimed_ist_kein_endzustand(conn):
    store = ApprovalStore(conn)
    eintrag = einstellen(store)
    with pytest.raises(ValueError):
        store.settle(eintrag.id, CLAIMED)


# --- Der Durchlauf reiht ein ------------------------------------------------ #


class Zaehlskill(Skill):
    name = "mail"
    autonomy_level = 2
    requires_outbound = True

    def poll(self):
        return [Event(skill=self.name, key="a", summary="eine Nachricht", payload=None)]

    def decide(self, event):
        return Decision(
            skill=self.name,
            event_key=event.key,
            action="label",
            reason="weil",
            decided_by="model",
            fields={"kategorie": "rechnung"},
            targets={"message_id": "a"},
        )

    def act(self, decision):
        return Result(skill=self.name, event_key=decision.event_key, performed=True)


def test_durchlauf_reiht_offene_entscheidungen_ein(conn, home):
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    store = ApprovalStore(conn)
    bericht = run_skill(
        Zaehlskill(), gate=gate, audit=audit, approvals=store, collect_approvals=True
    )
    assert bericht.dry_run == 1
    assert bericht.queued == 1
    assert store.count_pending() == 1


def test_ohne_sammeln_wird_nichts_eingereiht(conn, home):
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    store = ApprovalStore(conn)
    bericht = run_skill(Zaehlskill(), gate=gate, audit=audit, approvals=store)
    assert bericht.queued == 0
    assert store.count_pending() == 0


def test_ausgefuehrtes_wird_nicht_eingereiht(conn, home):
    gate, audit, _ = gatter(conn, home, dry_run=False, level=2)
    store = ApprovalStore(conn)
    bericht = run_skill(
        Zaehlskill(), gate=gate, audit=audit, approvals=store, collect_approvals=True
    )
    assert bericht.acted == 1
    assert store.count_pending() == 0


def test_bei_gestopptem_system_wird_nichts_eingereiht(conn, home):
    """Dann steht die Antwort schon fest -- es gibt nichts zu entscheiden."""
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    StopSwitch(home / "STOP").engage("Vorfall")
    store = ApprovalStore(conn)
    bericht = run_skill(
        Zaehlskill(), gate=gate, audit=audit, approvals=store, collect_approvals=True
    )
    assert bericht.blocked == 1
    assert store.count_pending() == 0


def test_zweiter_durchlauf_reiht_nicht_doppelt_ein(conn, home):
    gate, audit, _ = gatter(conn, home, dry_run=False, level=0)
    store = ApprovalStore(conn)
    skill = Zaehlskill()
    run_skill(skill, gate=gate, audit=audit, approvals=store, collect_approvals=True)
    zweiter = run_skill(skill, gate=gate, audit=audit, approvals=store, collect_approvals=True)
    assert zweiter.queued == 0
    assert store.count_pending() == 1


# --- Gatter: die Vorschau erklaert, ohne zu entscheiden ---------------------- #
#
# Die Vorschau ist fuer die Oberflaeche da. Sie beantwortet nicht "darf
# gehandelt werden" -- das tut weiter `evaluate` --, sondern "woran wuerde es
# gerade haengen". Zwei Eigenschaften muessen halten, sonst richtet sie mehr
# Schaden an als Nutzen: sie darf nichts veraendern, und sie darf nie etwas
# anderes sagen als das Gatter selbst.


def test_vorschau_veraendert_nichts(conn, home):
    """Kein Protokolleintrag, kein verbrauchtes Kontingent."""
    gate, audit, config = gatter(conn, home, dry_run=False, level=1, limits={"hour": 2})
    limiter = RateLimiter(conn, config.capabilities)
    vorher = audit.count()

    for _ in range(5):
        gate.preview("mail", required_level=1)

    assert audit.count() == vorher
    assert limiter.usage("mail")[0].used == 0
    # Gegenprobe: eine echte Auswertung tut beides sehr wohl.
    gate.evaluate("mail", required_level=1)
    assert audit.count() == vorher + 1
    assert limiter.usage("mail")[0].used == 1


@pytest.mark.parametrize(
    "lage",
    [
        {"dry_run": False, "level": 1},
        {"dry_run": False, "level": 0},
        {"dry_run": True, "level": 1},
        {"dry_run": False, "level": 1, "enabled": False},
        {"dry_run": False, "level": 0, "limits": {"hour": 0}},
    ],
)
@pytest.mark.parametrize("freigegeben", [False, True])
def test_vorschau_stimmt_mit_dem_gatter_ueberein(conn, home, lage, freigegeben):
    """Der eigentliche Schutz gegen Auseinanderdriften.

    Die Vorschau bildet die Reihenfolge aus Abschnitt 4.2 ein zweites Mal ab.
    Zwei Fassungen derselben Rechnung driften auseinander, wenn nichts sie
    zusammenhaelt -- und eine Oberflaeche, die etwas anderes anzeigt als das
    Gatter tut, ist schlimmer als eine, die nichts anzeigt.
    """
    gate, _, _ = gatter(conn, home, **lage)
    vorschau = gate.preview("mail", required_level=1, approved=freigegeben)
    urteil = gate.evaluate("mail", required_level=1, approved=freigegeben)
    assert vorschau.disposition is urteil.disposition


@pytest.mark.parametrize("freigegeben", [False, True])
def test_vorschau_stimmt_auch_bei_gesetztem_stoppschalter(conn, home, freigegeben):
    """Der Fall, den die Matrix oben nicht abdeckt -- und der teuer waere."""
    gate, _, _ = gatter(conn, home, dry_run=False, level=1)
    StopSwitch(home / "STOP").engage("Vorfall")
    vorschau = gate.preview("mail", required_level=1, approved=freigegeben)
    urteil = gate.evaluate("mail", required_level=1, approved=freigegeben)
    assert vorschau.disposition is urteil.disposition is Disposition.BLOCKED


def test_vorschau_beim_stoppschalter(conn, home):
    gate, _, _ = gatter(conn, home, dry_run=False, level=1)
    StopSwitch(home / "STOP").engage("Vorfall")
    vorschau = gate.preview("mail", required_level=1, approved=True)

    assert vorschau.disposition is Disposition.BLOCKED
    schritte = {s.name: s for s in vorschau.steps}
    assert schritte["Stoppschalter"].outcome == "blockiert"
    assert "Vorfall" in schritte["Stoppschalter"].value
    # Was danach kommt, wurde nicht ausgewertet -- und sagt das auch.
    assert schritte["Obergrenze"].outcome == "offen"
    assert schritte["Stufe / Freigabe"].outcome == "offen"


def test_vorschau_zeigt_dass_die_freigabe_nur_die_stufe_ersetzt(conn, home):
    """Prinzip aus 4.2, an der Leiter ablesbar."""
    gate, _, _ = gatter(conn, home, dry_run=True, level=0)
    vorschau = gate.preview("mail", required_level=1, approved=True)
    schritte = {s.name: s for s in vorschau.steps}

    # Die Freigabe wirkt auf Sprosse 3 ...
    assert schritte["Stufe / Freigabe"].outcome == "weiter"
    assert "freigegeben" in schritte["Stufe / Freigabe"].value.lower()
    # ... und nicht auf den Trockenlauf.
    assert vorschau.disposition is Disposition.DRY_RUN
    assert schritte["Ausfuehrung"].outcome == "trocken"
    assert "Trockenlauf" in schritte["Ausfuehrung"].value


def test_vorschau_haelt_an_der_stufe(conn, home):
    gate, _, _ = gatter(conn, home, dry_run=False, level=0)
    vorschau = gate.preview("mail", required_level=1)
    schritte = {s.name: s for s in vorschau.steps}

    assert vorschau.disposition is Disposition.DRY_RUN
    assert schritte["Stufe / Freigabe"].outcome == "trocken"
    assert vorschau.granted_level == 0
    assert vorschau.required_level == 1


def test_vorschau_nennt_die_fuenf_sprossen_in_der_reihenfolge(conn, home):
    """Die Reihenfolge ist Absicht (4.2) und wird nie umsortiert."""
    gate, _, _ = gatter(conn, home, dry_run=False, level=1)
    assert [s.name for s in gate.preview("mail", required_level=1).steps] == [
        "Faehigkeit aktiv",
        "Stoppschalter",
        "Stufe / Freigabe",
        "Obergrenze",
        "Ausfuehrung",
    ]


def test_vorschau_zeigt_die_obergrenze_mit_bezug(conn, home):
    gate, _, _ = gatter(conn, home, dry_run=False, level=1, limits={"hour": 2})
    gate.evaluate("mail", required_level=1)
    schritte = {s.name: s for s in gate.preview("mail", required_level=1).steps}
    assert "1/2" in schritte["Obergrenze"].value
