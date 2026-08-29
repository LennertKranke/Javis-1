"""Mail: lesen, einordnen, Entwuerfe schreiben, Entwuerfe senden."""

from jarvis.skills.mail.allowlist import Allowlist, AllowVerdict
from jarvis.skills.mail.compose import ReplyTarget, fingerprint, reply_target
from jarvis.skills.mail.gmail import (
    DRAFTING,
    LABELLING,
    READ_ONLY,
    SENDING,
    GmailAuth,
    GmailAuthError,
    GmailClient,
    GmailError,
)
from jarvis.skills.mail.message import MailAddress, MailMessage, parse_message
from jarvis.skills.mail.reply import MailDraftSkill, MailSendSkill, ReplyOptions, SendOptions
from jarvis.skills.mail.skill import MailOptions, MailSkill
from jarvis.skills.mail.store import MailStore, ReplyStore
from jarvis.skills.mail.style import StyleProfile, StyleStore, extract_profile

__all__ = [
    "DRAFTING",
    "LABELLING",
    "READ_ONLY",
    "SENDING",
    "AllowVerdict",
    "Allowlist",
    "GmailAuth",
    "GmailAuthError",
    "GmailClient",
    "GmailError",
    "MailAddress",
    "MailDraftSkill",
    "MailMessage",
    "MailOptions",
    "MailSendSkill",
    "MailSkill",
    "MailStore",
    "ReplyOptions",
    "ReplyStore",
    "ReplyTarget",
    "SendOptions",
    "StyleProfile",
    "StyleStore",
    "extract_profile",
    "fingerprint",
    "parse_message",
    "reply_target",
]
