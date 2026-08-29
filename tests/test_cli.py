"""Kommandozeile: init, status, stop, resume, log, verify."""

from __future__ import annotations

from jarvis.core.audit import AuditLog
from jarvis.core.config import StopSwitch
from jarvis.core.db import open_database
from jarvis.interfaces.cli import main


def run(home, *args, capsys):
    code = main(["--home", str(home), *args])
    return code, capsys.readouterr().out


def test_init_legt_alles_an(home, capsys):
    code, out = run(home, "init", capsys=capsys)
    assert code == 0
    assert (home / "config.toml").exists()
    assert (home / "state.db").exists()
    assert (home / "logs").is_dir()
    assert "Stufe 0" in out


def test_init_ist_wiederholbar(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "init", capsys=capsys)
    assert code == 0
    assert "vorhanden" in out


def test_status_zeigt_stufe_und_zaehler(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert code == 0
    assert "BETRIEB" in out
    assert "Schattenbetrieb" in out
    assert "hour 0/10" in out  # Zaehler der Faehigkeit mail
    assert "Kette intakt" in out
    assert "classify" in out and "->" in out


def test_status_legt_nichts_an(home, capsys):
    """Ein Lesebefehl darf keine Datenbank erzeugen."""
    code, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert code == 0
    assert not (home / "state.db").exists()
    assert "nicht angelegt" in out


def test_status_zeigt_den_stopp_ganz_oben(home, capsys):
    run(home, "init", capsys=capsys)
    run(home, "stop", "--grund", "Postfach unklar", capsys=capsys)
    _code, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert "ANGEHALTEN" in out
    assert "Postfach unklar" in out
    assert out.index("ANGEHALTEN") < out.index("FAEHIGKEIT")


def test_stop_erzeugt_die_datei(home, capsys):
    run(home, "init", capsys=capsys)
    code, _out = run(home, "stop", "--grund", "Test", capsys=capsys)
    assert code == 0
    assert (home / "STOP").exists()
    assert StopSwitch(home / "STOP").engaged()


def test_stop_funktioniert_ohne_datenbank(home, capsys):
    """Der Schalter darf nicht davon abhaengen, dass sonst etwas laeuft."""
    code, _out = run(home, "stop", "--grund", "Notfall", capsys=capsys)
    assert code == 0
    assert (home / "STOP").exists()


def test_stop_steht_im_protokoll(home, capsys):
    run(home, "init", capsys=capsys)
    run(home, "stop", "--grund", "Vorfall", capsys=capsys)
    conn = open_database(home / "state.db")
    try:
        outcomes = [e.outcome for e in AuditLog(conn).recent(10)]
    finally:
        conn.close()
    assert "stop_engaged" in outcomes


def test_resume_braucht_bestaetigung(home, capsys, monkeypatch):
    run(home, "init", capsys=capsys)
    run(home, "stop", capsys=capsys)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _: "n")
    code, _out = run(home, "resume", capsys=capsys)
    assert code == 1
    assert (home / "STOP").exists()


def test_resume_mit_ja(home, capsys):
    run(home, "init", capsys=capsys)
    run(home, "stop", capsys=capsys)
    code, out = run(home, "resume", "--ja", capsys=capsys)
    assert code == 0
    assert not (home / "STOP").exists()
    assert "Freigegeben" in out


def test_resume_ohne_stopp(home, capsys):
    code, out = run(home, "resume", "--ja", capsys=capsys)
    assert code == 0
    assert "nicht gesetzt" in out


def test_log_zeigt_eintraege(home, capsys):
    run(home, "init", capsys=capsys)
    run(home, "stop", "--grund", "Grund X", capsys=capsys)
    code, out = run(home, "log", capsys=capsys)
    assert code == 0
    assert "stop_engaged" in out
    assert "Trockenlauf" in out


def test_log_ohne_datenbank(home, capsys):
    code, out = run(home, "log", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_verify_ist_gruen(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "verify", capsys=capsys)
    assert code == 0
    assert "intakt" in out


def test_verify_meldet_eine_veraenderung(home, capsys):
    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET outcome = 'gefaelscht' WHERE id = 1")
    conn.close()

    code, out = run(home, "verify", capsys=capsys)
    assert code == 1
    assert "VERAENDERT" in out


def test_status_meldet_kaputte_kette(home, capsys):
    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET capability = 'x' WHERE id = 1")
    conn.close()

    code, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert code == 1
    assert "KETTE GEBROCHEN" in out


def test_fehlerhafte_konfiguration_wird_gemeldet(home, capsys):
    (home / "config.toml").write_text("[capabilities.mail]\nautonomie_level = 3\n", "utf-8")
    code = main(["--home", str(home), "status"])
    err = capsys.readouterr().err
    assert code == 2
    assert "Konfiguration fehlerhaft" in err


def test_keine_ausrufezeichen_und_keine_emojis(home, capsys):
    """Abschnitt 7: knapp und sachlich."""
    run(home, "init", capsys=capsys)
    run(home, "stop", "--grund", "Test", capsys=capsys)
    _, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    _, log = run(home, "log", capsys=capsys)
    for text in (out, log):
        assert "!" not in text
        assert all(ord(ch) < 0x2100 or ch in "->" for ch in text)
