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
    "offene_pfade",
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

    Und `parents=True` setzt den Modus **nur auf das letzte** Verzeichnis: bei
    einem mehrstufigen Pfad entstanden die Zwischenstufen mit den
    Standardrechten. Deshalb wird vorher festgehalten, welche Stufen noch
    fehlen, und danach jede davon nachgezogen.

    Nachgezogen wird ausschliesslich, was hier selbst entstanden ist. Ein
    Verzeichnis, das es schon gab, gehoert jemand anderem -- `~` oder `/tmp`
    umzustellen waere ein Uebergriff, nicht eine Absicherung.
    """
    ziel = Path(path)
    neu_angelegt = [stufe for stufe in (ziel, *ziel.parents) if not stufe.exists()]
    ziel.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    for stufe in neu_angelegt:
        _chmod(stufe, DIR_MODE)
    _chmod(ziel, DIR_MODE)  # auch wenn es das Verzeichnis schon gab
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


def offene_pfade(basis: Path | str) -> list[Path]:
    """Alles unter `basis`, worauf auch andere zugreifen duerfen.

    Ein Durchlauf statt einer gepflegten Liste. Die erste Fassung dieser
    Pruefung zaehlte vier bekannte Pfade auf -- und uebersah genau die zwei,
    die tatsaechlich offen waren: die Sperrdatei des Daemons und den
    Sitzungstoken des Dashboards. Eine Liste, die von Hand nachgezogen werden
    muss, wird irgendwann nicht nachgezogen.

    Symbolischen Verknuepfungen wird nicht gefolgt: sonst haengt das Ergebnis
    davon ab, wohin jemand sie gelegt hat, und ein Ring liesse den Durchlauf
    nie enden.
    """
    wurzel = Path(basis)
    if not wurzel.exists():
        return []

    offen: list[Path] = [] if ist_geschuetzt(wurzel) else [wurzel]
    for ordner, unterordner, dateien in os.walk(wurzel, followlinks=False):
        hier = Path(ordner)
        for name in sorted(unterordner) + sorted(dateien):
            pfad = hier / name
            if not pfad.is_symlink() and not ist_geschuetzt(pfad):
                offen.append(pfad)
    return offen


def _chmod(path: Path, mode: int) -> None:
    """Best effort. Ein Dateisystem ohne Unix-Rechte ist kein Fehlerfall."""
    with contextlib.suppress(OSError):
        os.chmod(path, mode)
