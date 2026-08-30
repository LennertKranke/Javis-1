"""Was ein gesprochener Satz bedeuten darf -- und was nicht.

Ein Mikrofon ist kein angemeldeter Eingabekanal. Was an der Tastatur getippt
wird, kommt von jemandem, der davorsitzt; was das Mikrofon hoert, kommt aus
dem Raum: vom Fernseher, aus einer Videokonferenz, von Besuch, aus einem
Podcast. Ein Transkript ist damit genau das, was Abschnitt 2.3 meint --
fremder Text, keine Anweisung.

Daraus folgt die Regel dieser Phase:

    Sprache liest vor. Sprache handelt nicht.

Die Absichten sind eine geschlossene Menge, kein freier Befehl. Vier davon
lesen nur; eine setzt den Stoppschalter; eine ist ausdruecklich das
Erkennen-und-Verweigern. Ein Ziel -- eine Adresse, ein Pfad, eine Kennung --
kommt in keiner davon vor, und es gibt im Code keinen Weg von hier zu einer
ausgehenden Aktion.

Beim Anhalten ist die Richtung entscheidend. Ein Podcast, der JARVIS anhaelt,
ist ein Aergernis: man merkt es und gibt von Hand frei. Ein Podcast, der ihn
wieder freigibt, waere eine Luecke. Deshalb kann Sprache anhalten und
niemals fortsetzen.

Erkannt wird zuerst mit Regeln, erst danach mit dem Modell. Das ist nicht
Sparsamkeit: "anhalten" muss auch dann noch funktionieren, wenn kein Anbieter
erreichbar ist.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

__all__ = [
    "ABSICHTEN",
    "ANHALTEN",
    "BRIEFING",
    "HANDELN",
    "LESEND",
    "OFFEN",
    "STATUS",
    "UNBEKANNT",
    "Erkennung",
    "erkenne_mit_regeln",
    "loese_weckwort",
    "schema_fuer_absichten",
]

STATUS = "status"
BRIEFING = "briefing"
OFFEN = "offen"
ANHALTEN = "anhalten"
HANDELN = "handeln"
UNBEKANNT = "unbekannt"

ABSICHTEN: tuple[str, ...] = (STATUS, BRIEFING, OFFEN, ANHALTEN, HANDELN, UNBEKANNT)

#: Absichten, die nichts aendern. Sie duerfen auch bei gesetztem Stoppschalter
#: antworten -- gerade dann will man wissen, warum er steht.
LESEND: frozenset[str] = frozenset({STATUS, BRIEFING, OFFEN})


@dataclass(frozen=True)
class Erkennung:
    absicht: str
    quelle: str  # "rule", "model" oder "none"
    treffer: str = ""  # welche Wendung gegriffen hat, fuer das Protokoll

    @property
    def bekannt(self) -> bool:
        return self.absicht != UNBEKANNT


# --------------------------------------------------------------------------- #
# Regeln
#
# Wendungen, keine einzelnen Woerter, wo es geht: "halt an" soll greifen,
# "das Gespraech hielt an" moeglichst nicht. Absolute Sicherheit gibt es hier
# nicht -- die liegt darin, dass keine Absicht nach aussen wirken kann.
# --------------------------------------------------------------------------- #

_REGELN: tuple[tuple[str, tuple[str, ...]], ...] = (
    # Zuerst das Anhalten: im Zweifel lieber einmal zu viel stehen bleiben.
    (
        ANHALTEN,
        (
            r"\bhalt an\b",
            r"\bhalte an\b",
            r"\banhalten\b",
            r"\bstopp?\b",
            r"\bnot ?aus\b",
            r"\bhoer auf\b",
            r"\bmach nichts mehr\b",
        ),
    ),
    # Dann das ausdrueckliche Verweigern. Es steht vor den lesenden Absichten,
    # damit "gib die Entwuerfe frei" nicht als Frage nach Offenem durchgeht.
    (
        HANDELN,
        (
            r"\bsend\w*\b",
            r"\bverschick\w*\b",
            r"\babschick\w*\b",
            # Trennbares Verb: "schick die Entwuerfe ab". Der Wortteil steht
            # weit weg vom "ab", also greift der Stamm allein. Ein Fehltreffer
            # ("das ist schick") kostet hier nichts -- verweigert wird ohnehin.
            r"\bschick\w*\b",
            r"\bfrei ?gib\w*\b",
            # "gib die offenen Entscheidungen frei" -- zwischen "gib" und
            # "frei" steht das Objekt, und das kann laenger sein.
            r"\bgib .{0,40}frei\b",
            r"\bfreigeben\b",
            r"\bgenehmig\w*\b",
            r"\bbestaetig\w*\b",
            r"\bfortsetzen\b",
            r"\bweitermachen\b",
            r"\bmach weiter\b",
            r"\bloesch\w*\b",
            r"\bantwort\w* auf\b",
        ),
    ),
    (
        BRIEFING,
        (
            r"\bbriefing\b",
            r"\bwas steht (heute )?an\b",
            r"\bwie sieht (der|mein) tag\b",
            r"\btermine? heute\b",
            r"\bmorgenbriefing\b",
        ),
    ),
    (
        OFFEN,
        (
            r"\bwas liegt an\b",
            r"\boffene\w* entscheidung\w*\b",
            r"\bzur freigabe\b",
            r"\bwas wartet\b",
            r"\bwarteschlange\b",
        ),
    ),
    (
        STATUS,
        (
            r"\bstatus\b",
            r"\bwie ist der stand\b",
            r"\bwie geht es dir\b",
            r"\blaeuft (alles|noch)\b",
            r"\bzustand\b",
            r"\bbist du (da|wach)\b",
        ),
    ),
)

_KOMPILIERT: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...] = tuple(
    (absicht, tuple(re.compile(m) for m in muster)) for absicht, muster in _REGELN
)

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _vereinfacht(text: str) -> str:
    """Kleinschreibung, Umlaute aufgeloest, Satzzeichen weg.

    Whisper setzt Kommas und Punkte, mal so und mal so, und schreibt Umlaute
    manchmal aus. Die Regeln sollen daran nicht scheitern.
    """
    text = unicodedata.normalize("NFKC", text).casefold().translate(_UMLAUTE)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def loese_weckwort(text: str, weckwort: str) -> tuple[bool, str]:
    """(angesprochen, Rest ohne Weckwort).

    Ohne Weckwort gilt alles als angesprochen. Das Weckwort ist ein Filter
    gegen Zufall, keine Sicherung: ein Podcast kann "Jarvis" sagen. Die
    Sicherung liegt darin, dass keine Absicht nach aussen wirkt.
    """
    einfach = _vereinfacht(text)
    if not weckwort.strip():
        return True, einfach
    wort = _vereinfacht(weckwort)
    treffer = re.search(rf"\b{re.escape(wort)}\b", einfach)
    if treffer is None:
        return False, einfach
    return True, einfach[treffer.end() :].strip() or einfach


def erkenne_mit_regeln(text: str) -> Erkennung:
    """Deterministisch, ohne Modell, ohne Netz."""
    einfach = _vereinfacht(text)
    if not einfach:
        return Erkennung(absicht=UNBEKANNT, quelle="none")
    for absicht, muster in _KOMPILIERT:
        for m in muster:
            if m.search(einfach):
                return Erkennung(absicht=absicht, quelle="rule", treffer=m.pattern)
    return Erkennung(absicht=UNBEKANNT, quelle="none")


def schema_fuer_absichten() -> dict:
    """Das Ausgabeschema des Modells: eine Aufzaehlung, sonst nichts.

    Kein freier Text, keine Kennung, kein Ziel -- die Zielfeldsperre aus
    `llm/schema.py` haette ein solches Feld ohnehin abgewiesen.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["absicht"],
        "properties": {"absicht": {"enum": list(ABSICHTEN)}},
    }
