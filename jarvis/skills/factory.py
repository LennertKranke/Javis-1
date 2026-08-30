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

from jarvis.core.config import Config, ConfigError
from jarvis.core.context import ContextBuilder, ShortTermContext
from jarvis.core.memory import LongTermMemory
from jarvis.core.secrets import SecretStore, default_store
from jarvis.llm.providers import build_providers
from jarvis.llm.router import Router
from jarvis.skills.base import Skill
from jarvis.skills.mail.allowlist import Allowlist
from jarvis.skills.mail.gmail import DRAFTING, LABELLING, SENDING, GmailAuth, GmailClient
from jarvis.skills.mail.reply import MailDraftSkill, MailSendSkill, SendOptions
from jarvis.skills.mail.skill import MailOptions, MailSkill
from jarvis.skills.mail.store import MailStore, ReplyStore
from jarvis.skills.mail.style import StyleStore

__all__ = ["BUILDABLE", "build_skill", "gmail_auth", "gmail_client", "send_capabilities"]

BUILDABLE = ("mail", "mail_reply", "mail_send")


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


def gmail_client(
    config: Config, capabilities: frozenset[str], *, secrets: SecretStore | None = None
) -> GmailClient:
    return GmailClient(gmail_auth(config, secrets=secrets), capabilities=capabilities)


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

    bekannt = ", ".join(BUILDABLE)
    raise ConfigError(f"Unbekannte Faehigkeit {name!r} (bekannt: {bekannt})")
