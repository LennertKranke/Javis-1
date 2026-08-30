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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jarvis import __version__
from jarvis.core.approvals import ApprovalStore
from jarvis.core.audit import KIND_SYSTEM, AuditLog
from jarvis.core.config import DEFAULT_CONFIG_TOML, Config, ConfigError, Paths
from jarvis.core.context import ContextBuilder, ShortTermContext
from jarvis.core.db import open_database
from jarvis.core.gate import Gate
from jarvis.core.log import configure as configure_logging
from jarvis.core.memory import CATEGORIES, LongTermMemory
from jarvis.core.ratelimit import RateLimiter
from jarvis.core.secrets import default_store
from jarvis.llm.providers import build_providers
from jarvis.llm.router import Router, RouterError
from jarvis.skills.briefing.store import BriefingStore
from jarvis.skills.calendar.event import local_moment
from jarvis.skills.calendar.google import has_calendar_scope
from jarvis.skills.calendar.store import CalendarStore
from jarvis.skills.factory import (
    build_skill,
    gmail_auth,
    gmail_client,
    send_capabilities,
)
from jarvis.skills.mail import GmailAuthError, GmailError, MailStore
from jarvis.skills.mail.allowlist import Allowlist
from jarvis.skills.mail.compose import fingerprint_of_draft
from jarvis.skills.mail.gmail import DRAFTING, READ_ONLY
from jarvis.skills.mail.reply import SendOptions
from jarvis.skills.mail.store import ReplyStore
from jarvis.skills.mail.style import StyleStore, extract_profile
from jarvis.skills.runner import run_skill

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


def _trennung_von(provider) -> str:
    """Laeuft der Modellaufruf dieses Anbieters woanders?"""
    modus = getattr(provider, "mode", None)
    if modus:
        return modus
    return "-- (ohne Netz)" if provider.config.kind == "static" else "derselbe Prozess"


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
    speicher = default_store()
    out.field("Zugangsdaten", f"{speicher.describe()}  ({speicher.mode})")
    abweichung = speicher.insecure_reason()
    if abweichung and speicher.violates_spec:
        out.line(f"  {out.alarm(' UNSICHER ')}  {abweichung}")
        exit_code = 1
    elif abweichung:
        out.line(f"  {out.dim(abweichung)}")

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
            rows.append(
                [
                    name,
                    provider.model,
                    "lokal" if provider.local else "extern",
                    _trennung_von(provider),
                    state,
                ]
            )
        out.table(["ANBIETER", "MODELL", "ORT", "TRENNUNG", "ZUSTAND"], rows)
        if config.llm.isolation == "off":
            hinweis = "Trennung aus: der Modellaufruf laeuft im selben Prozess (Abschnitt 2.2)."
            out.line(f"  {out.dim(hinweis)}")

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
# Mail
# --------------------------------------------------------------------------- #


def _mail_parts(config, conn, *, max_per_run: int | None = None):
    skill = build_skill("mail", config=config, conn=conn)
    if max_per_run:
        skill.options.max_per_run = max_per_run
    return skill.client, skill


def _require_db(paths, out: Out):
    if not paths.db_file.exists():
        out.line("Keine Datenbank. Erst: jarvis init")
        return None
    return open_database(paths.db_file)


def cmd_mail_login(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        secrets = default_store()
        if not secrets.writable:
            out.line("Zugangsdaten lassen sich hier nicht ablegen.")
            out.line(f"  {out.dim('Die Anmeldung braucht die macOS-Keychain.')}")
            return 1

        auth = gmail_auth(config, secrets=secrets)
        out.line("Ein Browserfenster oeffnet sich fuer die Zustimmung.")
        auth.login()

        client = gmail_client(config, READ_ONLY, secrets=secrets)
        darf_senden = "send" in send_capabilities(config)
        out.line(f"Angemeldet als {client.address()}")
        out.line(f"  {out.dim('Berechtigungen: gmail.modify und gmail.send')}")
        stand = "freigeschaltet" if darf_senden else "gesperrt (mail_send auf Stufe 0)"
        out.line(f"  {out.dim('Senden ist derzeit ' + stand)}")
        return 0
    except (GmailError, ConfigError) as exc:
        out.line(f"Anmeldung fehlgeschlagen: {exc}")
        return 1
    finally:
        conn.close()


def cmd_mail_poll(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        _client, skill = _mail_parts(config, conn, max_per_run=args.anzahl)
        audit = AuditLog(conn)
        gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
        try:
            report = run_skill(
                skill,
                gate=gate,
                audit=audit,
                approvals=ApprovalStore(conn),
                collect_approvals=config.capability(skill.name).collect_approvals,
            )
        except GmailAuthError as exc:
            out.line(f"{exc}")
            return 1
        except GmailError as exc:
            out.line(f"Gmail: {exc}")
            return 1

        out.line()
        out.line(f"{out.accent('Durchlauf')} {skill.name}   {out.dim(skill.options.query)}")
        out.line()
        out.field("Gefunden", str(report.polled))
        nachsatz = "  (Trockenlauf)" if config.dry_run and report.dry_run else ""
        out.field("Eingeordnet", f"{report.acted}{nachsatz}")
        if report.dry_run:
            out.field("Nur beurteilt", str(report.dry_run))
        out.field("Uebersprungen", str(report.skipped))
        if report.blocked:
            out.field("Blockiert", str(report.blocked))
        if report.failed:
            out.field("Fehler", str(report.failed))
        if report.queued:
            out.field("Zur Freigabe", str(report.queued))

        if report.by_category:
            out.line()
            rows = [[k, str(v)] for k, v in report.by_category.most_common()]
            out.table(["KATEGORIE", "ANZAHL"], rows)
        for fehler in report.errors[:5]:
            out.line(f"  {out.dim(fehler)}")
        out.line()
        return 1 if report.failed else 0
    finally:
        conn.close()


def cmd_mail_labels(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        _client, skill = _mail_parts(config, conn)
        try:
            zuordnung = skill.labels.ensure(skill.options.categories)
        except GmailError as exc:
            out.line(f"Gmail: {exc}")
            return 1
        out.line()
        out.table(
            ["KATEGORIE", "LABEL", "ID"],
            [[k, skill.labels.label_name(k), v] for k, v in zuordnung.items()],
        )
        out.line()
        return 0
    finally:
        conn.close()


def cmd_mail_state(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        store = MailStore(conn)
        zustaende = store.counts_by_state()
        out.line()
        out.field("Erfasst", str(store.total()))
        out.field("Beschriftet", str(store.labelled_count()))
        out.field(
            "Zustaende",
            "  ".join(f"{name} {anzahl}" for name, anzahl in sorted(zustaende.items())) or "--",
        )
        counts = store.counts_by_category()
        if counts:
            out.line()
            out.table(["KATEGORIE", "ANZAHL"], [[k, str(v)] for k, v in counts.items()])
        eintraege = store.recent(args.anzahl)
        if eintraege:
            out.line()
            out.table(
                ["NACHRICHT", "KATEGORIE", "QUELLE", "LABEL", "ZULETZT"],
                [
                    [
                        e.message_id[:16],
                        e.category or "--",
                        e.decided_by or "--",
                        "ja" if e.labelled else "nein",
                        e.last_seen[:19].replace("T", " "),
                    ]
                    for e in eintraege
                ],
            )
        out.line()
        return 0
    finally:
        conn.close()


def cmd_mail_style(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        store = StyleStore(conn)
        if args.refresh:
            client = gmail_client(config, READ_ONLY)
            try:
                ids = client.list_message_ids("in:sent", args.anzahl)
                koerper = [parse_sent_body(client.get_message(mid)) for mid in ids]
            except GmailError as exc:
                out.line(f"Gmail: {exc}")
                return 1
            profil = extract_profile([k for k in koerper if k])
            store.save(profil)
            out.line(f"{len(ids)} gesendete Nachrichten ausgewertet.")
        else:
            profil = store.load()

        out.line()
        out.line(profil.describe())
        if store.updated_at():
            out.line()
            out.line(f"  {out.dim('Stand: ' + str(store.updated_at()))}")
        out.line(f"  {out.dim('Gespeichert werden nur diese Kennzahlen, kein Nachrichtentext.')}")
        out.line()
        return 0
    finally:
        conn.close()


def parse_sent_body(roh: dict) -> str:
    from jarvis.skills.mail.message import parse_message

    return parse_message(roh).body


def _reply_teile(config, conn, *, max_per_run=None):
    skill = build_skill("mail_reply", config=config, conn=conn)
    if max_per_run:
        skill.options.max_per_run = max_per_run
    return skill.client, skill


def cmd_mail_draft(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        _client, skill = _reply_teile(config, conn, max_per_run=args.anzahl)
        audit = AuditLog(conn)
        gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
        try:
            bericht = run_skill(
                skill,
                gate=gate,
                audit=audit,
                approvals=ApprovalStore(conn),
                collect_approvals=config.capability(skill.name).collect_approvals,
            )
        except GmailAuthError as exc:
            out.line(str(exc))
            return 1
        except GmailError as exc:
            out.line(f"Gmail: {exc}")
            return 1

        out.line()
        out.line(f"{out.accent('Durchlauf')} {skill.name}")
        out.line()
        out.field("Gefunden", str(bericht.polled))
        nachsatz = "  (Trockenlauf)" if config.dry_run and bericht.dry_run else ""
        out.field("Entworfen", f"{bericht.acted}{nachsatz}")
        if bericht.dry_run:
            out.field("Nur beurteilt", str(bericht.dry_run))
        out.field("Uebersprungen", str(bericht.skipped))
        if bericht.blocked:
            out.field("Blockiert", str(bericht.blocked))
        if bericht.failed:
            out.field("Fehler", str(bericht.failed))
        if bericht.queued:
            out.field("Zur Freigabe", str(bericht.queued))
        zurueck = sum(1 for e in ReplyStore(conn).recent(bericht.polled or 1) if e.needs_human)
        if zurueck:
            out.field("Zur Durchsicht", str(zurueck))
        for fehler in bericht.errors[:5]:
            out.line(f"  {out.dim(fehler)}")
        out.line()
        return 1 if bericht.failed else 0
    finally:
        conn.close()


def cmd_mail_send(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        capabilities = send_capabilities(config)
        skill = build_skill("mail_send", config=config, conn=conn)
        if args.anzahl:
            skill.options.max_per_run = args.anzahl
        audit = AuditLog(conn)
        gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
        try:
            bericht = run_skill(
                skill,
                gate=gate,
                audit=audit,
                approvals=ApprovalStore(conn),
                collect_approvals=config.capability(skill.name).collect_approvals,
            )
        except GmailAuthError as exc:
            out.line(str(exc))
            return 1
        except GmailError as exc:
            out.line(f"Gmail: {exc}")
            return 1

        stufe = int(config.capability("mail_send").autonomy_level)
        out.line()
        out.line(f"{out.accent('Durchlauf')} {skill.name}")
        out.line()
        out.field("Stufe", f"{stufe} (Senden verlangt 1)")
        out.field("Senderecht", "ja" if "send" in capabilities else out.bold("nein"))
        out.field("Gefunden", str(bericht.polled))
        out.field("Gesendet", str(bericht.acted))
        if bericht.dry_run:
            out.field("Nur beurteilt", str(bericht.dry_run))
        if bericht.skipped:
            out.field("Zurueckgehalten", str(bericht.skipped))
        if bericht.blocked:
            out.field("Blockiert", str(bericht.blocked))
        if bericht.failed:
            out.field("Fehler", str(bericht.failed))
        if bericht.queued:
            out.field("Zur Freigabe", str(bericht.queued))
        for fehler in bericht.errors[:5]:
            out.line(f"  {out.dim(fehler)}")
        out.line()
        return 1 if bericht.failed else 0
    finally:
        conn.close()


def cmd_mail_allowlist(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        options = SendOptions(config.skill_options("mail_send"))
        allowlist = Allowlist(
            conn,
            manual=options.allowlist_manual,
            blocked=options.allowlist_blocked,
            threshold=options.allowlist_threshold,
        )
        if args.refresh:
            client = gmail_client(config, READ_ONLY)
            try:
                eigene = client.address()
                gezaehlt = allowlist.refresh_from_sent(
                    client, max_messages=options.allowlist_scan, own_address=eigene
                )
            except GmailError as exc:
                out.line(f"Gmail: {exc}")
                return 1
            out.line(f"{len(gezaehlt)} Adressen aus gesendeten Nachrichten gezaehlt.")

        out.line()
        out.field("Schwelle", f"{allowlist.threshold} eigene Nachrichten")
        out.field("Erlaubt", str(allowlist.count(only_permitted=True)))
        out.field("Erfasst", str(allowlist.count()))
        if options.allowlist_manual:
            out.field("Von Hand", ", ".join(options.allowlist_manual))
        if options.allowlist_blocked:
            out.field("Gesperrt", ", ".join(options.allowlist_blocked))

        eintraege = allowlist.entries(limit=args.anzahl)
        if eintraege:
            out.line()
            out.table(
                ["ADRESSE", "EIGENE", "ERLAUBT", "ZULETZT"],
                [
                    [
                        e.address,
                        str(e.sent_count),
                        "ja" if allowlist.permits(e.address).allowed else "nein",
                        (e.last_seen or "--")[:10],
                    ]
                    for e in eintraege
                ],
            )
        out.line()
        return 0
    finally:
        conn.close()


def cmd_mail_compare(args: argparse.Namespace, out: Out) -> int:
    """Die Abnahmeprobe: stimmt der Entwurf im Postfach mit dem Protokoll ueberein?"""
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        client = gmail_client(config, DRAFTING)
        eintraege = ReplyStore(conn).with_drafts(limit=args.anzahl)
        if not eintraege:
            out.line("Keine Entwuerfe vorhanden.")
            return 0

        zeilen, abweichungen = [], 0
        for eintrag in eintraege:
            try:
                roh = client.get_draft(str(eintrag.draft_id))
                tatsaechlich = fingerprint_of_draft(roh)
            except GmailError as exc:
                zeilen.append([str(eintrag.draft_id), eintrag.recipient, f"FEHLER: {exc}"])
                abweichungen += 1
                continue
            passt = tatsaechlich == eintrag.fingerprint
            if not passt:
                abweichungen += 1
            zeilen.append(
                [
                    str(eintrag.draft_id),
                    eintrag.recipient,
                    "stimmt ueberein" if passt else out.bold("WEICHT AB"),
                ]
            )

        out.line()
        out.table(["ENTWURF", "EMPFAENGER", "ABGLEICH"], zeilen)
        out.line()
        out.field("Geprueft", str(len(eintraege)))
        out.field("Abweichungen", str(abweichungen))
        out.line()
        return 1 if abweichungen else 0
    finally:
        conn.close()


def cmd_web(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    if not paths.db_file.exists():
        out.line("Keine Datenbank. Erst: jarvis init")
        return 1

    import uvicorn

    from jarvis.interfaces.web import create_app
    from jarvis.interfaces.web.security import load_or_create_token

    # Beide Wege -- Datei und Schalter -- gehen durch dieselbe Pruefung. Ein
    # ConfigError landet in main() und beendet mit Code 2.
    web = config.web.with_overrides(host=args.host, port=args.port)
    token = load_or_create_token(paths.home)

    out.line()
    out.line(f"{out.accent('JARVIS')} {out.dim('Dashboard')}")
    out.line()
    out.field("Adresse", f"{web.base_url}/?token={token}")
    out.field("Token", str(paths.home / "web-token"))
    out.field("Freigaben", "wirken nur ohne Trockenlauf" if config.dry_run else "wirken")
    out.line()
    out.line(f"  {out.dim('Die vollstaendige Adresse mit ?token= im Browser oeffnen.')}")
    out.line(f"  {out.dim('Beenden mit Strg-C.')}")
    out.line()
    # uvicorn blockiert gleich. Die Adresse mit dem Token ist der einzige Weg
    # hinein -- sie darf nicht in einem Puffer stehen bleiben, wenn die Ausgabe
    # kein Terminal ist.
    out.stream.flush()

    uvicorn.run(
        create_app(home=paths.home, token=token, port=web.port),
        host=web.host,
        port=web.port,
        log_level="warning",
        access_log=False,
    )
    return 0


# --------------------------------------------------------------------------- #
# Kalender und Briefing
# --------------------------------------------------------------------------- #


def _durchlauf(skill, config, conn, out: Out) -> int:
    """Ein Durchlauf durch dasselbe Gatter wie bei Mail, gleiche Ausgabe."""
    audit = AuditLog(conn)
    gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
    try:
        report = run_skill(
            skill,
            gate=gate,
            audit=audit,
            approvals=ApprovalStore(conn),
            collect_approvals=config.capability(skill.name).collect_approvals,
        )
    except GmailAuthError as exc:
        out.line(f"{exc}")
        return 1
    except GmailError as exc:
        out.line(f"Google: {exc}")
        return 1

    out.line()
    out.line(f"{out.accent('Durchlauf')} {skill.name}")
    out.line()
    out.field("Gefunden", str(report.polled))
    nachsatz = "  (Trockenlauf)" if config.dry_run and report.dry_run else ""
    out.field("Erledigt", f"{report.acted}{nachsatz}")
    if report.dry_run:
        out.field("Nur beurteilt", str(report.dry_run))
    out.field("Uebersprungen", str(report.skipped))
    if report.blocked:
        out.field("Blockiert", str(report.blocked))
    if report.failed:
        out.field("Fehler", str(report.failed))
    if report.queued:
        out.field("Zur Freigabe", str(report.queued))
    for fehler in report.errors[:5]:
        out.line(f"  {out.dim(fehler)}")
    out.line()
    return 1 if report.failed else 0


def _ortszeit(gespeichert: str | None, zone) -> str:
    """Gespeichert wird UTC, angezeigt wird die Zeit auf der eigenen Uhr."""
    oertlich = local_moment(gespeichert, zone)
    return oertlich.strftime("%d.%m. %H:%M") if oertlich else "ohne Zeit"


def cmd_calendar_poll(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        skill = build_skill("calendar", config=config, conn=conn)
        if args.tage:
            skill.options.window_days = args.tage
        if not has_calendar_scope(gmail_auth(config)):
            out.line("Der vorhandene Token traegt kein Kalenderrecht.")
            out.line(f"  {out.dim('Einmal neu zustimmen: jarvis mail login')}")
            return 1
        return _durchlauf(skill, config, conn, out)
    finally:
        conn.close()


def cmd_calendar_state(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        store = CalendarStore(conn)
        zustaende = store.counts_by_state()
        out.line()
        out.field("Erfasst", str(store.total()))
        out.field(
            "Zustaende",
            "  ".join(f"{name} {anzahl}" for name, anzahl in sorted(zustaende.items())) or "--",
        )
        jetzt = datetime.now(config.timezone)
        termine = store.between(
            von=jetzt.astimezone(UTC).isoformat(),
            bis=(jetzt + timedelta(days=args.tage)).astimezone(UTC).isoformat(),
            limit=args.anzahl,
        )
        if termine:
            out.line()
            out.table(
                ["BEGINN", "TERMIN", "ZUSTAND", "BEFUND"],
                [
                    [
                        _ortszeit(e.starts_at, config.timezone),
                        e.summary[:40],
                        e.state,
                        (e.finding or "--")[:44],
                    ]
                    for e in termine
                ],
            )
        else:
            out.line(f"  {out.dim('Nichts im Fenster. Erst: jarvis calendar poll')}")
        out.line()
        return 0
    finally:
        conn.close()


def cmd_briefing(args: argparse.Namespace, out: Out) -> int:
    """Zeigt das Briefing des Tages, oder erzeugt es."""
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        store = BriefingStore(conn)
        heute = datetime.now(config.timezone).date().isoformat()

        if args.neu:
            code = _durchlauf(build_skill("briefing", config=config, conn=conn), config, conn, out)
            if code:
                return code

        briefing = store.get(heute)
        if briefing is None:
            out.line()
            hinweis = "Fuer heute liegt kein Briefing vor. Erzeugen: jarvis briefing --neu"
            out.line(f"  {out.dim(hinweis)}")
            out.line()
            return 1

        out.line()
        out.line(f"{out.accent('Briefing')} {out.dim(briefing.day)}")
        out.field("Quelle", briefing.model or "ohne Modell")
        out.line()
        for zeile in briefing.text.splitlines():
            out.line(f"  {zeile}")
        out.line()
        return 0
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Dauerbetrieb
# --------------------------------------------------------------------------- #


def cmd_daemon(args: argparse.Namespace, out: Out) -> int:
    """Startet die Uhr. Beendet sich auf Strg-C oder SIGTERM."""
    import signal

    from jarvis.daemon import Daemon, LockBusy

    paths = _paths(args)
    config = Config.load(home=paths.home)
    if not paths.db_file.exists():
        out.line("Keine Datenbank. Erst: jarvis init")
        return 1
    if not config.daemon.enabled:
        out.line("Der Daemon ist nicht eingeschaltet.")
        out.line(f"  {out.dim('In der Konfiguration: [daemon] enabled = true')}")
        return 2
    if not config.daemon.schedule:
        out.line("Kein Zeitplan hinterlegt ([daemon.schedule]).")
        return 2

    logger = configure_logging(paths.log_dir, level=config.log_level)
    daemon = Daemon(config=config, paths=paths, logger=logger.getChild("daemon"))
    signal.signal(signal.SIGTERM, daemon.anhalten)
    signal.signal(signal.SIGINT, daemon.anhalten)

    plan = "  ".join(f"{k} alle {v} min" for k, v in sorted(config.daemon.schedule.items()))
    out.line()
    out.line(f"{out.accent('JARVIS')} {out.dim('Dauerbetrieb')}")
    out.line()
    out.field("Zeitplan", plan)
    out.field("Takt", f"{config.daemon.tick_seconds} s")
    out.field("Trockenlauf", "an" if config.dry_run else out.bold("AUS"))
    out.field("Protokoll", str(paths.log_dir / "jarvis.jsonl"))
    out.line()
    out.line(f"  {out.dim('Beenden mit Strg-C. Anhalten jederzeit: jarvis stop')}")
    out.line()
    out.stream.flush()

    try:
        return daemon.run()
    except LockBusy as exc:
        out.line(f"{exc}")
        return 3


# --------------------------------------------------------------------------- #
# Modelltrennung
# --------------------------------------------------------------------------- #

PRUEFPUNKTE = (
    ("jarvis_verzeichnis", "~/.jarvis lesen"),
    ("jarvis_datenbank", "state.db lesen"),
    ("keychain_verzeichnis", "Keychain-Dateien lesen"),
    ("keychain_kommando", "security aufrufen"),
    ("netz_ausgehend", "Netz nach aussen"),
)


def cmd_llm_check(args: argparse.Namespace, out: Out) -> int:
    """Misst nach, was der auswertende Prozess tatsaechlich noch kann.

    Eine Sandbox, die man nicht nachmisst, ist eine Behauptung. Gemessen wird
    zweimal -- ohne und mit Trennung -- weil ein einzelner Lauf nichts
    beweist: dass etwas fehlt, kann auch heissen, dass es das nie gab.
    """
    from jarvis.llm.isolation import sandbox_available, sonde_starten

    paths = _paths(args)
    config = Config.load(home=paths.home)
    eingestellt = config.llm.isolation

    out.line()
    out.field("Eingestellt", f"[llm] isolation = {eingestellt}")
    out.field("Plattform", f"{sys.platform}")
    out.field("sandbox-exec", "vorhanden" if sandbox_available() else "nicht vorhanden")
    out.line()

    laeufe = {}
    for modus in ("geerbt", "subprocess", "sandbox"):
        laeufe[modus] = sonde_starten(mode=modus, home=paths.home)

    spalten = ["PRUEFUNG"]
    gemessen = [m for m in ("geerbt", "subprocess", "sandbox") if laeufe[m].ok]
    spalten += [m.upper() for m in gemessen]

    zeilen = []
    for schluessel, beschriftung in PRUEFPUNKTE:
        zeile = [beschriftung]
        for modus in gemessen:
            befund = laeufe[modus].befunde.get("checks", {}).get(schluessel, {})
            zeile.append("moeglich" if befund.get("ok") else "verweigert")
        zeilen.append(zeile)

    zeile = ["JARVIS-Variablen"]
    for modus in gemessen:
        anzahl = len(laeufe[modus].befunde.get("jarvis_env", []))
        zeile.append(f"{anzahl} sichtbar")
    zeilen.append(zeile)

    if zeilen and len(spalten) > 1:
        out.table(spalten, zeilen)
    out.line()

    for modus in ("geerbt", "subprocess", "sandbox"):
        if not laeufe[modus].ok:
            out.line(f"  {out.dim(modus + ': ' + (laeufe[modus].fehler or 'kein Befund'))}")

    out.line()
    out.line(f"  {out.dim('geerbt = ohne Trennung, nur als Vergleichswert.')}")
    if not laeufe["sandbox"].ok:
        hinweis = "Die Sandbox-Stufe wurde hier nicht gemessen. Sie braucht macOS."
        out.line(f"  {out.dim(hinweis)}")
    out.line()
    return 0


# --------------------------------------------------------------------------- #
# Sprache
# --------------------------------------------------------------------------- #


def _voice_ausgeben(antwort, out: Out) -> int:
    """Immer auch schreiben. Was gesprochen wurde, soll nachlesbar sein."""
    if not antwort.angesprochen:
        out.line()
        out.line(f"  {out.dim('Ohne Weckwort. Nichts geantwortet.')}")
        if antwort.gehoert:
            out.line(f"  {out.dim('Gehoert: ' + antwort.gehoert)}")
        out.line()
        return 0

    out.line()
    # Ist schon das Zuhoeren gescheitert, gibt es nichts zu "verstehen".
    # Dann steht da der Fehler, nicht eine Absicht, die niemand gemeint hat.
    if not antwort.gehoert and antwort.fehler:
        for zeile in (antwort.text or "(nichts)").splitlines():
            out.line(f"  {zeile}")
        out.line(f"  {out.dim(antwort.fehler)}")
        out.line()
        return 1

    out.field("Verstanden", f"{antwort.absicht}  ({antwort.quelle})")
    if antwort.gehoert:
        out.field("Gehoert", antwort.gehoert)
    out.line()
    for zeile in (antwort.text or "(nichts)").splitlines():
        out.line(f"  {zeile}")
    if antwort.fehler:
        out.line()
        out.line(f"  {out.dim('Nicht vorgelesen: ' + antwort.fehler)}")
    out.line()
    return 1 if antwort.fehler else 0


def cmd_voice_check(args: argparse.Namespace, out: Out) -> int:
    """Was auf diesem Rechner bereitsteht. Aendert nichts."""
    from jarvis.interfaces.voice.speak import MacSpeaker
    from jarvis.interfaces.voice.transcribe import CommandRecorder, WhisperCppTranscriber

    paths = _paths(args)
    config = Config.load(home=paths.home)
    stimme = config.voice

    umwandler = WhisperCppTranscriber(
        binary=stimme.whisper_bin, model=stimme.whisper_model, language=stimme.language
    )
    sprecher = MacSpeaker(voice=stimme.voice_name, rate=stimme.rate)
    aufnahme = CommandRecorder(command=stimme.record_command)

    out.line()
    out.field("Weckwort", stimme.wake_word or "keins (jeder Satz gilt)")
    out.field("Vorlesen", "an" if stimme.speak else "aus")
    out.field("Absichten", f"Regeln + {stimme.task}" if stimme.uses_model else "nur Regeln")
    out.line()
    out.table(
        ["TEIL", "BEREIT", "BEFUND"],
        [
            ["Aufnahme", "ja" if aufnahme.available() else "nein", aufnahme.describe()],
            ["Whisper", "ja" if umwandler.available() else "nein", umwandler.describe()],
            ["Stimme", "ja" if sprecher.available() else "nein", sprecher.describe()],
        ],
    )
    out.line()
    if not umwandler.available():
        out.line(f"  {out.dim("Ohne Whisper bleibt: jarvis voice ask '...'")}")
    hinweis = "Sprache liest vor und haelt an. Senden und Freigeben nur im Dashboard."
    out.line(f"  {out.dim(hinweis)}")
    out.line()
    return 0


def cmd_voice_ask(args: argparse.Namespace, out: Out) -> int:
    """Ein getippter Satz durch dieselbe Kette. Braucht kein Mikrofon."""
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        from jarvis.interfaces.voice.session import build_session

        sitzung = build_session(config, conn, speak=None if args.laut else False)
        return _voice_ausgeben(sitzung.ask(" ".join(args.satz), herkunft="cli"), out)
    finally:
        conn.close()


def cmd_voice_hear(args: argparse.Namespace, out: Out) -> int:
    """Eine fertige Aufnahme."""
    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        from jarvis.interfaces.voice.session import build_session

        datei = Path(args.datei).expanduser()
        if not datei.is_file():
            out.line(f"Keine Aufnahme unter {datei}")
            return 1
        sitzung = build_session(config, conn, speak=None if args.laut else False)
        return _voice_ausgeben(sitzung.hear(datei), out)
    finally:
        conn.close()


def cmd_voice_listen(args: argparse.Namespace, out: Out) -> int:
    """Aufnehmen, umwandeln, antworten. Eine Runde, keine Dauerschleife.

    Eine Dauerschleife gehoert in den Daemon, den es noch nicht gibt. Bis
    dahin ist das hier der ganze Weg vom Mikrofon bis zur Antwort.
    """
    import tempfile

    paths = _paths(args)
    config = Config.load(home=paths.home)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        from jarvis.interfaces.voice.session import build_session
        from jarvis.interfaces.voice.transcribe import CommandRecorder, RecordingError

        aufnahme = CommandRecorder(command=config.voice.record_command)
        if not aufnahme.available():
            out.line(f"Aufnahme nicht eingerichtet: {aufnahme.describe()}")
            out.line(f"  {out.dim('voice.record_command in der Konfiguration setzen.')}")
            return 1

        out.line()
        out.line(f"  {out.dim('Aufnahme laeuft ...')}")
        out.stream.flush()
        with tempfile.TemporaryDirectory(prefix="jarvis-voice-") as ordner:
            ziel = Path(ordner) / "aufnahme.wav"
            try:
                aufnahme.record(ziel)
            except RecordingError as exc:
                out.line(f"{exc}")
                return 1
            sitzung = build_session(config, conn, speak=None if args.laut else False)
            return _voice_ausgeben(sitzung.hear(ziel), out)
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Gedaechtnis und Kontext
# --------------------------------------------------------------------------- #


def cmd_memory(args: argparse.Namespace, out: Out) -> int:
    paths = _paths(args)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        gedaechtnis = LongTermMemory(conn)

        if args.vergessen:
            entfernt = gedaechtnis.forget(args.vergessen)
            out.line("Vergessen." if entfernt else "War nicht gespeichert.")
            return 0

        if args.schluessel:
            if not args.wert:
                out.line("Zum Ablegen wird ein Wert gebraucht.")
                return 1
            fakt = gedaechtnis.remember(
                args.schluessel,
                " ".join(args.wert),
                category=args.kategorie,
                source="cli",
                weight=args.gewicht,
            )
            out.line(f"Gemerkt: {fakt.key} = {fakt.value}")
            return 0

        fakten = gedaechtnis.all(limit=args.anzahl, category=args.kategorie_filter)
        out.line()
        out.field("Tatsachen", str(gedaechtnis.count()))
        if fakten:
            out.line()
            out.table(
                ["SCHLUESSEL", "WERT", "KATEGORIE", "GEWICHT"],
                [[f.key, f.value[:60], f.category, f"{f.weight:g}"] for f in fakten],
                mono=(0, 3),
            )
        else:
            out.line(f"  {out.dim('Nichts abgelegt.')}")
        out.line()
        return 0
    finally:
        conn.close()


def cmd_context(args: argparse.Namespace, out: Out) -> int:
    """Zeigt, was bei einer Anfrage tatsaechlich ans Modell ginge.

    Der Sinn der Trennung von Speicherung und Kontext ist, dass man sie
    nachsehen kann. Ohne diesen Befehl waere die Obergrenze eine Behauptung.
    """
    paths = _paths(args)
    conn = _require_db(paths, out)
    if conn is None:
        return 1
    try:
        bauer = ContextBuilder(
            memory=LongTermMemory(conn),
            short_term=ShortTermContext(conn, scope=args.bereich),
        )
        gebaut = bauer.build(preamble=args.praeambel or "", terms=args.suche or "")

        out.line()
        out.field("Bereich", args.bereich)
        out.field("Obergrenze", f"{bauer.budget.max_chars} Zeichen")
        out.field("Belegt", f"{gebaut.chars} Zeichen")
        out.field("Tatsachen", f"{len(gebaut.facts)} von hoechstens {bauer.budget.max_facts}")
        out.field("Verlauf", f"{len(gebaut.entries)} von hoechstens {bauer.budget.max_entries}")
        if gebaut.truncated:
            out.field(
                "Weggelassen",
                f"{gebaut.dropped_facts} Tatsachen, {gebaut.dropped_entries} Eintraege",
            )
        out.line()
        out.line(f"  {out.dim('--- was ans Modell ginge ---')}")
        for zeile in (gebaut.text or "(nichts)").splitlines():
            out.line(f"  {zeile}")
        out.line()
        out.line(f"  {out.dim('Protokoll und Logs sind hier keine Quelle und gehen nie mit.')}")
        out.line()
        return 0
    finally:
        conn.close()


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

    p = sub.add_parser("memory", help="Dauerhaft abgelegte Tatsachen")
    p.add_argument("schluessel", nargs="?", help="Schluessel zum Ablegen")
    p.add_argument("wert", nargs="*", help="Wert zum Ablegen")
    p.add_argument("--vergessen", metavar="SCHLUESSEL", help="Eintrag entfernen")
    p.add_argument(
        "--kategorie", default="sonstiges", choices=sorted(CATEGORIES), help="beim Ablegen"
    )
    p.add_argument("--kategorie-filter", dest="kategorie_filter", help="beim Auflisten")
    p.add_argument("--gewicht", type=float, default=1.0, help="Wichtigkeit")
    p.add_argument("-n", "--anzahl", type=int, default=30, help="Anzahl Zeilen")
    p.set_defaults(func=cmd_memory)

    p = sub.add_parser("context", help="Was bei einer Anfrage ans Modell ginge")
    p.add_argument("--bereich", default="mail_reply", help="Bereich des Kurzzeitkontexts")
    p.add_argument("--suche", help="Suchbegriffe fuer passende Tatsachen")
    p.add_argument("--praeambel", help="Anweisungstext, der vorangestellt wird")
    p.set_defaults(func=cmd_context)

    p = sub.add_parser("web", help="Dashboard auf localhost starten")
    p.add_argument("--host", default=None, help="statt [web].host")
    p.add_argument("--port", type=int, default=None, help="statt [web].port")
    p.set_defaults(func=cmd_web)

    p = sub.add_parser("daemon", help="Dauerbetrieb starten (Zeitplan aus [daemon])")
    p.set_defaults(func=cmd_daemon)

    modell = sub.add_parser("llm", help="Modelltrennung nachmessen")
    modell_sub = modell.add_subparsers(dest="unterbefehl", required=True)
    m = modell_sub.add_parser("check", help="Was der auswertende Prozess noch kann")
    m.set_defaults(func=cmd_llm_check)

    sprache = sub.add_parser("voice", help="Sprache: vorlesen und anhalten")
    sprache_sub = sprache.add_subparsers(dest="unterbefehl", required=True)

    v = sprache_sub.add_parser("check", help="Was auf diesem Rechner bereitsteht")
    v.set_defaults(func=cmd_voice_check)

    v = sprache_sub.add_parser("ask", help="Einen getippten Satz durch dieselbe Kette")
    v.add_argument("satz", nargs="+", help="was gesagt worden waere")
    v.add_argument("--laut", action="store_true", help="Antwort auch vorlesen")
    v.set_defaults(func=cmd_voice_ask)

    v = sprache_sub.add_parser("hear", help="Eine fertige Aufnahme auswerten")
    v.add_argument("datei", help="Pfad zur Audiodatei")
    v.add_argument("--laut", action="store_true", help="Antwort auch vorlesen")
    v.set_defaults(func=cmd_voice_hear)

    v = sprache_sub.add_parser("listen", help="Aufnehmen und antworten (eine Runde)")
    v.add_argument("--laut", action="store_true", help="Antwort auch vorlesen")
    v.set_defaults(func=cmd_voice_listen)

    kalender = sub.add_parser("calendar", help="Termine lesen und auf Konflikte pruefen")
    kalender_sub = kalender.add_subparsers(dest="unterbefehl", required=True)

    k = kalender_sub.add_parser("poll", help="Einen Durchlauf ausfuehren")
    k.add_argument("--tage", type=int, default=None, help="statt [skills.calendar].window_days")
    k.set_defaults(func=cmd_calendar_poll)

    k = kalender_sub.add_parser("state", help="Was bisher gesehen wurde")
    k.add_argument("--tage", type=int, default=7, help="Fenster in Tagen")
    k.add_argument("-n", "--anzahl", type=int, default=20, help="Anzahl Zeilen")
    k.set_defaults(func=cmd_calendar_state)

    p = sub.add_parser("briefing", help="Das Briefing des Tages")
    p.add_argument("--neu", action="store_true", help="jetzt erzeugen statt nur zeigen")
    p.set_defaults(func=cmd_briefing)

    mail = sub.add_parser("mail", help="Postfach lesen und einordnen")
    mail_sub = mail.add_subparsers(dest="unterbefehl", required=True)

    m = mail_sub.add_parser("login", help="Bei Gmail anmelden (einmalig, mit Browser)")
    m.set_defaults(func=cmd_mail_login)

    m = mail_sub.add_parser("poll", help="Einen Durchlauf ausfuehren")
    m.add_argument(
        "-n", "--anzahl", type=int, default=None, help="Obergrenze fuer diesen Durchlauf"
    )
    m.set_defaults(func=cmd_mail_poll)

    m = mail_sub.add_parser("labels", help="Fehlende Labels anlegen")
    m.set_defaults(func=cmd_mail_labels)

    m = mail_sub.add_parser("state", help="Was bisher beurteilt wurde")
    m.add_argument("-n", "--anzahl", type=int, default=15, help="Anzahl Zeilen")
    m.set_defaults(func=cmd_mail_state)

    m = mail_sub.add_parser("style", help="Schreibstil zeigen oder neu ableiten")
    m.add_argument("--refresh", action="store_true", help="aus gesendeten Mails neu ableiten")
    m.add_argument("-n", "--anzahl", type=int, default=200, help="wie viele durchsehen")
    m.set_defaults(func=cmd_mail_style)

    m = mail_sub.add_parser("draft", help="Antwortentwuerfe schreiben")
    m.add_argument("-n", "--anzahl", type=int, default=None, help="Obergrenze")
    m.set_defaults(func=cmd_mail_draft)

    m = mail_sub.add_parser("send", help="Fertige Entwuerfe senden (verlangt Stufe 1)")
    m.add_argument("-n", "--anzahl", type=int, default=None, help="Obergrenze")
    m.set_defaults(func=cmd_mail_send)

    m = mail_sub.add_parser("allowlist", help="Wer eine Antwort bekommen darf")
    m.add_argument("--refresh", action="store_true", help="aus gesendeten Mails neu zaehlen")
    m.add_argument("-n", "--anzahl", type=int, default=25, help="Anzahl Zeilen")
    m.set_defaults(func=cmd_mail_allowlist)

    m = mail_sub.add_parser("compare", help="Entwuerfe gegen das Protokoll abgleichen")
    m.add_argument("-n", "--anzahl", type=int, default=100, help="wie viele pruefen")
    m.set_defaults(func=cmd_mail_compare)

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
