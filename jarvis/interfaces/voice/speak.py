"""Text zu Sprache. Ueber die Stimme, die macOS ohnehin mitbringt.

Was JARVIS laut sagt, hoert jeder im Raum. Das ist kein Nebeneffekt, sondern
eine Eigenschaft des Kanals, und sie begrenzt, was hier hinausgehen darf: der
eigene Zustand und das eigene Briefing. Mailinhalte werden nicht vorgelesen --
nicht weil es technisch schwer waere, sondern weil eine vorgelesene Betreffzeile
im falschen Moment eine Offenlegung ist, die niemand rueckgaengig machen kann.

`say` wird mit einer Argumentliste aufgerufen, nie ueber eine Shell. Der Text
stammt aus deterministischem Code, aber er enthaelt Termintitel, und die
kommen von Einladenden.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import IO, Protocol, runtime_checkable

__all__ = ["MacSpeaker", "Speaker", "SpeechError", "TextSpeaker"]

#: Obergrenze fuer eine Ansage. Was laenger ist, gehoert auf einen Bildschirm.
MAX_ZEICHEN = 1200


class SpeechError(RuntimeError):
    """Die Ausgabe ist gescheitert."""


@runtime_checkable
class Speaker(Protocol):
    name: str

    def available(self) -> bool: ...

    def describe(self) -> str: ...

    def say(self, text: str) -> None: ...


#: Was am Ende einer gekuerzten Ansage steht.
NACHSATZ = " -- Rest im Dashboard."


def kuerzen(text: str) -> str:
    """Auf MAX_ZEICHEN, den Nachsatz eingerechnet.

    Der Platz fuer den Nachsatz wird abgezogen, nicht geschaetzt: sonst wird
    die Ansage genau um dessen Laenge zu lang.
    """
    sauber = " ".join(text.split())
    if len(sauber) <= MAX_ZEICHEN:
        return sauber
    return sauber[: MAX_ZEICHEN - len(NACHSATZ)].rstrip() + NACHSATZ


@dataclass
class MacSpeaker:
    """Die eingebaute Stimme von macOS."""

    voice: str = ""
    rate: int = 0  # 0 = Vorgabe des Systems
    timeout: float = 120.0
    name: str = "say"

    def _programm(self) -> str | None:
        return shutil.which("say")

    def available(self) -> bool:
        return sys.platform == "darwin" and self._programm() is not None

    def describe(self) -> str:
        if sys.platform != "darwin":
            return "nur unter macOS"
        if self._programm() is None:
            return "say nicht gefunden"
        return f"say{f' mit Stimme {self.voice}' if self.voice else ''}"

    def command(self, text: str) -> list[str]:
        befehl = ["say"]
        if self.voice:
            befehl += ["-v", self.voice]
        if self.rate:
            befehl += ["-r", str(self.rate)]
        # "--" beendet die Optionen: ein Text, der mit "-" beginnt, bleibt Text.
        return [*befehl, "--", text]

    def say(self, text: str) -> None:
        gekuerzt = kuerzen(text)
        if not gekuerzt:
            return
        if not self.available():
            raise SpeechError(f"Sprachausgabe steht nicht bereit: {self.describe()}")
        try:
            ergebnis = subprocess.run(
                self.command(gekuerzt),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SpeechError("Sprachausgabe antwortet nicht rechtzeitig") from exc
        except OSError as exc:
            raise SpeechError(f"Sprachausgabe liess sich nicht starten ({exc})") from exc
        if ergebnis.returncode != 0:
            raise SpeechError(f"say endete mit {ergebnis.returncode}")


@dataclass
class TextSpeaker:
    """Schreibt statt zu sprechen.

    Der Rueckfall auf allen Systemen ohne `say` -- und der Weg, die ganze
    Kette zu pruefen, ohne dass jemand zuhoeren muss.
    """

    stream: IO[str] | None = None
    gesagt: list[str] = field(default_factory=list)
    name: str = "text"

    def available(self) -> bool:
        return True

    def describe(self) -> str:
        return "geschrieben statt gesprochen"

    def say(self, text: str) -> None:
        gekuerzt = kuerzen(text)
        self.gesagt.append(gekuerzt)
        if self.stream is not None:
            print(gekuerzt, file=self.stream)
