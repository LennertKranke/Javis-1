"""Audio zu Text. Ausschliesslich auf diesem Rechner.

Es gibt hier bewusst keinen Anbieter, der Audio irgendwohin schickt. Nicht
weil einer schwer zu bauen waere, sondern weil das Mikrofon eines
Arbeitszimmers alles aufnimmt, was im Raum gesprochen wird -- Gespraeche, die
nie fuer eine Schnittstelle bestimmt waren. Was es nicht gibt, kann nicht
versehentlich benutzt werden; dasselbe Argument wie bei den Werkzeugen in
Abschnitt 2.2.

`WhisperCppTranscriber` ruft ein Programm auf, kein Python-Paket: whisper.cpp
laeuft auf Apple Silicon schnell und bringt kein PyTorch mit. Der Aufruf geht
ueber eine Argumentliste, nie ueber eine Shell -- ein Dateiname mit
Anfuehrungszeichen soll nichts anderes bedeuten als einen Dateinamen.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

__all__ = [
    "PLATZHALTER",
    "CommandRecorder",
    "RecordingError",
    "StaticTranscriber",
    "Transcriber",
    "TranscriptionError",
    "WhisperCppTranscriber",
]

#: Wird im Aufnahmebefehl durch den Zielpfad ersetzt.
PLATZHALTER = "{datei}"


class TranscriptionError(RuntimeError):
    """Die Umwandlung ist gescheitert. Nie mit dem Audioinhalt darin."""


@runtime_checkable
class Transcriber(Protocol):
    name: str

    def available(self) -> bool: ...

    def describe(self) -> str: ...

    def transcribe(self, audio: Path) -> str: ...


# Zeitmarken wie "[00:00:00.000 --> 00:00:02.400]" stehen am Zeilenanfang.
_ZEITMARKE = re.compile(r"^\s*\[[\d:.]+\s*-->\s*[\d:.]+\]\s*")


@dataclass
class WhisperCppTranscriber:
    """whisper.cpp ueber sein Kommandozeilenprogramm."""

    binary: str = "whisper-cli"
    model: str = ""
    language: str = "de"
    timeout: float = 120.0
    name: str = "whisper.cpp"

    def _programm(self) -> str | None:
        return shutil.which(self.binary)

    def available(self) -> bool:
        return self._programm() is not None and bool(self.model) and Path(self.model).is_file()

    def describe(self) -> str:
        if self._programm() is None:
            return f"{self.binary} nicht gefunden"
        if not self.model:
            return "kein Modell konfiguriert (voice.whisper_model)"
        if not Path(self.model).is_file():
            return f"Modell fehlt: {self.model}"
        return f"{self._programm()} mit {Path(self.model).name}"

    def command(self, audio: Path) -> list[str]:
        """Der Aufruf als Liste. Ausgelagert, damit er pruefbar ist."""
        return [
            self.binary,
            "--model",
            self.model,
            "--language",
            self.language,
            "--no-timestamps",
            "--no-prints",
            "--output-txt",
            "--file",
            str(audio),
        ]

    def transcribe(self, audio: Path) -> str:
        if not audio.is_file():
            raise TranscriptionError(f"Aufnahme nicht gefunden: {audio}")
        if not self.available():
            raise TranscriptionError(f"Whisper steht nicht bereit: {self.describe()}")
        try:
            ergebnis = subprocess.run(
                self.command(audio),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TranscriptionError("Whisper antwortet nicht rechtzeitig") from exc
        except OSError as exc:
            raise TranscriptionError(f"Whisper liess sich nicht starten ({exc})") from exc
        if ergebnis.returncode != 0:
            # stderr kann Pfade enthalten, aber keinen Audioinhalt.
            kurz = (ergebnis.stderr or "").strip().splitlines()
            raise TranscriptionError(
                f"Whisper endete mit {ergebnis.returncode}: {kurz[-1] if kurz else 'ohne Angabe'}"
            )
        return clean_transcript(ergebnis.stdout)


@dataclass
class StaticTranscriber:
    """Gibt immer denselben Text. Fuer Trockenlaeufe und Tests."""

    reply: str = ""
    name: str = "static"

    def available(self) -> bool:
        return True

    def describe(self) -> str:
        return "fester Text (kein Whisper)"

    def transcribe(self, audio: Path) -> str:
        return clean_transcript(self.reply)


def clean_transcript(roh: str) -> str:
    """Zeitmarken weg, Leerzeilen weg. Nicht mehr -- der Rest ist Fremdtext.

    Die eigentliche Normalisierung macht `sanitize`. Hier wird nur entfernt,
    was das Programm selbst hinzufuegt.
    """
    zeilen = [_ZEITMARKE.sub("", z).strip() for z in roh.split("\n")]
    return " ".join(z for z in zeilen if z).strip()


class RecordingError(RuntimeError):
    """Die Aufnahme ist gescheitert."""


@dataclass
class CommandRecorder:
    """Nimmt ueber ein konfiguriertes Programm auf.

    macOS bringt kein Aufnahmeprogramm auf der Kommandozeile mit, und ein
    Python-Paket dafuer waere eine schwere Abhaengigkeit fuer eine Zeile
    Arbeit. Deshalb sagt die Konfiguration, womit aufgenommen wird -- mit
    `sox`, mit `ffmpeg`, oder womit sonst. Ohne Eintrag gibt es keine
    Aufnahme; dann bleibt der Weg ueber eine fertige Datei.
    """

    command: tuple[str, ...] = ()
    timeout: float = 120.0
    name: str = "command"

    def available(self) -> bool:
        return bool(self.command) and shutil.which(self.command[0]) is not None

    def describe(self) -> str:
        if not self.command:
            return "nicht eingerichtet (voice.record_command)"
        if shutil.which(self.command[0]) is None:
            return f"{self.command[0]} nicht gefunden"
        return " ".join(self.command)

    def build(self, target: Path) -> list[str]:
        """Der Aufruf mit eingesetztem Zielpfad. Ausgelagert, um pruefbar zu sein."""
        return [teil.replace(PLATZHALTER, str(target)) for teil in self.command]

    def record(self, target: Path) -> Path:
        if not self.available():
            raise RecordingError(f"Aufnahme steht nicht bereit: {self.describe()}")
        befehl = self.build(target)
        if str(target) not in befehl:
            raise RecordingError(
                f"Der Aufnahmebefehl nennt das Ziel nicht. {PLATZHALTER} gehoert hinein."
            )
        try:
            ergebnis = subprocess.run(
                befehl, capture_output=True, text=True, timeout=self.timeout, check=False
            )
        except subprocess.TimeoutExpired as exc:
            raise RecordingError("Aufnahme endete nicht rechtzeitig") from exc
        except OSError as exc:
            raise RecordingError(f"Aufnahme liess sich nicht starten ({exc})") from exc
        if ergebnis.returncode != 0:
            kurz = (ergebnis.stderr or "").strip().splitlines()
            raise RecordingError(
                f"Aufnahme endete mit {ergebnis.returncode}: {kurz[-1] if kurz else 'ohne Angabe'}"
            )
        if not target.is_file():
            raise RecordingError(f"Aufnahme hat keine Datei erzeugt: {target}")
        return target
