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
from dataclasses import dataclass, field
from datetime import UTC, datetime, tzinfo
from enum import IntEnum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "DEFAULT_CONFIG_TOML",
    "ISOLATION_MODES",
    "AutonomyLevel",
    "Capability",
    "Config",
    "ConfigError",
    "DaemonConfig",
    "LLMConfig",
    "Paths",
    "ProviderConfig",
    "RateLimit",
    "ServiceConfig",
    "StopSwitch",
    "TaskRoute",
    "VoiceConfig",
    "WebConfig",
    "jarvis_home",
    "local_timezone",
    "url_host",
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


def local_timezone() -> tzinfo:
    """Die Zeitzone dieses Rechners, moeglichst als benannte Zone.

    Eine benannte Zone (`Europe/Berlin`) kennt ihre Sommerzeit; ein blosser
    Versatz kennt nur den von jetzt. Fuer eine Tagesgrenze macht das den
    Unterschied, sobald die Umstellung dazwischen liegt. Der feste Versatz ist
    deshalb nur der letzte Ausweg -- wem er nicht genuegt, der traegt die Zone
    in die Konfiguration ein.
    """
    if name := os.environ.get("TZ", "").strip():
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    try:
        ziel = Path("/etc/localtime").resolve()
        teile = ziel.parts
        if "zoneinfo" in teile:
            return ZoneInfo("/".join(teile[teile.index("zoneinfo") + 1 :]))
    except (OSError, ZoneInfoNotFoundError, ValueError):
        pass
    return datetime.now().astimezone().tzinfo or UTC


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

#: Wie weit der auswertende Teil vom handelnden getrennt laeuft (Abschnitt 2.2).
#: Steht hier und nicht in llm/isolation.py, damit config.py nichts aus llm/
#: importieren muss -- der Kern kennt die Schichten ueber sich nicht.
ISOLATION_MODES = ("off", "subprocess", "sandbox")
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
    #: Wie weit der Modellaufruf vom handelnden Teil getrennt laeuft.
    #: "off" | "subprocess" | "sandbox" -- siehe llm/isolation.py.
    isolation: str = "subprocess"


LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


SERVICE_MODES = ("live", "mock")


@dataclass(frozen=True)
class ServiceConfig:
    """Externe Dienste: echt oder Mock.

    `mock` ersetzt Gmail und Kalender durch Laufzeit-Doppel, damit sich der
    ganze Weg ohne Konten ansehen laesst. Es ist ausdruecklich kein
    Trockenlauf-Ersatz: der Mock laeuft durch dieselben Faehigkeiten und
    dasselbe Gatter, und `dry_run` gilt unveraendert.

    Der Modus steht in der Konfiguration und nicht in einer
    Umgebungsvariablen: er aendert, womit JARVIS spricht, und das gehoert an
    dieselbe Stelle wie alles andere, was er darf.
    """

    mode: str = "live"
    fixtures: str = ""

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"


@dataclass(frozen=True)
class DaemonConfig:
    """Der Dauerbetrieb. Eine Uhr, sonst nichts.

    `enabled` steht auf false, bis jemand es ausdruecklich umlegt. Ein
    Assistent, der nach `jarvis init` von selbst losliefe, waere genau das,
    was Abschnitt 3 verhindern will -- auch wenn er dabei nur im Trockenlauf
    entscheidet.

    `schedule` nennt Faehigkeit und Abstand in Minuten. Was nicht darin steht,
    laeuft nicht. Faehigkeiten, die nach aussen wirken, gehoeren hier nicht
    hinein, solange man ihnen nicht zusieht.
    """

    enabled: bool = False
    tick_seconds: int = 30
    schedule: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class VoiceConfig:
    """Sprache als zusaetzliche Bedienweise.

    `task` leer heisst: nur Regeln, kein Modell. Das ist eine brauchbare
    Betriebsart -- die Regeln decken alles ab, was Sprache darf, und ohne
    Modell entsteht weder Kosten noch ein Weg fuer Fremdtext ins Modell.

    Einen Anbieter, der Audio wegschickt, gibt es nicht. `whisper_bin` ruft
    ein Programm auf diesem Rechner auf; ist es nicht da, wird nichts
    umgewandelt, statt auf etwas anderes auszuweichen.
    """

    wake_word: str = "jarvis"
    speak: bool = True
    voice_name: str = ""
    rate: int = 0
    whisper_bin: str = "whisper-cli"
    whisper_model: str = ""
    language: str = "de"
    task: str = ""
    record_command: tuple[str, ...] = ()

    @property
    def uses_model(self) -> bool:
        return bool(self.task)


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

    def spoken_reason(self) -> str:
        """Nur der Grund, ohne Zeitstempel und Urheber.

        Die Datei traegt "<zeit> <urheber>: <grund>", damit man ihr ansieht,
        wer sie gesetzt hat. Vorgelesen ist der Zeitstempel Laerm. Passt die
        Zeile nicht auf die Form, wird sie unveraendert genommen -- die Datei
        darf auch von Hand geschrieben worden sein.
        """
        roh = (self.reason() or "").strip()
        if not roh:
            return "ohne Angabe"
        kopf, trenner, rest = roh.partition(": ")
        if trenner and len(kopf.split()) == 2 and rest.strip():
            return rest.strip()
        return roh

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
    timezone: tzinfo
    capabilities: dict[str, Capability]
    llm: LLMConfig
    skills: dict[str, dict[str, Any]]
    web: WebConfig
    voice: VoiceConfig
    daemon: DaemonConfig
    services: ServiceConfig
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

    def permits(self, name: str, required_level: int, *, approved: bool = False) -> bool:
        """Darf die Faehigkeit handeln?

        Die eine Stelle, an der diese Frage beantwortet wird. Das Gatter fragt
        hier, und die Fabrik fragt hier, wenn sie entscheidet welche Rechte ein
        Client bekommt. Frueher hatten beide ihre eigene Rechnung -- dann
        konnte das Gatter eine Freigabe durchlassen, waehrend der Client sie
        mangels Recht gar nicht ausfuehren konnte.

        `approved` ist eine ausdrueckliche Freigabe durch einen Menschen. Sie
        ersetzt die Autonomiestufe, nicht den Ein-Aus-Schalter: eine
        abgeschaltete Faehigkeit bleibt abgeschaltet.
        """
        cap = self.capability(name)
        if not cap.enabled:
            return False
        return approved or int(cap.autonomy_level) >= int(required_level)

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
                "timezone",
                "capabilities",
                "llm",
                "daemon",
                "services",
                "skills",
                "voice",
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

        zone = _parse_timezone(raw.get("timezone", ""))
        capabilities = _parse_capabilities(raw.get("capabilities", {}))
        llm = _parse_llm(raw.get("llm", {}))
        skills = _parse_skills(raw.get("skills", {}))
        web = _parse_web(raw.get("web", {}))
        voice = _parse_voice(raw.get("voice", {}), known_tasks=set(llm.tasks))
        daemon = _parse_daemon(raw.get("daemon", {}), known_capabilities=set(capabilities))
        _pruefe_zeitplan(daemon)
        services = _parse_services(raw.get("services", {}))
        return cls(
            paths=paths,
            dry_run=dry_run,
            log_level=log_level,
            sanitize_max_chars=max_chars,
            timezone=zone,
            capabilities=capabilities,
            llm=llm,
            skills=skills,
            web=web,
            voice=voice,
            daemon=daemon,
            services=services,
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


def _parse_timezone(raw: Any) -> tzinfo:
    """Leer heisst: die des Rechners. Ein Tippfehler ist ein Fehler."""
    name = _as_str(raw, "timezone").strip()
    if not name:
        return local_timezone()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(
            f"timezone: {name!r} ist keine bekannte Zone (erwartet etwa 'Europe/Berlin')"
        ) from exc


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


def _pruefe_zeitplan(daemon: DaemonConfig) -> None:
    """Ein Zeitplan darf nur Faehigkeiten nennen, die sich auch bauen lassen.

    Vorher genuegte ein Eintrag in [capabilities]. Damit liess sich `voice`
    einplanen -- Sprache ist aber eine Bedienweise und keine Faehigkeit, sie
    hat kein poll/decide/act. Der Daemon haette den Job stumm bei jedem Tick
    scheitern lassen, statt dass die Konfiguration es sofort sagt.

    Der Import steht absichtlich in der Funktion: `config.py` ist der Kern und
    kennt die Schichten ueber sich sonst nicht.
    """
    if not daemon.schedule:
        return
    from jarvis.skills.factory import BUILDABLE

    for name in sorted(daemon.schedule):
        if name not in BUILDABLE:
            bekannt = ", ".join(BUILDABLE)
            raise ConfigError(
                f"daemon.schedule.{name}: laesst sich nicht als Faehigkeit bauen "
                f"(moeglich: {bekannt})"
            )


def _parse_services(raw: Any) -> ServiceConfig:
    if not isinstance(raw, dict):
        raise ConfigError("services: erwartet eine Tabelle")
    _reject_unknown(raw, {"mode", "fixtures"}, "services")
    modus = _as_str(raw.get("mode", "live"), "services.mode").strip()
    if modus not in SERVICE_MODES:
        erlaubt = ", ".join(SERVICE_MODES)
        raise ConfigError(f"services.mode: {modus!r} unbekannt (erlaubt: {erlaubt})")
    return ServiceConfig(
        mode=modus,
        fixtures=_as_str(raw.get("fixtures", ""), "services.fixtures").strip(),
    )


def _parse_daemon(raw: Any, *, known_capabilities: set[str]) -> DaemonConfig:
    if not isinstance(raw, dict):
        raise ConfigError("daemon: erwartet eine Tabelle")
    _reject_unknown(raw, {"enabled", "tick_seconds", "schedule"}, "daemon")

    takt = _as_int(raw.get("tick_seconds", 30), "daemon.tick_seconds")
    if not 5 <= takt <= 3600:
        raise ConfigError("daemon.tick_seconds: muss zwischen 5 und 3600 liegen")

    roh_plan = raw.get("schedule", {})
    if not isinstance(roh_plan, dict):
        raise ConfigError("daemon.schedule: erwartet eine Tabelle")
    plan: dict[str, int] = {}
    for name, minuten in roh_plan.items():
        if name not in known_capabilities:
            bekannt = ", ".join(sorted(known_capabilities)) or "keine"
            raise ConfigError(
                f"daemon.schedule.{name}: keine bekannte Faehigkeit (bekannt: {bekannt})"
            )
        wert = _as_int(minuten, f"daemon.schedule.{name}")
        if not 1 <= wert <= 10080:
            raise ConfigError(f"daemon.schedule.{name}: muss zwischen 1 Minute und 7 Tagen liegen")
        plan[name] = wert

    return DaemonConfig(
        enabled=_as_bool(raw.get("enabled", False), "daemon.enabled"),
        tick_seconds=takt,
        schedule=plan,
    )


def _parse_voice(raw: Any, *, known_tasks: set[str]) -> VoiceConfig:
    if not isinstance(raw, dict):
        raise ConfigError("voice: erwartet eine Tabelle")
    _reject_unknown(
        raw,
        {
            "wake_word",
            "speak",
            "voice_name",
            "rate",
            "whisper_bin",
            "whisper_model",
            "language",
            "task",
            "record_command",
        },
        "voice",
    )

    task = _as_str(raw.get("task", ""), "voice.task").strip()
    if task and task not in known_tasks:
        bekannt = ", ".join(sorted(known_tasks)) or "keine"
        raise ConfigError(f"voice.task: {task!r} steht nicht in [llm.tasks] (bekannt: {bekannt})")

    rate = _as_int(raw.get("rate", 0), "voice.rate")
    if rate and not 80 <= rate <= 400:
        raise ConfigError("voice.rate: 0 oder zwischen 80 und 400 Woertern je Minute")

    befehl = raw.get("record_command", [])
    if not isinstance(befehl, list) or not all(isinstance(t, str) for t in befehl):
        raise ConfigError("voice.record_command: erwartet eine Liste von Zeichenketten")

    modell = _as_str(raw.get("whisper_model", ""), "voice.whisper_model").strip()
    if modell and not Path(modell).expanduser().is_absolute():
        # Ein relativer Pfad haengt am Arbeitsverzeichnis. Unter `launchd` ist
        # das ein anderes als in der Shell -- die Umwandlung schluege dort
        # fehl, und zwar erst im Betrieb, nicht beim Laden.
        raise ConfigError(
            f"voice.whisper_model: {modell!r} ist relativ. Ein Daemon startet in "
            f"einem anderen Verzeichnis; bitte den vollen Pfad angeben."
        )

    return VoiceConfig(
        wake_word=_as_str(raw.get("wake_word", "jarvis"), "voice.wake_word").strip(),
        speak=_as_bool(raw.get("speak", True), "voice.speak"),
        voice_name=_as_str(raw.get("voice_name", ""), "voice.voice_name").strip(),
        rate=rate,
        whisper_bin=_as_str(raw.get("whisper_bin", "whisper-cli"), "voice.whisper_bin").strip(),
        whisper_model=str(Path(modell).expanduser()) if modell else "",
        language=_as_str(raw.get("language", "de"), "voice.language").strip() or "de",
        task=task,
        record_command=tuple(befehl),
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
    _reject_unknown(raw, {"providers", "tasks", "isolation"}, "llm")
    providers = _parse_providers(raw.get("providers", {}))
    tasks = _parse_tasks(raw.get("tasks", {}), providers)
    trennung = _as_str(raw.get("isolation", "subprocess"), "llm.isolation").strip()
    if trennung not in ISOLATION_MODES:
        erlaubt = ", ".join(ISOLATION_MODES)
        raise ConfigError(f"llm.isolation: {trennung!r} unbekannt (erlaubt: {erlaubt})")
    return LLMConfig(providers=providers, tasks=tasks, isolation=trennung)


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

        local = _as_bool(body.get("local", kind in {"ollama", "static"}), f"{where}.local")
        _check_local_claim(where, kind=kind, local=local, base_url=body.get("base_url"))

        out[name] = ProviderConfig(
            name=name,
            kind=kind,
            model=_as_str(body["model"], f"{where}.model"),
            local=local,
            max_tokens=_as_int(body.get("max_tokens", 4096), f"{where}.max_tokens"),
            timeout=float(timeout),
            secret=body.get("secret"),
            base_url=body.get("base_url"),
            effort=effort,
            reply=body.get("reply"),
        )
    return out


def _check_local_claim(where: str, *, kind: str, local: bool, base_url: Any) -> None:
    """Prueft, ob "lokal" technisch haltbar ist.

    Abschnitt 5.2 schickt sensible persoenliche Daten nur an lokale Modelle.
    Bisher war `local = true` eine Behauptung in der Konfigurationsdatei: ein
    Anbieter durfte sich lokal nennen und seine base_url auf einen fremden
    Rechner zeigen lassen. Dann waere die Vertraulichkeitssperre im Router
    eine Beschriftung ohne Wirkung.

    Deshalb hier: wer lokal sein will, muss auf eine Loopback-Adresse zeigen.
    Der Anbieter selbst prueft das vor jeder Anfrage noch einmal.
    """
    if not local:
        return
    if kind == "anthropic":
        raise ConfigError(
            f"{where}.local: ein Anthropic-Anbieter laeuft nicht auf diesem Rechner. "
            f"local = true ist hier nicht haltbar."
        )
    if base_url is None:
        return  # Vorgabe ist Loopback, siehe OllamaProvider
    host = url_host(_as_str(base_url, f"{where}.base_url"))
    if host not in LOOPBACK:
        erlaubt = ", ".join(sorted(LOOPBACK))
        raise ConfigError(
            f"{where}: local = true, aber base_url zeigt auf {host!r}. Ein als lokal "
            f"gefuehrter Anbieter muss auf diesen Rechner zeigen (erlaubt: {erlaubt})."
        )


def url_host(url: str) -> str:
    """Der Wirt einer URL, ohne Klammern bei IPv6."""
    from urllib.parse import urlsplit

    zerlegt = urlsplit(url if "//" in url else f"//{url}")
    return (zerlegt.hostname or "").lower()


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

# Zeitzone fuer Tagesgrenzen: welche Termine "heute" sind und wann das
# Morgenbriefing den Tag wechselt. Leer heisst: die dieses Rechners.
# Eine benannte Zone ist robuster, weil sie ihre Sommerzeit kennt.
timezone = ""


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

# Termine lesen und auf Ueberschneidungen pruefen. Liest den eigenen Kalender
# und erreicht niemanden -- wie das Mail-Lesen also nicht ausgehend. Der
# Kalender-Client wird ohne Schreibrecht gebaut.
[capabilities.calendar]
autonomy_level = 0
requires_outbound = false
rate_limits = { hour = 60, day = 300 }

# Recherche. Sie greift spaeter ins Netz und unterliegt deshalb von Anfang an
# Ratenbegrenzung und Stoppschalter -- auch solange die einzige Quelle ein
# fester Bestand ohne Netz ist.
[capabilities.research]
autonomy_level = 0
requires_outbound = true
rate_limits = { hour = 20, day = 100 }

# Das Morgenbriefing. Fasst nur zusammen, was ohnehin schon bekannt ist, und
# schreibt es in die eigene Datenbank.
[capabilities.briefing]
autonomy_level = 0
requires_outbound = false
rate_limits = { hour = 5, day = 20 }

# Sprache. Liest vor und haelt an, mehr nicht -- es gibt im Code keinen Weg
# von einem gesprochenen Satz zu einer ausgehenden Aktion. Sie laeuft deshalb
# nicht durchs Gatter: wer angehalten hat, soll hoeren koennen, warum. Die
# Obergrenze hier bremst nur den Modellrueckfall bei der Absichtserkennung.
[capabilities.voice]
autonomy_level = 0
requires_outbound = false
rate_limits = { hour = 60, day = 400 }


# --------------------------------------------------------------------------- #
# Modelle
#
# local = true bedeutet: laeuft auf diesem Rechner, verlaesst ihn nicht.
# secret nennt den Namen des Keychain-Eintrags, nie den Wert selbst.
# --------------------------------------------------------------------------- #

# Wie weit der auswertende Teil vom handelnden getrennt laeuft (Abschnitt 2.2).
#
#   off         alles in einem Prozess. Schnell, aber die Trennung gilt dann
#               nur als Zusage des Codes.
#   subprocess  der Modellaufruf laeuft in einem eigenen Prozess, mit
#               gefilterter Umgebung: kein JARVIS_HOME, keine Gmail-
#               Zugangsdaten, kein Weg zur Datenbank. Der Standard.
#   sandbox     zusaetzlich sandbox-exec unter macOS -- dann verweigert das
#               Betriebssystem den Zugriff auf ~/.jarvis und den
#               Schluesselbund, nicht nur der Code.
#
# Der statische Anbieter wird nie ausgelagert: er antwortet mit einer
# Konstanten und sieht den Text gar nicht an.
[llm]
isolation = "subprocess"


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

# Das Briefing formuliert nur, es entscheidet nichts. Der billige Anbieter
# zuerst; faellt die ganze Kette aus, entsteht die Fassung ohne Modell.
[llm.tasks.briefing]
providers = ["ollama", "anthropic"]
effort = "low"

# Gesprochene Saetze einer von sechs Absichten zuordnen. Vertraulich: was im
# Raum gesagt wird, verlaesst diesen Rechner nicht. Damit steht hier nur ein
# lokaler Anbieter, und die Konfiguration prueft das.
[llm.tasks.voice]
providers = ["ollama"]
confidential = true
effort = "low"


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


[skills.research]
# Aufgabe aus [llm.tasks], die aus einer Frage Suchbegriffe macht.
task = "classify"

# Die Freigabeliste der Quellen. Was hier nicht steht, wird nicht gefragt --
# auch wenn es vorhanden waere. Das Modell kann diese Liste nicht aendern und
# nennt niemals selbst eine Adresse (Abschnitt 2.1).
#
# "beispiel" ist ein fester Bestand ohne Netz. Eine echte Quelle mit Websuche
# kommt spaeter dazu; bis dahin geht von hier nichts hinaus.
sources = ["beispiel"]

# Fragen je Durchlauf, Funde je Frage.
max_per_run = 5
max_findings = 5

# Die Kategorien sind zugleich das Ausgabeschema des Modells.
categories = ["allgemein", "recht", "technik", "finanzen", "gesundheit"]


[skills.calendar]
# Welche Kalender angesehen werden. "primary" ist der eigene Hauptkalender.
calendar_ids = ["primary"]

# Wie weit nach vorne geschaut wird, in Tagen.
window_days = 7

# Weniger Zeit als das zwischen zwei Terminen gilt als "kein Puffer".
# 0 schaltet diese Pruefung ab; Ueberschneidungen werden weiter gemeldet.
min_gap_minutes = 15

# Obergrenze je Durchlauf und Kalender, ueber alle Seiten zusammen.
# Der Client blaettert ueber nextPageToken, bis das Fenster abgearbeitet
# oder diese Zahl erreicht ist.
max_per_run = 250


[skills.briefing]
# Aufgabe aus [llm.tasks], die den Text formuliert. Faellt sie aus, entsteht
# das Briefing trotzdem -- dann ohne Modell.
task = "briefing"

# Ungefaehre Obergrenze fuer die Laenge des Textes, in Woertern.
max_words = 200

# Ab wie vielen Tagen eine unbeantwortete Anfrage als Frist gilt. Gerechnet
# wird ab dem ersten Sehen, nicht ab dem letzten Durchlauf.
overdue_days = 3


# --------------------------------------------------------------------------- #
# Externe Dienste
#
#   live   Gmail und Kalender sprechen mit Google.
#   mock   Beide werden durch Laufzeit-Doppel ersetzt. Damit laeuft der ganze
#          Weg ohne Konten -- lesen, einordnen, Entwerfen, Briefing. Nichts
#          geht hinaus, und "jarvis services check" sagt hin, dass der Mock
#          laeuft. Ein Mock zaehlt nie als Nachweis, dass der echte Dienst
#          erreichbar ist.
#
# fixtures: Verzeichnis mit eigenen Beispieldaten als JSON. Leer heisst:
# die eingebauten Beispiele.
# --------------------------------------------------------------------------- #

[services]
mode = "live"
fixtures = ""


# --------------------------------------------------------------------------- #
# Dauerbetrieb
#
# Der Daemon ist eine Uhr, kein zweites Gehirn. Er ruft dieselben Durchlaeufe
# auf, die auch die Kommandozeile aufruft -- Autonomiestufen, Gatter,
# Ratenbegrenzung und Stoppschalter gelten unveraendert.
#
# enabled bleibt false, bis du es umlegst. Ein Assistent, der nach
# "jarvis init" von selbst losliefe, waere genau das, was Abschnitt 3
# verhindern will.
#
# In schedule steht, welche Faehigkeit in welchem Abstand (Minuten) laeuft.
# Was nicht darin steht, laeuft nicht. Absichtlich fehlen mail_reply und
# mail_send: was Entwuerfe schreibt oder sendet, laeuft erst dann von selbst,
# wenn du ihm eine Weile zugesehen hast.
#
# briefing darf oft laufen, ohne etwas zu kosten: liegt das Briefing des
# Tages schon vor, findet der Durchlauf nichts zu tun und fragt kein Modell.
# --------------------------------------------------------------------------- #

[daemon]
enabled = false
tick_seconds = 30

[daemon.schedule]
mail = 15
calendar = 60
briefing = 60


# --------------------------------------------------------------------------- #
# Sprache
#
# Eine zusaetzliche Bedienweise, kein Ersatz. Sprache liest vor und kann
# anhalten; senden und freigeben gehen nur im Dashboard. Ein Mikrofon hoert
# den ganzen Raum -- auch den Fernseher, auch Besuch.
# --------------------------------------------------------------------------- #

[voice]
# Ohne diese Anrede wird nicht geantwortet. Leer heisst: auf jeden Satz
# reagieren. Das Weckwort ist ein Filter gegen Zufall, keine Sicherung.
wake_word = "jarvis"

# Antworten laut vorlesen. false heisst: nur schreiben.
speak = true

# Stimme von macOS ("say -v ?" zeigt die vorhandenen). Leer = Systemstimme.
voice_name = ""

# Sprechtempo in Woertern je Minute. 0 = Vorgabe des Systems.
rate = 0

# Whisper laeuft auf diesem Rechner. Ohne Modelldatei wird nichts umgewandelt;
# es gibt bewusst keinen Anbieter, der Audio wegschickt.
whisper_bin = "whisper-cli"
whisper_model = ""
language = "de"

# Aufgabe aus [llm.tasks] fuer Saetze, die keine Regel trifft. Leer heisst:
# nur Regeln. Das reicht fuer alles, was Sprache darf.
task = "voice"

# Wie aufgenommen wird. Leer heisst: "jarvis voice listen" steht nicht bereit,
# und es bleibt bei "jarvis voice hear <datei>". macOS bringt kein
# Aufnahmeprogramm mit; mit sox etwa:
#   record_command = ["rec", "-q", "-r", "16000", "-c", "1", "{datei}", "trim", "0", "6"]
# {datei} wird durch den Pfad der Aufnahme ersetzt.
record_command = []


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
