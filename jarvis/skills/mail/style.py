"""Schreibstil aus gesendeten Nachrichten ableiten.

Ohne Modell. Das ist Absicht und nicht Sparsamkeit: was hier herauskommt, sind
Kennzahlen und Bezeichner aus einem festen Katalog -- "Anrede: Sie",
"Grussformel: viele_gruesse", "Satzlaenge: 14 Woerter". Kein Satz aus deinem
Briefwechsel wird gespeichert, und keiner geht je an ein Modell. Was das Modell
spaeter sieht, ist eine Beschreibung, die aus diesen Kennzahlen zusammengesetzt
wird.

Deshalb der geschlossene Katalog: wuerde die haeufigste Begruessung als freier
Text uebernommen, stuende irgendwann doch ein Stueck echter Korrespondenz in
der Datenbank und im Prompt. So steht dort hoechstens ein Bezeichner, den
dieses Modul selbst vergeben hat.
"""

from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from jarvis.core.db import transaction

__all__ = ["StyleProfile", "StyleStore", "extract_profile"]

# --------------------------------------------------------------------------- #
# Kataloge. Was hier nicht steht, wird nicht erkannt -- und nicht gespeichert.
# --------------------------------------------------------------------------- #

GREETINGS: dict[str, tuple[str, ...]] = {
    "sehr_geehrte": ("sehr geehrte", "sehr geehrter", "sehr geehrtes"),
    "guten_tag": ("guten tag", "guten morgen", "guten abend"),
    "hallo": ("hallo",),
    "liebe": ("liebe", "lieber", "liebes"),
    "moin": ("moin", "servus", "gruess dich", "gruezi"),
    "hi": ("hi", "hey", "hallihallo"),
    "dear": ("dear",),
    "hello": ("hello",),
}

SIGNOFFS: dict[str, tuple[str, ...]] = {
    "mit_freundlichen_gruessen": ("mit freundlichen gruessen", "mfg"),
    "freundliche_gruesse": ("freundliche gruesse", "beste gruesse"),
    "viele_gruesse": ("viele gruesse", "vg"),
    "herzliche_gruesse": ("herzliche gruesse", "liebe gruesse", "lg"),
    "gruesse": ("gruesse", "gruss"),
    "danke": ("danke", "vielen dank", "besten dank"),
    "bis_bald": ("bis bald", "bis dann", "bis gleich"),
    "best_regards": ("best regards", "kind regards", "regards"),
    "cheers": ("cheers", "thanks", "thank you"),
}

DE_STOPWORDS = frozenset(
    [
        "der",
        "die",
        "das",
        "und",
        "ist",
        "nicht",
        "ein",
        "eine",
        "mit",
        "fuer",
        "auf",
        "von",
        "den",
        "dem",
        "im",
        "zu",
        "sich",
        "auch",
    ]
)
EN_STOPWORDS = frozenset(
    [
        "the",
        "and",
        "is",
        "not",
        "a",
        "an",
        "with",
        "for",
        "on",
        "of",
        "to",
        "in",
        "it",
        "that",
        "this",
        "you",
        "are",
        "be",
        "have",
    ]
)

SIE_MARKER = frozenset(["sie", "ihnen", "ihr", "ihre", "ihrem", "ihren"])
DU_MARKER = frozenset(["du", "dir", "dich", "dein", "deine", "deinem", "deinen", "euch", "euer"])

# Zitierte Vorgaengernachrichten. Alles ab hier gehoert nicht mehr zum Stil.
_ZITAT_START = re.compile(
    r"^\s*(?:>|am .{0,80}schrieb|on .{0,80}wrote|-{2,}\s*(?:urspruengliche|original)|"
    r"von:\s|from:\s|gesendet:\s|sent:\s)",
    re.IGNORECASE,
)
_SATZ_ENDE = re.compile(r"[.!?]+")
_WORT = re.compile(r"[a-z0-9]+")
# Als Escapes geschrieben: gleich aussehende Umlaute koennen zerlegt vorliegen
# (a + Trema) und waeren dann zwei Zeichen -- die Tabelle nimmt nur eines.
_UMLAUTE = str.maketrans({"\u00e4": "ae", "\u00f6": "oe", "\u00fc": "ue", "\u00df": "ss"})


def _falte(text: str) -> str:
    """Klein, ohne Umlaute, ohne Satzzeichen -- damit der Katalog ASCII bleibt."""
    ohne = unicodedata.normalize("NFC", text.lower()).translate(_UMLAUTE)
    return re.sub(r"[^a-z0-9 ]+", " ", ohne).strip()


def _ist_emoji(zeichen: str) -> bool:
    nummer = ord(zeichen)
    return (
        0x1F300 <= nummer <= 0x1FAFF or 0x2600 <= nummer <= 0x27BF or 0x1F000 <= nummer <= 0x1F2FF
    )


def eigener_text(koerper: str) -> str:
    """Schneidet zitierte Vorgaengernachrichten ab.

    Ohne das misst der Stil die Schreibweise der Gegenseite mit -- und der
    laengste Teil einer Antwort ist meistens das Zitat.
    """
    zeilen: list[str] = []
    for zeile in koerper.splitlines():
        if _ZITAT_START.match(zeile):
            break
        zeilen.append(zeile)
    return "\n".join(zeilen).strip()


@dataclass(frozen=True)
class StyleProfile:
    sample_count: int = 0
    language: str = "unbekannt"
    form_of_address: str = "unbekannt"
    greeting: str | None = None
    signoff: str | None = None
    avg_sentence_words: int = 0
    avg_reply_words: int = 0
    exclamations_per_reply: float = 0.0
    emojis_per_reply: float = 0.0
    greeting_counts: dict[str, int] = field(default_factory=dict)
    signoff_counts: dict[str, int] = field(default_factory=dict)

    LABELS = {  # noqa: RUF012 - fester Katalog, bewusst am Typ
        "sehr_geehrte": "Sehr geehrte / Sehr geehrter",
        "guten_tag": "Guten Tag",
        "hallo": "Hallo",
        "liebe": "Liebe / Lieber",
        "moin": "Moin",
        "hi": "Hi",
        "dear": "Dear",
        "hello": "Hello",
        "mit_freundlichen_gruessen": "Mit freundlichen Gruessen",
        "freundliche_gruesse": "Freundliche Gruesse",
        "viele_gruesse": "Viele Gruesse",
        "herzliche_gruesse": "Herzliche Gruesse",
        "gruesse": "Gruesse",
        "danke": "Danke",
        "bis_bald": "Bis bald",
        "best_regards": "Best regards",
        "cheers": "Cheers",
    }

    @property
    def usable(self) -> bool:
        return self.sample_count > 0

    def describe(self) -> str:
        """Die Beschreibung, die ins Modell geht. Nur Abgeleitetes."""
        if not self.usable:
            return (
                "Kein Stilprofil vorhanden. Schreibe sachlich, knapp und hoeflich, "
                "in der Sprache der eingehenden Nachricht."
            )
        haeufig = "selten" if self.exclamations_per_reply < 0.3 else "gelegentlich"
        emoji = "nie" if self.emojis_per_reply < 0.1 else "gelegentlich"
        zeilen = [
            f"Schreibstil, abgeleitet aus {self.sample_count} eigenen gesendeten Nachrichten:",
            f"- Sprache: {self.language}",
            f"- Anrede: {self.form_of_address}",
        ]
        if self.greeting:
            name = self.LABELS.get(self.greeting, self.greeting)
            zeilen.append(f"- Uebliche Begruessung: {name}")
        if self.signoff:
            name = self.LABELS.get(self.signoff, self.signoff)
            zeilen.append(f"- Uebliche Grussformel: {name}")
        zeilen += [
            f"- Durchschnittliche Satzlaenge: {self.avg_sentence_words} Woerter",
            f"- Uebliche Laenge einer Antwort: {self.avg_reply_words} Woerter",
            f"- Ausrufezeichen: {haeufig}",
            f"- Emojis: {emoji}",
        ]
        return "\n".join(zeilen)


def _erkenne(gefaltet: str, katalog: dict[str, tuple[str, ...]]) -> str | None:
    for bezeichner, formen in katalog.items():
        for form in formen:
            if gefaltet.startswith(form):
                return bezeichner
    return None


def extract_profile(koerper_liste: list[str]) -> StyleProfile:
    """Rechnet die Kennzahlen aus. Bekommt Text, gibt Zahlen und Bezeichner."""
    begruessungen: Counter[str] = Counter()
    grussformeln: Counter[str] = Counter()
    saetze_gesamt = woerter_gesamt = 0
    antwort_woerter: list[int] = []
    ausrufezeichen = emojis = 0
    sie = du = 0
    deutsch = englisch = 0
    verwertbar = 0

    for roh in koerper_liste:
        text = eigener_text(roh)
        if not text:
            continue
        verwertbar += 1

        zeilen = [z.strip() for z in text.splitlines() if z.strip()]
        if zeilen:
            if treffer := _erkenne(_falte(zeilen[0]), GREETINGS):
                begruessungen[treffer] += 1
            # Die Grussformel steht in einer der letzten Zeilen, davor kommt
            # oft noch eine Signatur.
            for zeile in reversed(zeilen[-4:]):
                if treffer := _erkenne(_falte(zeile), SIGNOFFS):
                    grussformeln[treffer] += 1
                    break

        woerter = _WORT.findall(_falte(text))
        antwort_woerter.append(len(woerter))
        woerter_gesamt += len(woerter)
        saetze_gesamt += max(1, len(_SATZ_ENDE.findall(text)))
        ausrufezeichen += text.count("!")
        emojis += sum(1 for z in text if _ist_emoji(z))

        menge = set(woerter)
        sie += len(menge & SIE_MARKER)
        du += len(menge & DU_MARKER)
        deutsch += len(menge & DE_STOPWORDS)
        englisch += len(menge & EN_STOPWORDS)

    if not verwertbar:
        return StyleProfile()

    if sie and du:
        anrede = "Sie" if sie >= du * 2 else ("du" if du >= sie * 2 else "gemischt")
    elif sie:
        anrede = "Sie"
    elif du:
        anrede = "du"
    else:
        anrede = "unbekannt"

    if deutsch or englisch:
        sprache = "Deutsch" if deutsch >= englisch else "Englisch"
    else:
        sprache = "unbekannt"

    return StyleProfile(
        sample_count=verwertbar,
        language=sprache,
        form_of_address=anrede,
        greeting=begruessungen.most_common(1)[0][0] if begruessungen else None,
        signoff=grussformeln.most_common(1)[0][0] if grussformeln else None,
        avg_sentence_words=round(woerter_gesamt / saetze_gesamt) if saetze_gesamt else 0,
        avg_reply_words=round(sum(antwort_woerter) / len(antwort_woerter)),
        exclamations_per_reply=round(ausrufezeichen / verwertbar, 2),
        emojis_per_reply=round(emojis / verwertbar, 2),
        greeting_counts=dict(begruessungen),
        signoff_counts=dict(grussformeln),
    )


class StyleStore:
    """Genau eine Zeile. Ein Profil, nicht viele."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save(self, profile: StyleProfile) -> None:
        daten = {k: v for k, v in asdict(profile).items() if k != "sample_count"}
        with transaction(self._conn):
            self._conn.execute(
                """
                INSERT INTO style_profile (id, updated_at, sample_count, profile)
                VALUES (1, ?, ?, ?)
                ON CONFLICT (id) DO UPDATE SET
                    updated_at   = excluded.updated_at,
                    sample_count = excluded.sample_count,
                    profile      = excluded.profile
                """,
                (
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    profile.sample_count,
                    json.dumps(daten, ensure_ascii=False, sort_keys=True),
                ),
            )

    def load(self) -> StyleProfile:
        zeile = self._conn.execute("SELECT * FROM style_profile WHERE id = 1").fetchone()
        if zeile is None:
            return StyleProfile()
        return StyleProfile(sample_count=zeile["sample_count"], **json.loads(zeile["profile"]))

    def updated_at(self) -> str | None:
        zeile = self._conn.execute("SELECT updated_at FROM style_profile WHERE id = 1").fetchone()
        return zeile["updated_at"] if zeile else None
