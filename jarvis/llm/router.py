"""Modellwahl nach Aufgabe, mit Rueckfallkette.

Die Zuordnung Aufgabe -> Anbieter steht in der Konfiguration, nicht im Code
(Abschnitt 5.2). Der Router liest sie und arbeitet die Kette der Reihe nach ab.
Ein ausgefallener Anbieter fuehrt zum naechsten, nicht zum Absturz -- erst wenn
alle ausfallen, gibt es einen Fehler, und der nennt jeden Versuch einzeln.

Die Vertraulichkeitssperre wird hier ein zweites Mal geprueft, obwohl die
Konfiguration sie beim Laden schon geprueft hat. Der Router ist die letzte
Stelle vor der Anfrage; eine im laufenden Betrieb zusammengesetzte Kette darf
nicht an einer Pruefung vorbeikommen, die nur beim Start stattfand.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from jarvis.core.config import LLMConfig
from jarvis.llm.provider import Provider, ProviderError, Request, Response

__all__ = ["Attempt", "ConfidentialityError", "RoutedResponse", "Router", "RouterError"]


class RouterError(RuntimeError):
    """Keine Antwort zu bekommen, oder die Aufgabe ist unbekannt."""


class ConfidentialityError(RouterError):
    """Eine vertrauliche Aufgabe sollte an einen externen Anbieter gehen."""


@dataclass(frozen=True)
class Attempt:
    provider: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class RoutedResponse:
    response: Response
    task: str
    attempts: tuple[Attempt, ...]


class Router:
    def __init__(
        self,
        llm: LLMConfig,
        providers: Mapping[str, Provider],
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._llm = llm
        self._providers = providers
        self._log = logger or logging.getLogger("jarvis.router")

    def chain(self, task: str) -> tuple[Provider, ...]:
        """Die Anbieterkette fuer eine Aufgabe, in der Reihenfolge des Versuchs."""
        route = self._llm.tasks.get(task)
        if route is None:
            known = ", ".join(sorted(self._llm.tasks)) or "keine"
            raise RouterError(f"Unbekannte Aufgabe {task!r} (bekannt: {known})")

        providers = []
        for name in route.providers:
            provider = self._providers.get(name)
            if provider is None:
                raise RouterError(f"Aufgabe {task!r}: Anbieter {name!r} ist nicht gebaut")
            if route.confidential and not provider.local:
                raise ConfidentialityError(
                    f"Aufgabe {task!r} ist vertraulich, {name!r} ist kein lokaler Anbieter. "
                    f"Abschnitt 5.2: sensible persoenliche Daten bleiben auf dem Geraet."
                )
            providers.append(provider)
        return tuple(providers)

    def complete(self, task: str, request: Request) -> RoutedResponse:
        route = self._llm.tasks.get(task)
        chain = self.chain(task)

        if route is not None:
            # Aufgabenweite Vorgaben, sofern die Anfrage selbst nichts sagt.
            if request.effort is None and route.effort:
                request = Request(
                    messages=request.messages,
                    system=request.system,
                    max_tokens=request.max_tokens,
                    effort=route.effort,
                    metadata=request.metadata,
                )
            if request.max_tokens is None and route.max_tokens:
                request = Request(
                    messages=request.messages,
                    system=request.system,
                    max_tokens=route.max_tokens,
                    effort=request.effort,
                    metadata=request.metadata,
                )

        attempts: list[Attempt] = []
        for provider in chain:
            try:
                response = provider.complete(request)
            except ProviderError as exc:
                attempts.append(Attempt(provider=provider.name, error=str(exc)))
                self._log.warning(
                    "Anbieter ausgefallen",
                    extra={"task": task, "provider": provider.name, "error": str(exc)},
                )
                continue
            attempts.append(Attempt(provider=provider.name))
            self._log.info(
                "Antwort erhalten",
                extra={
                    "task": task,
                    "provider": provider.name,
                    "model": provider.model,
                    "latency_ms": response.latency_ms,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                },
            )
            return RoutedResponse(response=response, task=task, attempts=tuple(attempts))

        summary = "; ".join(f"{a.provider}: {a.error}" for a in attempts) or "keine Anbieter"
        raise RouterError(f"Aufgabe {task!r}: kein Anbieter konnte antworten ({summary})")
