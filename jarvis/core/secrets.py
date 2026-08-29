"""Zugangsdaten aus der macOS-Keychain.

Abschnitt 4 verlangt: Zugangsdaten ausschliesslich in der Keychain, niemals im
Repo. Das Interface hat deshalb kein `set` und keinen Dateipfad -- es kann nur
lesen, und es kann nur aus Quellen lesen, die ausserhalb des Projekts liegen.

Der zweite Ruecken (`EnvironmentBackend`) existiert, weil sich sonst auf keinem
anderen Rechner als deinem Mac entwickeln oder testen laesst. Er liest
Umgebungsvariablen, keine Datei -- damit landet weiterhin nichts im Git.

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

    def get(self, key: str) -> str | None:
        for backend in self._backends:
            value = backend.get(key)
            if value:
                return value
        return None

    def has(self, key: str) -> bool:
        return self.get(key) is not None

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
