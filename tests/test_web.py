"""Das Dashboard: Zugang, Herkunft, Maskierung, Freigabe.

Der Kern hier sind nicht die Ansichten, sondern die drei Wege, auf denen eine
Oberflaeche mit einem Freigabeknopf schiefgehen kann: jemand kommt ohne Token
hinein, eine fremde Seite loest ein Formular aus, oder eine praeparierte
Betreffzeile wird als Markup ausgeliefert.
"""

from __future__ import annotations

import json
import re
from html import unescape

import pytest
from starlette.testclient import TestClient

from jarvis.core.approvals import ApprovalStore
from jarvis.core.audit import AuditLog
from jarvis.core.config import DEFAULT_CONFIG_TOML, StopSwitch
from jarvis.core.db import open_database
from jarvis.interfaces.web.app import create_app
from jarvis.interfaces.web.security import COOKIE_NAME
from jarvis.skills.base import Decision, Result, Skill

TOKEN = "test-token-fuer-die-sitzung"
BASIS = "http://127.0.0.1:8765"
BOESE = "<script>alert('x')</script>"


@pytest.fixture
def dashboard(home):
    """Fertig eingerichtetes Basisverzeichnis mit Datenbank."""
    (home / "config.toml").write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    conn = open_database(home / "state.db")
    conn.close()
    return home


def trockenlauf_aus(home):
    pfad = home / "config.toml"
    pfad.write_text(
        pfad.read_text(encoding="utf-8").replace("dry_run = true", "dry_run = false"),
        encoding="utf-8",
    )


def klient(home, *, angemeldet=True) -> TestClient:
    client = TestClient(create_app(home=home, token=TOKEN, port=8765), base_url=BASIS)
    if angemeldet:
        client.cookies.set(COOKIE_NAME, TOKEN)
    return client


def vorgang_einstellen(home, **kwargs):
    conn = open_database(home / "state.db")
    try:
        grund = {
            "skill": "mail_reply",
            "event_key": "m1",
            "action": "draft",
            "reason": "Entwurf enthaelt einen Link",
            "decided_by": "model",
            "summary": "kunde@example.com -- Frage zum Termin",
            "targets": {"to": "kunde@example.com", "subject": "Re: Frage", "body": "Guten Tag."},
        }
        grund.update(kwargs)
        return ApprovalStore(conn).enqueue(**grund)
    finally:
        conn.close()


# --- Zugang ----------------------------------------------------------------- #


def test_ohne_token_kein_zugang(dashboard):
    antwort = klient(dashboard, angemeldet=False).get("/")
    assert antwort.status_code == 403
    assert "web-token" in antwort.text


def test_falscher_token_kein_zugang(dashboard):
    client = klient(dashboard, angemeldet=False)
    client.cookies.set(COOKIE_NAME, "geraten")
    assert client.get("/").status_code == 403


def test_token_aus_der_adresszeile_wird_zum_cookie(dashboard):
    client = klient(dashboard, angemeldet=False)
    antwort = client.get(f"/?token={TOKEN}", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"
    assert COOKIE_NAME in antwort.cookies
    # Der Token soll nicht im Verlauf jeder Seite stehen bleiben.
    assert "token=" not in antwort.headers["location"]


def test_mit_cookie_kommt_die_seite(dashboard):
    antwort = klient(dashboard).get("/")
    assert antwort.status_code == 200
    assert "JARVIS" in antwort.text


@pytest.mark.parametrize("pfad", ["/", "/entscheidungen", "/protokoll", "/jarvis.css"])
def test_schutzkopfzeilen_auf_jeder_antwort(dashboard, pfad):
    kopf = klient(dashboard).get(pfad).headers
    assert "default-src 'none'" in kopf["content-security-policy"]
    assert kopf["x-content-type-options"] == "nosniff"
    assert kopf["referrer-policy"] == "no-referrer"


def test_die_richtlinie_laesst_kein_skript_zu(dashboard):
    richtlinie = klient(dashboard).get("/").headers["content-security-policy"]
    assert "unsafe-inline" not in richtlinie
    assert "unsafe-eval" not in richtlinie
    assert "frame-ancestors 'none'" in richtlinie


def test_stylesheet_wird_ausgeliefert(dashboard):
    antwort = klient(dashboard).get("/jarvis.css")
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("text/css")
    assert "--accent" in antwort.text


# --- Maskierung ------------------------------------------------------------- #


def test_praeparierter_betreff_wird_maskiert(dashboard):
    vorgang_einstellen(
        dashboard,
        summary=f"kunde@example.com -- {BOESE}",
        targets={"to": f"a@b.de{BOESE}", "subject": BOESE, "body": BOESE},
        reason=BOESE,
    )
    text = klient(dashboard).get("/entscheidungen").text
    assert "<script>" not in text
    assert "alert('x')" not in text
    assert "&lt;script&gt;" in text


def test_praepariertes_protokoll_wird_maskiert(dashboard):
    conn = open_database(dashboard / "state.db")
    AuditLog(conn).record(
        capability="mail",
        kind="decision",
        outcome="label",
        detail={"summary": BOESE, "reason": BOESE},
    )
    conn.close()
    text = klient(dashboard).get("/protokoll").text
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_stoppgrund_wird_maskiert(dashboard):
    StopSwitch(dashboard / "STOP").engage(BOESE)
    text = klient(dashboard).get("/").text
    assert "<script>" not in text


def test_meldung_kommt_aus_der_tabelle_nicht_aus_der_adresszeile(dashboard):
    """Sonst zeigt ein praeparierter Link beliebigen Text auf der eigenen Seite."""
    text = klient(dashboard).get("/entscheidungen?m=" + BOESE).text
    assert "<script>" not in text
    assert "alert" not in text


# --- Herkunft --------------------------------------------------------------- #


def test_fremde_herkunft_wird_abgewiesen(dashboard):
    vorgang = vorgang_einstellen(dashboard)
    antwort = klient(dashboard).post(
        f"/entscheidungen/{vorgang.id}/verwerfen", headers={"Origin": "http://boese.tld"}
    )
    assert antwort.status_code == 403


def test_ohne_herkunftskopf_wird_abgewiesen(dashboard):
    vorgang = vorgang_einstellen(dashboard)
    antwort = klient(dashboard).post(f"/entscheidungen/{vorgang.id}/verwerfen")
    assert antwort.status_code == 403


def test_referer_der_eigenen_seite_genuegt(dashboard):
    vorgang = vorgang_einstellen(dashboard)
    antwort = klient(dashboard).post(
        f"/entscheidungen/{vorgang.id}/verwerfen",
        headers={"Referer": f"{BASIS}/entscheidungen"},
        follow_redirects=False,
    )
    assert antwort.status_code == 303


def test_lesen_braucht_keinen_herkunftskopf(dashboard):
    assert klient(dashboard).get("/entscheidungen").status_code == 200


# --- Verwerfen und Freigeben ------------------------------------------------ #


def eigene_post(client, pfad):
    return client.post(pfad, headers={"Origin": BASIS}, follow_redirects=False)


def test_verwerfen(dashboard):
    vorgang = vorgang_einstellen(dashboard)
    antwort = eigene_post(klient(dashboard), f"/entscheidungen/{vorgang.id}/verwerfen")
    assert antwort.status_code == 303
    assert "m=verworfen" in antwort.headers["location"]

    conn = open_database(dashboard / "state.db")
    try:
        assert ApprovalStore(conn).get(vorgang.id).state == "rejected"
        assert AuditLog(conn).recent(1)[0].outcome == "rejected"
    finally:
        conn.close()


def test_unbekannter_vorgang(dashboard):
    antwort = eigene_post(klient(dashboard), "/entscheidungen/999/verwerfen")
    assert "m=unbekannt" in antwort.headers["location"]


class Attrappe(Skill):
    name = "mail_reply"
    autonomy_level = 0
    requires_outbound = False
    ausgefuehrt: list[Decision] = []  # noqa: RUF012 - Testattrappe

    def poll(self):
        return []

    def decide(self, event):
        raise NotImplementedError

    def verify_targets(self, decision):
        return decision

    def act(self, decision):
        type(self).ausgefuehrt.append(decision)
        return Result(skill=self.name, event_key=decision.event_key, performed=True)


@pytest.fixture
def attrappe(monkeypatch):
    Attrappe.ausgefuehrt = []
    monkeypatch.setattr("jarvis.interfaces.web.app.build_skill", lambda name, **kwargs: Attrappe())
    return Attrappe


def test_freigeben_fuehrt_aus(dashboard, attrappe):
    """Die Abnahmebedingung aus Abschnitt 6."""
    trockenlauf_aus(dashboard)
    vorgang = vorgang_einstellen(dashboard)

    antwort = eigene_post(klient(dashboard), f"/entscheidungen/{vorgang.id}/freigeben")
    assert antwort.status_code == 303
    assert "m=freigegeben" in antwort.headers["location"]
    assert len(attrappe.ausgefuehrt) == 1
    assert attrappe.ausgefuehrt[0].targets["to"] == "kunde@example.com"

    conn = open_database(dashboard / "state.db")
    try:
        assert ApprovalStore(conn).get(vorgang.id).state == "executed"
    finally:
        conn.close()


def test_freigabe_im_trockenlauf_bewirkt_nichts(dashboard, attrappe):
    vorgang = vorgang_einstellen(dashboard)
    antwort = eigene_post(klient(dashboard), f"/entscheidungen/{vorgang.id}/freigeben")
    assert "m=nicht-ausgefuehrt" in antwort.headers["location"]
    assert attrappe.ausgefuehrt == []

    conn = open_database(dashboard / "state.db")
    try:
        frisch = ApprovalStore(conn).get(vorgang.id)
        assert frisch.pending
        assert "Trockenlauf" in (frisch.note or "")
    finally:
        conn.close()


def test_freigabe_bei_gestopptem_system(dashboard, attrappe):
    trockenlauf_aus(dashboard)
    vorgang = vorgang_einstellen(dashboard)
    StopSwitch(dashboard / "STOP").engage("Vorfall")

    antwort = eigene_post(klient(dashboard), f"/entscheidungen/{vorgang.id}/freigeben")
    assert "m=nicht-ausgefuehrt" in antwort.headers["location"]
    assert attrappe.ausgefuehrt == []


def test_der_trockenlauf_wird_auf_der_seite_erklaert(dashboard):
    vorgang_einstellen(dashboard)
    text = klient(dashboard).get("/entscheidungen").text
    assert "Trockenlauf ist an" in text
    assert "dry_run" in text


# --- Stoppschalter ---------------------------------------------------------- #


def test_stoppschalter_auf_jeder_ansicht(dashboard):
    client = klient(dashboard)
    for pfad in ("/", "/entscheidungen", "/protokoll"):
        text = client.get(pfad).text
        assert "BETRIEB" in text
        assert 'action="/stop"' in text


def test_anhalten_und_fortsetzen(dashboard):
    client = klient(dashboard)
    antwort = eigene_post(client, "/stop")
    assert antwort.status_code == 303
    assert (dashboard / "STOP").exists()
    assert "ANGEHALTEN" in client.get("/").text

    eigene_post(client, "/weiter")
    assert not (dashboard / "STOP").exists()


def test_anhalten_steht_im_protokoll(dashboard):
    eigene_post(klient(dashboard), "/stop")
    conn = open_database(dashboard / "state.db")
    try:
        assert "stop_engaged" in [e.outcome for e in AuditLog(conn).recent(5)]
    finally:
        conn.close()


# --- Ansichten -------------------------------------------------------------- #


def test_zustand_zeigt_stufen_und_zaehler(dashboard):
    text = klient(dashboard).get("/").text
    assert "Schattenbetrieb" in text
    assert "mail_send" in text
    assert "Trockenlauf" in text


def test_navigation_zeigt_die_anzahl_offener_vorgaenge(dashboard):
    vorgang_einstellen(dashboard, event_key="a")
    vorgang_einstellen(dashboard, event_key="b")
    text = klient(dashboard).get("/").text
    assert '<span class="count">2</span>' in text


def test_ohne_vorgaenge_eine_ruhige_ansicht(dashboard):
    text = klient(dashboard).get("/entscheidungen").text
    assert "Nichts anstehend" in text


def test_protokoll_zeigt_eintraege(dashboard):
    conn = open_database(dashboard / "state.db")
    AuditLog(conn).record(capability="mail", kind="action", outcome="dry_run")
    conn.close()
    text = klient(dashboard).get("/protokoll").text
    assert "dry_run" in text


def sichtbarer_text(html: str) -> str:
    """Nur das, was der Nutzer liest -- ohne Markup und ohne Stylesheet."""
    ohne_style = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL)
    return unescape(re.sub(r"<[^>]+>", " ", ohne_style))


def test_keine_ausrufezeichen_und_keine_emojis(dashboard):
    """Abschnitt 7: knapp und sachlich. Gemeint ist die Sprache, nicht das Markup."""
    vorgang_einstellen(dashboard)
    client = klient(dashboard)
    for pfad in ("/", "/entscheidungen", "/protokoll"):
        text = sichtbarer_text(client.get(pfad).text)
        assert "!" not in text
        assert all(ord(z) < 0x2100 for z in text)


def test_die_seite_laedt_nichts_nach(dashboard):
    """Nur das eigene Stylesheet -- kein Skript, kein Bild, keine Schrift."""
    text = klient(dashboard).get("/").text
    assert "<script" not in text
    assert "<img" not in text
    assert text.count("<link") == 1
    assert 'href="/jarvis.css"' in text


def test_kaputte_konfiguration_wirft_nicht_ins_leere(dashboard):
    (dashboard / "config.toml").write_text("web = 5\n", encoding="utf-8")
    with pytest.raises(Exception, match="web"):
        klient(dashboard).get("/")


def test_json_bleibt_json(dashboard):
    """Die Zielfelder eines Vorgangs kommen unveraendert wieder heraus."""
    ziele = {"to": "a@b.de", "subject": "Re: x", "body": "Text"}
    vorgang = vorgang_einstellen(dashboard, targets=ziele)
    conn = open_database(dashboard / "state.db")
    try:
        assert ApprovalStore(conn).get(vorgang.id).targets == ziele
        roh = conn.execute("SELECT targets FROM approvals WHERE id = ?", (vorgang.id,)).fetchone()[
            0
        ]
        assert json.loads(roh) == ziele
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Briefing
# --------------------------------------------------------------------------- #


def test_briefing_ohne_eintrag_sagt_wie_es_geht(dashboard):
    antwort = klient(dashboard).get("/briefing")
    assert antwort.status_code == 200
    assert "jarvis briefing --neu" in antwort.text


def test_briefing_zeigt_den_neuesten_eintrag(dashboard):
    from datetime import UTC, datetime

    from jarvis.skills.briefing.store import BriefingStore

    heute = datetime.now(UTC).date().isoformat()
    conn = open_database(dashboard / "state.db")
    try:
        BriefingStore(conn).save(day="2026-03-01", text="Gestern war ruhig.")
        BriefingStore(conn).save(day=heute, text="Heute nur der Zahnarzt.", model="static")
    finally:
        conn.close()

    antwort = klient(dashboard).get("/briefing")
    assert antwort.status_code == 200
    assert "Heute nur der Zahnarzt." in antwort.text
    assert "static" in antwort.text
    # Aeltere stehen darunter, aber nicht im Vordergrund.
    assert "Gestern war ruhig." in antwort.text
    assert antwort.text.index("Heute nur der Zahnarzt.") < antwort.text.index("Gestern war ruhig.")


def test_briefingtext_wird_maskiert(dashboard):
    from datetime import UTC, datetime

    from jarvis.skills.briefing.store import BriefingStore

    conn = open_database(dashboard / "state.db")
    try:
        BriefingStore(conn).save(day=datetime.now(UTC).date().isoformat(), text=BOESE)
    finally:
        conn.close()

    antwort = klient(dashboard).get("/briefing")
    assert BOESE not in antwort.text
    assert "&lt;script&gt;" in antwort.text


def test_briefing_verlangt_den_token(dashboard):
    antwort = klient(dashboard, angemeldet=False).get("/briefing")
    assert antwort.status_code == 403
    assert "web-token" in antwort.text


def test_briefing_steht_in_der_navigation(dashboard):
    antwort = klient(dashboard).get("/")
    assert 'href="/briefing"' in antwort.text
