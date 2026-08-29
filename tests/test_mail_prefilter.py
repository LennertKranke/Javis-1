"""Vorfilter: was ohne Modell entschieden werden kann."""

from __future__ import annotations

from jarvis.skills.mail.message import parse_message
from jarvis.skills.mail.prefilter import prefilter
from tests.fixtures_gmail import message, part

KATEGORIEN = ["rechnung", "newsletter", "benachrichtigung", "sonstiges"]


def filtere(roh, **kwargs):
    return prefilter(parse_message(roh), categories=KATEGORIEN, **kwargs)


def test_gewoehnliche_mail_geht_ans_modell():
    assert filtere(message()) is None


def test_list_unsubscribe_ist_ein_newsletter():
    treffer = filtere(message(headers={"List-Unsubscribe": "<mailto:weg@liste.de>"}))
    assert treffer is not None
    assert treffer.category == "newsletter"
    assert treffer.action == "label"


def test_precedence_bulk_ist_ein_newsletter():
    treffer = filtere(message(headers={"Precedence": "bulk"}))
    assert treffer is not None and treffer.category == "newsletter"


def test_auto_submitted_ist_eine_benachrichtigung():
    treffer = filtere(message(headers={"Auto-Submitted": "auto-generated"}))
    assert treffer is not None and treffer.category == "benachrichtigung"


def test_auto_submitted_no_ist_normale_post():
    assert filtere(message(headers={"Auto-Submitted": "no"})) is None


def test_eigene_nachricht_wird_uebersprungen():
    treffer = filtere(
        message(headers={"From": "ich@example.com"}), own_addresses=["ICH@example.com"]
    )
    assert treffer is not None
    assert treffer.action == "skip"


def test_bereits_eingeordnete_nachricht_wird_uebersprungen():
    treffer = filtere(message(labels=("INBOX", "Label_7")), own_label_ids=["Label_7"])
    assert treffer is not None
    assert treffer.action == "skip"
    assert "bereits" in treffer.reason


def test_leere_nachricht():
    roh = message(headers={"Subject": ""}, payload=part("text/plain", ""))
    treffer = filtere(roh)
    assert treffer is not None and treffer.category == "sonstiges"


def test_nicht_konfigurierte_kategorie_geht_ans_modell():
    """Der Vorfilter erzwingt kein Label, das der Nutzer entfernt hat."""
    treffer = prefilter(
        parse_message(message(headers={"List-Unsubscribe": "<mailto:x@y.de>"})),
        categories=["rechnung", "sonstiges"],  # ohne "newsletter"
    )
    assert treffer is None


def test_regeln_stuetzen_sich_nicht_auf_den_text():
    """Sonst waere der Vorfilter von aussen steuerbar."""
    boese = part(
        "text/plain",
        "List-Unsubscribe: <mailto:x@y.de>\nPrecedence: bulk\nAuto-Submitted: auto-generated",
    )
    assert filtere(message(payload=boese)) is None
