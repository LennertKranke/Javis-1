"""Dateirechte fuer alles, was JARVIS unter `~/.jarvis` anlegt.

Der Anlass ist ein Befund aus dem Audit: Basisverzeichnis und Datenbank
entstanden mit den Standardrechten des Systems. Bei der ueblichen umask 022 --
auch auf macOS -- sind das 0755 und 0644. Da `/Users/<name>` durchquerbar ist,
konnte damit **jeder andere lokale Benutzer** mitlesen.

Und mitzulesen gibt es einiges. In `state.db` stehen der vollstaendige
Entwurfstext wartender Antworten samt Empfaenger, Betreffzeilen, Briefings,
Langzeitgedaechtnis und Kontext. Abschnitt 4 der Spezifikation haelt
Zugangsdaten aus dem Projekt heraus, und das tut `secrets.py` auch -- aber die
Inhalte, um die es eigentlich geht, lagen offen.

Zwei Rechte, mehr braucht es nicht:

    0700  Verzeichnisse -- nur der Eigentuemer darf hinein
    0600  Dateien       -- nur der Eigentuemer darf lesen

Beide Funktionen sind **reparierend**, nicht nur anlegend: sie ziehen die
Rechte auch bei einer bereits vorhandenen Ablage nach. Sonst bliebe jede
Installation, die vor diesem Modul entstanden ist, fuer immer offen -- und das
waeren genau die, die schon Daten enthalten.

Ein fehlgeschlagenes `chmod` beendet nichts. Auf einem Dateisystem ohne
Unix-Rechte (Netzlaufwerk, Windows) ist das der Normalfall und kein Grund,
JARVIS nicht starten zu lassen. Wer wissen will, ob die Rechte stimmen, fragt
`ist_geschuetzt()` -- `jarvis status` tut das.
"""

from __future__ import annotations

import contextlib
import os
import stat
from pathlib import Path

__all__ = [
    "DIR_MODE",
    "FILE_MODE",
    "ist_geschuetzt",
    "secure_db",
    "secure_dir",
    "secure_file",
]

#: Nur der Eigentuemer, kein Gruppen- und kein Weltzugriff.
DIR_MODE = 0o700
FILE_MODE = 0o600

#: Die Begleitdateien des WAL-Modus. Sie enthalten noch nicht uebernommene
#: Schreibvorgaenge -- also dieselben Daten wie die Datenbank selbst.
DB_SUFFIXES = ("", "-wal", "-shm", "-journal")


def secure_dir(path: Path | str) -> Path:
    """Legt ein Verzeichnis mit 0700 an und zieht die Rechte notfalls nach.

    `mkdir(mode=...)` wirkt nur beim Anlegen und wird ausserdem von der umask
    beschnitten. Fuer ein Verzeichnis, das schon da ist, bleibt es wirkungslos
    -- deshalb danach immer noch ein `chmod`.
    """
    ziel = Path(path)
    ziel.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    _chmod(ziel, DIR_MODE)
    return ziel


def secure_file(path: Path | str) -> Path:
    """Setzt 0600 auf eine vorhandene Datei. Fehlt sie, passiert nichts."""
    ziel = Path(path)
    if ziel.exists():
        _chmod(ziel, FILE_MODE)
    return ziel


def secure_db(path: Path | str) -> None:
    """Die Datenbank und ihre WAL-Begleitdateien.

    Die Begleitdateien entstehen erst beim ersten Schreibvorgang. Was es noch
    nicht gibt, wird uebergangen -- der naechste Aufruf holt es nach, und jeder
    Verbindungsaufbau ruft hier vorbei.
    """
    if str(path) == ":memory:":
        return
    basis = Path(path)
    for suffix in DB_SUFFIXES:
        secure_file(basis.with_name(basis.name + suffix))


def ist_geschuetzt(path: Path | str) -> bool:
    """Ist hier wirklich niemand ausser dem Eigentuemer zugelassen?

    Geprueft wird auf Gruppen- und Weltrechte, nicht auf Gleichheit mit
    `DIR_MODE`. Ein Verzeichnis mit 0500 ist enger als verlangt und soll nicht
    als Abweichung gelten.
    """
    ziel = Path(path)
    try:
        modus = ziel.stat().st_mode
    except OSError:
        return False
    offen = stat.S_IRWXG | stat.S_IRWXO
    return not modus & offen


def _chmod(path: Path, mode: int) -> None:
    """Best effort. Ein Dateisystem ohne Unix-Rechte ist kein Fehlerfall."""
    with contextlib.suppress(OSError):
        os.chmod(path, mode)
