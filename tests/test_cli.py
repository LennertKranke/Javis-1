"""Kommandozeile: init, status, stop, resume, log, verify."""

from __future__ import annotations

from zoneinfo import ZoneInfo

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
    assert "hour 0/120" in out  # Zaehler der Faehigkeit mail
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


# --------------------------------------------------------------------------- #
# Mail
# --------------------------------------------------------------------------- #


def test_mail_state_auf_leerer_datenbank(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "mail", "state", capsys=capsys)
    assert code == 0
    assert "Erfasst" in out
    assert "Beschriftet" in out
    assert "Zustaende" in out


def test_mail_state_zeigt_beurteiltes(home, capsys):
    from jarvis.skills.mail.store import MailStore

    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    store = MailStore(conn)
    store.remember(message_id="abc123", category="rechnung", decided_by="model", labelled=True)
    store.remember(message_id="def456", category="newsletter", decided_by="prefilter")
    conn.close()

    code, out = run(home, "mail", "state", capsys=capsys)
    assert code == 0
    assert "rechnung" in out and "newsletter" in out
    assert "prefilter" in out


def test_mail_poll_ohne_datenbank(home, capsys):
    code, out = run(home, "mail", "poll", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_mail_poll_ohne_anmeldung(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "mail", "poll", capsys=capsys)
    assert code == 1
    assert "jarvis mail login" in out


def test_mail_login_ohne_schreibbaren_speicher(home, capsys):
    """Auf diesem System gibt es keine Keychain -- das muss klar gesagt werden."""
    run(home, "init", capsys=capsys)
    code, out = run(home, "mail", "login", capsys=capsys)
    assert code == 1
    assert "Keychain" in out


def test_fehlerhafte_mail_einstellungen_werden_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace(
            'query = "is:unread in:inbox"', 'quary = "is:unread in:inbox"'
        ),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "mail", "poll"])
    err = capsys.readouterr().err
    assert code == 2
    assert "Konfiguration fehlerhaft" in err
    assert "quary" in err


# --------------------------------------------------------------------------- #
# Antworten (Phase 3)
# --------------------------------------------------------------------------- #


def test_mail_style_ohne_profil(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "mail", "style", capsys=capsys)
    assert code == 0
    assert "Kein Stilprofil" in out
    assert "kein Nachrichtentext" in out


def test_mail_style_zeigt_gespeichertes(home, capsys):
    from jarvis.skills.mail.style import StyleStore, extract_profile

    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    StyleStore(conn).save(extract_profile(["Hallo,\n\nja passt, bis Montag.\n\nViele Gruesse\nL"]))
    conn.close()

    code, out = run(home, "mail", "style", capsys=capsys)
    assert code == 0
    assert "Hallo" in out
    assert "Viele Gruesse" in out


def test_mail_allowlist_zeigt_schwelle_und_eintraege(home, capsys):
    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    conn.execute(
        "INSERT INTO mail_allowlist (address, sent_count, source) VALUES ('anna@x.de', 5, 'sent')"
    )
    conn.execute(
        "INSERT INTO mail_allowlist (address, sent_count, source) VALUES ('tom@x.de', 1, 'sent')"
    )
    conn.close()

    code, out = run(home, "mail", "allowlist", capsys=capsys)
    assert code == 0
    assert "Schwelle" in out
    assert "anna@x.de" in out and "tom@x.de" in out


def test_mail_compare_ohne_entwuerfe(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "mail", "compare", capsys=capsys)
    assert code == 0
    assert "Keine Entwuerfe" in out


def test_mail_draft_ohne_offene_nachricht(home, capsys):
    """Nichts zu tun heisst nichts zu tun -- nicht einmal eine Gmail-Anfrage."""
    run(home, "init", capsys=capsys)
    code, out = run(home, "mail", "draft", capsys=capsys)
    assert code == 0
    assert "Gefunden" in out


def test_mail_draft_ohne_anmeldung(home, capsys):
    from jarvis.skills.mail.store import MailStore

    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    MailStore(conn).remember(message_id="a", category="anfrage", needs_reply=True, state="analysed")
    conn.close()

    code, out = run(home, "mail", "draft", capsys=capsys)
    assert code == 1
    assert "jarvis mail login" in out


def test_mail_send_zeigt_die_stufe(home, capsys):
    """Der Befehl sagt vor allem anderen, ob er ueberhaupt senden darf."""
    run(home, "init", capsys=capsys)
    _code, out = run(home, "mail", "send", capsys=capsys)
    assert "Stufe" in out
    assert "Senderecht" in out
    assert "nein" in out


def test_fehlerhafte_antworteinstellungen_werden_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace(
            'categories = ["anfrage", "termin"]', 'kategorien = ["anfrage"]'
        ),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "mail", "draft"])
    err = capsys.readouterr().err
    assert code == 2
    assert "kategorien" in err


# --------------------------------------------------------------------------- #
# Dashboard (Phase 4)
# --------------------------------------------------------------------------- #


def test_web_ohne_datenbank(home, capsys):
    code, out = run(home, "web", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_web_zeigt_adresse_und_token(home, capsys, monkeypatch):
    """Ohne die vollstaendige Adresse kommt niemand hinein."""
    run(home, "init", capsys=capsys)
    gestartet = {}

    def fake_run(app, **kwargs):
        gestartet.update(kwargs)

    monkeypatch.setattr("uvicorn.run", fake_run)
    code, out = run(home, "web", "--port", "9123", capsys=capsys)

    assert code == 0
    assert "http://127.0.0.1:9123/?token=" in out
    assert "web-token" in out
    assert gestartet["port"] == 9123
    assert gestartet["host"] == "127.0.0.1"


def test_web_meldet_dass_freigaben_im_trockenlauf_nichts_bewirken(home, capsys, monkeypatch):
    run(home, "init", capsys=capsys)
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: None)
    _code, out = run(home, "web", capsys=capsys)
    assert "wirken nur ohne Trockenlauf" in out


def test_web_host_ausserhalb_von_localhost_wird_abgelehnt(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('host = "127.0.0.1"', 'host = "0.0.0.0"'),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "web"])
    err = capsys.readouterr().err
    assert code == 2
    assert "web.host" in err


def test_web_host_schalter_umgeht_die_loopback_sperre_nicht(home, capsys):
    """Sonst waere die Sperre ueber einen Schalter zu umgehen."""
    run(home, "init", capsys=capsys)
    code = main(["--home", str(home), "web", "--host", "0.0.0.0"])
    err = capsys.readouterr().err
    assert code == 2
    assert "web.host" in err
    assert "ausschliesslich lokal" in err


def test_web_port_schalter_wird_geprueft(home, capsys):
    run(home, "init", capsys=capsys)
    code = main(["--home", str(home), "web", "--port", "80"])
    assert code == 2
    assert "web.port" in capsys.readouterr().err


def test_web_erlaubt_die_anderen_loopback_schreibweisen(home, capsys, monkeypatch):
    run(home, "init", capsys=capsys)
    gestartet = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: gestartet.update(kwargs))
    code, out = run(home, "web", "--host", "localhost", capsys=capsys)
    assert code == 0
    assert "http://localhost:8765/?token=" in out
    assert gestartet["host"] == "localhost"


# --------------------------------------------------------------------------- #
# Kalender und Briefing
# --------------------------------------------------------------------------- #


def test_calendar_state_auf_leerer_datenbank(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "calendar", "state", capsys=capsys)
    assert code == 0
    assert "Erfasst" in out
    assert "jarvis calendar poll" in out


def test_calendar_state_zeigt_termine_und_befunde(home, capsys):
    from datetime import UTC, datetime, timedelta

    from jarvis.skills.calendar.store import CalendarStore

    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    beginn = datetime.now(UTC) + timedelta(hours=2)
    CalendarStore(conn).remember(
        event_id="e1",
        calendar_id="primary",
        starts_at=beginn.isoformat(),
        ends_at=(beginn + timedelta(hours=1)).isoformat(),
        summary="Zahnarzt",
        finding="Zahnarzt ueberschneidet sich mit Standup",
    )
    conn.close()

    code, out = run(home, "calendar", "state", capsys=capsys)
    assert code == 0
    assert "Zahnarzt" in out
    assert "ueberschneidet sich" in out


def test_calendar_poll_ohne_datenbank(home, capsys):
    code, out = run(home, "calendar", "poll", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_calendar_poll_ohne_kalenderrecht(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "calendar", "poll", capsys=capsys)
    assert code == 1
    assert "jarvis mail login" in out


def test_briefing_ohne_datenbank(home, capsys):
    code, out = run(home, "briefing", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_briefing_ohne_eintrag_sagt_wie_es_geht(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "briefing", capsys=capsys)
    assert code == 1
    assert "jarvis briefing --neu" in out


def test_briefing_zeigt_den_abgelegten_text(home, capsys):
    from datetime import UTC, datetime

    from jarvis.skills.briefing.store import BriefingStore

    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    BriefingStore(conn).save(
        day=datetime.now(UTC).date().isoformat(), text="Heute nur der Zahnarzt."
    )
    conn.close()

    code, out = run(home, "briefing", capsys=capsys)
    assert code == 0
    assert "Heute nur der Zahnarzt." in out
    assert "ohne Modell" in out


def test_fehlerhafte_kalendereinstellungen_werden_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace("window_days = 7", "window_days = 900"),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "calendar", "poll"])
    assert code == 2
    assert "skills.calendar.window_days" in capsys.readouterr().err


def test_status_nennt_die_abweichung_beim_geheimnisspeicher(home, capsys, monkeypatch):
    """Eine Ausnahme, die nirgends auftaucht, wird zur Regel."""
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    run(home, "init", capsys=capsys)
    _, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert "environment" in out
    assert "Umgebungsvariablen" in out


def test_status_meldet_den_verstoss_laut_und_mit_fehlercode(home, capsys, monkeypatch):
    """Auf macOS ist die Umgebung ein Verstoss, nicht bloss ein Hinweis."""
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "darwin")
    run(home, "init", capsys=capsys)
    code, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert code == 1
    assert "UNSICHER" in out
    assert "Keychain" in out


def test_status_bleibt_ruhig_wenn_nur_die_keychain_gilt(home, capsys, monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "keychain")
    run(home, "init", capsys=capsys)
    code, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert code == 0
    assert "UNSICHER" not in out


def test_status_schweigt_wenn_nur_die_keychain_gilt(home, capsys, monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "keychain")
    run(home, "init", capsys=capsys)
    _, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert "Abschnitt 4" not in out


def test_calendar_state_zeigt_ortszeit(home, capsys):
    """Gespeichert wird UTC, angezeigt gehoert die Zeit auf der Wanduhr."""
    from datetime import UTC, datetime, timedelta

    from jarvis.skills.calendar.store import CalendarStore

    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('timezone = ""', 'timezone = "Europe/Berlin"'),
        encoding="utf-8",
    )
    beginn = (datetime.now(UTC) + timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    conn = open_database(home / "state.db")
    CalendarStore(conn).remember(
        event_id="e1",
        calendar_id="primary",
        starts_at=beginn.isoformat(),
        ends_at=(beginn + timedelta(hours=1)).isoformat(),
        summary="Zahnarzt",
    )
    conn.close()

    code, out = run(home, "calendar", "state", capsys=capsys)
    assert code == 0
    erwartet = beginn.astimezone(ZoneInfo("Europe/Berlin")).strftime("%d.%m. %H:%M")
    assert erwartet in out, f"erwartet {erwartet!r} in der Ausgabe"


def test_fehlerhafte_zeitzone_wird_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('timezone = ""', 'timezone = "Europa/Berlin"'),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "status", "--ohne-anbieter"])
    assert code == 2
    assert "timezone" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Sprache
# --------------------------------------------------------------------------- #


def test_voice_check_sagt_was_fehlt(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "check", capsys=capsys)
    assert code == 0
    assert "Weckwort" in out
    assert "Whisper" in out
    # Auf diesem System gibt es weder whisper-cli noch say.
    assert "nein" in out
    assert "Dashboard" in out


def test_voice_ask_ohne_datenbank(home, capsys):
    code, out = run(home, "voice", "ask", "Jarvis, status", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_voice_ask_antwortet_auf_den_status(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "ask", "Jarvis,", "wie", "ist", "der", "Stand", capsys=capsys)
    assert code == 0
    assert "status" in out
    assert "Betrieb" in out


def test_voice_ask_verweigert_das_senden(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "ask", "Jarvis,", "schick", "das", "ab", capsys=capsys)
    assert code == 0
    assert "handeln" in out
    assert "Dashboard" in out


def test_voice_ask_ohne_weckwort_antwortet_nicht(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "ask", "wie", "ist", "der", "Stand", capsys=capsys)
    assert code == 0
    assert "Ohne Weckwort" in out


def test_voice_haelt_ueber_die_kommandozeile_an(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "ask", "Jarvis,", "halt", "an", capsys=capsys)
    assert code == 0
    assert (home / "STOP").exists()
    assert "jarvis resume" in out


def test_voice_hear_ohne_datei(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "hear", str(home / "gibtsnicht.wav"), capsys=capsys)
    assert code == 1
    assert "Keine Aufnahme" in out


def test_voice_listen_ohne_aufnahmebefehl(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "voice", "listen", capsys=capsys)
    assert code == 1
    assert "record_command" in out


def test_fehlerhafte_spracheinstellungen_werden_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('wake_word = "jarvis"', "wake_word = 7"),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "voice", "check"])
    assert code == 2
    assert "voice.wake_word" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Externe Dienste
# --------------------------------------------------------------------------- #


def mock_modus(home):
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('mode = "live"', 'mode = "mock"'),
        encoding="utf-8",
    )


def test_services_check_ohne_datenbank(home, capsys):
    code, out = run(home, "services", "check", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_services_check_zeigt_alle_vier_stufen(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "services", "check", capsys=capsys)
    assert code == 0
    for spalte in ("DIENST", "GEBAUT", "GETESTET", "MOCK", "ECHT GEPRUEFT"):
        assert spalte in out
    for name in ("anthropic", "ollama", "gmail", "calendar", "keychain"):
        assert name in out


def dienstzeilen(ausgabe: str) -> dict[str, str]:
    """Nur die Tabellenzeilen, nach Dienstnamen. Fussnoten zaehlen nicht mit."""
    zeilen = {}
    for roh in ausgabe.splitlines():
        teile = roh.split()
        if len(teile) >= 5 and teile[0] in {
            "anthropic",
            "ollama",
            "gmail",
            "calendar",
            "keychain",
        }:
            zeilen[teile[0]] = roh
    return zeilen


def test_services_check_sagt_nie_wenn_nichts_echt_lief(home, capsys):
    """Der wichtigste Satz der Tabelle: nichts hat je einen echten Dienst erreicht."""
    run(home, "init", capsys=capsys)
    _, out = run(home, "services", "check", capsys=capsys)
    zeilen = dienstzeilen(out)
    assert len(zeilen) == 5
    for name, zeile in zeilen.items():
        assert " nie " in zeile, f"{name}: erwartet 'nie', gefunden {zeile!r}"


def test_services_check_zeigt_einen_festgehaltenen_kontakt(home, capsys):
    from jarvis.core.integrations import merke_kontakt

    run(home, "init", capsys=capsys)
    conn = open_database(home / "state.db")
    merke_kontakt(conn, "gmail", detail="Anmeldung als ich@example.com")
    conn.close()

    _, out = run(home, "services", "check", capsys=capsys)
    zeilen = dienstzeilen(out)
    assert " nie " not in zeilen["gmail"], "der festgehaltene Kontakt fehlt"
    assert "2" in zeilen["gmail"], "kein Zeitpunkt in der Zeile"
    for name in ("anthropic", "ollama", "calendar", "keychain"):
        assert " nie " in zeilen[name]


def test_services_check_meldet_den_mock_modus(home, capsys):
    run(home, "init", capsys=capsys)
    mock_modus(home)
    _, out = run(home, "services", "check", capsys=capsys)
    assert "MOCK" in out
    assert "Nichts geht hinaus" in out


def test_ein_live_versuch_im_mock_zaehlt_nicht_als_nachweis(home, capsys):
    run(home, "init", capsys=capsys)
    mock_modus(home)
    _, out = run(home, "services", "check", "--live", capsys=capsys)
    assert "zaehlt nicht als Nachweis" in out

    conn = open_database(home / "state.db")
    try:
        from jarvis.core.integrations import letzter_kontakt

        assert letzter_kontakt(conn, "gmail") is None
    finally:
        conn.close()


def test_ein_live_versuch_ohne_zugangsdaten_endet_mit_fehlercode(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "services", "check", "--live", capsys=capsys)
    assert code == 1
    for zeile in dienstzeilen(out).values():
        assert " nie " in zeile, "ein gescheiterter Versuch wurde als Nachweis gewertet"


def test_status_meldet_den_mock_modus(home, capsys):
    run(home, "init", capsys=capsys)
    mock_modus(home)
    _, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert "MOCK" in out


def test_status_schweigt_im_live_modus(home, capsys):
    run(home, "init", capsys=capsys)
    _, out = run(home, "status", "--ohne-anbieter", capsys=capsys)
    assert "MOCK" not in out


def test_mail_poll_laeuft_im_mock_ohne_anmeldung(home, capsys):
    run(home, "init", capsys=capsys)
    mock_modus(home)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8")
        .replace(
            'providers = ["ollama", "anthropic"]\neffort = "low"',
            'providers = ["trocken", "ollama"]\neffort = "low"',
        )
        .replace(
            'reply = "{}"',
            'reply = \'{"kategorie": "rechnung", "dringlichkeit": 1, '
            '"antwort_noetig": false, "begruendung": "Beispiel"}\'',
        ),
        encoding="utf-8",
    )
    code, out = run(home, "mail", "poll", capsys=capsys)
    assert code == 0
    assert "Gefunden" in out
    assert "5" in out


def test_mail_login_im_mock_meldet_dass_es_nichts_gibt(home, capsys):
    run(home, "init", capsys=capsys)
    mock_modus(home)
    code, out = run(home, "mail", "login", capsys=capsys)
    assert code == 1
    assert "Mock-Modus" in out


def test_fehlerhafte_dienstkonfiguration_wird_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('mode = "live"', 'mode = "halb"'),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "services", "check"])
    assert code == 2
    assert "services.mode" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Recherche
# --------------------------------------------------------------------------- #


def research_bereit(home):
    """Statischer Anbieter fuer classify, damit kein Netz noetig ist."""
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8")
        .replace(
            'providers = ["ollama", "anthropic"]\neffort = "low"',
            'providers = ["trocken", "ollama"]\neffort = "low"',
        )
        .replace(
            'reply = "{}"',
            'reply = \'{"begriffe": ["rechnung", "aufbewahrung"], "kategorie": "recht"}\'',
        )
        .replace("dry_run = true", "dry_run = false")
        .replace(
            "[capabilities.research]\nautonomy_level = 0",
            "[capabilities.research]\nautonomy_level = 1",
        ),
        encoding="utf-8",
    )


def test_research_ask_ohne_datenbank(home, capsys):
    code, out = run(home, "research", "ask", "Testfrage", capsys=capsys)
    assert code == 1
    assert "jarvis init" in out


def test_research_ask_stellt_eine_frage_ein(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "research", "ask", "Wie", "lange", "aufbewahren", capsys=capsys)
    assert code == 0
    assert "Wie lange aufbewahren" in out
    assert "jarvis research poll" in out


def test_research_list_zeigt_offene_fragen_und_quellen(home, capsys):
    run(home, "init", capsys=capsys)
    run(home, "research", "ask", "Erste", "Frage", capsys=capsys)
    code, out = run(home, "research", "list", capsys=capsys)
    assert code == 0
    assert "Erste Frage" in out
    assert "beispiel" in out
    assert "kein Netz" in out


def test_research_poll_findet_etwas(home, capsys):
    run(home, "init", capsys=capsys)
    research_bereit(home)
    run(home, "research", "ask", "Wie", "lange", "Rechnungen", "aufbewahren", capsys=capsys)
    code, out = run(home, "research", "poll", capsys=capsys)
    assert code == 0
    assert "Gefunden" in out

    code, out = run(home, "research", "list", "1", capsys=capsys)
    assert code == 0
    assert "Aufbewahrungsfristen" in out
    assert "beispiel://" in out


def test_research_poll_bleibt_im_trockenlauf_wirkungslos(home, capsys):
    run(home, "init", capsys=capsys)
    research_bereit(home)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace("dry_run = false", "dry_run = true"),
        encoding="utf-8",
    )
    run(home, "research", "ask", "Wie", "lange", "aufbewahren", capsys=capsys)
    run(home, "research", "poll", capsys=capsys)
    _, out = run(home, "research", "list", "1", capsys=capsys)
    assert "Noch nichts gefunden" in out


def test_research_list_meldet_eine_unbekannte_nummer(home, capsys):
    run(home, "init", capsys=capsys)
    code, out = run(home, "research", "list", "999", capsys=capsys)
    assert code == 1
    assert "Keine Frage" in out


def test_fehlerhafte_recherche_einstellungen_werden_gemeldet(home, capsys):
    run(home, "init", capsys=capsys)
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace('sources = ["beispiel"]', "sources = 5"),
        encoding="utf-8",
    )
    code = main(["--home", str(home), "research", "poll"])
    assert code == 2
    assert "skills.research.sources" in capsys.readouterr().err


# --- Ganztaegige Termine ---------------------------------------------------- #


def test_ganztaegiger_termin_zeigt_keine_uhrzeit():
    """ "00:00" sieht aus wie eine Angabe und ist keine."""
    from zoneinfo import ZoneInfo

    from jarvis.interfaces.cli import _ortszeit

    gespeichert = "2026-03-02T00:00:00+00:00"
    assert _ortszeit(gespeichert, ZoneInfo("Europe/Berlin"), ganztags=True) == "02.03. ganztags"


def test_ganztaegiger_termin_rutscht_nicht_auf_den_vortag():
    """Der eigentliche Fehler hinter dem kosmetischen.

    Ganztaegige Termine liegen als UTC-Mitternacht ihres Kalendertages in der
    Datenbank -- sie sind ein Datum, kein Zeitpunkt. Wer sie nach New York
    umrechnet, landet am Vorabend und zeigt den falschen Tag an.
    """
    from zoneinfo import ZoneInfo

    from jarvis.interfaces.cli import _ortszeit

    gespeichert = "2026-03-02T00:00:00+00:00"
    for zone in ("America/New_York", "Pacific/Honolulu", "Asia/Tokyo"):
        assert _ortszeit(gespeichert, ZoneInfo(zone), ganztags=True) == "02.03. ganztags"


def test_termine_mit_uhrzeit_werden_weiterhin_umgerechnet():
    """Die Gegenprobe: fuer echte Zeitpunkte gilt die Ortszeit unveraendert."""
    from zoneinfo import ZoneInfo

    from jarvis.interfaces.cli import _ortszeit

    gespeichert = "2026-03-02T09:00:00+00:00"
    assert _ortszeit(gespeichert, ZoneInfo("Europe/Berlin")) == "02.03. 10:00"
    assert _ortszeit(gespeichert, ZoneInfo("America/New_York")) == "02.03. 04:00"


# --------------------------------------------------------------------------- #
# Gedaechtnis
#
# Der Weg "ablegen, dann auflisten" war nie ausgefuehrt worden: `cmd_memory`
# rief `Out.table` mit einem Parameter auf, den diese Methode in keiner Fassung
# je hatte. Sichtbar wurde das erst mit mindestens einer abgelegten Tatsache --
# ohne Eintrag greift der leere Zweig und die fehlerhafte Zeile bleibt kalt.
# Deshalb pruefen die folgenden Tests genau diesen Uebergang.
# --------------------------------------------------------------------------- #


def test_memory_listet_eine_abgelegte_tatsache_auf(home, capsys):
    """Der Regressionsfall: ablegen, dann auflisten.

    Deckt den ganzen Weg ab -- die Tatsache wird ueber den vorgesehenen
    Memory-Befehl abgelegt, der Vorgang endet erfolgreich, und sie ist danach
    in der Auflistung wiederzufinden.
    """
    run(home, "init", capsys=capsys)

    code, out = run(home, "memory", "buero", "Muenchen,", "3.", "Stock", capsys=capsys)
    assert code == 0
    assert "Gemerkt: buero = Muenchen, 3. Stock" in out

    code, out = run(home, "memory", capsys=capsys)
    assert code == 0
    assert "Tatsachen" in out
    assert "SCHLUESSEL" in out and "GEWICHT" in out
    assert "buero" in out
    assert "Muenchen, 3. Stock" in out
    assert "Nichts abgelegt." not in out


def test_memory_bleibt_auf_leerer_ablage_lauffaehig(home, capsys):
    """Die Gegenprobe: ohne Eintrag darf keine Tabelle entstehen.

    Genau dieser Zweig lief immer -- er hat den Fehler im anderen verdeckt.
    """
    run(home, "init", capsys=capsys)
    code, out = run(home, "memory", capsys=capsys)
    assert code == 0
    assert "Nichts abgelegt." in out
    assert "SCHLUESSEL" not in out


def test_memory_zeigt_gewicht_und_kategorie(home, capsys):
    """Alle vier Spalten der Tabelle werden tatsaechlich gefuellt."""
    run(home, "init", capsys=capsys)
    run(
        home,
        "memory",
        "chef",
        "Frau",
        "Meier",
        "--kategorie",
        "person",
        "--gewicht",
        "2.5",
        capsys=capsys,
    )
    code, out = run(home, "memory", capsys=capsys)
    assert code == 0
    assert "chef" in out
    assert "person" in out
    assert "2.5" in out


def test_memory_filtert_nach_kategorie(home, capsys):
    """Der Filterweg fuehrt in dieselbe Tabelle und muss ebenso laufen."""
    run(home, "init", capsys=capsys)
    run(home, "memory", "chef", "Frau", "Meier", "--kategorie", "person", capsys=capsys)
    run(home, "memory", "kaffee", "schwarz", "--kategorie", "praeferenz", capsys=capsys)

    code, out = run(home, "memory", "--kategorie-filter", "person", capsys=capsys)
    assert code == 0
    assert "chef" in out
    assert "kaffee" not in out


def test_memory_laesst_die_hashkette_intakt(home, capsys):
    """Das Gedaechtnis ist Zustand, keine Aussenwirkung.

    Es gehoert deshalb nicht ins Protokoll -- aber es darf die Kette der
    bereits vorhandenen Eintraege auch nicht beschaedigen. Beides wird hier
    gemessen, damit der Fix an der Anzeige nicht unbemerkt am Protokoll ruettelt.
    """
    run(home, "init", capsys=capsys)
    run(home, "memory", "buero", "Muenchen", capsys=capsys)
    run(home, "memory", capsys=capsys)

    code, out = run(home, "verify", capsys=capsys)
    assert code == 0
    assert "intakt" in out

    conn = open_database(home / "state.db")
    try:
        pruefung = AuditLog(conn).verify()
        assert pruefung.ok
        offen = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE capability LIKE '%memory%'"
        ).fetchone()[0]
        assert offen == 0, "Das Gedaechtnis schreibt bewusst keine Protokolleintraege"
    finally:
        conn.close()


def test_memory_vergessen_entfernt_die_tatsache(home, capsys):
    """Der dritte Zweig desselben Befehls, damit er nicht ungeprueft bleibt."""
    run(home, "init", capsys=capsys)
    run(home, "memory", "buero", "Muenchen", capsys=capsys)

    code, out = run(home, "memory", "--vergessen", "buero", capsys=capsys)
    assert code == 0
    assert "Vergessen." in out

    _code, out = run(home, "memory", capsys=capsys)
    assert "buero" not in out
    assert "Nichts abgelegt." in out
