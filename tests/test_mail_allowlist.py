"""Allowlist: die drei Bremsen gegen "ein Gruss genuegt"."""

from __future__ import annotations

import pytest

from jarvis.skills.mail.allowlist import Allowlist
from tests.fixtures_gmail import FakeGmailClient, message


def liste(conn, **kwargs):
    return Allowlist(conn, **kwargs)


def eintragen(conn, adresse, anzahl):
    conn.execute(
        "INSERT INTO mail_allowlist (address, sent_count, source) VALUES (?, ?, 'sent')",
        (adresse, anzahl),
    )


# --- Mindestzahl ------------------------------------------------------------ #


def test_unbekannte_adresse_bekommt_nichts(conn):
    urteil = liste(conn).permits("fremd@example.com")
    assert urteil.allowed is False
    assert urteil.source == "unbekannt"


def test_ein_einzelner_gruss_genuegt_nicht(conn):
    """Genau der Einwand, den die automatische Liste sonst haette."""
    eintragen(conn, "einmal@example.com", 1)
    urteil = liste(conn, threshold=3).permits("einmal@example.com")
    assert urteil.allowed is False
    assert "erst 1 von 3" in urteil.reason


def test_ab_der_schwelle_erlaubt(conn):
    eintragen(conn, "oft@example.com", 3)
    urteil = liste(conn, threshold=3).permits("oft@example.com")
    assert urteil.allowed is True
    assert urteil.source == "sent"


def test_schwelle_ist_einstellbar(conn):
    eintragen(conn, "a@example.com", 5)
    assert liste(conn, threshold=10).permits("a@example.com").allowed is False
    assert liste(conn, threshold=5).permits("a@example.com").allowed is True


# --- Sperrliste gewinnt immer ----------------------------------------------- #


def test_sperrliste_schlaegt_hundert_nachrichten(conn):
    eintragen(conn, "chef@example.com", 100)
    urteil = liste(conn, blocked=["chef@example.com"]).permits("chef@example.com")
    assert urteil.allowed is False
    assert urteil.source == "blocked"


def test_sperrliste_schlaegt_die_handfreigabe(conn):
    urteil = liste(conn, manual=["x@example.com"], blocked=["x@example.com"]).permits(
        "x@example.com"
    )
    assert urteil.allowed is False


@pytest.mark.parametrize("eintrag", ["@example.com", "*@example.com", "example.com"])
def test_ganze_domain_sperren(conn, eintrag):
    eintragen(conn, "wer@example.com", 50)
    assert liste(conn, blocked=[eintrag]).permits("wer@example.com").allowed is False


def test_domainsperre_trifft_nur_die_domain(conn):
    eintragen(conn, "wer@andere.de", 50)
    assert liste(conn, blocked=["@example.com"]).permits("wer@andere.de").allowed is True


# --- Handfreigabe ----------------------------------------------------------- #


def test_von_hand_freigegeben_braucht_keine_zaehlung(conn):
    urteil = liste(conn, manual=["neu@example.com"]).permits("neu@example.com")
    assert urteil.allowed is True
    assert urteil.source == "manual"


def test_grossschreibung_ist_egal(conn):
    assert liste(conn, manual=["Neu@Example.COM"]).permits("neu@example.com").allowed is True


def test_unbrauchbare_adresse(conn):
    assert liste(conn).permits("kein-at-zeichen").allowed is False
    assert liste(conn).permits("").allowed is False


# --- Aus gesendeten Nachrichten zaehlen ------------------------------------- #


def gesendet(mid, *empfaenger, cc=""):
    return message(
        mid=mid,
        headers={"To": ", ".join(empfaenger), "Cc": cc, "From": "ich@example.com"},
    )


def test_zaehlen_aus_gesendetem(conn):
    client = FakeGmailClient(
        sent=[
            gesendet("s1", "anna@example.com"),
            gesendet("s2", "anna@example.com", "tom@example.com"),
            gesendet("s3", "anna@example.com"),
        ]
    )
    allowlist = liste(conn, threshold=3)
    gezaehlt = allowlist.refresh_from_sent(client, own_address="ich@example.com")

    assert gezaehlt["anna@example.com"] == 3
    assert gezaehlt["tom@example.com"] == 1
    assert allowlist.permits("anna@example.com").allowed is True
    assert allowlist.permits("tom@example.com").allowed is False


def test_cc_zaehlt_mit(conn):
    client = FakeGmailClient(sent=[gesendet("s1", "a@x.de", cc="b@x.de")])
    gezaehlt = liste(conn).refresh_from_sent(client)
    assert set(gezaehlt) == {"a@x.de", "b@x.de"}


def test_eigene_adresse_zaehlt_nicht(conn):
    client = FakeGmailClient(sent=[gesendet("s1", "ich@example.com", "anna@example.com")])
    gezaehlt = liste(conn).refresh_from_sent(client, own_address="ich@example.com")
    assert "ich@example.com" not in gezaehlt


def test_zaehlen_holt_nur_kopffelder(conn, monkeypatch):
    """Fuer das Zaehlen von Adressen braucht niemand alte Korrespondenz."""
    client = FakeGmailClient(sent=[gesendet("s1", "a@x.de")])
    gesehen = {}
    echtes = client.get_message

    def beobachtet(mid, *, fmt="full", headers=None):
        gesehen["fmt"] = fmt
        gesehen["headers"] = headers
        return echtes(mid)

    client.get_message = beobachtet
    liste(conn).refresh_from_sent(client)
    assert gesehen["fmt"] == "metadata"
    assert gesehen["headers"] == ["To", "Cc"]


def test_erneutes_zaehlen_ersetzt_statt_zu_addieren(conn):
    client = FakeGmailClient(sent=[gesendet("s1", "a@x.de"), gesendet("s2", "a@x.de")])
    allowlist = liste(conn)
    allowlist.refresh_from_sent(client)
    allowlist.refresh_from_sent(client)
    assert allowlist.get("a@x.de").sent_count == 2


def test_uebersicht(conn):
    eintragen(conn, "viel@x.de", 9)
    eintragen(conn, "wenig@x.de", 1)
    allowlist = liste(conn, threshold=3)
    assert allowlist.count() == 2
    assert allowlist.count(only_permitted=True) == 1
    assert [e.address for e in allowlist.entries()] == ["viel@x.de", "wenig@x.de"]
