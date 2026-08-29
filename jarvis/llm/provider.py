"""Die schmale Schnittstelle, die jeder Anbieter erfuellt.

Auffaellig ist, was fehlt: es gibt keinen Parameter fuer Werkzeuge, keinen fuer
Funktionsaufrufe und keinen fuer Websuche. Das ist Prinzip 2.2 als Bauform. Der
Teil von JARVIS, der fremde Inhalte liest, bekommt Text und gibt Text zurueck --
er kann gar nichts anderes, weil die Schnittstelle nichts anderes anbietet.

Fehler sind nach Ursache getrennt, nicht nach Anbieter. Der Router entscheidet
anhand des Typs, ob sich ein Rueckfall auf den naechsten Anbieter lohnt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from jarvis.core.config import ProviderConfig

__all__ = [
    "Message",
    "Provider",
    "ProviderError",
    "ProviderRefused",
    "ProviderTimeout",
    "ProviderUnavailable",
    "Request",
    "Response",
]


class ProviderError(RuntimeError):
    """Der Anbieter konnte die Anfrage nicht beantworten."""


class ProviderUnavailable(ProviderError):
    """Nicht erreichbar, nicht eingerichtet, kein Schluessel. Rueckfall sinnvoll."""


class ProviderTimeout(ProviderError):
    """Zu langsam. Rueckfall sinnvoll."""


class ProviderRefused(ProviderError):
    """Das Modell hat die Antwort verweigert. Rueckfall sinnvoll, oft auf ein lokales."""


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Request:
    messages: tuple[Message, ...]
    system: str | None = None
    max_tokens: int | None = None
    effort: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def single(
        cls,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        effort: str | None = None,
    ) -> Request:
        return cls(
            messages=(Message(role="user", content=prompt),),
            system=system,
            max_tokens=max_tokens,
            effort=effort,
        )


@dataclass(frozen=True)
class Response:
    text: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    stop_reason: str | None = None


class Provider(ABC):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def local(self) -> bool:
        """Laeuft auf diesem Rechner. Entscheidet ueber vertrauliche Aufgaben."""
        return self.config.local

    @abstractmethod
    def available(self) -> bool:
        """Schnelle Pruefung ohne echte Anfrage. Fuer `jarvis status`."""

    @abstractmethod
    def complete(self, request: Request) -> Response:
        """Eine Anfrage, eine Antwort. Kein Werkzeug, kein Zustand."""

    def __repr__(self) -> str:
        ort = "lokal" if self.local else "extern"
        return f"<{type(self).__name__} {self.name} {self.model} {ort}>"
