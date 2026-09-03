"""Modellwahl nach Aufgabe, mit Rueckfallkette.

Die Zuordnung Aufgabe -> Anbieter steht in der Konfiguration, nicht im Code
(Abschnitt 5.2). Der Router liest sie und arbeitet die Kette der Reihe nach ab.
Ein ausgefallener Anbieter fuehrt zum naechsten, nicht zum Absturz -- erst wenn
alle ausfallen, gibt es einen Fehler, und der nennt jeden Versuch einzeln.

Die Vertraulichkeitssperre wird hier ein zweites Mal geprueft, obwohl die
Konfiguration sie beim Laden schon geprueft hat. Der Router ist die letzte
Stelle vor der Anfrage; eine im laufenden Betrieb zusammengesetzte Kette darf
nicht an einer Pruefung vorbeikommen, die nur beim Start stattfand.

**Ausfallpause.** Ein Anbieter, der nicht erreichbar war oder nicht antwortete,
wird fuer `[llm] cooldown_seconds` uebersprungen, statt bei jeder Anfrage
erneut mit vollem Zeitlimit versucht zu werden. Ohne sie wartet jede einzelne
Anfrage einer Kette erst das Zeitlimit des ausgefallenen Anbieters ab.

Drei Punkte, an denen die Pause bewusst eng gehalten ist:

* Sie **ueberspringt nur, sie erlaubt nie**. Ein Anbieter, den die
  Vertraulichkeitssperre ausschliesst, wird nicht dadurch zulaessig, dass die
  lokalen pausieren -- die Kette entsteht in `chain()`, vor jeder Pause, und
  eine Aufgabe ohne verbleibenden Anbieter scheitert. Geschlossen ausfallen.
* Sie steht **im Arbeitsspeicher**, nicht in der Datenbank. Anbietergesundheit
  ist Betriebszustand dieses Prozesses und keine Datenkategorie aus Abschnitt 8.
  Nach einem Neustart weiss der Router wieder nichts -- das ist richtig so, er
  probiert dann eben einmal.
* Sie greift nur bei `ProviderUnavailable` und `ProviderTimeout` -- Aussagen
  ueber den *Anbieter*. Eine Verweigerung oder eine unbrauchbare Antwort ist
  eine Aussage ueber die *eine Anfrage* und pausiert nichts.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from jarvis.core.config import LLMConfig
from jarvis.llm.provider import (
    Provider,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
    Response,
)

__all__ = [
    "BEREIT",
    "PAUSIERT",
    "UNBEKANNT",
    "Anbietergesundheit",
    "Anbieterzustand",
    "Attempt",
    "ConfidentialityError",
    "RoutedResponse",
    "Router",
    "RouterError",
]

#: Die drei Zustaende, die der Router ueber einen Anbieter kennt. Mehr weiss er
#: nicht: er sieht nur, was seine eigenen Aufrufe ergeben haben.
BEREIT = "bereit"  # hat in diesem Prozess zuletzt geantwortet
PAUSIERT = "pausiert"  # war nicht erreichbar, wird bis zum Ablauf uebersprungen
UNBEKANNT = "unbekannt"  # nie aufgerufen, oder die Pause ist gerade abgelaufen


class RouterError(RuntimeError):
    """Keine Antwort zu bekommen, oder die Aufgabe ist unbekannt."""


class ConfidentialityError(RouterError):
    """Eine vertrauliche Aufgabe sollte an einen externen Anbieter gehen."""


@dataclass(frozen=True)
class Attempt:
    """Ein Anbieter der Kette und was aus ihm wurde.

    `uebersprungen` unterscheidet zwei Faelle, die sonst gleich aussaehen: der
    Anbieter hat es versucht und ist gescheitert, oder er wurde wegen einer
    laufenden Ausfallpause gar nicht erst gefragt. Fuer `ok` sind beide gleich
    -- eine Antwort kam in keinem Fall.
    """

    provider: str
    error: str | None = None
    uebersprungen: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class Anbieterzustand:
    """Was der Router ueber einen Anbieter weiss, ohne ihn zu fragen."""

    name: str
    zustand: str
    grund: str | None = None
    rest_sekunden: int = 0

    @property
    def nutzbar(self) -> bool:
        """Darf jetzt versucht werden. `unbekannt` heisst versuchen, nicht nein."""
        return self.zustand != PAUSIERT


class Anbietergesundheit:
    """Merkt sich je Anbieter, ob ein Versuch gerade lohnt.

    Bewusst klein: ein Woerterbuch im Arbeitsspeicher, eine Uhr, kein Zaehler
    und keine Heuristik. Die Uhr ist `time.monotonic` -- sie laeuft vorwaerts,
    auch wenn jemand die Systemzeit stellt -- und im Test austauschbar, damit
    keine Pruefung schlafen muss.
    """

    def __init__(
        self,
        *,
        pause_sekunden: int = 60,
        uhr: Callable[[], float] | None = None,
    ) -> None:
        self._pause = max(0, int(pause_sekunden))
        self._uhr = uhr or time.monotonic
        self._pausen: dict[str, tuple[float, str]] = {}
        self._bereit: set[str] = set()

    @property
    def pause_sekunden(self) -> int:
        return self._pause

    def zustand(self, name: str) -> Anbieterzustand:
        eintrag = self._pausen.get(name)
        if eintrag is not None:
            bis, grund = eintrag
            rest = bis - self._uhr()
            if rest > 0:
                # Aufgerundet: "noch 0 Sekunden" waere eine irrefuehrende Auskunft
                # ueber eine Pause, die noch gilt.
                return Anbieterzustand(
                    name=name,
                    zustand=PAUSIERT,
                    grund=grund,
                    rest_sekunden=max(1, int(rest + 0.999)),
                )
            # Abgelaufen. Weggeraeumt wird beim Nachsehen, nicht per Uhrwerk.
            del self._pausen[name]
        if name in self._bereit:
            return Anbieterzustand(name=name, zustand=BEREIT)
        return Anbieterzustand(name=name, zustand=UNBEKANNT)

    def melde_erfolg(self, name: str) -> None:
        self._pausen.pop(name, None)
        self._bereit.add(name)

    def melde_ausfall(self, name: str, exc: ProviderError) -> bool:
        """Wahr, wenn dieser Ausfall eine Pause ausgeloest hat.

        Nur `nicht erreichbar` und `zu langsam` sagen etwas ueber den Anbieter.
        Eine Verweigerung oder eine unbrauchbare Antwort gehoert zur Anfrage;
        deswegen den Anbieter zu sperren hiesse, die naechste Anfrage fuer eine
        Eigenschaft der vorigen zu bestrafen.
        """
        # Ein Ausfall macht ein frueheres `bereit` ungueltig: sonst stuende der
        # Anbieter nach Ablauf der Pause wieder als bereit da, ohne dass seither
        # jemand mit ihm gesprochen haette.
        self._bereit.discard(name)
        if self._pause <= 0 or not isinstance(exc, ProviderUnavailable | ProviderTimeout):
            return False
        self._pausen[name] = (self._uhr() + self._pause, type(exc).__name__)
        return True

    def uebersicht(self) -> dict[str, Anbieterzustand]:
        """Alle Anbieter, ueber die etwas bekannt ist."""
        namen = set(self._pausen) | self._bereit
        return {name: self.zustand(name) for name in sorted(namen)}


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
        uhr: Callable[[], float] | None = None,
    ) -> None:
        self._llm = llm
        self._providers = providers
        self._log = logger or logging.getLogger("jarvis.router")
        self._gesundheit = Anbietergesundheit(
            pause_sekunden=llm.cooldown_seconds,
            uhr=uhr,
        )

    @property
    def gesundheit(self) -> Anbietergesundheit:
        """Der Gesundheitsstand dieses Routers. Auskunft, keine Entscheidung."""
        return self._gesundheit

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
            zustand = self._gesundheit.zustand(provider.name)
            if not zustand.nutzbar:
                # Nicht gefragt, also auch kein Zeitlimit abgewartet. Der Grund
                # steht dabei, sonst sieht die Kette aus wie ein stiller Sprung.
                attempts.append(
                    Attempt(
                        provider=provider.name,
                        error=f"pausiert nach {zustand.grund}, noch {zustand.rest_sekunden}s",
                        uebersprungen=True,
                    )
                )
                self._log.info(
                    "Anbieter uebersprungen",
                    extra={
                        "task": task,
                        "provider": provider.name,
                        "zustand": zustand.zustand,
                        "grund": zustand.grund,
                        "rest_sekunden": zustand.rest_sekunden,
                    },
                )
                continue
            try:
                response = provider.complete(request)
            except ProviderError as exc:
                pausiert = self._gesundheit.melde_ausfall(provider.name, exc)
                attempts.append(Attempt(provider=provider.name, error=str(exc)))
                self._log.warning(
                    "Anbieter ausgefallen",
                    extra={
                        "task": task,
                        "provider": provider.name,
                        "error": str(exc),
                        "pausiert_sekunden": self._gesundheit.pause_sekunden if pausiert else 0,
                    },
                )
                continue
            self._gesundheit.melde_erfolg(provider.name)
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
