"""Zugangsdaten: Keychain zuerst, Umgebung als Rueckfall."""

from __future__ import annotations

import subprocess

import pytest

from jarvis.core.secrets import (
    EnvironmentBackend,
    KeychainBackend,
    SecretsError,
    SecretStore,
    default_store,
)


def test_umgebung_liest_mit_praefix(monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_ANTHROPIC_API_KEY", "geheim")
    assert EnvironmentBackend().get("anthropic_api_key") == "geheim"


def test_umgebung_ohne_eintrag(monkeypatch):
    monkeypatch.delenv("JARVIS_SECRET_FEHLT", raising=False)
    assert EnvironmentBackend().get("fehlt") is None


def test_leerer_wert_zaehlt_als_fehlend(monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_LEER", "   ")
    assert EnvironmentBackend().get("leer") is None


def test_erster_treffer_gewinnt(monkeypatch):
    class Immer:
        name = "immer"

        def available(self):
            return True

        def get(self, key):
            return "aus-keychain"

    monkeypatch.setenv("JARVIS_SECRET_X", "aus-umgebung")
    store = SecretStore([Immer(), EnvironmentBackend()])
    assert store.get("x") == "aus-keychain"


def test_rueckfall_wenn_der_erste_nichts_hat(monkeypatch):
    class Nie:
        name = "nie"

        def available(self):
            return True

        def get(self, key):
            return None

    monkeypatch.setenv("JARVIS_SECRET_X", "aus-umgebung")
    assert SecretStore([Nie(), EnvironmentBackend()]).get("x") == "aus-umgebung"


def test_fehlendes_geheimnis_nennt_den_weg_zur_keychain():
    with pytest.raises(SecretsError, match="add-generic-password"):
        SecretStore([]).require("anthropic_api_key")


def test_fehlermeldung_verraet_keinen_wert(monkeypatch):
    store = SecretStore([EnvironmentBackend()])
    monkeypatch.setenv("JARVIS_SECRET_DA", "streng-geheim")
    assert store.require("da") == "streng-geheim"
    with pytest.raises(SecretsError) as exc:
        store.require("fehlt")
    assert "streng-geheim" not in str(exc.value)


def test_keychain_ruft_das_richtige_kommando(monkeypatch):
    aufgezeichnet = {}

    def fake_run(cmd, **kwargs):
        aufgezeichnet["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="wert\n", stderr="")

    monkeypatch.setattr("jarvis.core.secrets.subprocess.run", fake_run)
    backend = KeychainBackend()
    monkeypatch.setattr(type(backend), "available", lambda self: True)

    assert backend.get("anthropic_api_key") == "wert"
    assert aufgezeichnet["cmd"] == [
        "security",
        "find-generic-password",
        "-s",
        "jarvis",
        "-a",
        "anthropic_api_key",
        "-w",
    ]


def test_keychain_ohne_treffer(monkeypatch):
    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 44, stdout="", stderr="not found")

    monkeypatch.setattr("jarvis.core.secrets.subprocess.run", fake_run)
    backend = KeychainBackend()
    monkeypatch.setattr(type(backend), "available", lambda self: True)
    assert backend.get("fehlt") is None


def test_keychain_ist_auf_nicht_macos_nicht_verfuegbar(monkeypatch):
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "linux")
    assert KeychainBackend().available() is False


def test_backend_laesst_sich_erzwingen(monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    assert default_store().backends == ("environment",)
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "none")
    assert default_store().backends == ()
    assert default_store().describe() == "keine"


# --------------------------------------------------------------------------- #
# Sichtbarkeit der Entwicklungsausnahme
# --------------------------------------------------------------------------- #


def test_nur_keychain_entspricht_abschnitt_4():
    assert SecretStore([KeychainBackend()]).keychain_only is (KeychainBackend().available())


def test_umgebung_in_der_kette_ist_keine_reine_keychain():
    speicher = SecretStore([EnvironmentBackend()])
    assert speicher.keychain_only is False
    assert "environment" in speicher.describe()


def test_leerer_speicher_behauptet_nicht_keychain_zu_sein():
    """Sonst saehe "keine" aus wie "alles in Ordnung"."""
    assert SecretStore([]).keychain_only is False


# --------------------------------------------------------------------------- #
# Keychain-only als Produktionsverhalten (Abschnitt 4)
# --------------------------------------------------------------------------- #


def test_auf_macos_gibt_es_keinen_stillen_rueckfall(monkeypatch):
    """Der eigentliche Punkt: ein fehlender Eintrag sah aus wie ein vorhandener."""
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "darwin")
    monkeypatch.delenv("JARVIS_SECRET_BACKEND", raising=False)
    speicher = default_store()
    assert "environment" not in speicher.backends


def test_ohne_macos_ist_die_umgebung_der_entwicklungspfad(monkeypatch):
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "linux")
    monkeypatch.delenv("JARVIS_SECRET_BACKEND", raising=False)
    speicher = default_store()
    assert speicher.backends == ("environment",)
    assert speicher.violates_spec is False
    assert "Entwicklungspfad" in (speicher.insecure_reason() or "")


def test_auf_macos_ist_die_umgebung_ein_verstoss(monkeypatch):
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "darwin")
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    speicher = default_store()
    assert speicher.violates_spec is True
    assert "Keychain" in (speicher.insecure_reason() or "")


def test_die_umgebung_bleibt_auf_macos_ausdruecklich_waehlbar(monkeypatch):
    """Sie wird nicht verboten -- nur nicht mehr stillschweigend genommen."""
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "darwin")
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    monkeypatch.setenv("JARVIS_SECRET_TESTWERT", "vorhanden")
    assert default_store().get("testwert") == "vorhanden"


def test_reine_keychain_ist_kein_verstoss(monkeypatch):
    monkeypatch.setattr("jarvis.core.secrets.sys.platform", "darwin")
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "keychain")
    speicher = default_store()
    assert speicher.violates_spec is False
    assert speicher.insecure_reason() is None


def test_der_modus_wird_mitgefuehrt(monkeypatch):
    for wahl in ("keychain", "env", "none"):
        monkeypatch.setenv("JARVIS_SECRET_BACKEND", wahl)
        assert default_store().mode == wahl


# --------------------------------------------------------------------------- #
# Nie ein Wert nach draussen
# --------------------------------------------------------------------------- #


def test_der_fehler_nennt_den_namen_nicht_den_wert(monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    monkeypatch.setenv("JARVIS_SECRET_ANTHROPIC_API_KEY", "sk-streng-geheim")
    speicher = default_store()
    with pytest.raises(SecretsError) as fehler:
        speicher.require("gibtsnicht")
    assert "gibtsnicht" in str(fehler.value)
    assert "sk-streng-geheim" not in str(fehler.value)


def test_describe_nennt_nur_die_quellen(monkeypatch):
    monkeypatch.setenv("JARVIS_SECRET_BACKEND", "env")
    monkeypatch.setenv("JARVIS_SECRET_ANTHROPIC_API_KEY", "sk-streng-geheim")
    assert "sk-streng-geheim" not in default_store().describe()
