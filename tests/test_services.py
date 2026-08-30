"""Externe Dienste: Laufzeit-Mock und der Nachweis, was je echt lief.

Der Kern dieser Datei ist eine einzige Unterscheidung: ein Mock darf nie als
Beleg dafuer gelten, dass der echte Dienst erreichbar ist. Alles andere hier
haengt daran.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.core.config import Config, ConfigError, Paths
from jarvis.core.integrations import (
    DIENSTE,
    dienst,
    letzter_kontakt,
    merke_kontakt,
)
from jarvis.skills.calendar.google import CALENDAR_READ, CalendarClient
from jarvis.skills.calendar.mock import MockCalendarClient, beispiel_kalender
from jarvis.skills.factory import calendar_client, gmail_client
from jarvis.skills.mail.gmail import DRAFTING, LABELLING, SENDING, GmailClient, GmailError
from jarvis.skills.mail.mock import MockGmailClient, beispiel_postfach


def services_config(home, *, mode: str = "mock", fixtures: str = "") -> Config:
    return Config.from_mapping(
        {
            "services": {"mode": mode, "fixtures": fixtures},
            "capabilities": {"mail": {"requires_outbound": False}},
            "llm": {
                "providers": {
                    "trocken": {"kind": "static", "model": "s", "local": True, "reply": "{}"}
                },
                "tasks": {"classify": {"providers": ["trocken"]}},
            },
            "skills": {"mail": {"task": "classify"}},
        },
        paths=Paths(home=home),
    )


# --------------------------------------------------------------------------- #
# Der Nachweis
# --------------------------------------------------------------------------- #


def test_ohne_kontakt_gibt_es_keinen_eintrag(conn):
    assert letzter_kontakt(conn, "gmail") is None


def test_ein_kontakt_wird_mit_zeitpunkt_festgehalten(conn):
    eintrag = merke_kontakt(conn, "gmail", detail="Anmeldung als ich@example.com")
    gelesen = letzter_kontakt(conn, "gmail")
    assert gelesen is not None
    assert gelesen.wann == eintrag.wann
    assert "ich@example.com" in gelesen.detail


def test_ein_neuer_kontakt_ersetzt_den_alten(conn):
    merke_kontakt(conn, "gmail", detail="erster")
    merke_kontakt(conn, "gmail", detail="zweiter")
    gelesen = letzter_kontakt(conn, "gmail")
    assert gelesen is not None
    assert gelesen.detail == "zweiter"


def test_dienste_sind_voneinander_unabhaengig(conn):
    merke_kontakt(conn, "gmail", detail="a")
    assert letzter_kontakt(conn, "calendar") is None


def test_ein_unbrauchbarer_eintrag_gilt_als_kein_kontakt(conn):
    with conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?)",
            ("integration.last_live.gmail", ""),
        )
    assert letzter_kontakt(conn, "gmail") is None


def test_das_detail_wird_gekuerzt(conn):
    from jarvis.core.integrations import MAX_DETAIL

    eintrag = merke_kontakt(conn, "gmail", detail="x" * 500)
    assert len(eintrag.detail) <= MAX_DETAIL


def test_jeder_dienst_im_verzeichnis_ist_auffindbar():
    for eintrag in DIENSTE:
        assert dienst(eintrag.name) is eintrag
    assert dienst("gibtsnicht") is None


def test_das_verzeichnis_nennt_zu_jedem_dienst_ein_modul():
    import importlib

    for eintrag in DIENSTE:
        importlib.import_module(eintrag.modul)


def test_kein_dienst_behauptet_einen_echten_kontakt_von_sich_aus(conn):
    """Die vierte Stufe kommt aus der Datenbank, nicht aus einer Angabe."""
    for eintrag in DIENSTE:
        assert letzter_kontakt(conn, eintrag.name) is None


# --------------------------------------------------------------------------- #
# Der Mock schreibt nie einen Nachweis
# --------------------------------------------------------------------------- #


def test_die_mocks_kennen_merke_kontakt_gar_nicht():
    """Struktur statt Vertrauen: der Aufruf steht dort nicht im Quelltext."""
    from jarvis.skills.calendar import mock as kalender_mock
    from jarvis.skills.mail import mock as mail_mock

    for modul in (mail_mock, kalender_mock):
        quelle = Path(modul.__file__).read_text(encoding="utf-8")
        assert "merke_kontakt" not in quelle.replace("`merke_kontakt`", "")


def test_ein_mock_durchlauf_hinterlaesst_keinen_nachweis(home, conn):
    config = services_config(home, mode="mock")
    client = gmail_client(config, LABELLING)
    assert client.address() == "ich@example.com"
    assert len(client.list_message_ids("is:unread", 25)) == 5
    assert letzter_kontakt(conn, "gmail") is None


# --------------------------------------------------------------------------- #
# Die Fabrik waehlt nach [services]
# --------------------------------------------------------------------------- #


def test_im_mock_modus_kommt_das_doppel(home):
    config = services_config(home, mode="mock")
    assert isinstance(gmail_client(config, LABELLING), MockGmailClient)
    assert isinstance(calendar_client(config), MockCalendarClient)


def test_im_live_modus_kommt_der_echte_client(home):
    config = services_config(home, mode="live")
    assert isinstance(gmail_client(config, LABELLING), GmailClient)
    assert isinstance(calendar_client(config), CalendarClient)


def test_live_ist_die_vorgabe(home):
    assert Config.load(home=home).services.mode == "live"
    assert Config.load(home=home).services.is_mock is False


def test_ein_unbekannter_modus_faellt_beim_laden_auf(home):
    with pytest.raises(ConfigError, match=r"services\.mode"):
        services_config(home, mode="halb")


# --------------------------------------------------------------------------- #
# Der Mock ist nicht nachsichtiger als der echte Client
# --------------------------------------------------------------------------- #


def test_ohne_senderecht_sendet_auch_der_mock_nicht():
    """Sonst saehe ein Trockenlauf im Mock besser aus als die Wirklichkeit."""
    client = MockGmailClient(DRAFTING)
    entwurf = client.create_draft("From: a\r\nTo: b\r\n\r\nText")
    with pytest.raises(GmailError, match="send"):
        client.send_draft(entwurf["id"])


def test_ohne_labelrecht_beschriftet_der_mock_nicht():
    from jarvis.skills.mail.gmail import READ_ONLY

    with pytest.raises(GmailError, match="label"):
        MockGmailClient(READ_ONLY).create_label("JARVIS/Rechnung")


def test_mit_senderecht_geht_es(home):
    client = MockGmailClient(SENDING)
    entwurf = client.create_draft("From: a\r\nTo: b\r\n\r\nText")
    ergebnis = client.send_draft(entwurf["id"])
    assert ergebnis["id"]
    assert len(client.gesendet) == 1


def test_der_mock_haelt_gesendetes_nur_bei_sich(home):
    """Es geht nirgendwohin -- das ist der Punkt."""
    client = MockGmailClient(SENDING)
    entwurf = client.create_draft("From: a\r\nTo: b\r\n\r\nText")
    client.send_draft(entwurf["id"])
    assert client.gesendet[0]["message"]["raw"].endswith("Text")


def test_der_kalendermock_hat_keinen_schreibpfad():
    client = MockCalendarClient()
    assert not hasattr(client, "create_event")
    assert not hasattr(client, "delete_event")
    assert client.capabilities == CALENDAR_READ


def test_der_kalendermock_verlangt_leserecht():
    with pytest.raises(GmailError, match="read"):
        MockCalendarClient(capabilities=frozenset()).list_events(
            "primary", time_min="2026-01-01T00:00:00+00:00", time_max="2026-12-31T00:00:00+00:00"
        )


# --------------------------------------------------------------------------- #
# Die Beispieldaten
# --------------------------------------------------------------------------- #


def test_das_beispielpostfach_deckt_die_unangenehmen_faelle_ab():
    texte = []
    for nachricht in beispiel_postfach():
        kopf = {h["name"]: h["value"] for h in nachricht["payload"]["headers"]}
        texte.append(f"{kopf['From']} {kopf['Subject']}")
    zusammen = " ".join(texte).lower()
    assert "noreply" in zusammen, "kein noreply-Absender im Beispiel"
    assert "newsletter" in zusammen, "kein Newsletter im Beispiel"
    assert len(beispiel_postfach()) >= 5


def test_das_beispielpostfach_enthaelt_einen_einschleusversuch():
    """Wer den Mock benutzt, soll den Abwehrfall einmal sehen."""
    import base64

    roh = []
    for nachricht in beispiel_postfach():
        daten = nachricht["payload"]["body"]["data"]
        roh.append(base64.urlsafe_b64decode(daten + "=" * (-len(daten) % 4)).decode("utf-8"))
    assert any("ignoriere alle vorherigen anweisungen" in t.lower() for t in roh)


def test_der_beispielkalender_enthaelt_beide_befundarten():
    from jarvis.skills.calendar.conflicts import KEIN_PUFFER, UEBERSCHNEIDUNG, find_conflicts
    from jarvis.skills.calendar.event import parse_event

    termine = [parse_event(e, calendar_id="primary") for e in beispiel_kalender()]
    arten = {b.kind for b in find_conflicts(termine, min_gap_minutes=15)}
    assert UEBERSCHNEIDUNG in arten
    assert KEIN_PUFFER in arten


def test_der_beispielkalender_liegt_in_der_zukunft():
    """Sonst findet die Konflikterkennung nichts und wirkt kaputt."""
    from datetime import UTC, datetime

    jetzt = datetime.now(UTC)
    beginne = [
        datetime.fromisoformat(e["start"]["dateTime"])
        for e in beispiel_kalender()
        if "dateTime" in e["start"]
    ]
    assert all(b > jetzt for b in beginne)


def test_der_kalendermock_filtert_nach_fenster():
    from datetime import UTC, datetime, timedelta

    jetzt = datetime.now(UTC)
    client = MockCalendarClient()
    eng = client.list_events(
        "primary",
        time_min=jetzt.isoformat(),
        time_max=(jetzt + timedelta(hours=1)).isoformat(),
    )
    weit = client.list_events(
        "primary",
        time_min=jetzt.isoformat(),
        time_max=(jetzt + timedelta(days=7)).isoformat(),
    )
    assert len(eng) < len(weit)


# --------------------------------------------------------------------------- #
# Eigene Beispieldaten
# --------------------------------------------------------------------------- #


def test_eigene_nachrichten_aus_einem_verzeichnis(tmp_path):
    (tmp_path / "eins.json").write_text(
        json.dumps(
            [
                {
                    "id": "x1",
                    "threadId": "t1",
                    "labelIds": ["INBOX"],
                    "internalDate": "1740000000000",
                    "snippet": "",
                    "payload": {"mimeType": "text/plain", "body": {"data": ""}, "headers": []},
                }
            ]
        ),
        encoding="utf-8",
    )
    client = MockGmailClient(LABELLING, fixtures=tmp_path)
    assert client.list_message_ids("is:unread", 25) == ["x1"]


def test_ein_fehlendes_verzeichnis_wird_gemeldet(tmp_path):
    with pytest.raises(GmailError, match="Beispielverzeichnis"):
        MockGmailClient(LABELLING, fixtures=tmp_path / "gibtsnicht")


def test_unlesbares_json_wird_gemeldet(tmp_path):
    (tmp_path / "kaputt.json").write_text("{kein json", encoding="utf-8")
    with pytest.raises(GmailError, match="unlesbar"):
        MockGmailClient(LABELLING, fixtures=tmp_path)


# --------------------------------------------------------------------------- #
# Der ganze Weg ohne Konten
#
# Das ist der Zweck dieser Betriebsart: die Faehigkeiten laufen ueber dieselbe
# Fabrik, dasselbe Gatter und dasselbe Protokoll -- nur ohne Google.
# --------------------------------------------------------------------------- #


def voll_config(home, *, dry_run: bool = True) -> Config:
    antwort = json.dumps(
        {
            "kategorie": "rechnung",
            "dringlichkeit": 1,
            "antwort_noetig": False,
            "begruendung": "Beispiel",
        }
    )
    return Config.from_mapping(
        {
            "dry_run": dry_run,
            "timezone": "Europe/Berlin",
            "services": {"mode": "mock"},
            "capabilities": {
                "mail": {"requires_outbound": False, "rate_limits": {"hour": 100}},
                "calendar": {"requires_outbound": False, "rate_limits": {"hour": 100}},
                "briefing": {"requires_outbound": False},
            },
            "llm": {
                "isolation": "off",
                "providers": {
                    "trocken": {
                        "kind": "static",
                        "model": "static",
                        "local": True,
                        "reply": antwort,
                    }
                },
                "tasks": {"classify": {"providers": ["trocken"]}},
            },
            "skills": {"mail": {"task": "classify"}, "briefing": {"task": "classify"}},
        },
        paths=Paths(home=home),
    )


def durchlauf(config, conn, name):
    from jarvis.core.audit import AuditLog
    from jarvis.core.gate import Gate
    from jarvis.core.ratelimit import RateLimiter
    from jarvis.skills.factory import build_skill
    from jarvis.skills.runner import run_skill

    audit = AuditLog(conn)
    skill = build_skill(name, config=config, conn=conn)
    return run_skill(
        skill, gate=Gate(config, audit, RateLimiter(conn, config.capabilities)), audit=audit
    )


def test_mail_laeuft_vollstaendig_ohne_google(home, conn):
    bericht = durchlauf(voll_config(home), conn, "mail")
    assert bericht.polled == 5
    assert bericht.failed == 0
    assert bericht.by_category["rechnung"] == 5


def test_kalender_laeuft_vollstaendig_ohne_google(home, conn):
    bericht = durchlauf(voll_config(home), conn, "calendar")
    assert bericht.polled == 5
    assert bericht.failed == 0
    # Drei Termine stecken in einem Konflikt, zwei nicht.
    assert bericht.skipped == 2


def test_der_trockenlauf_gilt_auch_im_mock(home, conn):
    """Mock ist kein Ersatz fuer den Trockenlauf -- beide gelten unabhaengig."""
    bericht = durchlauf(voll_config(home, dry_run=True), conn, "calendar")
    assert bericht.acted == 0
    assert bericht.dry_run > 0


def test_ohne_trockenlauf_entstehen_im_mock_echte_befunde(home, conn):
    from jarvis.skills.calendar.store import CalendarStore

    durchlauf(voll_config(home, dry_run=False), conn, "calendar")
    mit_befund = [
        e for e in CalendarStore(conn).between(von="2000-01-01", bis="2100-01-01") if e.finding
    ]
    assert mit_befund, "keine Konflikte im Beispielkalender gefunden"


def test_das_briefing_entsteht_aus_mock_daten(home, conn):
    from jarvis.skills.briefing.store import BriefingStore

    config = voll_config(home, dry_run=False)
    durchlauf(config, conn, "calendar")
    durchlauf(config, conn, "mail")
    bericht = durchlauf(config, conn, "briefing")
    assert bericht.acted == 1

    from datetime import datetime

    heute = datetime.now(config.timezone).date().isoformat()
    briefing = BriefingStore(conn).get(heute)
    assert briefing is not None
    assert briefing.facts["termine"], "Briefing ohne Termine aus dem Mock-Kalender"


def test_ein_mock_lauf_protokolliert_wie_ein_echter(home, conn):
    from jarvis.core.audit import AuditLog

    durchlauf(voll_config(home), conn, "mail")
    eintraege = AuditLog(conn).recent(50)
    assert any(e.capability == "mail" for e in eintraege)
    assert AuditLog(conn).verify().ok


def test_der_einschleusversuch_wird_auch_im_mock_entschaerft(home, conn):
    """Die Nachricht m5 will JARVIS umlenken. Sie bleibt Fremdtext."""
    from jarvis.skills.mail.store import MailStore

    durchlauf(voll_config(home, dry_run=False), conn, "mail")
    eintrag = MailStore(conn).get("m5")
    assert eintrag is not None
    # Sie wurde eingeordnet wie jede andere -- nicht befolgt.
    assert eintrag.category == "rechnung"
