"""Anbieter Anthropic, ueber das offizielle SDK.

Das SDK wird verzoegert importiert. So bleiben `core/` und die gesamte
Testsuite lauffaehig, wenn das Paket fehlt -- und `jarvis status` kann melden,
dass es fehlt, statt beim Start zu scheitern.

Zwei Antwortzustaende werden zu Fehlern gemacht, statt sie durchzureichen:
eine Verweigerung (`stop_reason == "refusal"`) und eine abgeschnittene Antwort
(`"max_tokens"`). Beides liefert Text, der wie eine Antwort aussieht, aber
keine ist. Als Fehler landen sie beim Router, der auf das lokale Modell
zurueckfaellt.
"""

from __future__ import annotations

import time
from typing import Any

from jarvis.core.config import ProviderConfig
from jarvis.core.secrets import SecretsError, SecretStore
from jarvis.llm.provider import (
    Provider,
    ProviderError,
    ProviderRefused,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
    Response,
)

__all__ = ["AnthropicProvider"]

DEFAULT_SECRET = "anthropic_api_key"


class AnthropicProvider(Provider):
    def __init__(self, config: ProviderConfig, secrets: SecretStore) -> None:
        super().__init__(config)
        self._secrets = secrets
        self._client: Any = None

    @property
    def _secret_name(self) -> str:
        return self.config.secret or DEFAULT_SECRET

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return self._secrets.has(self._secret_name)

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:
            raise ProviderUnavailable("Paket 'anthropic' ist nicht installiert (uv sync)") from exc
        try:
            key = self._secrets.require(self._secret_name)
        except SecretsError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        self._client = anthropic.Anthropic(api_key=key, timeout=self.config.timeout, max_retries=2)
        return self._client

    def complete(self, request: Request) -> Response:
        import anthropic

        client = self._ensure_client()
        effort = request.effort or self.config.effort
        params: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": request.max_tokens or self.config.max_tokens,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            # Adaptives Denken: das Modell entscheidet selbst ueber die Tiefe.
            # Die Denk-Token teilen sich das Budget mit der Antwort, deshalb ist
            # max_tokens grosszuegig gesetzt.
            "thinking": {"type": "adaptive"},
        }
        if request.system:
            params["system"] = request.system
        if effort:
            params["output_config"] = {"effort": effort}

        started = time.monotonic()
        try:
            message = client.messages.create(**params)
        except anthropic.APITimeoutError as exc:
            raise ProviderTimeout(f"{self.name}: Zeitueberschreitung") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderUnavailable(f"{self.name}: nicht erreichbar") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderUnavailable(f"{self.name}: Kontingent erschoepft") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"{self.name}: HTTP {exc.status_code}") from exc
        elapsed = int((time.monotonic() - started) * 1000)

        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) or "ohne Angabe"
            raise ProviderRefused(f"{self.name}: Antwort verweigert ({category})")
        if message.stop_reason == "max_tokens":
            raise ProviderError(f"{self.name}: Antwort bei max_tokens abgeschnitten, unbrauchbar")

        text = "".join(block.text for block in message.content if block.type == "text")
        if not text.strip():
            raise ProviderError(f"{self.name}: leere Antwort")

        usage = message.usage
        return Response(
            text=text,
            provider=self.name,
            model=self.config.model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            latency_ms=elapsed,
            stop_reason=message.stop_reason,
        )
