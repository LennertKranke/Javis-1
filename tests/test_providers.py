"""Anbieter: Fehlerzuordnung und die beiden Antwortzustaende, die keine sind."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from jarvis.core.config import ProviderConfig
from jarvis.core.secrets import SecretStore
from jarvis.llm.provider import (
    ProviderError,
    ProviderRefused,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
)
from jarvis.llm.providers.anthropic import AnthropicProvider
from jarvis.llm.providers.ollama import OllamaProvider
from jarvis.llm.providers.static import StaticProvider


def antwort(text="{}", stop_reason="end_turn", category=None):
    blocks = [SimpleNamespace(type="text", text=text)] if text else []
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category=category) if category else None,
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )


class FakeClient:
    def __init__(self, ergebnis):
        self._ergebnis = ergebnis
        self.letzte_parameter: dict | None = None
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.letzte_parameter = kwargs
        if isinstance(self._ergebnis, Exception):
            raise self._ergebnis
        return self._ergebnis


def anthropic_provider(monkeypatch, ergebnis):
    config = ProviderConfig(
        name="anthropic",
        kind="anthropic",
        model="claude-opus-5",
        local=False,
        secret="anthropic_api_key",
        max_tokens=16000,
        effort="high",
    )
    provider = AnthropicProvider(config, SecretStore([]))
    client = FakeClient(ergebnis)
    monkeypatch.setattr(provider, "_ensure_client", lambda: client)
    return provider, client


def test_anthropic_normale_antwort(monkeypatch):
    provider, client = anthropic_provider(monkeypatch, antwort('{"kategorie": "termin"}'))
    ergebnis = provider.complete(Request.single("hallo", system="sei knapp"))

    assert ergebnis.text == '{"kategorie": "termin"}'
    assert ergebnis.provider == "anthropic"
    assert (ergebnis.input_tokens, ergebnis.output_tokens) == (11, 7)
    assert client.letzte_parameter["model"] == "claude-opus-5"
    assert client.letzte_parameter["system"] == "sei knapp"
    assert client.letzte_parameter["thinking"] == {"type": "adaptive"}
    assert client.letzte_parameter["output_config"] == {"effort": "high"}


def test_anthropic_anfrage_schlaegt_die_anbietervorgabe(monkeypatch):
    provider, client = anthropic_provider(monkeypatch, antwort())
    provider.complete(Request.single("hallo", max_tokens=512, effort="low"))
    assert client.letzte_parameter["max_tokens"] == 512
    assert client.letzte_parameter["output_config"] == {"effort": "low"}


def test_verweigerung_wird_ein_fehler(monkeypatch):
    """Sonst kaeme Text zurueck, der aussieht wie eine Antwort, aber keine ist."""
    provider, _ = anthropic_provider(
        monkeypatch, antwort("Ich kann das nicht.", stop_reason="refusal", category="cyber")
    )
    with pytest.raises(ProviderRefused, match="cyber"):
        provider.complete(Request.single("hallo"))


def test_abgeschnittene_antwort_wird_ein_fehler(monkeypatch):
    provider, _ = anthropic_provider(
        monkeypatch, antwort('{"kategorie": "term', stop_reason="max_tokens")
    )
    with pytest.raises(ProviderError, match="abgeschnitten"):
        provider.complete(Request.single("hallo"))


def test_leere_antwort_wird_ein_fehler(monkeypatch):
    provider, _ = anthropic_provider(monkeypatch, antwort("   "))
    with pytest.raises(ProviderError, match="leere Antwort"):
        provider.complete(Request.single("hallo"))


def test_fehlender_schluessel_meldet_nicht_verfuegbar():
    config = ProviderConfig(
        name="anthropic",
        kind="anthropic",
        model="claude-opus-5",
        local=False,
        secret="anthropic_api_key",
    )
    provider = AnthropicProvider(config, SecretStore([]))
    assert provider.available() is False
    with pytest.raises(ProviderUnavailable):
        provider.complete(Request.single("hallo"))


@pytest.mark.parametrize(
    ("sdk_fehler", "erwartet"),
    [
        ("APITimeoutError", ProviderTimeout),
        ("APIConnectionError", ProviderUnavailable),
        ("RateLimitError", ProviderUnavailable),
    ],
)
def test_sdk_fehler_werden_uebersetzt(monkeypatch, sdk_fehler, erwartet):
    """Der Router entscheidet nach Fehlertyp, also muss die Zuordnung stimmen."""
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    if sdk_fehler == "RateLimitError":
        response = httpx2.Response(429, request=request)
        fehler = anthropic.RateLimitError("zu viel", response=response, body=None)
    else:
        fehler = getattr(anthropic, sdk_fehler)(request=request)

    provider, _ = anthropic_provider(monkeypatch, fehler)
    with pytest.raises(erwartet):
        provider.complete(Request.single("hallo"))


# --- Ollama ---------------------------------------------------------------- #


def ollama_provider():
    return OllamaProvider(
        ProviderConfig(
            name="ollama",
            kind="ollama",
            model="llama3.1:8b",
            local=True,
            base_url="http://127.0.0.1:11434",
        )
    )


def test_ollama_normale_antwort(monkeypatch):
    provider = ollama_provider()
    aufgezeichnet = {}

    def fake(pfad, payload, timeout):
        aufgezeichnet["pfad"] = pfad
        aufgezeichnet["payload"] = payload
        return {"message": {"content": '{"a": 1}'}, "prompt_eval_count": 5, "eval_count": 3}

    monkeypatch.setattr(provider, "_request", fake)
    ergebnis = provider.complete(Request.single("hallo", system="kurz"))

    assert ergebnis.text == '{"a": 1}'
    assert ergebnis.input_tokens == 5
    assert aufgezeichnet["pfad"] == "/api/chat"
    assert aufgezeichnet["payload"]["stream"] is False
    assert aufgezeichnet["payload"]["messages"][0] == {"role": "system", "content": "kurz"}


def test_ollama_leere_antwort(monkeypatch):
    provider = ollama_provider()
    monkeypatch.setattr(provider, "_request", lambda *a, **k: {"message": {"content": ""}})
    with pytest.raises(ProviderError, match="leere Antwort"):
        provider.complete(Request.single("hallo"))


def test_ollama_nicht_erreichbar_ist_kein_absturz(monkeypatch):
    provider = ollama_provider()

    def fake(*args, **kwargs):
        raise ProviderUnavailable("aus")

    monkeypatch.setattr(provider, "_request", fake)
    assert provider.available() is False


def test_ollama_umgeht_den_proxy(monkeypatch):
    """Ein System-Proxy wuerde eine Anfrage an 127.0.0.1 ins Leere schicken.

    `build_opener(ProxyHandler({}))` setzt keinen leeren Proxy ein, sondern
    entfernt den Proxy-Handler vollstaendig. Geprueft wird deshalb seine
    Abwesenheit -- und zum Vergleich, dass der Standard-Opener ihn haette.
    """
    import urllib.request

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:8080")

    eigener = ollama_provider()._opener
    assert not any(isinstance(h, urllib.request.ProxyHandler) for h in eigener.handlers)

    standard = urllib.request.build_opener()
    assert any(isinstance(h, urllib.request.ProxyHandler) for h in standard.handlers)


# --- Statisch --------------------------------------------------------------- #


def test_statischer_anbieter_braucht_nichts():
    provider = StaticProvider(
        ProviderConfig(name="trocken", kind="static", model="static", local=True, reply="{}")
    )
    assert provider.available() is True
    assert provider.complete(Request.single("beliebig")).text == "{}"
