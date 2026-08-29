"""Stoppschalter und Gatter -- Prinzip 2.4."""

from __future__ import annotations

import pathlib

from jarvis.core.audit import AuditLog
from jarvis.core.config import StopSwitch
from jarvis.core.gate import Disposition, Gate
from jarvis.core.ratelimit import RateLimiter
from tests.conftest import build_config


def test_am_anfang_nicht_gesetzt(home):
    assert not StopSwitch(home / "STOP").engaged()


def test_setzen_und_loesen(home):
    switch = StopSwitch(home / "STOP")
    switch.engage("Testlauf")
    assert switch.engaged()
    assert "Testlauf" in (switch.reason() or "")
    assert switch.release() is True
    assert not switch.engaged()
    assert switch.release() is False


def test_blosse_existenz_genuegt(home):
    """Auch eine leere Datei von Hand haelt an -- `touch ~/.jarvis/STOP`."""
    (home / "STOP").touch()
    assert StopSwitch(home / "STOP").engaged()


def test_faellt_geschlossen_aus(home, monkeypatch):
    """Laesst sich der Zustand nicht feststellen, gilt angehalten."""

    def kaputt(self):
        raise OSError("Dateisystem nicht lesbar")

    monkeypatch.setattr(pathlib.Path, "exists", kaputt)
    assert StopSwitch(home / "STOP").engaged() is True


def gate_bauen(conn, home, **kwargs):
    config = build_config(home, **kwargs)
    audit = AuditLog(conn)
    limiter = RateLimiter(conn, config.capabilities)
    return Gate(config, audit, limiter), audit, limiter


def test_gatter_blockiert_bei_gesetztem_schalter(conn, home):
    gate, _audit, _limiter = gate_bauen(conn, home, dry_run=False, level=1)
    StopSwitch(home / "STOP").engage("Vorfall")

    verdict = gate.evaluate("mail", required_level=1)
    assert verdict.disposition is Disposition.BLOCKED
    assert not verdict.may_act
    assert "Vorfall" in verdict.reason


def test_gestoppt_verbraucht_kein_kontingent(conn, home):
    """Ein angehaltenes System soll seine Kontingente nicht aufbrauchen."""
    gate, _audit, limiter = gate_bauen(conn, home, dry_run=False, level=1, limits={"hour": 3})
    StopSwitch(home / "STOP").engage("Vorfall")
    for _ in range(10):
        gate.evaluate("mail", required_level=1)
    assert limiter.usage("mail")[0].used == 0


def test_stufe_null_ergibt_trockenlauf(conn, home):
    gate, _audit, _limiter = gate_bauen(conn, home, dry_run=False, level=0)
    verdict = gate.evaluate("mail", required_level=1)
    assert verdict.disposition is Disposition.DRY_RUN
    assert not verdict.may_act
    assert "Stufe 0" in verdict.reason


def test_ausreichende_stufe_gibt_frei(conn, home):
    gate, _audit, _limiter = gate_bauen(conn, home, dry_run=False, level=1)
    verdict = gate.evaluate("mail", required_level=1)
    assert verdict.disposition is Disposition.ACT
    assert verdict.may_act


def test_globaler_trockenlauf_schlaegt_die_stufe(conn, home):
    gate, _audit, _limiter = gate_bauen(conn, home, dry_run=True, level=3)
    verdict = gate.evaluate("mail", required_level=1)
    assert verdict.disposition is Disposition.DRY_RUN
    assert "Trockenlauf" in verdict.reason


def test_abgeschaltete_faehigkeit_blockiert(conn, home):
    gate, _audit, _limiter = gate_bauen(conn, home, dry_run=False, level=3, enabled=False)
    verdict = gate.evaluate("mail", required_level=0)
    assert verdict.disposition is Disposition.BLOCKED


def test_erschoepfte_grenze_blockiert(conn, home):
    gate, _audit, _limiter = gate_bauen(conn, home, dry_run=False, level=1, limits={"hour": 2})
    assert gate.evaluate("mail", required_level=1).may_act
    assert gate.evaluate("mail", required_level=1).may_act
    dritter = gate.evaluate("mail", required_level=1)
    assert dritter.disposition is Disposition.BLOCKED
    assert "Obergrenze" in dritter.reason


def test_jede_entscheidung_landet_im_protokoll(conn, home):
    gate, audit, _limiter = gate_bauen(conn, home, dry_run=False, level=1, limits={"hour": 1})
    gate.evaluate("mail", required_level=1, subject="nachricht-1")
    gate.evaluate("mail", required_level=1, subject="nachricht-2")  # blockiert

    entries = audit.recent(10)
    assert len(entries) == 2
    assert {e.outcome for e in entries} == {"act", "blocked"}
    assert audit.verify().ok


def test_trockenlauf_wird_als_solcher_protokolliert(conn, home):
    gate, audit, _limiter = gate_bauen(conn, home, dry_run=True, level=0)
    verdict = gate.evaluate("mail", required_level=1)
    entry = audit.recent(1)[0]
    assert entry.dry_run is True
    assert entry.id == verdict.audit_id
