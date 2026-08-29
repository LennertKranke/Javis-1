"""Anbieter Ollama, ueber die Standardbibliothek.

Hier kein SDK: Ollama laeuft auf demselben Rechner, die API ist ein einzelner
POST, und `urllib` reicht dafuer vollstaendig. Eine Abhaengigkeit fuer eine
HTTP-Anfrage an localhost waere nicht zu rechtfertigen.

Der Opener umgeht bewusst jeden konfigurierten Proxy. Ein System-Proxy fuer
externe Anfragen wuerde eine Anfrage an 127.0.0.1 sonst ins Leere schicken --
ein Fehler, der sich als "Ollama laeuft nicht" tarnt.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from jarvis.core.config import ProviderConfig
from jarvis.llm.provider import (
    Provider,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
    Response,
)

__all__ = ["OllamaProvider"]

DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaProvider(Provider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._base_url = (config.base_url or DEFAULT_BASE_URL).rstrip("/")
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _request(self, path: str, payload: dict | None, timeout: float) -> dict:
        url = f"{self._base_url}{path}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with self._opener.open(req, timeout=timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"{self.name}: HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise ProviderTimeout(f"{self.name}: Zeitueberschreitung") from exc
        except urllib.error.URLError as exc:
            raise ProviderUnavailable(f"{self.name}: nicht erreichbar ({exc.reason})") from exc
        except OSError as exc:
            raise ProviderUnavailable(f"{self.name}: nicht erreichbar") from exc
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{self.name}: unlesbare Antwort") from exc

    def available(self) -> bool:
        try:
            self._request("/api/tags", None, timeout=2.0)
        except ProviderError:
            return False
        return True

    def complete(self, request: Request) -> Response:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.extend({"role": m.role, "content": m.content} for m in request.messages)

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": request.max_tokens or self.config.max_tokens,
            },
        }
        started = time.monotonic()
        body = self._request("/api/chat", payload, timeout=self.config.timeout)
        elapsed = int((time.monotonic() - started) * 1000)

        text = (body.get("message") or {}).get("content", "")
        if not text.strip():
            raise ProviderError(f"{self.name}: leere Antwort")
        return Response(
            text=text,
            provider=self.name,
            model=self.config.model,
            input_tokens=int(body.get("prompt_eval_count") or 0),
            output_tokens=int(body.get("eval_count") or 0),
            latency_ms=elapsed,
            stop_reason=body.get("done_reason"),
        )
