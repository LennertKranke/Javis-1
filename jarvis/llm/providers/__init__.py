"""Konkrete Anbieter und die Fabrik, die sie aus der Konfiguration baut."""

from __future__ import annotations

from jarvis.core.config import LLMConfig, ProviderConfig
from jarvis.core.secrets import SecretStore
from jarvis.llm.isolation import SubprocessProvider
from jarvis.llm.provider import Provider
from jarvis.llm.providers.anthropic import DEFAULT_SECRET, AnthropicProvider
from jarvis.llm.providers.ollama import OllamaProvider
from jarvis.llm.providers.static import StaticProvider

__all__ = [
    "AnthropicProvider",
    "OllamaProvider",
    "StaticProvider",
    "build_provider",
    "build_providers",
]


def build_provider(config: ProviderConfig, secrets: SecretStore | None = None) -> Provider:
    """Ein Anbieter, ohne Trennung. Das ist der Aufruf im selben Prozess."""
    if config.kind == "anthropic":
        if secrets is None:
            raise ValueError(f"Anbieter {config.name!r} braucht einen Geheimnisspeicher")
        return AnthropicProvider(config, secrets)
    if config.kind == "ollama":
        return OllamaProvider(config)
    if config.kind == "static":
        return StaticProvider(config)
    raise ValueError(f"Unbekannte Anbieterart: {config.kind!r}")


def build_providers(
    llm: LLMConfig, secrets: SecretStore, *, isolation: str | None = None
) -> dict[str, Provider]:
    """Baut alle konfigurierten Anbieter. Keiner davon nimmt hier Kontakt auf.

    Ist die Trennung eingeschaltet (Abschnitt 2.2, siehe `llm/isolation.py`),
    kommt jeder Anbieter in einen eigenen Prozess -- ausser dem statischen.
    Der antwortet mit einer Konstanten, ohne Netz und ohne den Text anzusehen;
    dort gibt es nichts zu trennen, und ein Prozessstart je Aufruf waere reine
    Kosten in Tests und Trockenlaeufen.

    `available()` bleibt im Elternprozess: das ist eine Frage nach Paketen und
    Zugangsdaten, dabei geht kein Fremdtext durch die Haende.
    """
    trennung = llm.isolation if isolation is None else isolation
    providers: dict[str, Provider] = {}
    for name, config in llm.providers.items():
        direkt = build_provider(config, secrets)
        if trennung == "off" or config.kind == "static":
            providers[name] = direkt
            continue
        providers[name] = SubprocessProvider(
            config,
            secret=_geheimnis_von(config, secrets),
            probe=direkt.available,
            mode=trennung,
        )
    return providers


def _geheimnis_von(config: ProviderConfig, secrets: SecretStore):
    """Traege: erst beim Aufruf gefragt, nicht beim Bauen.

    Sonst weckte `jarvis status` den Schluesselbund, nur um eine Tabelle zu
    zeichnen.
    """
    if config.kind != "anthropic":
        return lambda: None
    name = config.secret or DEFAULT_SECRET
    return lambda: secrets.get(name)
