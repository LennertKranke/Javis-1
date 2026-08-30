"""Dauerbetrieb: die Uhr, und was passiert, wenn etwas kaputt ist.

Die Leitfrage aller Fehlertests hier ist immer dieselbe: darf ein Fehler
dazu fuehren, dass JARVIS etwas tut, was vorher blockiert war? Die Antwort
muss nein sein, und zwar bei jedem einzelnen.
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from jarvis.core.audit import AuditLog
from jarvis.core.config import Config, Paths
from jarvis.daemon import Daemon, DaemonLock, LockBusy, letzter_lauf, merke_lauf
from jarvis.skills.base import Decision, Event, Result, Skill


class Doppel(Skill):
    """Eine Faehigkeit, die sich steuern laesst."""

    name = "mail"
    autonomy_level = 1
    requires_outbound = True

    def __init__(self, *, events=1, wirft: Exception | None = None, beim_handeln=None):
        self.events = events
        self.wirft = wirft
        self.beim_handeln = beim_handeln
        self.gehandelt: list[str] = []
        self.durchlaeufe = 0

    def poll(self):
        self.durchlaeufe += 1
        if self.wirft:
            raise self.wirft
        return [
            Event(skill=self.name, key=f"e{i}", summary=f"Sache {i}") for i in range(self.events)
        ]

    def decide(self, event):
        return Decision(
            skill=self.name,
            event_key=event.key,
            action="label",
            reason="Doppel",
            decided_by="rule",
            targets={"category": "rechnung"},
        )

    def act(self, decision):
        if self.beim_handeln:
            raise self.beim_handeln
        self.gehandelt.append(decision.event_key)
        return Result(skill=self.name, event_key=decision.event_key, performed=True)

    def verify_targets(self, decision):
        return decision


def daemon_config(
    home, *, dry_run: bool = True, level: int = 1, schedule=None, enabled: bool = True
) -> Config:
    return Config.from_mapping(
        {
            "dry_run": dry_run,
            "capabilities": {
                "mail": {
                    "autonomy_level": level,
                    "requires_outbound": True,
                    "rate_limits": {"hour": 100},
                }
            },
            "llm": {
                "isolation": "off",
                "providers": {
                    "trocken": {"kind": "static", "model": "s", "local": True, "reply": "{}"}
                },
                "tasks": {"classify": {"providers": ["trocken"]}},
            },
            "daemon": {
                "enabled": enabled,
                "tick_seconds": 5,
                "schedule": {"mail": 15} if schedule is None else schedule,
            },
        },
        paths=Paths(home=home),
    )


def baue_daemon(home, conn, *, doppel=None, **kw):
    """Ein Daemon, dessen Faehigkeit ein Doppel ist."""
    config = daemon_config(home, **kw)
    d = Daemon(config=config, paths=Paths(home=home), schlafen=lambda s: None, uhr=lambda: 1000.0)
    if doppel is not None:
        d._skill_doppel = doppel  # type: ignore[attr-defined]
        original = d.einen_durchlauf

        def mit_doppel(c, job, _orig=original, _d=doppel):
            import jarvis.daemon as modul

            echt = modul.build_skill
            modul.build_skill = lambda name, **kwargs: _d
            try:
                return _orig(c, job)
            finally:
                modul.build_skill = echt

        d.einen_durchlauf = mit_doppel  # type: ignore[method-assign]
    return d, config


# --------------------------------------------------------------------------- #
# Einzelinstanz
# --------------------------------------------------------------------------- #


def test_eine_zweite_instanz_wird_abgewiesen(home):
    erste = DaemonLock(home / "daemon.lock")
    erste.acquire()
    try:
        with pytest.raises(LockBusy, match="bereits ein Daemon"):
            DaemonLock(home / "daemon.lock").acquire()
    finally:
        erste.release()


def test_die_sperre_wird_beim_beenden_frei(home):
    with DaemonLock(home / "daemon.lock"):
        pass
    zweite = DaemonLock(home / "daemon.lock")
    zweite.acquire()
    zweite.release()


def test_die_sperre_nennt_die_pid(home):
    import os

    with DaemonLock(home / "daemon.lock"):
        assert f"pid {os.getpid()}" in (home / "daemon.lock").read_text(encoding="utf-8")


def test_eine_liegengebliebene_datei_blockiert_nicht(home):
    """Nach einem Absturz bleibt die Datei liegen -- die Sperre nicht."""
    (home / "daemon.lock").write_text("pid 999999 seit irgendwann\n", encoding="utf-8")
    sperre = DaemonLock(home / "daemon.lock")
    sperre.acquire()
    sperre.release()


# --------------------------------------------------------------------------- #
# Zeitplan
# --------------------------------------------------------------------------- #


def test_beim_ersten_mal_ist_alles_faellig(home, conn):
    d, _ = baue_daemon(home, conn)
    assert d.faellig(conn, 1000.0) == ["mail"]


def test_vor_ablauf_des_abstands_ist_nichts_faellig(home, conn):
    d, _ = baue_daemon(home, conn)
    merke_lauf(conn, "mail", 1000.0)
    assert d.faellig(conn, 1000.0 + 14 * 60) == []
    assert d.faellig(conn, 1000.0 + 15 * 60) == ["mail"]


def test_der_zeitplan_wird_in_fester_reihenfolge_abgearbeitet(home, conn):
    """Gleiche Reihenfolge bei jedem Tick -- sonst ist ein Fehler schwer zu finden."""
    config = Config.from_mapping(
        {
            "capabilities": {
                "mail": {"requires_outbound": False},
                "calendar": {"requires_outbound": False},
                "briefing": {"requires_outbound": False},
            },
            "llm": {"providers": {}, "tasks": {}},
            "daemon": {
                "enabled": True,
                "schedule": {"mail": 15, "briefing": 60, "calendar": 60},
            },
        },
        paths=Paths(home=home),
    )
    d = Daemon(config=config, paths=Paths(home=home))
    assert d.faellig(conn, 1000.0) == ["briefing", "calendar", "mail"]


def test_der_letzte_lauf_ueberlebt_einen_neustart(home, conn):
    """Sonst faengt nach jedem Neustart alles von vorne an."""
    merke_lauf(conn, "mail", 1234.0)
    assert letzter_lauf(conn, "mail") == 1234.0

    neu, _ = baue_daemon(home, conn)
    assert neu.faellig(conn, 1234.0 + 60) == []


def test_ein_unbrauchbarer_eintrag_gilt_als_nie_gelaufen(home, conn):
    with conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)", ("daemon.last_run.mail", "kaputt")
        )
    assert letzter_lauf(conn, "mail") is None


def test_auch_ein_fehlgeschlagener_lauf_zaehlt_als_lauf(home, conn):
    """Sonst rennt der Daemon bei jedem Tick gegen dieselbe Wand."""
    doppel = Doppel(wirft=RuntimeError("Anbieter weg"))
    d, _ = baue_daemon(home, conn, doppel=doppel)
    d.tick(conn)
    assert letzter_lauf(conn, "mail") is not None
    d.tick(conn)
    assert doppel.durchlaeufe == 1


# --------------------------------------------------------------------------- #
# Der Stoppschalter
# --------------------------------------------------------------------------- #


def test_bei_gesetztem_schalter_wird_gar_nicht_erst_angefangen(home, conn):
    doppel = Doppel()
    d, config = baue_daemon(home, conn, doppel=doppel, dry_run=False)
    config.stop_switch.engage("von Hand", actor="test")
    d.config = config

    lauf = d.einen_durchlauf(conn, "mail")
    assert lauf.uebersprungen == "Stoppschalter"
    assert doppel.durchlaeufe == 0
    assert doppel.gehandelt == []


def test_der_schalter_waehrend_eines_durchlaufs_verhindert_die_aktion(home, conn):
    """Er wird zwischen Beurteilung und Aktion gesetzt -- das Gatter faengt es."""
    config = daemon_config(home, dry_run=False, level=1)
    doppel = Doppel(events=2)

    class SchaltetUm(Doppel):
        def decide(self, event):
            config.stop_switch.engage("mitten im Lauf", actor="test")
            return super().decide(event)

    umschalter = SchaltetUm(events=2)
    d = Daemon(config=config, paths=Paths(home=home), schlafen=lambda s: None, uhr=lambda: 1000.0)

    import jarvis.daemon as modul

    echt = modul.build_skill
    modul.build_skill = lambda name, **kw: umschalter
    try:
        d.einen_durchlauf(conn, "mail")
    finally:
        modul.build_skill = echt

    assert umschalter.gehandelt == [], "trotz Stoppschalter gehandelt"
    assert doppel.gehandelt == []


def test_nach_dem_schalter_laeuft_der_daemon_weiter(home, conn):
    """Angehalten heisst nicht beendet -- sonst muesste man ihn neu starten."""
    doppel = Doppel()
    d, config = baue_daemon(home, conn, doppel=doppel)
    config.stop_switch.engage("kurz", actor="test")
    d.config = config
    d.run(max_ticks=2)
    assert d.haelt_an is False


# --------------------------------------------------------------------------- #
# Fehler beenden die Uhr nicht
# --------------------------------------------------------------------------- #


def test_ein_fehler_im_job_beendet_den_daemon_nicht(home, conn):
    doppel = Doppel(wirft=RuntimeError("kaputt"))
    d, _ = baue_daemon(home, conn, doppel=doppel)
    lauf = d.einen_durchlauf(conn, "mail")
    assert lauf.ok is False
    assert "kaputt" in (lauf.fehler or "")


def test_ein_fehler_beim_handeln_fuehrt_zu_keiner_aktion(home, conn):
    doppel = Doppel(beim_handeln=RuntimeError("Gmail weg"))
    d, _ = baue_daemon(home, conn, doppel=doppel, dry_run=False)
    d.einen_durchlauf(conn, "mail")
    assert doppel.gehandelt == []


def test_der_daemon_startet_nicht_wenn_er_aus_ist(home, conn):
    d, _ = baue_daemon(home, conn, enabled=False)
    assert d.run() == 2


def test_ohne_zeitplan_startet_er_nicht(home, conn):
    d, _ = baue_daemon(home, conn, schedule={})
    assert d.run() == 2


def test_ein_signal_beendet_die_schleife(home, conn):
    d, _ = baue_daemon(home, conn, doppel=Doppel())
    d.anhalten()
    assert d.haelt_an is True
    assert d.run() == 0


def test_der_start_und_das_ende_stehen_im_protokoll(home, conn):
    conn.close()
    d, _ = baue_daemon(home, None, doppel=Doppel())
    d.run(max_ticks=1)

    from jarvis.core.db import open_database

    frisch = open_database(home / "state.db")
    try:
        ergebnisse = [e.outcome for e in AuditLog(frisch).recent(20)]
    finally:
        frisch.close()
    assert "daemon_started" in ergebnisse
    assert "daemon_stopped" in ergebnisse


# --------------------------------------------------------------------------- #
# Fehlerfaelle im Dauerbetrieb
#
# Die Leitfrage bei jedem: darf dieser Fehler dazu fuehren, dass JARVIS etwas
# tut, was vorher blockiert war? Nein. Bei keinem.
# --------------------------------------------------------------------------- #


def lauf_mit(home, conn, doppel, **kw):
    d, config = baue_daemon(home, conn, doppel=doppel, **kw)
    return d.einen_durchlauf(conn, "mail"), config


def test_llm_nicht_erreichbar_schaltet_nichts_frei(home, conn):
    from jarvis.llm.provider import ProviderUnavailable

    doppel = Doppel(wirft=ProviderUnavailable("ollama: nicht erreichbar"))
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
    assert lauf.ok is False
    assert doppel.gehandelt == []


def test_llm_timeout_schaltet_nichts_frei(home, conn):
    from jarvis.llm.provider import ProviderTimeout

    doppel = Doppel(wirft=ProviderTimeout("zu langsam"))
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
    assert lauf.ok is False
    assert doppel.gehandelt == []


def test_google_nicht_erreichbar_schaltet_nichts_frei(home, conn):
    from jarvis.skills.mail.gmail import GmailError

    doppel = Doppel(wirft=GmailError("Gmail nicht erreichbar"))
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
    assert lauf.ok is False
    assert doppel.gehandelt == []


def test_abgelaufene_zugangsdaten_schalten_nichts_frei(home, conn):
    from jarvis.skills.mail.gmail import GmailAuthError

    doppel = Doppel(wirft=GmailAuthError("Token abgelaufen"))
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
    assert lauf.ok is False
    assert "GmailAuthError" in (lauf.fehler or "")
    assert doppel.gehandelt == []


def test_sqlite_kurz_weg_beendet_den_daemon_nicht(home, conn):
    doppel = Doppel(wirft=sqlite3.OperationalError("database is locked"))
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
    assert lauf.ok is False
    assert doppel.gehandelt == []


def test_eine_unerwartete_api_antwort_schaltet_nichts_frei(home, conn):
    """Kaputtes JSON, fehlende Felder, ein Wert vom falschen Typ."""
    for kaputt in (KeyError("items"), ValueError("kein JSON"), TypeError("None ist keine Liste")):
        doppel = Doppel(wirft=kaputt)
        lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
        assert lauf.ok is False
        assert doppel.gehandelt == []


def test_ein_leeres_ergebnis_ist_kein_fehler(home, conn):
    doppel = Doppel(events=0)
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False)
    assert lauf.ok is True
    assert lauf.polled == 0
    assert doppel.gehandelt == []


def test_ein_sehr_grosser_durchlauf_bleibt_in_der_ratenbegrenzung(home, conn):
    """Die Obergrenze gilt auch, wenn viel auf einmal kommt."""
    doppel = Doppel(events=500)
    config = daemon_config(home, dry_run=False, level=1)
    config = Config.from_mapping(
        {
            "dry_run": False,
            "capabilities": {
                "mail": {
                    "autonomy_level": 1,
                    "requires_outbound": True,
                    "rate_limits": {"hour": 10},
                }
            },
            "llm": {"providers": {}, "tasks": {}},
            "daemon": {"enabled": True, "schedule": {"mail": 15}},
        },
        paths=Paths(home=home),
    )
    d = Daemon(config=config, paths=Paths(home=home), uhr=lambda: 1000.0)

    import jarvis.daemon as modul

    echt = modul.build_skill
    modul.build_skill = lambda name, **kw: doppel
    try:
        lauf = d.einen_durchlauf(conn, "mail")
    finally:
        modul.build_skill = echt

    assert lauf.polled == 500
    assert len(doppel.gehandelt) <= 10, "Ratenbegrenzung nicht eingehalten"
    assert lauf.blocked > 0


def test_ein_trockenlauf_handelt_auch_im_daemon_nicht(home, conn):
    doppel = Doppel(events=3)
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=True)
    assert lauf.dry_run == 3
    assert lauf.acted == 0
    assert doppel.gehandelt == []


def test_stufe_null_handelt_auch_im_daemon_nicht(home, conn):
    doppel = Doppel(events=2)
    lauf, _ = lauf_mit(home, conn, doppel, dry_run=False, level=0)
    assert doppel.gehandelt == []
    assert lauf.acted == 0


def test_ein_neustart_handelt_nicht_zweimal(home, conn):
    """Briefing ist je Tag genau eines -- auch ueber einen Neustart hinweg."""
    from jarvis.skills.briefing.store import BriefingStore

    config = Config.from_mapping(
        {
            "dry_run": False,
            "timezone": "Europe/Berlin",
            "capabilities": {"briefing": {"requires_outbound": False}},
            "llm": {
                "isolation": "off",
                "providers": {
                    "trocken": {
                        "kind": "static",
                        "model": "s",
                        "local": True,
                        "reply": '{"text": "Ruhiger Tag."}',
                    }
                },
                "tasks": {"briefing": {"providers": ["trocken"]}},
            },
            "skills": {"briefing": {"task": "briefing"}},
            "daemon": {"enabled": True, "schedule": {"briefing": 60}},
        },
        paths=Paths(home=home),
    )

    erster = Daemon(config=config, paths=Paths(home=home), uhr=lambda: 1000.0)
    assert erster.einen_durchlauf(conn, "briefing").acted == 1

    # "Neustart": neue Instanz, dieselbe Datenbank, viel spaeter.
    zweiter = Daemon(config=config, paths=Paths(home=home), uhr=lambda: 99999.0)
    zweiter_lauf = zweiter.einen_durchlauf(conn, "briefing")
    assert zweiter_lauf.polled == 0
    assert zweiter_lauf.acted == 0
    assert len(BriefingStore(conn).recent(limit=10)) == 1


def test_der_daemon_ruft_kein_modell_wenn_es_nichts_zu_tun_gibt(home, conn):
    """Punkt 7: der Dauerbetrieb darf die Modellkosten nicht treiben."""
    from datetime import datetime

    from jarvis.skills.briefing.store import BriefingStore

    config = Config.from_mapping(
        {
            "dry_run": False,
            "timezone": "Europe/Berlin",
            "capabilities": {"briefing": {"requires_outbound": False}},
            "llm": {
                "isolation": "off",
                "providers": {
                    "trocken": {"kind": "static", "model": "s", "local": True, "reply": "{}"}
                },
                "tasks": {"briefing": {"providers": ["trocken"]}},
            },
            "skills": {"briefing": {"task": "briefing"}},
            "daemon": {"enabled": True, "schedule": {"briefing": 60}},
        },
        paths=Paths(home=home),
    )
    heute = datetime.now(config.timezone).date().isoformat()
    BriefingStore(conn).save(day=heute, text="steht schon")

    aufrufe: list[str] = []
    import jarvis.llm.router as router_modul

    echt = router_modul.Router.complete

    def zaehlen(self, task, request):  # pragma: no cover - darf nicht laufen
        aufrufe.append(task)
        return echt(self, task, request)

    router_modul.Router.complete = zaehlen
    try:
        d = Daemon(config=config, paths=Paths(home=home), uhr=lambda: 1000.0)
        lauf = d.einen_durchlauf(conn, "briefing")
    finally:
        router_modul.Router.complete = echt

    assert lauf.polled == 0
    assert aufrufe == [], "der Daemon hat ohne Anlass ein Modell gefragt"


def test_der_daemon_haelt_mitten_im_tick_an(home, conn):
    """Signal waehrend eines Ticks: der laufende Job endet, danach ist Schluss."""
    config = daemon_config(home, dry_run=False, schedule={"mail": 15})
    doppel = Doppel(events=1)
    d = Daemon(config=config, paths=Paths(home=home), uhr=lambda: 1000.0)

    class HaeltAn(Doppel):
        def poll(self_inner):
            d.anhalten()
            return super().poll()

    haelt = HaeltAn(events=1)
    import jarvis.daemon as modul

    echt = modul.build_skill
    modul.build_skill = lambda name, **kw: haelt
    try:
        laeufe = d.tick(conn)
    finally:
        modul.build_skill = echt

    assert len(laeufe) == 1
    assert d.haelt_an is True
    assert doppel.gehandelt == []


def test_der_daemon_ueberlebt_einen_fehler_im_tick_selbst(home, conn):
    d, _ = baue_daemon(home, conn)

    def kaputt(_conn):
        raise RuntimeError("Tick kaputt")

    d.tick = kaputt  # type: ignore[method-assign]
    assert d.run(max_ticks=2) == 0


def test_nebenlaeufige_sperrversuche_lassen_nur_einen_durch(home):
    """Zwei Daemons auf derselben Datenbank waeren zwei Uhren."""
    ergebnisse: list[str] = []
    sperre = threading.Lock()

    def versuchen():
        eigene = DaemonLock(home / "daemon.lock")
        try:
            eigene.acquire()
        except LockBusy:
            with sperre:
                ergebnisse.append("abgewiesen")
            return
        with sperre:
            ergebnisse.append("bekommen")

    erste = DaemonLock(home / "daemon.lock")
    erste.acquire()
    try:
        faeden = [threading.Thread(target=versuchen) for _ in range(3)]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join(timeout=10)
    finally:
        erste.release()

    assert ergebnisse.count("bekommen") == 0
    assert ergebnisse.count("abgewiesen") == 3
