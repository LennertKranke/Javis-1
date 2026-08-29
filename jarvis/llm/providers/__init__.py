"""Konkrete Anbieter und die Fabrik, die sie aus der Konfiguration baut."""

from __future__ import annotations

from jarvis.core.config import LLMConfig
from jarvis.core.secrets import SecretStore
from jarvis.llm.provider import Provider
from jarvis.llm.providers.anthropic import AnthropicProvider
from jarvis.llm.providers.ollama import OllamaProvider
from jarvis.llm.providers.static import StaticProvider

__all__ = ["AnthropicProvider", "OllamaProvider", "StaticProvider", "build_providers"]


def build_providers(llm: LLMConfig, secrets: SecretStore) -> dict[str, Provider]:
    """Baut alle konfigurierten Anbieter. Keiner davon nimmt hier Kontakt auf."""
    providers: dict[str, Provider] = {}
    for name, config in llm.providers.items():
        if config.kind == "anthropic":
            providers[name] = AnthropicProvider(config, secrets)
        elif config.kind == "ollama":
            providers[name] = OllamaProvider(config)
        elif config.kind == "static":
            providers[name] = StaticProvider(config)
        else:  # pragma: no cover - von der Konfiguration bereits ausgeschlossen
            raise ValueError(f"Unbekannte Anbieterart: {config.kind!r}")
    return providers
