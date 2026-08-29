"""Erzwungene JSON-Ausgabe und die Zielfeld-Sperre -- Prinzip 2.1."""

from __future__ import annotations

import pytest

from jarvis.llm.schema import (
    OutputSchema,
    SchemaError,
    ValidationError,
    assert_no_target_fields,
    extract_json,
    validate,
)

KLASSIFIZIERER = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kategorie", "dringlichkeit"],
    "properties": {
        "kategorie": {"type": "string", "enum": ["rechnung", "termin", "werbung", "sonstiges"]},
        "dringlichkeit": {"type": "integer", "minimum": 0, "maximum": 3},
        "begruendung": {"type": "string", "maxLength": 200},
    },
}


# --- Zielfeld-Sperre -------------------------------------------------------- #


@pytest.mark.parametrize(
    "feld",
    [
        "to",
        "cc",
        "bcc",
        "recipient",
        "recipients",
        "reply_to_address",
        "url",
        "target_url",
        "webhook_url",
        "file_path",
        "destination",
        "iban",
        "payee_account",
        "forward_to",
    ],
)
def test_zielfelder_werden_abgelehnt(feld):
    schema = {"type": "object", "properties": {feld: {"type": "string"}}}
    with pytest.raises(SchemaError, match=r"2\.1"):
        assert_no_target_fields(schema)


@pytest.mark.parametrize(
    "feld",
    [
        "kategorie",
        "subject_line",
        "summary",
        "sender_domain_known",
        "status",
        "auto_reply",
        "confidence",
        "language",
    ],
)
def test_harmlose_felder_gehen_durch(feld):
    schema = {"type": "object", "properties": {feld: {"type": "string"}}}
    assert_no_target_fields(schema)


def test_sperre_greift_auch_verschachtelt():
    schema = {
        "type": "object",
        "properties": {"antwort": {"type": "object", "properties": {"to": {"type": "string"}}}},
    }
    with pytest.raises(SchemaError):
        assert_no_target_fields(schema)


def test_sperre_greift_in_listen():
    schema = {
        "type": "object",
        "properties": {
            "anhaenge": {
                "type": "array",
                "items": {"type": "object", "properties": {"path": {"type": "string"}}},
            }
        },
    }
    with pytest.raises(SchemaError):
        assert_no_target_fields(schema)


def test_output_schema_prueft_schon_beim_anlegen():
    with pytest.raises(SchemaError):
        OutputSchema(
            name="antwort", schema={"type": "object", "properties": {"to": {"type": "string"}}}
        )


# --- Validierung ------------------------------------------------------------ #


def test_gueltige_antwort():
    validate({"kategorie": "termin", "dringlichkeit": 2}, KLASSIFIZIERER)


def test_pflichtfeld_fehlt():
    with pytest.raises(ValidationError, match="Pflichtfeld"):
        validate({"kategorie": "termin"}, KLASSIFIZIERER)


def test_wert_ausserhalb_der_aufzaehlung():
    with pytest.raises(ValidationError, match="nicht erlaubt"):
        validate({"kategorie": "unfug", "dringlichkeit": 1}, KLASSIFIZIERER)


def test_zusaetzliche_felder_werden_abgelehnt():
    with pytest.raises(ValidationError, match="unerlaubte Felder"):
        validate({"kategorie": "termin", "dringlichkeit": 1, "extra": 1}, KLASSIFIZIERER)


def test_falscher_typ():
    with pytest.raises(ValidationError, match="erwartet integer"):
        validate({"kategorie": "termin", "dringlichkeit": "hoch"}, KLASSIFIZIERER)


def test_bool_ist_kein_integer():
    with pytest.raises(ValidationError):
        validate({"kategorie": "termin", "dringlichkeit": True}, KLASSIFIZIERER)


def test_zahlenbereich():
    with pytest.raises(ValidationError, match="groesser als 3"):
        validate({"kategorie": "termin", "dringlichkeit": 9}, KLASSIFIZIERER)


def test_maximale_laenge():
    with pytest.raises(ValidationError, match="laenger als"):
        validate(
            {"kategorie": "termin", "dringlichkeit": 1, "begruendung": "x" * 500},
            KLASSIFIZIERER,
        )


def test_listen_werden_elementweise_geprueft():
    schema = {"type": "array", "items": {"type": "integer"}, "maxItems": 3}
    validate([1, 2, 3], schema)
    with pytest.raises(ValidationError, match=r"\[1\]"):
        validate([1, "zwei"], schema)
    with pytest.raises(ValidationError, match="mehr als 3"):
        validate([1, 2, 3, 4], schema)


# --- JSON aus der Antwort holen --------------------------------------------- #


def test_blankes_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_json_im_codeblock():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_json_mit_geschwaetz_davor_und_danach():
    text = 'Gern. Hier das Ergebnis:\n{"a": 1, "b": [2, 3]}\nSoll ich noch etwas tun?'
    assert extract_json(text) == {"a": 1, "b": [2, 3]}


def test_klammern_in_zeichenketten_verwirren_nicht():
    assert extract_json('Text {"a": "} nicht das Ende {"}') == {"a": "} nicht das Ende {"}


def test_verschachteltes_objekt():
    assert extract_json('vor {"a": {"b": {"c": 1}}} nach') == {"a": {"b": {"c": 1}}}


def test_ohne_json_ein_fehler():
    with pytest.raises(ValidationError, match="kein verwertbares JSON"):
        extract_json("Ich kann dazu nichts sagen.")


def test_output_schema_holt_und_prueft_in_einem_schritt():
    schema = OutputSchema(name="klassifizierung", schema=KLASSIFIZIERER)
    ergebnis = schema.parse('```json\n{"kategorie": "rechnung", "dringlichkeit": 3}\n```')
    assert ergebnis["kategorie"] == "rechnung"


def test_anweisung_enthaelt_das_schema():
    schema = OutputSchema(name="klassifizierung", schema=KLASSIFIZIERER)
    assert "kategorie" in schema.instructions()
