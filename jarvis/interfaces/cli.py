"""Kommandozeile.

Abschnitt 7 gilt auch hier: knapp, sachlich, keine Ausrufezeichen, keine
Emojis, eine einzige Akzentfarbe, und der Zustand des Stoppschalters steht
oben, nicht irgendwo. Farbe faellt weg, sobald die Ausgabe kein Terminal ist
oder NO_COLOR gesetzt ist -- Logdateien sollen lesbar bleiben.

`status` legt bewusst nichts an. Ein Lesebefehl, der nebenbei eine Datenbank
erzeugt, macht die Frage "laeuft hier schon etwas" unbeantwortbar.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from jarvis import __version__
from jarvis.core.audit import KIND_SYSTEM, AuditLog
from jarvis.core.config import DEFAULT_CONFIG_TOML, Config, ConfigError, Paths
from jarvis.core.db import open_database
from jarvis.core.log import configure as configure_logging
from jarvis.core.ratelimit import RateLimiter
from jarvis.core.secrets import default_store
from jarvis.llm.providers import build_providers
from jarvis.llm.router import Router, RouterError

ACCENT = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
INVERT = "\033[7m"
RESET = "\033[0m"


def _color_enabled(stream: object) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


class Out:
    """Ausgabe mit einer Akzentfarbe, oder ganz ohne."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout
        self.color = _color_enabled(self.stream)

    def _wrap(self, text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if self.color else text

    def accent(self, text: str) -> str:
        return self._wrap(text, ACCENT)

    def dim(self, text: str) -> str:
        return self._wrap(text, DIM)

    def bold(self, text: str) -> str:
        return self._wrap(text, BOLD)

    def alarm(self, text: str) -> str:
        return self._wrap(text, ACCENT + INVERT)

    def line(self, text: str = "") -> None:
        print(text, file=self.stream)

    def field(self, label: str, value: str) -> None:
        self.line(f"  {self.dim(label.ljust(14))} {value}")

    def table(self, headers: list[str], rows: list[list[str]]) -> None:
        if not rows:
            return
        widths = [max(len(headers[i]), *(len(row[i]) for row in rows)) for i in range(len(headers))]
        head = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip()
        self.line(f"  {self.dim(head)}")
        for row in rows:
            body = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()
            self.line(f"  {body}")


def _paths(args: argparse.Namespace) -> Paths:
    return Paths(home=Path(args.home).expanduser()) if args.home else Paths.default()


# --------------------------------------------------------------------------- #
# Befehle
# --------------------------------------------------------------------------- #


def cmd_init(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    paths.ensure()
    if paths.config_file.exists():
        out.line(f"Konfiguration vorhanden: {paths.config_file}")
    else:
        paths.config_file.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
        out.line(f"Konfiguration angelegt: {paths.config_file}")

    conn = open_database(paths.db_file)
    try:
        AuditLog(conn).record(
            capability="core",
            kind=KIND_SYSTEM,
            outcome="initialised",
            detail={"version": __version__},
        )
    finally:
        conn.close()
    out.line(f"Datenbank bereit:      {paths.db_file}")
    out.line(f"Logverzeichnis:        {paths.log_dir}")
    out.line()
    out.line("Alle Faehigkeiten stehen auf Stufe 0, Trockenlauf ist an.")
    return 0


def cmd_status(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    stop = config.stop_switch
    exit_code = 0

    out.line()
    out.line(f"{out.accent('JARVIS')} {out.dim(__version__)}")
    out.line()

    if stop.engaged():
        out.line(f"  {out.alarm(' ANGEHALTEN ')}  {stop.reason() or 'ohne Angabe'}")
        out.line(f"  {out.dim('Freigeben mit: jarvis resume')}")
    else:
        out.field("Zustand", out.bold("BETRIEB"))
    out.field("Basis", str(paths.home))
    out.field(
        "Konfiguration",
        str(config.source) if config.source else "Vorgabe (keine Datei, jarvis init)",
    )
    out.field("Trockenlauf", "an" if config.dry_run else out.bold("AUS"))
    out.field("Zugangsdaten", default_store().describe())

    conn = None
    if paths.db_file.exists():
        conn = open_database(paths.db_file)
        audit = AuditLog(conn)
        check = audit.verify()
        state = "Kette intakt" if check.ok else out.bold(f"KETTE GEBROCHEN bei {check.broken_at}")
        anzahl = audit.count()
        wort = "Eintrag" if anzahl == 1 else "Eintraege"
        out.field("Protokoll", f"{anzahl} {wort}, {state}")
        if not check.ok:
            exit_code = 1
    else:
        out.field("Protokoll", "Datenbank nicht angelegt (jarvis init)")

    try:
        # ------------------------------------------------------------------ #
        out.line()
        limiter = RateLimiter(conn, config.capabilities) if conn else None
        zaehler: dict[str, list[str]] = {}
        for name in sorted(config.capabilities):
            cap = config.capabilities[name]
            if not cap.rate_limits:
                zaehler[name] = []
            elif limiter is None:
                zaehler[name] = [f"{lim.window} ?/{lim.limit}" for lim in cap.rate_limits]
            else:
                zaehler[name] = [f"{w.window} {w.used}/{w.limit}" for w in limiter.usage(name)]
        breite = max((len(z) for spalten in zaehler.values() for z in spalten), default=0)

        rows = []
        for name in sorted(config.capabilities):
            cap = config.capabilities[name]
            level = f"{int(cap.autonomy_level)}  {cap.autonomy_level.label}"
            if not cap.enabled:
                level += "  (abgeschaltet)"
            spalten = zaehler[name]
            counters = "  ".join(z.ljust(breite) for z in spalten).rstrip() if spalten else "--"
            rows.append([name, level, "ja" if cap.requires_outbound else "nein", counters])
        out.table(["FAEHIGKEIT", "STUFE", "AUSGEHEND", "ZAEHLER"], rows)

        # ------------------------------------------------------------------ #
        out.line()
        secrets = default_store()
        providers = build_providers(config.llm, secrets)
        rows = []
        for name in sorted(providers):
            provider = providers[name]
            if args.ohne_anbieter:
                state = "nicht geprueft"
            else:
                state = "bereit" if provider.available() else "nicht verfuegbar"
            rows.append([name, provider.model, "lokal" if provider.local else "extern", state])
        out.table(["ANBIETER", "MODELL", "ORT", "ZUSTAND"], rows)

        # ------------------------------------------------------------------ #
        out.line()
        router = Router(config.llm, providers)
        rows = []
        for task in sorted(config.llm.tasks):
            route = config.llm.tasks[task]
            try:
                chain = " -> ".join(p.name for p in router.chain(task))
            except RouterError as exc:
                chain = f"FEHLER: {exc}"
                exit_code = 1
            if route.confidential:
                chain += "   (vertraulich, nur lokal)"
            rows.append([task, chain])
        out.table(["AUFGABE", "KETTE"], rows)
        out.line()
    finally:
        if conn:
            conn.close()
    return exit_code


def cmd_stop(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    stop_file = paths.stop_file
    from jarvis.core.config import StopSwitch

    switch = StopSwitch(stop_file)
    # Erst die Datei, dann das Protokoll. Der Schalter darf nicht davon
    # abhaengen, dass die Datenbank erreichbar ist.
    switch.engage(args.grund, actor="cli")
    out.line(f"{out.alarm(' ANGEHALTEN ')}  {args.grund}")
    out.line(f"  {out.dim(str(stop_file))}")

    if paths.db_file.exists():
        try:
            conn = open_database(paths.db_file)
            AuditLog(conn).record(
                capability="core",
                kind=KIND_SYSTEM,
                outcome="stop_engaged",
                detail={"reason": args.grund},
            )
            conn.close()
        except Exception as exc:  # der Schalter zaehlt, das Protokoll ist Beiwerk
            out.line(f"  {out.dim(f'Protokoll nicht geschrieben: {exc}')}")
    return 0


def cmd_resume(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    from jarvis.core.config import StopSwitch

    switch = StopSwitch(paths.stop_file)
    if not switch.engaged():
        out.line("Der Stoppschalter ist nicht gesetzt.")
        return 0

    out.line(f"Angehalten wegen: {switch.reason() or 'ohne Angabe'}")
    if not args.ja:
        if not sys.stdin.isatty():
            out.line("Zum Freigeben: jarvis resume --ja")
            return 1
        antwort = input("Freigeben? [j/N] ").strip().lower()
        if antwort not in {"j", "ja"}:
            out.line("Bleibt angehalten.")
            return 1

    switch.release()
    out.line("Freigegeben. Ausgehende Aktionen sind wieder moeglich.")
    if paths.db_file.exists():
        try:
            conn = open_database(paths.db_file)
            AuditLog(conn).record(
                capability="core", kind=KIND_SYSTEM, outcome="stop_released", detail={}
            )
            conn.close()
        except Exception as exc:
            out.line(f"  {out.dim(f'Protokoll nicht geschrieben: {exc}')}")
    return 0


def cmd_log(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    if not paths.db_file.exists():
        out.line("Keine Datenbank. Erst: jarvis init")
        return 1
    conn = open_database(paths.db_file)
    try:
        entries = AuditLog(conn).recent(args.anzahl, capability=args.faehigkeit)
        if not entries:
            out.line("Protokoll ist leer.")
            return 0
        rows = []
        for entry in reversed(entries):
            marker = "T" if entry.dry_run else " "
            rows.append(
                [
                    str(entry.id),
                    entry.ts[:19].replace("T", " "),
                    marker,
                    entry.capability,
                    entry.kind,
                    entry.outcome,
                    str(entry.detail.get("reason", "")),
                ]
            )
        out.line()
        out.table(["ID", "ZEIT (UTC)", "T", "FAEHIGKEIT", "ART", "ERGEBNIS", "GRUND"], rows)
        out.line(f"  {out.dim('T = Trockenlauf')}")
        out.line()
    finally:
        conn.close()
    return 0


def cmd_verify(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    if not paths.db_file.exists():
        out.line("Keine Datenbank. Erst: jarvis init")
        return 1
    conn = open_database(paths.db_file)
    try:
        check = AuditLog(conn).verify()
    finally:
        conn.close()
    if check.ok:
        out.line(f"Protokoll intakt. {check.checked} Eintraege geprueft.")
        return 0
    out.line(f"{out.alarm(' PROTOKOLL VERAENDERT ')}  {check.message}")
    out.line(f"  {check.checked} Eintraege waren bis dahin in Ordnung.")
    return 1


# --------------------------------------------------------------------------- #
# Einstieg
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis", description="Persoenlicher Assistent. Zustand und Steuerung."
    )
    parser.add_argument("--version", action="version", version=f"jarvis {__version__}")
    parser.add_argument(
        "--home", metavar="PFAD", help="Basisverzeichnis statt ~/.jarvis oder JARVIS_HOME"
    )
    sub = parser.add_subparsers(dest="befehl", required=True)

    p = sub.add_parser("init", help="Konfiguration und Datenbank anlegen")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status", help="Stufe, Zaehler und Zustand zeigen")
    p.add_argument(
        "--ohne-anbieter",
        dest="ohne_anbieter",
        action="store_true",
        help="Anbieter nicht auf Erreichbarkeit pruefen (kein Netzzugriff)",
    )
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("stop", help="Jede ausgehende Aktion blockieren")
    p.add_argument("--grund", default="von Hand angehalten", help="Grund fuers Protokoll")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("resume", help="Stoppschalter loesen")
    p.add_argument("--ja", action="store_true", help="ohne Rueckfrage freigeben")
    p.set_defaults(func=cmd_resume)

    p = sub.add_parser("log", help="Letzte Protokolleintraege zeigen")
    p.add_argument("-n", "--anzahl", type=int, default=20, help="Anzahl Eintraege")
    p.add_argument("--faehigkeit", help="nur diese Faehigkeit")
    p.set_defaults(func=cmd_log)

    p = sub.add_parser("verify", help="Hash-Kette des Protokolls pruefen")
    p.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out = Out()

    # Betriebslog nur, wenn das Verzeichnis schon existiert. `status` und `log`
    # duerfen nichts anlegen; `init` legt es an und ist ab dann bedient.
    paths = _paths(args)
    log = None
    if paths.log_dir.is_dir():
        log = configure_logging(paths.log_dir)
        log.info("Befehl", extra={"command": args.befehl})

    try:
        code = int(args.func(args, out))
        if log:
            log.info("Befehl beendet", extra={"command": args.befehl, "exit_code": code})
        return code
    except ConfigError as exc:
        if log:
            log.error("Konfiguration fehlerhaft", extra={"error": str(exc)})
        print(f"Konfiguration fehlerhaft: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
