"""Zugangsdaten aus der macOS-Keychain.

Abschnitt 4 verlangt: Zugangsdaten ausschliesslich in der Keychain, niemals im
Repo. Das Interface hat deshalb kein `set` und keinen Dateipfad -- es kann nur
lesen, und es kann nur aus Quellen lesen, die ausserhalb des Projekts liegen.

Auf macOS ist die Keychain die einzige Quelle. Es gibt dort keinen stillen
Rueckfall mehr: fehlt ein Eintrag, scheitert der Aufruf laut, statt
stillschweigend eine Klartext-Umgebungsvariable zu nehmen. Genau dieser
Durchrutscher war die Abweichung von Abschnitt 4 -- ein fehlender
Keychain-Eintrag sah aus wie ein vorhandener.

Der zweite Ruecken (`EnvironmentBackend`) bleibt, weil sich sonst auf keinem
anderen Rechner als deinem Mac entwickeln oder testen laesst. Er liest
Umgebungsvariablen, keine Datei -- damit landet weiterhin nichts im Git. Auf
Nicht-macOS ist er der Normalfall, auf macOS nur nach ausdruecklicher Wahl
(`JARVIS_SECRET_BACKEND=env`).

Jede Abweichung ist sichtbar: `insecure_reason()` sagt sie in einem Satz,
`jarvis status` schreibt sie hin. Eine Abweichung, die nirgends auftaucht,
wird zur Regel.

Ausgegeben wird nie ein Wert -- weder in Fehlern noch in Logs noch im
Protokoll. `require()` nennt den Namen des Eintrags, nicht seinen Inhalt.

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
BACKEND_ENV = "JARVIS_SECRET_BACKEND"


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

    def __init__(self, backends: list[SecretBackend], *, mode: str = "auto") -> None:
        self._backends = [b for b in backends if b.available()]
        self._mode = mode

    @property
    def mode(self) -> str:
        """Wie der Speicher gewaehlt wurde. Nur zur Anzeige."""
        return self._mode

    @property
    def backends(self) -> tuple[str, ...]:
        return tuple(b.name for b in self._backends)

    def describe(self) -> str:
        return " -> ".join(self.backends) if self._backends else "keine"

    @property
    def keychain_only(self) -> bool:
        """Entspricht die Lage dem, was Abschnitt 4 verlangt?"""
        return bool(self._backends) and all(b.name == "keychain" for b in self._backends)

    @property
    def violates_spec(self) -> bool:
        """Ein echter Verstoss gegen Abschnitt 4 -- nicht bloss ein Hinweis.

        Nur auf macOS. Dort gibt es die Keychain, dort ist eine
        Klartext-Umgebungsvariable eine Entscheidung gegen sie. Auf einem
        System ohne Keychain ist die Umgebung der einzige Weg; das ist der
        Entwicklungspfad und kein Verstoss.
        """
        return sys.platform == "darwin" and bool(self._backends) and not self.keychain_only

    def insecure_reason(self) -> str | None:
        """Warum diese Lage von Abschnitt 4 abweicht -- oder None.

        Eine Abweichung, die nirgends auftaucht, wird zur Regel. `jarvis
        status` schreibt diesen Satz hin; wie laut, entscheidet
        `violates_spec`.
        """
        if not self._backends or self.keychain_only:
            return None
        if self.violates_spec:
            return (
                "Zugangsdaten kommen aus Klartext-Umgebungsvariablen, nicht aus der "
                "Keychain. Abschnitt 4 verlangt die Keychain: JARVIS_SECRET_BACKEND "
                "loeschen oder auf 'keychain' setzen."
            )
        return (
            "Entwicklungspfad: Zugangsdaten kommen aus Umgebungsvariablen. Die "
            "macOS-Keychain gibt es auf diesem System nicht."
        )

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
    """Auf macOS ausschliesslich die Keychain. Sonst nichts, ohne Ansage.

    Frueher haengte `auto` die Umgebung als stillen Rueckfall an -- auch auf
    dem Mac. Fehlte dort ein Keychain-Eintrag, rutschte die Suche
    stillschweigend auf eine Klartext-Variable durch, statt laut zu scheitern.
    Genau das verbietet Abschnitt 4.

    Jetzt gilt:

      macOS, auto      nur Keychain. Kein Rueckfall, keine Ausnahme.
      sonst, auto      nur Umgebung -- die Keychain gibt es dort nicht. Das
                       ist der Entwicklungspfad und wird als solcher gemeldet.
      env              Umgebung, ausdruecklich gewaehlt. Auch auf dem Mac
                       moeglich, aber nur so: als bewusste Entscheidung, die
                       `jarvis status` sichtbar macht.
      keychain         nur Keychain, ueberall.
      none             gar nichts.
    """
    choice = os.environ.get(BACKEND_ENV, "auto").lower()
    if choice == "keychain":
        return SecretStore([KeychainBackend()], mode="keychain")
    if choice == "env":
        return SecretStore([EnvironmentBackend()], mode="env")
    if choice == "none":
        return SecretStore([], mode="none")
    if sys.platform == "darwin":
        return SecretStore([KeychainBackend()], mode="auto")
    return SecretStore([EnvironmentBackend()], mode="auto")
