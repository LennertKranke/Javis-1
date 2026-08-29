"""Mail: lesen und einordnen. Sendet nicht."""

from jarvis.skills.mail.gmail import GmailAuth, GmailAuthError, GmailClient, GmailError
from jarvis.skills.mail.message import MailAddress, MailMessage, parse_message
from jarvis.skills.mail.skill import MailOptions, MailSkill
from jarvis.skills.mail.store import MailStore

__all__ = [
    "GmailAuth",
    "GmailAuthError",
    "GmailClient",
    "GmailError",
    "MailAddress",
    "MailMessage",
    "MailOptions",
    "MailSkill",
    "MailStore",
    "parse_message",
]
