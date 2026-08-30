"""Der auswertende Prozess. Bekommt Text, gibt JSON, kann sonst nichts.

Das ist Abschnitt 2.2 als eigener Prozess statt als Vorsatz. Hier laeuft der
Modellaufruf -- und damit alles, was fremden Text sieht. Was hier fehlt, ist
der Punkt:

  * kein Gmail- und kein Kalender-Zugang. Die Zugangsdaten dafuer liegen im
    Elternprozess und werden nicht weitergereicht.
  * kein Pfad zur Datenbank, kein `JARVIS_HOME`. Was hier passiert, kann den
    Zustand von JARVIS nicht anfassen.
  * kein Gatter, kein Protokoll, keine Faehigkeit. Die Module dafuer werden
    nicht importiert.

Hereingegeben wird ein einzelnes JSON-Objekt auf der Standardeingabe:
Anbieterkonfiguration, gegebenenfalls dessen Schluessel, und die Anfrage. Der
Schluessel kommt ueber die Eingabe und nicht ueber die Umgebung oder die
Kommandozeile -- sonst stuende er in `ps`.

Herausgegeben wird eine einzelne Zeile JSON auf der Standardausgabe. Alles
andere gehoert auf die Standardfehlerausgabe; der Elternprozess liest bewusst
nur die letzte Zeile, damit die Antwort auch dann noch lesbar ist, wenn eine
Bibliothek etwas dazwischenschreibt.
"""

from __future__ import annotations

import json
import sys
from typing import Any

__all__ = ["antwort_auf", "main"]

#: Fehlerarten, die der Elternprozess wieder in Ausnahmen uebersetzt.
UNAVAILABLE = "unavailable"
TIMEOUT = "timeout"
REFUSED = "refused"
ERROR = "error"


def _fehlerart(exc: Exception) -> str:
    from jarvis.llm.provider import ProviderRefused, ProviderTimeout, ProviderUnavailable

    if isinstance(exc, ProviderUnavailable):
        return UNAVAILABLE
    if isinstance(exc, ProviderTimeout):
        return TIMEOUT
    if isinstance(exc, ProviderRefused):
        return REFUSED
    return ERROR


def antwort_auf(eingabe: dict[str, Any]) -> dict[str, Any]:
    """Baut genau einen Anbieter und stellt genau eine Anfrage.

    Getrennt von `main`, damit sich der ganze Weg ohne Prozess pruefen laesst.
    """
    from jarvis.core.config import ProviderConfig
    from jarvis.llm.provider import Message, ProviderError, Request

    roh_anbieter = dict(eingabe["provider"])
    roh_anfrage = dict(eingabe["request"])
    geheimnis = eingabe.get("secret")

    config = ProviderConfig(**roh_anbieter)
    anfrage = Request(
        messages=tuple(
            Message(role=m["role"], content=m["content"]) for m in roh_anfrage["messages"]
        ),
        system=roh_anfrage.get("system"),
        max_tokens=roh_anfrage.get("max_tokens"),
        effort=roh_anfrage.get("effort"),
    )

    try:
        anbieter = _baue(config, geheimnis)
        antwort = anbieter.complete(anfrage)
    except ProviderError as exc:
        return {"ok": False, "error": str(exc), "kind": _fehlerart(exc)}
    except Exception as exc:  # nichts darf als Prozessabsturz herauskommen
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "kind": ERROR}

    return {
        "ok": True,
        "response": {
            "text": antwort.text,
            "provider": antwort.provider,
            "model": antwort.model,
            "input_tokens": antwort.input_tokens,
            "output_tokens": antwort.output_tokens,
            "latency_ms": antwort.latency_ms,
            "stop_reason": antwort.stop_reason,
        },
    }


def _baue(config: Any, geheimnis: str | None) -> Any:
    """Genau ein Anbieter, mit genau einem Geheimnis.

    Es wird kein Schluesselbund gefragt und keine Umgebung durchsucht: was der
    Elternprozess nicht mitgibt, gibt es hier nicht.
    """
    from jarvis.llm.providers.anthropic import AnthropicProvider
    from jarvis.llm.providers.ollama import OllamaProvider
    from jarvis.llm.providers.static import StaticProvider

    if config.kind == "anthropic":
        return AnthropicProvider(config, _EinGeheimnis(geheimnis))
    if config.kind == "ollama":
        return OllamaProvider(config)
    if config.kind == "static":
        return StaticProvider(config)
    raise ValueError(f"Unbekannte Anbieterart: {config.kind!r}")


class _EinGeheimnis:
    """Ein Geheimnisspeicher, der genau einen Wert kennt und sonst nichts."""

    def __init__(self, wert: str | None) -> None:
        self._wert = wert

    def describe(self) -> str:
        return "vom Elternprozess uebergeben"

    def get(self, key: str) -> str | None:
        return self._wert

    def has(self, key: str) -> bool:
        return bool(self._wert)

    def require(self, key: str) -> str:
        if not self._wert:
            from jarvis.core.secrets import SecretsError

            raise SecretsError(f"Zugangsdaten {key!r} wurden nicht uebergeben")
        return self._wert


def main() -> int:
    try:
        eingabe = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"unlesbare Eingabe: {exc}", "kind": ERROR}))
        return 1
    ergebnis = antwort_auf(eingabe)
    print(json.dumps(ergebnis, ensure_ascii=False))
    return 0 if ergebnis.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
