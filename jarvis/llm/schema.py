"""Erzwungene JSON-Ausgabe und die Zielfeld-Sperre aus Prinzip 2.1.

Zwei Aufgaben. Die erste ist gewoehnlich: aus einer Modellantwort JSON
herausholen und gegen ein Schema pruefen. Der Validierer ist eine bewusst kleine
Teilmenge von JSON Schema -- genug fuer Klassifizierer und Entscheidungen, und
klein genug, um ohne die Abhaengigkeit `jsonschema` auszukommen.

Die zweite ist die wichtigere: `assert_no_target_fields` lehnt jedes Schema ab,
das ein Feld mit einem Ziel enthaelt -- Empfaenger, URL, Pfad, Konto. Prinzip
2.1 sagt, das Modell waehlt niemals ein Ziel; damit das nicht bloss ein Vorsatz
bleibt, scheitert hier schon das Anlegen eines solchen Schemas.

Der eigentliche Schutz ist nicht diese Namenspruefung, sondern dass `act()`
Ziele ausschliesslich aus den Originalheadern berechnet. Die Pruefung ist die
Reissleine davor: sie faengt den Entwurf ab, in dem jemand es anders vorhatte.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

__all__ = [
    "OutputSchema",
    "SchemaError",
    "ValidationError",
    "assert_no_target_fields",
    "extract_json",
    "validate",
]


class SchemaError(ValueError):
    """Das Schema selbst ist unzulaessig."""


class ValidationError(ValueError):
    """Die Antwort passt nicht zum Schema."""


# Ein Feldname zaehlt als Ziel, wenn eines seiner Wortteile hier steht.
# Einzahl und Mehrzahl werden gleich behandelt.
#
# Die Liste nennt Woerter, die ein Ziel *sind*, nicht solche, die eines nur
# erwaehnen: "domain" steht bewusst nicht darin, weil "sender_domain_known" ein
# gewoehnliches Merkmal eines Klassifizierers ist. "host" dagegen ist als
# blosser Feldname fast immer eine Verbindungsangabe.
TARGET_TOKENS = frozenset(
    {
        "to",
        "cc",
        "bcc",
        "recipient",
        "addressee",
        "address",
        "mailto",
        "forward",
        "url",
        "uri",
        "href",
        "link",
        "endpoint",
        "webhook",
        "host",
        "path",
        "filepath",
        "filename",
        "destination",
        "dest",
        "target",
        "iban",
        "payee",
        "account",
    }
)

_WORD_RE = re.compile(r"[^a-z0-9]+")
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _tokens(name: str) -> set[str]:
    parts = {p for p in _WORD_RE.split(name.lower()) if p}
    singular = {p[:-1] for p in parts if len(p) > 2 and p.endswith("s")}
    return parts | singular


def assert_no_target_fields(schema: dict[str, Any], *, path: str = "$") -> None:
    """Laeuft das Schema durch und verweigert jedes Feld, das ein Ziel waere."""
    if not isinstance(schema, dict):
        return
    for name, sub in (schema.get("properties") or {}).items():
        hits = _tokens(name) & TARGET_TOKENS
        if hits:
            raise SchemaError(
                f"{path}.{name}: Feldname enthaelt {', '.join(sorted(hits))} und sieht damit "
                f"nach einem Ziel aus. Prinzip 2.1: Ziele berechnet deterministischer Code "
                f"aus den Originaldaten, nie das Modell. Feld entfernen oder umbenennen."
            )
        assert_no_target_fields(sub, path=f"{path}.{name}")
    items = schema.get("items")
    if isinstance(items, dict):
        assert_no_target_fields(items, path=f"{path}[]")


# --------------------------------------------------------------------------- #
# Validierung
# --------------------------------------------------------------------------- #

_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    py = _TYPE_MAP.get(expected)
    if py is None:
        raise SchemaError(f"Unbekannter Typ im Schema: {expected!r}")
    return isinstance(value, py)


def validate(value: Any, schema: dict[str, Any], *, path: str = "$") -> None:
    """Prueft `value` gegen `schema`. Wirft `ValidationError` beim ersten Fehler."""
    expected = schema.get("type")
    if expected is not None:
        options = [expected] if isinstance(expected, str) else list(expected)
        if not any(_type_ok(value, opt) for opt in options):
            raise ValidationError(
                f"{path}: erwartet {'/'.join(options)}, gefunden {type(value).__name__}"
            )

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(v) for v in schema["enum"])
        raise ValidationError(f"{path}: {value!r} nicht erlaubt (zulaessig: {allowed})")

    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{path}: erwartet {schema['const']!r}")

    if isinstance(value, str):
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValidationError(f"{path}: laenger als {schema['maxLength']} Zeichen")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValidationError(f"{path}: kuerzer als {schema['minLength']} Zeichen")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ValidationError(f"{path}: passt nicht auf {schema['pattern']!r}")

    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError(f"{path}: kleiner als {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError(f"{path}: groesser als {schema['maximum']}")

    if isinstance(value, dict):
        properties = schema.get("properties") or {}
        for name in schema.get("required", []):
            if name not in value:
                raise ValidationError(f"{path}: Pflichtfeld {name!r} fehlt")
        if schema.get("additionalProperties") is False:
            extra = sorted(set(value) - set(properties))
            if extra:
                raise ValidationError(f"{path}: unerlaubte Felder {', '.join(extra)}")
        for name, sub in properties.items():
            if name in value:
                validate(value[name], sub, path=f"{path}.{name}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ValidationError(f"{path}: weniger als {schema['minItems']} Eintraege")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValidationError(f"{path}: mehr als {schema['maxItems']} Eintraege")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, entry in enumerate(value):
                validate(entry, items, path=f"{path}[{index}]")


# --------------------------------------------------------------------------- #
# JSON aus einer Modellantwort holen
# --------------------------------------------------------------------------- #


def extract_json(text: str) -> Any:
    """Holt das erste vollstaendige JSON-Objekt oder -Array aus einer Antwort.

    Modelle rahmen ihre Ausgabe gern in Codebloecke oder stellen einen Satz
    davor. Statt darauf zu vertrauen, dass sie es diesmal nicht tun, wird das
    JSON gesucht.
    """
    candidates: list[str] = []
    fenced = _FENCE_RE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    candidates.append(text.strip())

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        block = _first_block(candidate)
        if block is not None:
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                continue
    raise ValidationError("Antwort enthaelt kein verwertbares JSON")


def _first_block(text: str) -> str | None:
    """Sucht die erste ausgeglichene Klammerung, Zeichenketten beachtend."""
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start < 0:
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            ch = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[start : index + 1]
    return None


@dataclass(frozen=True)
class OutputSchema:
    """Ein benanntes Ausgabeschema. Die Zielfeld-Sperre greift beim Anlegen."""

    name: str
    schema: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.schema, dict):
            raise SchemaError("schema muss eine Abbildung sein")
        assert_no_target_fields(self.schema, path=f"${self.name}")

    def parse(self, text: str) -> Any:
        value = extract_json(text)
        validate(value, self.schema)
        return value

    def instructions(self) -> str:
        """Der Teil der Anweisung, der die Form der Antwort festlegt."""
        return (
            "Antworte ausschliesslich mit einem JSON-Objekt nach diesem Schema. "
            "Kein Fliesstext, keine Erklaerung, kein Codeblock.\n"
            + json.dumps(self.schema, ensure_ascii=False, indent=2, sort_keys=True)
        )
