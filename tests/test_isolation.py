"""Prozesstrennung: was im auswertenden Teil fehlt, ist der Punkt."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from jarvis.core.config import Config, ConfigError, Paths, ProviderConfig
from jarvis.core.secrets import SecretStore
from jarvis.llm import isolated
from jarvis.llm.isolation import (
    DURCHGEREICHT,
    SubprocessProvider,
    child_env,
    sandbox_available,
    sandbox_command,
    sandbox_profile,
)
from jarvis.llm.provider import (
    ProviderError,
    ProviderRefused,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
)
from jarvis.llm.providers import build_providers
from jarvis.llm.providers.static import StaticProvider

TROCKEN = ProviderConfig(
    name="trocken", kind="static", model="static", local=True, reply='{"kategorie":"rechnung"}'
)
EXTERN = ProviderConfig(
    name="anthropic", kind="anthropic", model="claude-opus-5", local=False, secret="anthropic_key"
)


# --------------------------------------------------------------------------- #
# Die Umgebung des Kindes
# --------------------------------------------------------------------------- #


def test_kein_jarvis_geheimnis_erreicht_das_kind(monkeypatch):
    """Der eigentliche Gewinn: Gmail-Zugangsdaten bleiben im Elternprozess."""
    monkeypatch.setenv("JARVIS_SECRET_GMAIL_TOKEN", "streng-geheim")
    monkeypatch.setenv("JARVIS_SECRET_ANTHROPIC_API_KEY", "auch-geheim")
    monkeypatch.setenv("JARVIS_HOME", "/wo/die/mails/liegen")

    umgebung = child_env(home="/tmp/leer")

    assert not [k for k in umgebung if k.startswith("JARVIS")]
    assert "streng-geheim" not in " ".join(umgebung.values())


def test_die_umgebung_ist_eine_allowlist(monkeypatch):
    """Eine Sperrliste waere die falsche Richtung -- man vergisst darin etwas."""
    monkeypatch.setenv("IRGENDWAS_NEUES", "wert")
    assert "IRGENDWAS_NEUES" not in child_env(home="/tmp/leer")


def test_das_kind_bekommt_ein_leeres_zuhause():
    umgebung = child_env(home="/tmp/leer")
    assert umgebung["HOME"] == "/tmp/leer"
    assert umgebung["PYTHONNOUSERSITE"] == "1"


def test_die_netzvariablen_kommen_mit(monkeypatch):
    """Ohne sie kaeme das Kind gar nicht erst zum Anbieter."""
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/cert.pem")
    umgebung = child_env(home="/tmp/leer")
    assert umgebung["HTTPS_PROXY"] == "http://proxy:3128"
    assert umgebung["SSL_CERT_FILE"] == "/etc/ssl/cert.pem"


def test_in_der_allowlist_steht_nichts_geheimes():
    for name in DURCHGEREICHT:
        assert "SECRET" not in name.upper()
        assert "TOKEN" not in name.upper()
        assert "KEY" not in name.upper()


# --------------------------------------------------------------------------- #
# Was hinuebergeht
# --------------------------------------------------------------------------- #


def test_der_schluessel_steht_nicht_in_der_kommandozeile():
    """Sonst laese ihn jeder mit `ps`."""
    anbieter = SubprocessProvider(EXTERN, secret="sk-geheim")
    befehl = anbieter.command(schreibbar="/tmp/leer")
    assert "sk-geheim" not in " ".join(befehl)
    assert befehl[1:] == ["-m", "jarvis.llm.isolated"]


def test_der_schluessel_geht_ueber_die_eingabe():
    anbieter = SubprocessProvider(EXTERN, secret="sk-geheim")
    fracht = anbieter.payload(Request.single("hallo"))
    assert fracht["secret"] == "sk-geheim"


def test_hinueber_geht_nur_text_anbieter_und_anfrage():
    """Kein Pfad, keine Datenbank, kein Ziel."""
    fracht = SubprocessProvider(TROCKEN).payload(Request.single("hallo"))
    assert set(fracht) == {"provider", "secret", "request"}
    assert set(fracht["request"]) == {"messages", "system", "max_tokens", "effort"}
    als_text = json.dumps(fracht)
    for verboten in ("jarvis_home", "state.db", "gmail", "approvals"):
        assert verboten not in als_text.lower()


def test_der_schluessel_wird_erst_beim_aufruf_geholt():
    """Sonst weckte `jarvis status` den Schluesselbund fuer eine Tabelle."""
    gefragt: list[int] = []

    def geheimnis():
        gefragt.append(1)
        return "sk-spaet"

    anbieter = SubprocessProvider(EXTERN, secret=geheimnis)
    assert gefragt == []
    assert anbieter.payload(Request.single("hallo"))["secret"] == "sk-spaet"
    assert len(gefragt) == 1


# --------------------------------------------------------------------------- #
# Der Kindprozess selbst
# --------------------------------------------------------------------------- #


def test_das_kind_beantwortet_eine_anfrage():
    ergebnis = isolated.antwort_auf(
        {
            "provider": {
                "name": "t",
                "kind": "static",
                "model": "m",
                "local": True,
                "reply": '{"a":1}',
            },
            "request": {"messages": [{"role": "user", "content": "hallo"}]},
        }
    )
    assert ergebnis["ok"] is True
    assert ergebnis["response"]["text"] == '{"a":1}'


def test_das_kind_kennt_nur_das_uebergebene_geheimnis():
    speicher = isolated._EinGeheimnis("nur-dieser")
    assert speicher.get("anthropic_key") == "nur-dieser"
    # Es fragt keinen Schluesselbund und keine Umgebung: derselbe Wert fuer
    # jeden Namen, weil es nur einen gibt.
    assert speicher.get("gmail_token") == "nur-dieser"


def test_das_kind_ohne_geheimnis_meldet_das_sauber():
    speicher = isolated._EinGeheimnis(None)
    assert speicher.has("egal") is False
    with pytest.raises(Exception, match="nicht uebergeben"):
        speicher.require("anthropic_key")


def test_ein_fehler_im_kind_wird_kein_absturz():
    ergebnis = isolated.antwort_auf(
        {
            "provider": {"name": "t", "kind": "erfunden", "model": "m", "local": True},
            "request": {"messages": [{"role": "user", "content": "hallo"}]},
        }
    )
    assert ergebnis["ok"] is False
    assert ergebnis["kind"] == "error"


def test_das_kind_importiert_keine_faehigkeit_und_kein_gatter():
    """Struktur statt Vertrauen: die Bausteine zum Handeln fehlen dort."""
    quelle = Path(isolated.__file__).read_text(encoding="utf-8")
    for verboten in ("skills.", "core.gate", "core.db", "core.audit", "GmailClient"):
        assert verboten not in quelle, f"{verboten!r} steht im auswertenden Prozess"


def test_das_kind_laeuft_wirklich_als_eigener_prozess():
    """Nicht nachgestellt: hier startet ein echter zweiter Interpreter."""
    fracht = json.dumps(
        {
            "provider": {
                "name": "t",
                "kind": "static",
                "model": "m",
                "local": True,
                "reply": "hallo zurueck",
            },
            "request": {"messages": [{"role": "user", "content": "hallo"}]},
        }
    )
    lauf = subprocess.run(
        [sys.executable, "-m", "jarvis.llm.isolated"],
        input=fracht,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert lauf.returncode == 0, lauf.stderr
    assert json.loads(lauf.stdout.strip())["response"]["text"] == "hallo zurueck"


# --------------------------------------------------------------------------- #
# Hin und zurueck
# --------------------------------------------------------------------------- #


def test_ein_vollstaendiger_umlauf_durch_einen_zweiten_prozess():
    antwort = SubprocessProvider(TROCKEN).complete(Request.single("Rechnung ueber 40 Euro"))
    assert antwort.text == '{"kategorie":"rechnung"}'
    assert antwort.provider == "trocken"
    assert antwort.model == "static"


def test_die_fehlerart_ueberlebt_den_prozesswechsel(monkeypatch):
    """Sonst faende der Router keinen Rueckfall mehr."""
    for art, klasse in [
        ("unavailable", ProviderUnavailable),
        ("timeout", ProviderTimeout),
        ("refused", ProviderRefused),
        ("error", ProviderError),
    ]:
        anbieter = SubprocessProvider(TROCKEN)
        monkeypatch.setattr(
            anbieter,
            "_starte",
            lambda r, o, art=art: __import__(
                "jarvis.llm.isolation", fromlist=["_Ergebnis"]
            )._Ergebnis(ok=False, daten={"kind": art, "error": "x"}),
        )
        with pytest.raises(klasse):
            anbieter.complete(Request.single("hallo"))


def test_geschwaetzige_bibliotheken_machen_die_antwort_nicht_unlesbar(monkeypatch):
    """Eine Warnung auf stdout darf die Antwort nicht kippen."""
    echt = subprocess.run

    def mit_laerm(*a, **k):
        lauf = echt(*a, **k)
        return subprocess.CompletedProcess(
            lauf.args, lauf.returncode, "UserWarning: irgendwas\n" + lauf.stdout, lauf.stderr
        )

    monkeypatch.setattr(subprocess, "run", mit_laerm)
    assert SubprocessProvider(TROCKEN).complete(Request.single("x")).text.startswith("{")


def test_ohne_antwort_gibt_es_einen_verstaendlichen_fehler(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", "irgendein Absturz"),
    )
    with pytest.raises(ProviderError, match="ohne Antwort"):
        SubprocessProvider(TROCKEN).complete(Request.single("x"))


def test_ein_haengender_prozess_wird_abgebrochen(monkeypatch):
    def haengt(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(subprocess, "run", haengt)
    with pytest.raises(ProviderTimeout):
        SubprocessProvider(TROCKEN).complete(Request.single("x"))


def test_available_startet_keinen_prozess(monkeypatch):
    """`jarvis status` fragt das fuer jeden Anbieter -- das darf nichts kosten."""

    def darf_nicht(*a, **k):  # pragma: no cover
        raise AssertionError("available() hat einen Prozess gestartet")

    monkeypatch.setattr(subprocess, "run", darf_nicht)
    assert SubprocessProvider(TROCKEN, probe=lambda: True).available() is True


# --------------------------------------------------------------------------- #
# Die Sandbox
# --------------------------------------------------------------------------- #


def test_das_profil_verbietet_zuerst_alles():
    profil = sandbox_profile(schreibbar="/tmp/x")
    assert "(deny default)" in profil
    assert profil.index("(deny default)") < profil.index("(allow")


def test_das_profil_sperrt_das_basisverzeichnis_und_den_schluesselbund():
    profil = sandbox_profile(schreibbar="/tmp/x")
    assert ".jarvis" in profil
    assert "Keychains" in profil
    for zeile in profil.splitlines():
        if ".jarvis" in zeile or "Keychains" in zeile:
            assert zeile.strip().startswith("(deny")


def test_das_profil_laesst_das_netz_offen():
    """Den Anbieter zu erreichen ist die einzige Aufgabe des Kindes."""
    assert "(allow network-outbound)" in sandbox_profile(schreibbar="/tmp/x")


def test_der_sandbox_aufruf_umschliesst_den_eigentlichen_befehl():
    befehl = sandbox_command(["python", "-m", "jarvis.llm.isolated"], schreibbar="/tmp/x")
    assert befehl[0] == "/usr/bin/sandbox-exec"
    assert befehl[-3:] == ["python", "-m", "jarvis.llm.isolated"]


def test_sandbox_ohne_macos_meldet_das_statt_zu_scheitern():
    if sandbox_available():  # pragma: no cover - haengt am System
        pytest.skip("Auf diesem System gibt es sandbox-exec")
    anbieter = SubprocessProvider(TROCKEN, mode="sandbox")
    with pytest.raises(ProviderUnavailable, match="sandbox-exec"):
        anbieter.complete(Request.single("x"))


def test_unbekannte_trennung_wird_abgewiesen():
    with pytest.raises(ValueError, match="Unbekannte Trennung"):
        SubprocessProvider(TROCKEN, mode="halbwegs")


# --------------------------------------------------------------------------- #
# Die Fabrik
# --------------------------------------------------------------------------- #


def llm_config(home, isolation: str = "subprocess") -> Config:
    return Config.from_mapping(
        {
            "llm": {
                "isolation": isolation,
                "providers": {
                    "trocken": {"kind": "static", "model": "s", "local": True, "reply": "{}"},
                    "ollama": {
                        "kind": "ollama",
                        "model": "llama3.1:8b",
                        "local": True,
                        "base_url": "http://127.0.0.1:11434",
                    },
                },
                "tasks": {"classify": {"providers": ["trocken"]}},
            }
        },
        paths=Paths(home=home),
    )


def test_die_fabrik_trennt_nach_vorgabe(home):
    gebaut = build_providers(llm_config(home).llm, SecretStore([]))
    assert isinstance(gebaut["ollama"], SubprocessProvider)
    assert gebaut["ollama"].mode == "subprocess"


def test_der_statische_anbieter_wird_nie_ausgelagert(home):
    """Er antwortet mit einer Konstanten -- da ist nichts zu trennen."""
    gebaut = build_providers(llm_config(home).llm, SecretStore([]))
    assert isinstance(gebaut["trocken"], StaticProvider)


def test_bei_off_bleibt_alles_im_selben_prozess(home):
    gebaut = build_providers(llm_config(home, "off").llm, SecretStore([]))
    assert not isinstance(gebaut["ollama"], SubprocessProvider)


def test_die_vorgabe_trennt(home):
    assert Config.load(home=home).llm.isolation == "subprocess"


def test_eine_unbekannte_trennung_faellt_beim_laden_auf(home):
    with pytest.raises(ConfigError, match=r"llm\.isolation"):
        llm_config(home, "halbwegs")


def test_die_vertraulichkeitssperre_gilt_auch_getrennt(home):
    """`local` kommt aus derselben Konfiguration -- der Router merkt nichts."""
    gebaut = build_providers(llm_config(home).llm, SecretStore([]))
    assert gebaut["ollama"].local is True
    assert gebaut["ollama"].name == "ollama"
