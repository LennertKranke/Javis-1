"""Eine Gmail-Antwort zerlegen. Der Teil, der an echten Postfaechern bricht."""

from __future__ import annotations

from jarvis.skills.mail.message import parse_message
from tests.fixtures_gmail import b64, message, multipart, part


def test_reintext():
    m = parse_message(message(payload=part("text/plain", "Hallo Welt")))
    assert m.message_id == "m1"
    assert m.thread_id == "t1"
    assert m.body == "Hallo Welt"
    assert m.subject == "Betreff"


def test_absender_wird_zerlegt():
    m = parse_message(message(headers={"From": "Anna Beispiel <Anna@Example.COM>"}))
    assert m.sender is not None
    assert m.sender.address == "anna@example.com"  # klein, fuer Vergleiche
    assert m.sender.name == "Anna Beispiel"
    assert m.sender.domain == "example.com"


def test_mehrere_empfaenger_aus_to_und_cc():
    m = parse_message(message(headers={"To": "a@x.de, b@x.de", "Cc": "c@y.de"}))
    assert {e.address for e in m.recipients} == {"a@x.de", "b@x.de", "c@y.de"}


def test_doppeltes_from_zaehlt_nur_einmal():
    """Ein zweites From nach einem gueltigen ist der uebliche Verwirrungstrick."""
    roh = message()
    roh["payload"]["headers"].append({"name": "From", "value": "boese@angreifer.tld"})
    m = parse_message(roh)
    assert m.sender is not None
    assert m.sender.address == "absender@example.com"


def test_multipart_bevorzugt_reintext():
    m = parse_message(
        message(
            payload=multipart(
                part("text/plain", "der schlichte Text"),
                part("text/html", "<p>das bunte HTML</p>"),
            )
        )
    )
    assert m.body == "der schlichte Text"


def test_nur_html_wird_genommen():
    m = parse_message(message(payload=multipart(part("text/html", "<p>nur HTML</p>"))))
    assert "nur HTML" in m.body


def test_verschachtelte_teile():
    innen = multipart(part("text/plain", "tief drin"), mime="multipart/alternative")
    m = parse_message(message(payload=multipart(innen, mime="multipart/mixed")))
    assert m.body == "tief drin"


def test_anhaenge_werden_erfasst_aber_nicht_als_text():
    m = parse_message(
        message(
            payload=multipart(
                part("text/plain", "siehe Anhang"),
                part("application/pdf", "%PDF-1.4", filename="rechnung.pdf", size=8123),
                mime="multipart/mixed",
            )
        )
    )
    assert m.body == "siehe Anhang"
    assert len(m.attachments) == 1
    assert m.attachments[0].filename == "rechnung.pdf"
    assert m.attachments[0].size == 8123


def test_base64_ohne_auffuellung():
    roh = message()
    roh["payload"]["body"]["data"] = b64("Text ohne Padding-Zeichen")
    assert parse_message(roh).body == "Text ohne Padding-Zeichen"


def test_kaputte_kodierung_wirft_nicht():
    roh = message()
    roh["payload"]["body"]["data"] = "!!!kein base64!!!"
    assert parse_message(roh).body == ""


def test_umlaute_ueberleben():
    m = parse_message(message(payload=part("text/plain", "Gruesse aus Muenchen: ae oe ue")))
    assert "Muenchen" in m.body


def test_rfc2047_betreff_wird_aufgeloest():
    m = parse_message(message(headers={"Subject": "=?UTF-8?B?UmVjaG51bmcgZsO8ciBNw6Ryeg==?="}))
    assert m.subject == "Rechnung für März"


def test_kaputter_rfc2047_betreff_bleibt_stehen():
    m = parse_message(message(headers={"Subject": "=?UNSINN?X?abc?="}))
    assert "=?UNSINN?" in m.subject


def test_kopffelder_fuer_den_vorfilter():
    m = parse_message(
        message(
            headers={
                "List-Unsubscribe": "<mailto:weg@liste.de>",
                "Precedence": "Bulk",
                "Auto-Submitted": "auto-generated",
            }
        )
    )
    assert m.list_unsubscribe is True
    assert m.precedence == "bulk"
    assert m.auto_submitted == "auto-generated"


def test_ohne_payload_kein_absturz():
    m = parse_message({"id": "m9", "threadId": "t9"})
    assert m.message_id == "m9"
    assert m.body == ""
    assert m.sender is None


def test_untrusted_text_fuehrt_betreff_und_koerper_zusammen():
    """Beides bestimmt der Absender, beides geht denselben Weg."""
    m = parse_message(message(headers={"Subject": "Mahnung"}, payload=part("text/plain", "Text")))
    assert m.untrusted_text == "Betreff: Mahnung\n\nText"
