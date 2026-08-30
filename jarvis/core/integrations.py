"""Was JARVIS an externen Diensten hat, und wie weit es nachgewiesen ist.

Der Anlass ist eine unangenehme Wahrheit: eine Anbindung, die gegen ein
Testdoppel laeuft, sieht im Protokoll genauso aus wie eine, die je mit dem
echten Dienst gesprochen hat. Wer nur den Code liest, kann beides nicht
unterscheiden -- und faengt an, "implementiert" fuer "funktioniert" zu halten.

Deshalb vier Stufen, und die letzte wird nicht behauptet, sondern gemessen:

    implementiert     Der Adapter existiert.
    lokal getestet    Tests decken ihn ab, ohne Netz.
    mit Mock getestet Der ganze Weg laeuft gegen einen Laufzeit-Mock,
                      ueber dieselben Faehigkeiten und dasselbe Gatter.
    echt verifiziert  Es gab mindestens einen erfolgreichen Aufruf gegen
                      den echten Dienst. Diesen Eintrag schreibt nur der
                      echte Adapter, und nur nachdem er eine Antwort hatte.

Die ersten drei Stufen sind Aussagen ueber den Quelltext und stehen deshalb
hier als Angabe. Die vierte steht in der Datenbank und kommt von einem
tatsaechlichen Aufruf. `jarvis services check` zeigt beides nebeneinander.

Gespeichert wird nur, *dass* und *wann* -- nie eine Antwort, nie ein Wert aus
dem Dienst. Ein Nachweis, der Inhalte mitschreibt, waere selbst das Problem.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

__all__ = [
    "DIENSTE",
    "Dienst",
    "Kontakt",
    "dienst",
    "letzter_kontakt",
    "merke_kontakt",
]

META_PRAEFIX = "integration.last_live."

#: Kurze Angabe, wie ein Detail aussehen darf. Kein Inhalt, nur Form.
MAX_DETAIL = 120


@dataclass(frozen=True)
class Dienst:
    """Ein externer Dienst und was ueber seine Anbindung bekannt ist."""

    name: str
    zweck: str
    modul: str
    #: Deckt ein Test diesen Adapter ab, ohne Netz?
    lokal_getestet: bool
    #: Gibt es einen Laufzeit-Mock, mit dem der ganze Weg laeuft?
    mock: str | None
    #: Wonach der Adapter sucht, wenn er Zugangsdaten braucht.
    geheimnis: str | None = None


DIENSTE: tuple[Dienst, ...] = (
    Dienst(
        name="anthropic",
        zweck="Modell, extern",
        modul="jarvis.llm.providers.anthropic",
        lokal_getestet=True,
        mock="llm.providers.static",
        geheimnis="anthropic_api_key",
    ),
    Dienst(
        name="ollama",
        zweck="Modell, lokal",
        modul="jarvis.llm.providers.ollama",
        lokal_getestet=True,
        mock="llm.providers.static",
    ),
    Dienst(
        name="gmail",
        zweck="Postfach lesen, Entwuerfe, Versand",
        modul="jarvis.skills.mail.gmail",
        lokal_getestet=True,
        mock="skills.mail.mock",
        geheimnis="gmail_token",
    ),
    Dienst(
        name="calendar",
        zweck="Termine lesen",
        modul="jarvis.skills.calendar.google",
        lokal_getestet=True,
        mock="skills.calendar.mock",
        geheimnis="gmail_token",
    ),
    Dienst(
        name="keychain",
        zweck="Zugangsdaten",
        modul="jarvis.core.secrets",
        lokal_getestet=True,
        mock=None,
        geheimnis=None,
    ),
)


def dienst(name: str) -> Dienst | None:
    for eintrag in DIENSTE:
        if eintrag.name == name:
            return eintrag
    return None


@dataclass(frozen=True)
class Kontakt:
    dienst: str
    wann: str
    detail: str


def merke_kontakt(conn: sqlite3.Connection, name: str, *, detail: str = "") -> Kontakt:
    """Haelt fest, dass der echte Dienst geantwortet hat.

    Nur von den echten Adaptern aufzurufen, und nur nach einer Antwort. Ein
    Mock ruft das nie auf -- sonst waere die Unterscheidung, um die es hier
    geht, wieder weg.
    """
    eintrag = Kontakt(
        dienst=name,
        wann=datetime.now(UTC).isoformat(timespec="seconds"),
        detail=detail[:MAX_DETAIL],
    )
    with conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (META_PRAEFIX + name, f"{eintrag.wann}|{eintrag.detail}"),
        )
    return eintrag


def letzter_kontakt(conn: sqlite3.Connection, name: str) -> Kontakt | None:
    zeile = conn.execute("SELECT value FROM meta WHERE key = ?", (META_PRAEFIX + name,)).fetchone()
    if zeile is None:
        return None
    roh = str(zeile["value"])
    wann, _, detail = roh.partition("|")
    if not wann:
        return None
    return Kontakt(dienst=name, wann=wann, detail=detail)
