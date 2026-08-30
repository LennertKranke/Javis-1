"""Der Dauerbetrieb. Eine Uhr, kein zweites Gehirn.

Bisher lief JARVIS nur, wenn jemand einen Befehl tippte. Der Daemon aendert
daran genau eine Sache: er ruft dieselben Durchlaeufe zu festen Zeiten auf.
Er entscheidet nichts, er darf nichts, was die Kommandozeile nicht auch
duerfte, und er umgeht nichts.

Was er ausdruecklich *nicht* tut:

  * Er schaltet keine Faehigkeit frei. Autonomiestufen und Gatter gelten
    unveraendert; wer auf Stufe 0 steht, laeuft auch hier im Trockenlauf.
  * Er faehrt nicht alles permanent. Es laeuft nur, was in `[daemon.schedule]`
    steht -- und dort steht nichts, was von selbst nach aussen wirkt.
  * Er erzeugt keine zusaetzlichen Modellaufrufe. Die Faehigkeiten
    entscheiden weiter selbst, wann sie ein Modell brauchen; eine bereits
    beurteilte Nachricht wird wiederverwendet, nicht neu bewertet.

Wie er endet: auf SIGTERM oder SIGINT wird der laufende Durchlauf zu Ende
gefuehrt, danach ist Schluss. `launchd` schickt SIGTERM -- ein Abbruch
mitten in einem Durchlauf koennte eine Aktion hinterlassen, die nicht mehr
protokolliert wurde.

Wie er nicht doppelt laeuft: eine Sperrdatei mit `flock`. Zwei Daemons auf
demselben Basisverzeichnis waeren zwei Uhren auf derselben Datenbank, und
die Ratenbegrenzung zaehlte gegen sich selbst.
"""

from __future__ import annotations

import fcntl
import logging
import os
import signal
import sqlite3
import sys
import time
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jarvis.core.approvals import ApprovalStore
from jarvis.core.audit import KIND_SYSTEM, AuditLog
from jarvis.core.config import Config, ConfigError, Paths
from jarvis.core.db import open_database
from jarvis.core.files import secure_dir, secure_file
from jarvis.core.gate import Gate
from jarvis.core.ratelimit import RateLimiter
from jarvis.core.secrets import SecretStore, default_store
from jarvis.skills.factory import build_skill
from jarvis.skills.runner import run_skill

__all__ = ["Daemon", "DaemonLock", "Lauf", "LockBusy", "letzter_lauf", "merke_lauf"]

LOCK_NAME = "daemon.lock"

#: Groesse eines Schlafschritts. Kleiner heisst: schneller beendet, mehr
#: Aufwachen. Eine Sekunde ist fuer beides unauffaellig.
SCHLAFHAEPPCHEN = 1.0
META_PRAEFIX = "daemon.last_run."


class LockBusy(RuntimeError):
    """Es laeuft bereits ein Daemon auf diesem Basisverzeichnis."""


class DaemonLock:
    """Eine Sperrdatei mit `flock`. Loest sich beim Beenden von selbst.

    Kein PID-Vergleich von Hand: eine liegengebliebene Datei nach einem
    Absturz wuerde sonst jeden Neustart blockieren. `flock` gibt die Sperre
    frei, sobald der Prozess endet -- auch wenn er nicht dazu kam, aufzuraeumen.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: Any = None

    def acquire(self) -> None:
        # Der Inhalt ist harmlos -- eine PID und ein Zeitstempel. Die Rechte
        # werden trotzdem gesetzt: eine Regel mit Ausnahmen ist keine Regel,
        # und die naechste Datei an dieser Stelle ist vielleicht nicht harmlos.
        secure_dir(self.path.parent)
        self._fh = self.path.open("a+", encoding="utf-8")
        secure_file(self.path)
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._fh.seek(0)
            inhalt = self._fh.read().strip()
            self._fh.close()
            self._fh = None
            raise LockBusy(
                f"Es laeuft bereits ein Daemon ({inhalt or 'unbekannte PID'}). "
                f"Sperrdatei: {self.path}"
            ) from exc
        self._fh.seek(0)
        self._fh.truncate()
        self._fh.write(f"pid {os.getpid()} seit {_jetzt()}\n")
        self._fh.flush()

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> DaemonLock:
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Wann lief was zuletzt
# --------------------------------------------------------------------------- #


def letzter_lauf(conn: sqlite3.Connection, job: str) -> float | None:
    """Zeitpunkt des letzten Laufs, als Unix-Zeit.

    In der Datenbank, nicht im Speicher: sonst faengt nach jedem Neustart
    alles wieder von vorne an, und ein Daemon in einer Neustartschleife
    triebe die Modellkosten hoch.
    """
    zeile = conn.execute("SELECT value FROM meta WHERE key = ?", (META_PRAEFIX + job,)).fetchone()
    if zeile is None:
        return None
    try:
        return float(zeile["value"])
    except (TypeError, ValueError):
        return None


def merke_lauf(conn: sqlite3.Connection, job: str, wann: float) -> None:
    with conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (META_PRAEFIX + job, f"{wann:.0f}"),
        )


# --------------------------------------------------------------------------- #
# Der Daemon
# --------------------------------------------------------------------------- #


@dataclass
class Lauf:
    """Was ein einzelner Durchlauf ergeben hat. Nur fuer Protokoll und Tests."""

    job: str
    ok: bool
    polled: int = 0
    acted: int = 0
    dry_run: int = 0
    blocked: int = 0
    queued: int = 0
    fehler: str | None = None
    uebersprungen: str | None = None


@dataclass
class Daemon:
    config: Config
    paths: Paths
    secrets: SecretStore | None = None
    logger: logging.Logger | None = None
    #: Ersetzbar, damit Tests nicht wirklich warten muessen.
    schlafen: Any = time.sleep
    uhr: Any = time.monotonic
    _stoppt: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._log = self.logger or logging.getLogger("jarvis.daemon")

    # ------------------------------------------------------------------ #

    def anhalten(self, *_: object) -> None:
        """Signalhandler. Setzt nur eine Fahne -- der Durchlauf laeuft aus."""
        self._stoppt = True

    @property
    def haelt_an(self) -> bool:
        return self._stoppt

    def faellig(self, conn: sqlite3.Connection, jetzt: float) -> list[str]:
        """Welche Jobs jetzt an der Reihe sind, in fester Reihenfolge."""
        dran = []
        for job in sorted(self.config.daemon.schedule):
            abstand = self.config.daemon.schedule[job] * 60
            zuletzt = letzter_lauf(conn, job)
            if zuletzt is None or jetzt - zuletzt >= abstand:
                dran.append(job)
        return dran

    def einen_durchlauf(self, conn: sqlite3.Connection, job: str) -> Lauf:
        """Ein Job. Ein Fehler hier beendet den Daemon nie."""
        schalter = self.config.stop_switch
        if schalter.engaged():
            # Zweite Sperre neben dem Gatter. Der Daemon soll gar nicht erst
            # anfangen, wenn angehalten ist -- auch nicht mit dem Beurteilen.
            self._log.info("Durchlauf ausgelassen", extra={"job": job, "grund": "Stoppschalter"})
            return Lauf(job=job, ok=True, uebersprungen="Stoppschalter")

        audit = AuditLog(conn)
        gate = Gate(self.config, audit, RateLimiter(conn, self.config.capabilities))
        try:
            skill = build_skill(
                job, config=self.config, conn=conn, secrets=self.secrets or default_store()
            )
            bericht = run_skill(
                skill,
                gate=gate,
                audit=audit,
                approvals=ApprovalStore(conn),
                collect_approvals=self.config.capability(job).collect_approvals,
                logger=self._log,
            )
        except Exception as exc:
            # Ein kaputter Anbieter, ein abgelaufener Token, eine Datenbank,
            # die kurz weg ist: nichts davon darf die Uhr anhalten.
            self._log.warning(
                "Durchlauf fehlgeschlagen",
                extra={"job": job, "error": f"{type(exc).__name__}: {exc}"},
            )
            return Lauf(job=job, ok=False, fehler=f"{type(exc).__name__}: {exc}")

        self._log.info(
            "Durchlauf beendet",
            extra={
                "job": job,
                "polled": bericht.polled,
                "acted": bericht.acted,
                "dry_run": bericht.dry_run,
                "blocked": bericht.blocked,
                "queued": bericht.queued,
            },
        )
        return Lauf(
            job=job,
            ok=bericht.failed == 0,
            polled=bericht.polled,
            acted=bericht.acted,
            dry_run=bericht.dry_run,
            blocked=bericht.blocked,
            queued=bericht.queued,
        )

    def tick(self, conn: sqlite3.Connection) -> list[Lauf]:
        """Ein Blick auf die Uhr. Faellige Jobs, nacheinander."""
        jetzt = self.uhr()
        laeufe = []
        for job in self.faellig(conn, jetzt):
            if self._stoppt:
                break
            lauf = self.einen_durchlauf(conn, job)
            laeufe.append(lauf)
            # Auch ein fehlgeschlagener Lauf zaehlt als Lauf: sonst wird er
            # bei jedem Tick sofort wiederholt und rennt gegen dieselbe Wand.
            merke_lauf(conn, job, jetzt)
        return laeufe

    def _warte(self, sekunden: float) -> None:
        """Wartet in kleinen Schritten und sieht dabei nach dem Signal.

        `time.sleep` laesst sich nicht unterbrechen: der Signalhandler laeuft
        zwar sofort, aber der Schlaf laeuft danach zu Ende. Bei einem Takt von
        30 Sekunden haette `launchd` den Prozess laengst hart abgeraeumt, bevor
        er von selbst faehig gewesen waere aufzuhoeren.
        """
        rest = float(sekunden)
        while rest > 0 and not self._stoppt:
            haeppchen = min(SCHLAFHAEPPCHEN, rest)
            self.schlafen(haeppchen)
            rest -= haeppchen

    def run(self, *, max_ticks: int | None = None) -> int:
        """Die Schleife. `max_ticks` ist fuer Tests, nicht fuer den Betrieb."""
        if not self.config.daemon.enabled:
            self._log.warning("Daemon ist nicht eingeschaltet ([daemon] enabled)")
            return 2
        if not self.config.daemon.schedule:
            self._log.warning("Kein Zeitplan hinterlegt ([daemon.schedule])")
            return 2

        with DaemonLock(self.paths.home / LOCK_NAME):
            conn = open_database(self.paths.db_file)
            try:
                AuditLog(conn).record(
                    capability="core",
                    kind=KIND_SYSTEM,
                    outcome="daemon_started",
                    detail={
                        "pid": os.getpid(),
                        "schedule": dict(sorted(self.config.daemon.schedule.items())),
                        "dry_run": self.config.dry_run,
                    },
                )
                self._log.info(
                    "Daemon gestartet",
                    extra={"pid": os.getpid(), "tick": self.config.daemon.tick_seconds},
                )
                ticks = 0
                while not self._stoppt:
                    if max_ticks is not None and ticks >= max_ticks:
                        break
                    ticks += 1
                    try:
                        self.tick(conn)
                    except Exception as exc:  # die Uhr laeuft weiter
                        self._log.error(
                            "Tick fehlgeschlagen",
                            extra={"error": f"{type(exc).__name__}: {exc}"},
                        )
                    if self._stoppt:
                        break
                    self._warte(self.config.daemon.tick_seconds)
            finally:
                # Das Protokoll ist hier Beiwerk: der Daemon endet auch dann
                # sauber, wenn die Datenbank gerade nicht mehr erreichbar ist.
                with suppress(Exception):
                    AuditLog(conn).record(
                        capability="core",
                        kind=KIND_SYSTEM,
                        outcome="daemon_stopped",
                        detail={"pid": os.getpid()},
                    )
                conn.close()
        self._log.info("Daemon beendet", extra={"pid": os.getpid()})
        return 0


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - Einstieg
    """Einstieg fuer `python -m jarvis.daemon` und `jarvis daemon`."""
    from jarvis.core.log import configure as configure_logging

    heim = Path(argv[0]).expanduser() if argv else None
    paths = Paths(home=heim) if heim else Paths.default()
    try:
        config = Config.load(home=paths.home)
    except ConfigError as exc:
        print(f"Konfiguration fehlerhaft: {exc}", file=sys.stderr)
        return 2

    log = configure_logging(paths.log_dir, level=config.log_level, stderr=True)
    daemon = Daemon(config=config, paths=paths, logger=log.getChild("daemon"))
    signal.signal(signal.SIGTERM, daemon.anhalten)
    signal.signal(signal.SIGINT, daemon.anhalten)
    try:
        return daemon.run()
    except LockBusy as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
