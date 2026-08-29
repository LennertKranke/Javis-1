from __future__ import annotations

import pytest

from jarvis.core.config import Config, Paths
from jarvis.core.db import open_database


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Ein leeres JARVIS-Basisverzeichnis, isoliert vom echten Nutzer."""
    h = tmp_path / "jarvis-home"
    h.mkdir()
    monkeypatch.setenv("JARVIS_HOME", str(h))
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "none")
    monkeypatch.delenv("NO_COLOR", raising=False)
    return h


@pytest.fixture
def conn(home):
    connection = open_database(home / "state.db")
    yield connection
    connection.close()


def build_config(
    home,
    *,
    dry_run: bool = True,
    level: int = 0,
    limits: dict | None = None,
    enabled: bool = True,
    outbound: bool = True,
) -> Config:
    """Kleine Konfiguration mit genau einer Faehigkeit `mail`."""
    capability: dict = {
        "autonomy_level": level,
        "requires_outbound": outbound,
        "enabled": enabled,
    }
    if outbound:
        capability["rate_limits"] = limits if limits is not None else {"hour": 3}
    raw = {
        "dry_run": dry_run,
        "capabilities": {"mail": capability},
        "llm": {
            "providers": {
                "trocken": {"kind": "static", "model": "static", "local": True, "reply": "{}"}
            },
            "tasks": {"classify": {"providers": ["trocken"]}},
        },
    }
    return Config.from_mapping(raw, paths=Paths(home=home))
