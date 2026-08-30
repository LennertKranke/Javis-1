"""Der Vertrag, den jede Faehigkeit erfuellt (Abschnitt 5.1).

Der Ablauf ist immer derselbe: `poll` findet etwas, `decide` beurteilt es,
`act` fuehrt aus. Die Trennung ist keine Ordnungsliebe, sondern Prinzip 2.2:
`decide` sieht fremden Inhalt und darf deshalb nichts tun; `act` tut etwas und
sieht deshalb keinen fremden Inhalt mehr, sondern nur noch das Ergebnis.

Die entscheidende Stelle ist `Decision`. Sie hat zwei getrennte Haelften:

  fields   kommt vom Modell. Schema-geprueft, enthaelt nie ein Ziel.
  targets  kommt von deterministischem Code aus vertrauenswuerdigen Quellen --
           vor allem das Ziel, daneben was der deterministische Teil sonst
           ausgerechnet hat.

Prinzip 2.1 ist genau diese Trennung. Damit sie nicht bloss eine Verabredung
bleibt, prueft `Decision` beim Anlegen, dass in `fields` kein Zielfeld steckt --
eine Faehigkeit kann ein Ziel also nicht aus Versehen aus der Modellantwort
uebernehmen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from jarvis.core.sanitize import SanitizedText
from jarvis.llm.schema import is_target_name

__all__ = [
    "NOOP_ACTIONS",
    "Decision",
    "Event",
    "Result",
    "Skill",
    "TargetMismatch",
    "available_skills",
    "register_skill",
]

# Entscheidungen, nach denen nichts geschieht. "hold" heisst: es gaebe etwas zu
# tun, aber eine Regel haelt es zurueck -- das ist kein blockiertes Gatter.
NOOP_ACTIONS = frozenset({"skip", "hold", "none"})


class TargetMismatch(RuntimeError):
    """Die Ziele einer aufbewahrten Entscheidung stimmen nicht mehr."""


@dataclass(frozen=True)
class Event:
    """Etwas ist aufgetaucht, das beurteilt werden soll.

    `payload` und `key` stammen aus vertrauenswuerdiger Quelle -- bei E-Mail
    also aus den Headern und der API-Antwort. `content` ist der normalisierte
    Fremdtext und das Einzige, was ein Modell je zu sehen bekommt.
    """

    skill: str
    key: str
    summary: str
    payload: Any = None
    content: SanitizedText | None = None


@dataclass(frozen=True)
class Decision:
    skill: str
    event_key: str
    action: str
    reason: str
    decided_by: str
    fields: Mapping[str, Any] = field(default_factory=dict)
    targets: Mapping[str, Any] = field(default_factory=dict)
    model: str | None = None

    def __post_init__(self) -> None:
        verdaechtig = sorted(name for name in self.fields if is_target_name(name))
        if verdaechtig:
            raise ValueError(
                f"Entscheidung von {self.skill!r}: die Felder {', '.join(verdaechtig)} sehen "
                f"nach einem Ziel aus und stehen in der Modellhaelfte. Prinzip 2.1: Ziele "
                f"gehoeren nach targets und werden aus den Originaldaten berechnet."
            )

    @property
    def is_noop(self) -> bool:
        """Nichts zu tun. Kommt gar nicht erst ans Gatter und verbraucht nichts."""
        return self.action in NOOP_ACTIONS

    @property
    def audit_detail(self) -> dict[str, Any]:
        """Was vom Vorgang ins Protokoll gehoert -- ohne den Fremdtext selbst."""
        detail: dict[str, Any] = {
            "action": self.action,
            "decided_by": self.decided_by,
            "reason": self.reason,
        }
        detail.update({f"feld_{k}": v for k, v in self.fields.items()})
        if self.model:
            detail["model"] = self.model
        return detail


@dataclass(frozen=True)
class Result:
    skill: str
    event_key: str
    performed: bool
    detail: Mapping[str, Any] = field(default_factory=dict)
    error: str | None = None


class Skill(ABC):
    """Basisklasse. `name` ist zugleich der Schluessel in [capabilities]."""

    name: str = ""
    autonomy_level: int = 0
    requires_outbound: bool = False

    @abstractmethod
    def poll(self) -> list[Event]:
        """Findet, was zu beurteilen ist. Keine Aktion nach aussen."""

    @abstractmethod
    def decide(self, event: Event) -> Decision:
        """Beurteilt ein Ereignis. Ruft hoechstens das Modell, ohne Werkzeuge."""

    @abstractmethod
    def act(self, decision: Decision) -> Result:
        """Fuehrt aus. Deterministisch, ohne Modell, ohne fremden Text."""

    def verify_targets(self, decision: Decision) -> Decision:
        """Baut die Ziele aus der vertrauenswuerdigen Quelle neu und vergleicht.

        Eine gespeicherte Entscheidung ist keine vertrauenswuerdige Quelle. Sie
        hat in der Datenbank gelegen, moeglicherweise tagelang: das Postfach
        kann sich geaendert haben, ein Entwurf geloescht, eine Zeile von Hand
        angefasst worden sein. Wer eine aufbewahrte Entscheidung ausfuehrt,
        muss ihre Ziele vorher gegen die Quelle pruefen, aus der sie stammen.

        Der Rueckgabewert ist die gepruefte Entscheidung -- gegebenenfalls mit
        frisch berechneten Zielen. Passt etwas nicht, wird `TargetMismatch`
        geworfen und nichts ausgefuehrt.

        Die Vorgabe verweigert, sobald es ueberhaupt Ziele gibt. Eine
        Faehigkeit, die aufbewahrte Entscheidungen ausfuehren laesst, muss die
        Pruefung also ausdruecklich schreiben -- Vergessen faellt auf, statt
        stillschweigend durchzugehen.
        """
        if decision.targets:
            raise NotImplementedError(
                f"{type(self).__name__}.verify_targets fehlt. Eine aufbewahrte "
                f"Entscheidung mit Zielen darf nicht ungeprueft ausgefuehrt werden."
            )
        return decision

    def after(  # noqa: B027 - absichtlich leer: ein freiwilliger Haken, nichts Abstraktes
        self, event: Event, decision: Decision, disposition: str, result: Result | None
    ) -> None:
        """Buchfuehrung nach jedem Vorgang, auch im Trockenlauf.

        Wird immer aufgerufen, gleich wie das Gatter entschieden hat -- eine
        Faehigkeit soll auch festhalten koennen, was sie *nicht* getan hat.
        """


_REGISTRY: dict[str, type[Skill]] = {}


def register_skill(cls: type[Skill]) -> type[Skill]:
    """Faehigkeiten tragen sich selbst ein -- kein Eingriff in den Kern."""
    if not cls.name:
        raise ValueError(f"{cls.__name__}: name fehlt")
    _REGISTRY[cls.name] = cls
    return cls


def available_skills() -> dict[str, type[Skill]]:
    return dict(_REGISTRY)
