"""Ein Anbieter, der immer dasselbe sagt.

Er existiert wegen Abschnitt 8.3: kein Feature ohne Trockenlauf-Pfad. Damit
laesst sich die gesamte Kette -- Normalisierung, Router, Schemapruefung,
Gatter, Protokoll -- ohne Netz, ohne Schluessel und ohne Kosten durchspielen.
In Tests ersetzt er Attrappen, die sonst in jeder Datei neu entstuenden.
"""

from __future__ import annotations

from jarvis.core.config import ProviderConfig
from jarvis.llm.provider import Provider, Request, Response

__all__ = ["StaticProvider"]


class StaticProvider(Provider):
    def __init__(self, config: ProviderConfig) -> None:
        super().__init__(config)
        self._reply = config.reply if config.reply is not None else "{}"

    def available(self) -> bool:
        return True

    def complete(self, request: Request) -> Response:
        return Response(
            text=self._reply,
            provider=self.name,
            model=self.config.model,
            latency_ms=0,
            stop_reason="end_turn",
        )
