"""Konfiguration, Autonomiestufen, Vorlage."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from jarvis.core.config import (
    DEFAULT_CONFIG_TOML,
    AutonomyLevel,
    Config,
    ConfigError,
    Paths,
    jarvis_home,
)


def laden(home, raw: dict) -> Config:
    return Config.from_mapping(raw, paths=Paths(home=home))


def test_vorlage_ist_gueltig(home):
    config = laden(home, tomllib.loads(DEFAULT_CONFIG_TOML))
    assert config.dry_run is True
    assert set(config.capabilities) == {
        "mail",
        "mail_reply",
        "calendar",
        "research",
        "briefing",
    }
    assert all(int(c.autonomy_level) == 0 for c in config.capabilities.values())
    # Einordnen erreicht niemanden, Antworten schon.
    assert config.capabilities["mail"].requires_outbound is False
    assert config.capabilities["mail_reply"].requires_outbound is True
    # Antworten bleibt bis Phase 3 abgeschaltet, damit ein Umlegen von dry_run
    # es nicht mit freischaltet.
    assert config.capabilities["mail_reply"].enabled is False


def test_beispieldatei_im_repo_stimmt_mit_der_vorlage_ueberein():
    """Sonst laeuft die Datei im Repo still von der Wahrheit im Code weg."""
    beispiel = Path(__file__).resolve().parents[1] / "config.example.toml"
    assert beispiel.read_text(encoding="utf-8") == DEFAULT_CONFIG_TOML


def test_ohne_datei_gilt_die_vorlage(home):
    config = Config.load(home=home)
    assert config.source is None
    assert "mail" in config.capabilities


def test_datei_wird_gelesen_wenn_vorhanden(home):
    (home / "config.toml").write_text(
        "dry_run = false\n[capabilities.mail]\nautonomy_level = 2\nrate_limits = { hour = 1 }\n",
        encoding="utf-8",
    )
    config = Config.load(home=home)
    assert config.source == home / "config.toml"
    assert config.dry_run is False
    assert config.capabilities["mail"].autonomy_level is AutonomyLevel.CATEGORIES


def test_jarvis_home_folgt_der_umgebungsvariable(home, monkeypatch):
    monkeypatch.setenv("JARVIS_HOME", "/tmp/woanders")
    assert jarvis_home() == Path("/tmp/woanders")


def test_pfade_haengen_am_basisverzeichnis(home):
    paths = Paths(home=home)
    assert paths.db_file == home / "state.db"
    assert paths.stop_file == home / "STOP"
    assert paths.log_dir == home / "logs"


# --- Fehler muessen laut sein ---------------------------------------------- #


def test_tippfehler_wird_nicht_verschluckt(home):
    with pytest.raises(ConfigError, match="autonomie_level"):
        laden(home, {"capabilities": {"mail": {"autonomie_level": 3}}})


def test_stufe_ausserhalb_des_bereichs(home):
    with pytest.raises(ConfigError, match="0 bis 3"):
        laden(home, {"capabilities": {"mail": {"autonomy_level": 7, "rate_limits": {"hour": 1}}}})


def test_ausgehende_faehigkeit_braucht_eine_obergrenze(home):
    with pytest.raises(ConfigError, match="rate_limits"):
        laden(home, {"capabilities": {"mail": {"requires_outbound": True}}})


def test_unbekanntes_zeitfenster(home):
    with pytest.raises(ConfigError, match="Zeitfenster"):
        laden(home, {"capabilities": {"mail": {"rate_limits": {"fortnight": 3}}}})


def test_vertrauliche_aufgabe_darf_nicht_nach_draussen(home):
    """Abschnitt 5.2 als Sperre, nicht als Empfehlung."""
    raw = {
        "capabilities": {},
        "llm": {
            "providers": {
                "wolke": {"kind": "anthropic", "model": "claude-opus-5", "local": False},
                "lokal": {"kind": "ollama", "model": "llama3.1:8b", "local": True},
            },
            "tasks": {"personal": {"providers": ["lokal", "wolke"], "confidential": True}},
        },
    }
    with pytest.raises(ConfigError, match="vertraulich"):
        laden(home, raw)


def test_vertrauliche_aufgabe_mit_lokalen_anbietern_ist_in_ordnung(home):
    raw = {
        "capabilities": {},
        "llm": {
            "providers": {"lokal": {"kind": "ollama", "model": "llama3.1:8b", "local": True}},
            "tasks": {"personal": {"providers": ["lokal"], "confidential": True}},
        },
    }
    assert laden(home, raw).llm.tasks["personal"].confidential is True


def test_aufgabe_mit_unbekanntem_anbieter(home):
    raw = {
        "capabilities": {},
        "llm": {"providers": {}, "tasks": {"classify": {"providers": ["gibtesnicht"]}}},
    }
    with pytest.raises(ConfigError, match="nicht definiert"):
        laden(home, raw)


def test_anbieter_ohne_modell(home):
    raw = {"capabilities": {}, "llm": {"providers": {"x": {"kind": "ollama"}}}}
    with pytest.raises(ConfigError, match="model fehlt"):
        laden(home, raw)


def test_unbekannte_anbieterart(home):
    raw = {"capabilities": {}, "llm": {"providers": {"x": {"kind": "gemini", "model": "m"}}}}
    with pytest.raises(ConfigError, match="unbekannt"):
        laden(home, raw)


# --- Autonomiestufen -------------------------------------------------------- #


def test_permits_vergleicht_gewaehrte_mit_verlangter_stufe(home):
    raw = {
        "capabilities": {
            "mail": {"autonomy_level": 1, "rate_limits": {"hour": 1}},
            "briefing": {"autonomy_level": 3, "requires_outbound": False},
        }
    }
    config = laden(home, raw)
    assert config.permits("mail", 0) is True
    assert config.permits("mail", 1) is True
    assert config.permits("mail", 2) is False
    assert config.permits("briefing", 3) is True


def test_abgeschaltete_faehigkeit_darf_nie(home):
    raw = {
        "capabilities": {
            "mail": {"autonomy_level": 3, "enabled": False, "rate_limits": {"hour": 1}}
        }
    }
    assert laden(home, raw).permits("mail", 0) is False


def test_unbekannte_faehigkeit_ist_ein_fehler(home):
    with pytest.raises(ConfigError):
        laden(home, {"capabilities": {}}).capability("mail")


def test_stufen_haben_deutsche_bezeichnungen():
    assert AutonomyLevel(0).label == "Schattenbetrieb"
    assert AutonomyLevel(3).label == "Alles ausser Gesperrtes"
