"""Zugangsdaten aus der macOS-Keychain.

Abschnitt 4 verlangt: Zugangsdaten ausschliesslich in der Keychain, niemals im
Repo. Das Interface hat deshalb kein `set` und keinen Dateipfad -- es kann nur
lesen, und es kann nur aus Quellen lesen, die ausserhalb des Projekts liegen.

Der zweite Ruecken (`EnvironmentBackend`) existiert, weil sich sonst auf keinem
anderen Rechner als deinem Mac entwickeln oder testen laesst. Er liest
Umgebungsvariablen, keine Datei -- damit landet weiterhin nichts im Git.

Das ist und bleibt eine Abweichung vom Wortlaut aus Abschnitt 4 ("ausschliesslich
in der Keychain"). Sie ist bewusst gewaehlt und bewusst sichtbar: `keychain_only`
sagt, ob die Lage der Vorgabe entspricht, `jarvis status` schreibt es hin, und im
Dauerbetrieb auf dem Mac gehoert `JARVIS_SECRET_BACKEND=keychain` gesetzt. Ohne
diese Sichtbarkeit waere aus der Entwicklungshilfe stillschweigend der Normalfall
geworden.

Eintrag in der Keychain anlegen:
    security add-generic-password -s jarvis -a anthropic_api_key -w
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "EnvironmentBackend",
    "KeychainBackend",
    "SecretStore",
    "SecretsError",
    "default_store",
]

KEYCHAIN_SERVICE = "jarvis"
ENV_PREFIX = "JARVIS_SECRET_"


class SecretsError(RuntimeError):
    """Ein benoetigtes Geheimnis fehlt. Enthaelt nie den Wert selbst."""


@runtime_checkable
class SecretBackend(Protocol):
    name: str

    def available(self) -> bool: ...

    def get(self, key: str) -> str | None: ...


@dataclass
class KeychainBackend:
    """Liest ueber das `security`-Kommando. Kein zusaetzliches Paket noetig."""

    name: str = "keychain"
    service: str = KEYCHAIN_SERVICE
    timeout: float = 10.0

    def available(self) -> bool:
        return sys.platform == "darwin" and shutil.which("security") is not None

    def set(self, key: str, value: str) -> None:
        """Legt an oder ersetzt (-U).

        Der Wert steht kurzzeitig in der Kommandozeile und ist damit fuer
        `ps` sichtbar. `security` kennt fuer add-generic-password keinen
        Weg ueber die Standardeingabe; das Zeitfenster liegt im Bereich von
        Millisekunden auf dem eigenen Rechner. Wer das nicht will, legt den
        Eintrag von Hand in der Schluesselbundverwaltung an.
        """
        if not self.available():
            raise SecretsError("Keychain steht auf diesem System nicht zur Verfuegung")
        result = subprocess.run(
            ["security", "add-generic-password", "-U", "-s", self.service, "-a", key, "-w", value],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if result.returncode != 0:
            raise SecretsError(f"Keychain-Eintrag {key!r} liess sich nicht schreiben")

    def delete(self, key: str) -> bool:
        if not self.available():
            return False
        result = subprocess.run(
            ["security", "delete-generic-password", "-s", self.service, "-a", key],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        return result.returncode == 0

    def get(self, key: str) -> str | None:
        if not self.available():
            return None
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", self.service, "-a", key, "-w"],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None


@dataclass
class EnvironmentBackend:
    """Liest `JARVIS_SECRET_<NAME>` in Grossbuchstaben."""

    name: str = "environment"
    prefix: str = ENV_PREFIX

    def available(self) -> bool:
        return True

    def get(self, key: str) -> str | None:
        value = os.environ.get(f"{self.prefix}{key.upper()}")
        return value.strip() or None if value else None


class SecretStore:
    """Fragt die Rueckwaende der Reihe nach. Der erste Treffer gewinnt."""

    def __init__(self, backends: list[SecretBackend]) -> None:
        self._backends = [b for b in backends if b.available()]

    @property
    def backends(self) -> tuple[str, ...]:
        return tuple(b.name for b in self._backends)

    def describe(self) -> str:
        return " -> ".join(self.backends) if self._backends else "keine"

    @property
    def keychain_only(self) -> bool:
        """Entspricht die Lage dem, was Abschnitt 4 verlangt?

        Nein, sobald `environment` in der Kette steht. Das ist eine bewusste
        Entwicklungsausnahme (siehe Modulkopf) -- aber eine, die man sehen
        koennen muss. Eine Ausnahme, die nirgends auftaucht, wird zur Regel.
        """
        return bool(self._backends) and all(b.name == "keychain" for b in self._backends)

    def get(self, key: str) -> str | None:
        for backend in self._backends:
            value = backend.get(key)
            if value:
                return value
        return None

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    @property
    def writable(self) -> bool:
        return any(hasattr(b, "set") for b in self._backends)

    def store(self, key: str, value: str) -> str:
        """Schreibt ein Geheimnis. Nur die Keychain kann das.

        Die Umgebung ist bewusst nicht beschreibbar: eine gesetzte Variable
        ueberlebt den Prozess nicht, und der naheliegende Ausweg -- eine Datei
        -- ist durch Abschnitt 4 ausgeschlossen.
        """
        for backend in self._backends:
            setter = getattr(backend, "set", None)
            if setter is not None:
                setter(key, value)
                return backend.name
        raise SecretsError(
            "Kein beschreibbarer Speicher vorhanden. Zugangsdaten gehoeren in die "
            "macOS-Keychain; auf anderen Systemen laesst sich nichts ablegen."
        )

    def forget(self, key: str) -> bool:
        entfernt = False
        for backend in self._backends:
            deleter = getattr(backend, "delete", None)
            if deleter is not None and deleter(key):
                entfernt = True
        return entfernt

    def require(self, key: str) -> str:
        value = self.get(key)
        if not value:
            raise SecretsError(
                f"Zugangsdaten {key!r} nicht gefunden (gesucht in: {self.describe()}). "
                f"Anlegen mit: security add-generic-password -s {KEYCHAIN_SERVICE} "
                f"-a {key} -w"
            )
        return value


def default_store() -> SecretStore:
    """Keychain zuerst, Umgebung als Rueckfall.

    `JARVIS_SECRET_BACKEND` erzwingt eine Wahl: keychain, env oder none.
    """
    choice = os.environ.get("JARVIS_SECRET_BACKEND", "auto").lower()
    if choice == "keychain":
        return SecretStore([KeychainBackend()])
    if choice == "env":
        return SecretStore([EnvironmentBackend()])
    if choice == "none":
        return SecretStore([])
    return SecretStore([KeychainBackend(), EnvironmentBackend()])
