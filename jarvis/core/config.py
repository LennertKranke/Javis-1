"""Konfiguration, Autonomiestufen und Stoppschalter.

Alles, was JARVIS ueber sich selbst weiss, bevor er irgendetwas tut. Die Datei
haelt drei Dinge zusammen, die im Betrieb immer gemeinsam gebraucht werden: wo
etwas liegt (`Paths`), was erlaubt ist (`Capability.autonomy_level`) und ob
ueberhaupt noch gehandelt werden darf (`StopSwitch`).

Die Konfiguration ist TOML, weil Python 3.12 `tomllib` mitbringt und damit keine
Abhaengigkeit noetig ist. Unbekannte Schluessel sind ein Fehler, kein Hinweis:
ein Tippfehler in `autonomy_level` darf nicht stillschweigend zu Stufe 0
zurueckfallen, denn dann faellt er nie auf.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_CONFIG_TOML",
    "AutonomyLevel",
    "Capability",
    "Config",
    "ConfigError",
    "LLMConfig",
    "Paths",
    "ProviderConfig",
    "RateLimit",
    "StopSwitch",
    "TaskRoute",
    "WebConfig",
    "jarvis_home",
]


class ConfigError(RuntimeError):
    """Die Konfiguration ist unbrauchbar. Immer laut, nie stillschweigend."""


# --------------------------------------------------------------------------- #
# Orte
# --------------------------------------------------------------------------- #

CONFIG_NAME = "config.toml"
DB_NAME = "state.db"
LOG_DIR_NAME = "logs"
STOP_NAME = "STOP"


def jarvis_home() -> Path:
    """Basisverzeichnis. `JARVIS_HOME` schlaegt den Standard `~/.jarvis`."""
    raw = os.environ.get("JARVIS_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".jarvis"


@dataclass(frozen=True)
class Paths:
    home: Path

    @classmethod
    def default(cls) -> Paths:
        return cls(home=jarvis_home())

    @property
    def config_file(self) -> Path:
        return self.home / CONFIG_NAME

    @property
    def db_file(self) -> Path:
        return self.home / DB_NAME

    @property
    def log_dir(self) -> Path:
        return self.home / LOG_DIR_NAME

    @property
    def stop_file(self) -> Path:
        return self.home / STOP_NAME

    def ensure(self) -> None:
        """Legt Basis- und Logverzeichnis an. Idempotent."""
        self.home.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Autonomiestufen (Abschnitt 3 der Spezifikation)
# --------------------------------------------------------------------------- #


class AutonomyLevel(IntEnum):
    SHADOW = 0
    ALLOWLIST = 1
    CATEGORIES = 2
    UNLESS_BLOCKED = 3

    @property
    def label(self) -> str:
        return _AUTONOMY_LABELS[self]


_AUTONOMY_LABELS = {
    AutonomyLevel.SHADOW: "Schattenbetrieb",
    AutonomyLevel.ALLOWLIST: "Allowlist",
    AutonomyLevel.CATEGORIES: "Freigegebene Kategorien",
    AutonomyLevel.UNLESS_BLOCKED: "Alles ausser Gesperrtes",
}


# --------------------------------------------------------------------------- #
# Faehigkeiten
# --------------------------------------------------------------------------- #

WINDOW_SECONDS: dict[str, int] = {
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
}


@dataclass(frozen=True, order=True)
class RateLimit:
    seconds: int
    window: str
    limit: int


@dataclass(frozen=True)
class Capability:
    """Eine Faehigkeit, wie die Konfiguration sie sieht.

    `autonomy_level` ist die *gewaehrte* Stufe. Eine Faehigkeit im Code nennt
    ihrerseits die Stufe, die sie zum selbstaendigen Handeln braucht; erst der
    Vergleich beider Werte entscheidet (siehe `Config.permits`).
    """

    name: str
    autonomy_level: AutonomyLevel = AutonomyLevel.SHADOW
    requires_outbound: bool = True
    enabled: bool = True
    collect_approvals: bool = False
    rate_limits: tuple[RateLimit, ...] = ()


# --------------------------------------------------------------------------- #
# Modelle
# --------------------------------------------------------------------------- #

EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
PROVIDER_KINDS = frozenset({"anthropic", "ollama", "static"})


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    kind: str
    model: str
    local: bool
    max_tokens: int = 4096
    timeout: float = 120.0
    secret: str | None = None
    base_url: str | None = None
    effort: str | None = None
    reply: str | None = None  # nur kind = "static"


@dataclass(frozen=True)
class TaskRoute:
    """Eine Aufgabe und die Anbieterkette, die sie bedienen darf.

    `confidential` ist keine Beschriftung, sondern eine Sperre: eine
    vertrauliche Aufgabe darf ausschliesslich lokale Anbieter enthalten. Das
    wird beim Laden geprueft und im Router noch einmal.
    """

    name: str
    providers: tuple[str, ...]
    confidential: bool = False
    effort: str | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class LLMConfig:
    providers: dict[str, ProviderConfig]
    tasks: dict[str, TaskRoute]


LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


@dataclass(frozen=True)
class WebConfig:
    """Das Dashboard. Bindet ausschliesslich an die Loopback-Adresse.

    Das ist keine Vorsichtsmassnahme, sondern eine Sperre: die Oberflaeche
    kann Entscheidungen freigeben, und Abschnitt 6 sagt "unter localhost".
    Eine andere Adresse wird beim Laden abgewiesen, nicht bloss gewarnt.
    """

    host: str = "127.0.0.1"
    port: int = 8765
    refresh_seconds: int = 0

    @property
    def base_url(self) -> str:
        """Die Adresse, die in einen Browser gehoert."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"http://{host}:{self.port}"

    def with_overrides(self, *, host: str | None = None, port: int | None = None) -> WebConfig:
        """Wendet Werte von der Kommandozeile an -- durch dieselbe Pruefung.

        Ohne das haette `--host` die Loopback-Sperre umgangen, die nur beim
        Lesen der Konfigurationsdatei greift: der Server lauscht dann am Netz,
        und die Sperre waere eine Empfehlung.
        """
        return _validate_web(
            self.host if host is None else host,
            self.port if port is None else port,
            self.refresh_seconds,
        )


# --------------------------------------------------------------------------- #
# Stoppschalter (Prinzip 2.4)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StopSwitch:
    """Eine Datei, deren blosse Existenz jede ausgehende Aktion blockiert.

    Bewusst so primitiv: der Schalter muss auch dann funktionieren, wenn die
    Datenbank kaputt ist, der Daemon haengt oder nur noch eine Shell laeuft
    (`touch ~/.jarvis/STOP`). Er faellt geschlossen aus -- laesst sich der
    Zustand nicht feststellen, gilt "angehalten".
    """

    path: Path

    def engaged(self) -> bool:
        try:
            return self.path.exists()
        except OSError:
            return True

    def reason(self) -> str | None:
        try:
            return self.path.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def engage(self, reason: str, *, actor: str = "cli") -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        self.path.write_text(f"{stamp} {actor}: {reason}\n", encoding="utf-8")

    def release(self) -> bool:
        """Entfernt die Stoppdatei. Gibt zurueck, ob sie vorhanden war."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True


# --------------------------------------------------------------------------- #
# Gesamtkonfiguration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Config:
    paths: Paths
    dry_run: bool
    log_level: str
    sanitize_max_chars: int
    capabilities: dict[str, Capability]
    llm: LLMConfig
    skills: dict[str, dict[str, Any]]
    web: WebConfig
    source: Path | None

    @property
    def stop_switch(self) -> StopSwitch:
        return StopSwitch(self.paths.stop_file)

    def capability(self, name: str) -> Capability:
        try:
            return self.capabilities[name]
        except KeyError:
            raise ConfigError(f"Unbekannte Faehigkeit: {name!r}") from None

    def skill_options(self, name: str) -> dict[str, Any]:
        """Rohe Einstellungen einer Faehigkeit.

        Der Kern prueft sie bewusst nicht: eine Faehigkeit ist ein Plugin und
        kennt ihre eigenen Schluessel selbst. `config.py` wuerde sonst mit jeder
        neuen Faehigkeit mitwachsen, was Abschnitt 5.1 gerade vermeiden will.
        """
        return dict(self.skills.get(name, {}))

    def permits(self, name: str, required_level: int) -> bool:
        """Darf die Faehigkeit auf der gewaehrten Stufe selbstaendig handeln?"""
        cap = self.capability(name)
        return cap.enabled and int(cap.autonomy_level) >= int(required_level)

    @classmethod
    def load(cls, home: Path | None = None) -> Config:
        paths = Paths(home=home) if home is not None else Paths.default()
        if paths.config_file.exists():
            with paths.config_file.open("rb") as fh:
                try:
                    raw = tomllib.load(fh)
                except tomllib.TOMLDecodeError as exc:
                    raise ConfigError(f"{paths.config_file}: {exc}") from exc
            source: Path | None = paths.config_file
        else:
            raw = tomllib.loads(DEFAULT_CONFIG_TOML)
            source = None
        return cls.from_mapping(raw, paths=paths, source=source)

    @classmethod
    def from_mapping(
        cls, raw: dict[str, Any], *, paths: Paths, source: Path | None = None
    ) -> Config:
        _reject_unknown(
            raw,
            {
                "dry_run",
                "log_level",
                "sanitize_max_chars",
                "capabilities",
                "llm",
                "skills",
                "web",
            },
            "(Wurzel)",
        )
        dry_run = _as_bool(raw.get("dry_run", True), "dry_run")
        log_level = str(raw.get("log_level", "INFO")).upper()
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ConfigError(f"log_level: unbekannter Wert {log_level!r}")
        max_chars = _as_int(raw.get("sanitize_max_chars", 20000), "sanitize_max_chars")
        if max_chars < 1:
            raise ConfigError("sanitize_max_chars muss groesser als 0 sein")

        capabilities = _parse_capabilities(raw.get("capabilities", {}))
        llm = _parse_llm(raw.get("llm", {}))
        skills = _parse_skills(raw.get("skills", {}))
        web = _parse_web(raw.get("web", {}))
        return cls(
            paths=paths,
            dry_run=dry_run,
            log_level=log_level,
            sanitize_max_chars=max_chars,
            capabilities=capabilities,
            llm=llm,
            skills=skills,
            web=web,
            source=source,
        )


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def _reject_unknown(mapping: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ConfigError(f"{where}: unbekannte Schluessel {', '.join(unknown)}")


def _as_bool(value: Any, where: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigError(f"{where}: erwartet true oder false, gefunden {value!r}")
    return value


def _as_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{where}: erwartet eine ganze Zahl, gefunden {value!r}")
    return value


def _as_str(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{where}: erwartet Text, gefunden {value!r}")
    return value


def _parse_capabilities(raw: Any) -> dict[str, Capability]:
    if not isinstance(raw, dict):
        raise ConfigError("capabilities: erwartet eine Tabelle")
    out: dict[str, Capability] = {}
    for name, body in raw.items():
        where = f"capabilities.{name}"
        if not isinstance(body, dict):
            raise ConfigError(f"{where}: erwartet eine Tabelle")
        _reject_unknown(
            body,
            {
                "autonomy_level",
                "requires_outbound",
                "enabled",
                "collect_approvals",
                "rate_limits",
            },
            where,
        )
        level_value = _as_int(body.get("autonomy_level", 0), f"{where}.autonomy_level")
        try:
            level = AutonomyLevel(level_value)
        except ValueError:
            raise ConfigError(
                f"{where}.autonomy_level: {level_value} liegt ausserhalb von 0 bis 3"
            ) from None
        outbound = _as_bool(body.get("requires_outbound", True), f"{where}.requires_outbound")
        enabled = _as_bool(body.get("enabled", True), f"{where}.enabled")
        sammeln = _as_bool(body.get("collect_approvals", False), f"{where}.collect_approvals")
        limits = _parse_rate_limits(body.get("rate_limits", {}), where)
        if outbound and not limits:
            raise ConfigError(
                f"{where}: requires_outbound = true verlangt mindestens eine Obergrenze "
                f"in rate_limits. Prinzip 2.4 kennt keine unbegrenzte Faehigkeit."
            )
        out[name] = Capability(
            name=name,
            autonomy_level=level,
            requires_outbound=outbound,
            enabled=enabled,
            collect_approvals=sammeln,
            rate_limits=limits,
        )
    return out


def _parse_rate_limits(raw: Any, where: str) -> tuple[RateLimit, ...]:
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}.rate_limits: erwartet eine Tabelle")
    limits: list[RateLimit] = []
    for window, value in raw.items():
        if window not in WINDOW_SECONDS:
            known = ", ".join(sorted(WINDOW_SECONDS))
            raise ConfigError(
                f"{where}.rate_limits.{window}: unbekanntes Zeitfenster (bekannt: {known})"
            )
        limit = _as_int(value, f"{where}.rate_limits.{window}")
        if limit < 0:
            raise ConfigError(f"{where}.rate_limits.{window}: darf nicht negativ sein")
        limits.append(RateLimit(seconds=WINDOW_SECONDS[window], window=window, limit=limit))
    return tuple(sorted(limits))


def _validate_web(host: Any, port: Any, refresh: Any) -> WebConfig:
    """Die eine Stelle, an der Wirt und Port geprueft werden.

    Konfigurationsdatei und Kommandozeile gehen beide hier durch, damit die
    Loopback-Sperre nicht ueber einen Schalter zu umgehen ist.
    """
    host = _as_str(host, "web.host")
    if host not in LOOPBACK:
        erlaubt = ", ".join(sorted(LOOPBACK))
        raise ConfigError(
            f"web.host: {host!r} ist nicht erlaubt. Das Dashboard gibt Entscheidungen "
            f"frei und laeuft ausschliesslich lokal (erlaubt: {erlaubt})."
        )
    port = _as_int(port, "web.port")
    if not 1024 <= port <= 65535:
        raise ConfigError("web.port: muss zwischen 1024 und 65535 liegen")
    refresh = _as_int(refresh, "web.refresh_seconds")
    if refresh and not 5 <= refresh <= 3600:
        raise ConfigError("web.refresh_seconds: 0 oder zwischen 5 und 3600")
    return WebConfig(host=host, port=port, refresh_seconds=refresh)


def _parse_web(raw: Any) -> WebConfig:
    if not isinstance(raw, dict):
        raise ConfigError("web: erwartet eine Tabelle")
    _reject_unknown(raw, {"host", "port", "refresh_seconds"}, "web")
    return _validate_web(
        raw.get("host", "127.0.0.1"),
        raw.get("port", 8765),
        raw.get("refresh_seconds", 0),
    )


def _parse_skills(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        raise ConfigError("skills: erwartet eine Tabelle")
    out: dict[str, dict[str, Any]] = {}
    for name, body in raw.items():
        if not isinstance(body, dict):
            raise ConfigError(f"skills.{name}: erwartet eine Tabelle")
        out[name] = dict(body)
    return out


def _parse_llm(raw: Any) -> LLMConfig:
    if not isinstance(raw, dict):
        raise ConfigError("llm: erwartet eine Tabelle")
    _reject_unknown(raw, {"providers", "tasks"}, "llm")
    providers = _parse_providers(raw.get("providers", {}))
    tasks = _parse_tasks(raw.get("tasks", {}), providers)
    return LLMConfig(providers=providers, tasks=tasks)


def _parse_providers(raw: Any) -> dict[str, ProviderConfig]:
    if not isinstance(raw, dict):
        raise ConfigError("llm.providers: erwartet eine Tabelle")
    out: dict[str, ProviderConfig] = {}
    for name, body in raw.items():
        where = f"llm.providers.{name}"
        if not isinstance(body, dict):
            raise ConfigError(f"{where}: erwartet eine Tabelle")
        _reject_unknown(
            body,
            {
                "kind",
                "model",
                "local",
                "max_tokens",
                "timeout",
                "secret",
                "base_url",
                "effort",
                "reply",
            },
            where,
        )
        kind = _as_str(body.get("kind", name), f"{where}.kind")
        if kind not in PROVIDER_KINDS:
            known = ", ".join(sorted(PROVIDER_KINDS))
            raise ConfigError(f"{where}.kind: {kind!r} unbekannt (bekannt: {known})")
        if "model" not in body:
            raise ConfigError(f"{where}: model fehlt")
        effort = body.get("effort")
        if effort is not None and effort not in EFFORT_LEVELS:
            known = ", ".join(sorted(EFFORT_LEVELS))
            raise ConfigError(f"{where}.effort: {effort!r} unbekannt (bekannt: {known})")
        timeout = body.get("timeout", 120.0)
        if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
            raise ConfigError(f"{where}.timeout: erwartet eine positive Zahl")
        out[name] = ProviderConfig(
            name=name,
            kind=kind,
            model=_as_str(body["model"], f"{where}.model"),
            local=_as_bool(body.get("local", kind in {"ollama", "static"}), f"{where}.local"),
            max_tokens=_as_int(body.get("max_tokens", 4096), f"{where}.max_tokens"),
            timeout=float(timeout),
            secret=body.get("secret"),
            base_url=body.get("base_url"),
            effort=effort,
            reply=body.get("reply"),
        )
    return out


def _parse_tasks(raw: Any, providers: dict[str, ProviderConfig]) -> dict[str, TaskRoute]:
    if not isinstance(raw, dict):
        raise ConfigError("llm.tasks: erwartet eine Tabelle")
    out: dict[str, TaskRoute] = {}
    for name, body in raw.items():
        where = f"llm.tasks.{name}"
        if not isinstance(body, dict):
            raise ConfigError(f"{where}: erwartet eine Tabelle")
        _reject_unknown(body, {"providers", "confidential", "effort", "max_tokens"}, where)
        chain = body.get("providers")
        if not isinstance(chain, list) or not chain:
            raise ConfigError(f"{where}.providers: erwartet eine nicht leere Liste")
        for entry in chain:
            if entry not in providers:
                raise ConfigError(f"{where}.providers: Anbieter {entry!r} ist nicht definiert")
        confidential = _as_bool(body.get("confidential", False), f"{where}.confidential")
        if confidential:
            remote = [p for p in chain if not providers[p].local]
            if remote:
                raise ConfigError(
                    f"{where}: als vertraulich markiert, enthaelt aber die nicht lokalen "
                    f"Anbieter {', '.join(remote)}. Abschnitt 5.2 laesst dafuer nur lokale zu."
                )
        effort = body.get("effort")
        if effort is not None and effort not in EFFORT_LEVELS:
            raise ConfigError(f"{where}.effort: {effort!r} unbekannt")
        out[name] = TaskRoute(
            name=name,
            providers=tuple(chain),
            confidential=confidential,
            effort=effort,
            max_tokens=body.get("max_tokens"),
        )
    return out


# --------------------------------------------------------------------------- #
# Vorlage
# --------------------------------------------------------------------------- #

DEFAULT_CONFIG_TOML = """\
# JARVIS -- Konfiguration
#
# Diese Datei bestimmt, was JARVIS darf. Der Code bestimmt, wie er es tut.
# Unbekannte Schluessel sind ein Fehler, damit Tippfehler nicht stumm bleiben.

# Trockenlauf: es wird entschieden und protokolliert, aber nichts geht hinaus.
# Bleibt an, bis eine Faehigkeit nachweislich vernuenftige Entscheidungen trifft.
dry_run = true

log_level = "INFO"

# Obergrenze fuer normalisierten Fremdtext, in Zeichen.
sanitize_max_chars = 20000


# --------------------------------------------------------------------------- #
# Faehigkeiten
#
# autonomy_level ist die gewaehrte Stufe (Abschnitt 3):
#   0 Schattenbetrieb   entscheidet alles, sendet nichts
#   1 Allowlist         sendet nur an freigegebene Adressen
#   2 Kategorien        sendet in freigegebenen Kategorien an bekannte Kontakte
#   3 Ausser Gesperrtes sendet, ausser die Kategorie ist gesperrt
#
# Neue Faehigkeiten starten immer auf 0. rate_limits ist Pflicht, sobald die
# Faehigkeit nach aussen wirkt.
# --------------------------------------------------------------------------- #

# Lesen und Einsortieren. Beruehrt nur das eigene Postfach und erreicht
# niemanden, ist also keine ausgehende Faehigkeit. Die Obergrenzen bremsen
# trotzdem: sie begrenzen API-Aufrufe und Modellkosten pro Zeitfenster.
[capabilities.mail]
autonomy_level = 0
requires_outbound = false
rate_limits = { hour = 120, day = 600 }

# Antwortentwuerfe schreiben. Ein Entwurf liegt im eigenen Postfach und
# erreicht niemanden -- wie das Einordnen also nicht ausgehend.
[capabilities.mail_reply]
autonomy_level = 0
requires_outbound = false
# Was nicht von selbst durchgeht, landet als anstehende Entscheidung im
# Dashboard und laesst sich dort einzeln freigeben.
collect_approvals = true
rate_limits = { hour = 20, day = 100 }

# Entwuerfe tatsaechlich senden. Das erreicht Menschen.
#
# Hier steht die Umschaltung aus Abschnitt 6: autonomy_level = 1 schaltet das
# Senden frei. Solange hier 0 steht, laeuft die Faehigkeit im Trockenlauf mit
# und zeigt im Protokoll, was sie gesendet haette -- und der Gmail-Client wird
# ohne Senderecht gebaut, kann es also auch bei einem Fehler im Code nicht.
[capabilities.mail_send]
autonomy_level = 0
requires_outbound = true
collect_approvals = true
rate_limits = { hour = 5, day = 20 }

[capabilities.calendar]
autonomy_level = 0
requires_outbound = true
rate_limits = { hour = 5, day = 20 }

[capabilities.research]
autonomy_level = 0
requires_outbound = true
rate_limits = { hour = 20, day = 100 }

[capabilities.briefing]
autonomy_level = 0
requires_outbound = false


# --------------------------------------------------------------------------- #
# Modelle
#
# local = true bedeutet: laeuft auf diesem Rechner, verlaesst ihn nicht.
# secret nennt den Namen des Keychain-Eintrags, nie den Wert selbst.
# --------------------------------------------------------------------------- #

[llm.providers.anthropic]
kind = "anthropic"
model = "claude-opus-5"
local = false
secret = "anthropic_api_key"
max_tokens = 16000
timeout = 120.0
effort = "high"

[llm.providers.ollama]
kind = "ollama"
model = "llama3.1:8b"
local = true
base_url = "http://127.0.0.1:11434"
max_tokens = 8192
timeout = 120.0

# Antwortet immer dasselbe, ohne Netz. Fuer Trockenlaeufe und Tests.
[llm.providers.trocken]
kind = "static"
model = "static"
local = true
reply = "{}"


# --------------------------------------------------------------------------- #
# Aufgabenverteilung
#
# Die Reihenfolge ist die Rueckfallkette: faellt der erste Anbieter aus, wird
# der naechste versucht. confidential = true laesst ausschliesslich lokale
# Anbieter zu und wird beim Laden und beim Routen geprueft.
# --------------------------------------------------------------------------- #

[llm.tasks.classify]
providers = ["ollama", "anthropic"]
effort = "low"
# Auf true setzen, sobald Postfachinhalte den Rechner nicht mehr verlassen sollen.
# Dann faellt "anthropic" aus dieser Kette heraus und die Konfiguration meldet das.
confidential = false

[llm.tasks.draft]
providers = ["anthropic", "ollama"]
effort = "high"

[llm.tasks.personal]
providers = ["ollama"]
confidential = true


# --------------------------------------------------------------------------- #
# Faehigkeiten-Einstellungen
#
# Jede Faehigkeit prueft ihren eigenen Abschnitt selbst. Der Kern reicht ihn
# nur durch, damit config.py nicht mit jeder neuen Faehigkeit mitwaechst.
# --------------------------------------------------------------------------- #

[skills.mail]
# Gmail-Suchausdruck. Bestimmt, was ueberhaupt angesehen wird.
query = "is:unread in:inbox"

# Obergrenze je Durchlauf. Schuetzt den ersten Lauf vor einem vollen Postfach.
max_per_run = 25

# Labels entstehen als "JARVIS/Rechnung" und beruehren nichts Bestehendes.
label_prefix = "JARVIS"

# Aufgabe aus [llm.tasks], die den Klassifizierer bedient.
task = "classify"

# Die Kategorien sind zugleich Ausgabeschema und Labelnamen.
categories = [
    "rechnung",
    "termin",
    "anfrage",
    "newsletter",
    "werbung",
    "benachrichtigung",
    "persoenlich",
    "sonstiges",
]

# Namen der Keychain-Eintraege, nie die Werte selbst.
client_secret = "gmail_client_secret"
token_secret = "gmail_token"


[skills.mail_reply]
# Aufgabe aus [llm.tasks] fuer die Entwuerfe.
task = "draft"

# Nur diese Kategorien bekommen ueberhaupt einen Entwurf.
categories = ["anfrage", "termin"]

max_per_run = 10

# Laengere Entwuerfe werden nicht abgeschnitten, sondern zur Durchsicht
# zurueckgehalten.
max_words = 180

# Ein Link im Entwurf haelt ihn zur Durchsicht zurueck. Eine Antwort braucht
# selten einen, und ein untergeschobener waere schwer zu bemerken.
allow_links = false

# An solche Adressen wird nie geantwortet (Teilzeichenkette im lokalen Teil).
never_reply_to = [
    "noreply",
    "no-reply",
    "donotreply",
    "mailer-daemon",
    "postmaster",
    "bounce",
]

# Wird woertlich unter jeden Entwurf gesetzt. Kommt von dir, nicht vom Modell.
signature = ""


[skills.mail_send]
max_per_run = 10

# Ab so vielen eigenen Nachrichten an eine Adresse gilt sie als bekannter
# Kontakt. Verhindert, dass ein einzelner Hoeflichkeitsgruss genuegt.
allowlist_threshold = 3

# Wie viele gesendete Nachrichten "jarvis mail allowlist refresh" durchsieht.
allowlist_scan = 300

# Immer erlaubt, ohne Zaehlung.
allowlist_manual = []

# Immer verboten, schlaegt alles andere. Ganze Domains als "@example.com".
allowlist_blocked = []


# --------------------------------------------------------------------------- #
# Dashboard
#
# Laeuft ausschliesslich auf der Loopback-Adresse. Eine andere weist die
# Konfiguration ab -- die Oberflaeche kann Entscheidungen freigeben.
# --------------------------------------------------------------------------- #

[web]
host = "127.0.0.1"
port = 8765

# 0 heisst: die Seite laedt sich nicht von selbst neu. Sonst Sekunden (ab 5).
refresh_seconds = 0
"""
