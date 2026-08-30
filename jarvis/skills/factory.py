"""Faehigkeiten aus der Konfiguration bauen.

Eine Stelle, die weiss wie eine Faehigkeit entsteht -- Kommandozeile und
Dashboard benutzen dieselbe. Vorher stand das in der CLI, und das Dashboard
haette es abschreiben muessen; zwei Fassungen derselben Verdrahtung waeren
genau die Art Fehler, die man erst bemerkt, wenn eine davon zu viel darf.

Wichtig ist `send_capabilities`: welche Rechte der Gmail-Client bekommt,
leitet sich aus derselben Rechnung ab, die auch das Gatter anstellt --
`Config.permits`. Steht `mail_send` auf Stufe 0, wird der Client ohne
Senderecht gebaut, egal wer ihn baut.

`approved` reicht eine ausdrueckliche Freigabe durch. Ohne das gab es einen
widerspruechlichen Zustand: das Gatter liess eine freigegebene Aktion durch,
der Client hatte aber mangels Stufe kein Senderecht und scheiterte danach.
Beide fragen jetzt dieselbe Stelle -- die Freigabe wirkt auf das Gatter und
auf die Rechte des Clients gleichermassen.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jarvis.core.config import Config, ConfigError
from jarvis.core.context import ContextBuilder, ShortTermContext
from jarvis.core.memory import LongTermMemory
from jarvis.core.secrets import SecretStore, default_store
from jarvis.llm.providers import build_providers
from jarvis.llm.router import Router
from jarvis.skills.base import Skill
from jarvis.skills.briefing.skill import BriefingSkill
from jarvis.skills.briefing.store import BriefingStore
from jarvis.skills.calendar.google import CALENDAR_READ, CalendarClient
from jarvis.skills.calendar.mock import MockCalendarClient
from jarvis.skills.calendar.skill import CalendarSkill
from jarvis.skills.calendar.store import CalendarStore
from jarvis.skills.mail.allowlist import Allowlist
from jarvis.skills.mail.gmail import DRAFTING, LABELLING, SENDING, GmailAuth, GmailClient
from jarvis.skills.mail.mock import MockGmailClient
from jarvis.skills.mail.reply import MailDraftSkill, MailSendSkill, SendOptions
from jarvis.skills.mail.skill import MailOptions, MailSkill
from jarvis.skills.mail.store import MailStore, ReplyStore
from jarvis.skills.mail.style import StyleStore
from jarvis.skills.research.skill import ResearchSkill
from jarvis.skills.research.source import MockSource, Source
from jarvis.skills.research.store import ResearchStore

__all__ = [
    "BUILDABLE",
    "build_skill",
    "calendar_client",
    "gmail_auth",
    "gmail_client",
    "research_sources",
    "send_capabilities",
]

BUILDABLE = ("mail", "mail_reply", "mail_send", "calendar", "briefing", "research")


def send_capabilities(config: Config, *, approved: bool = False) -> frozenset[str]:
    """Senderecht nur, wenn Stufe oder Freigabe es hergeben -- dieselbe Rechnung."""
    return SENDING if config.permits("mail_send", 1, approved=approved) else DRAFTING


def gmail_auth(config: Config, *, secrets: SecretStore | None = None) -> GmailAuth:
    optionen = MailOptions(config.skill_options("mail"), known_tasks=set(config.llm.tasks))
    return GmailAuth(
        secrets or default_store(),
        client_secret_name=optionen.client_secret,
        token_name=optionen.token_secret,
    )


def _fixtures(config: Config) -> Path | None:
    pfad = config.services.fixtures.strip()
    return Path(pfad).expanduser() if pfad else None


def gmail_client(
    config: Config, capabilities: frozenset[str], *, secrets: SecretStore | None = None
) -> GmailClient | MockGmailClient:
    """Der echte Client -- oder das Laufzeit-Doppel, wenn `[services]` es sagt.

    Die Faehigkeiten gehen unveraendert weiter. Ein Mock, der mehr duerfte
    als der echte Client, waere ein Mock, dem man nichts glauben kann.
    """
    if config.services.is_mock:
        return MockGmailClient(capabilities, fixtures=_fixtures(config))
    return GmailClient(gmail_auth(config, secrets=secrets), capabilities=capabilities)


def calendar_client(
    config: Config, *, secrets: SecretStore | None = None
) -> CalendarClient | MockCalendarClient:
    """Immer nur lesend. Einen Schreibpfad gibt es in keinem der beiden."""
    if config.services.is_mock:
        return MockCalendarClient(capabilities=CALENDAR_READ, fixtures=_fixtures(config))
    return CalendarClient(gmail_auth(config, secrets=secrets), capabilities=CALENDAR_READ)


def research_sources(config: Config) -> dict[str, Source]:
    """Die vorhandenen Quellen. Welche davon benutzt werden, sagt die Freigabeliste.

    In diesem Stand gibt es genau eine, und sie geht nicht ins Netz. Eine
    echte Quelle kommt spaeter hier dazu -- die Faehigkeit selbst muss sich
    dafuer nicht aendern.
    """
    return {"beispiel": MockSource()}


def build_skill(
    name: str,
    *,
    config: Config,
    conn: sqlite3.Connection,
    secrets: SecretStore | None = None,
    approved: bool = False,
) -> Skill:
    """Baut eine Faehigkeit. `approved` steht fuer eine Freigabe von Hand.

    Sie wirkt nur auf die Rechte des Clients -- ob tatsaechlich gehandelt
    werden darf, entscheidet weiterhin das Gatter.
    """
    speicher = secrets or default_store()

    if name == "mail":
        return MailSkill.from_config(
            config,
            client=gmail_client(config, LABELLING, secrets=speicher),
            router=Router(config.llm, build_providers(config.llm, speicher)),
            store=MailStore(conn),
        )

    if name == "mail_reply":
        return MailDraftSkill.from_config(
            config,
            client=gmail_client(config, DRAFTING, secrets=speicher),
            router=Router(config.llm, build_providers(config.llm, speicher)),
            mail_store=MailStore(conn),
            reply_store=ReplyStore(conn),
            style=StyleStore(conn).load(),
            context=ContextBuilder(
                memory=LongTermMemory(conn),
                short_term=ShortTermContext(conn, scope="mail_reply"),
            ),
        )

    if name == "mail_send":
        optionen = SendOptions(config.skill_options("mail_send"))
        return MailSendSkill(
            options=optionen,
            client=gmail_client(
                config, send_capabilities(config, approved=approved), secrets=speicher
            ),
            reply_store=ReplyStore(conn),
            allowlist=Allowlist(
                conn,
                manual=optionen.allowlist_manual,
                blocked=optionen.allowlist_blocked,
                threshold=optionen.allowlist_threshold,
            ),
        )

    if name == "calendar":
        return CalendarSkill.from_config(
            config,
            client=calendar_client(config, secrets=speicher),
            store=CalendarStore(conn),
        )

    if name == "briefing":
        return BriefingSkill.from_config(
            config,
            router=Router(config.llm, build_providers(config.llm, speicher)),
            briefings=BriefingStore(conn),
            calendar=CalendarStore(conn),
            mail=MailStore(conn),
            replies=ReplyStore(conn),
            context=ContextBuilder(
                memory=LongTermMemory(conn),
                short_term=ShortTermContext(conn, scope="briefing"),
            ),
        )

    if name == "research":
        return ResearchSkill.from_config(
            config,
            router=Router(config.llm, build_providers(config.llm, speicher)),
            store=ResearchStore(conn),
            sources=research_sources(config),
        )

    bekannt = ", ".join(BUILDABLE)
    raise ConfigError(f"Unbekannte Faehigkeit {name!r} (bekannt: {bekannt})")
