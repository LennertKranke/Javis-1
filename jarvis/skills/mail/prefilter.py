"""Vorfilter: was sich ohne Modell entscheiden laesst, entscheidet sich hier.

Ein Newsletter mit List-Unsubscribe-Kopf ist ein Newsletter. Dafuer ein Modell
zu fragen kostet Geld, dauert laenger und ist unzuverlaessiger als die Regel.
Der Vorfilter nimmt deshalb alles vorweg, was aus vertrauenswuerdigen Kopffeldern
folgt -- und laesst den Rest an den Klassifizierer durch.

Alle Regeln stuetzen sich ausschliesslich auf Kopffelder und Gmail-Kennungen,
nie auf den Nachrichtentext. Eine Regel, die im Text nach "Rechnung" sucht,
waere von aussen steuerbar; die hier sind es nicht.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from jarvis.skills.mail.message import MailMessage

__all__ = ["PrefilterHit", "prefilter"]

BULK_PRECEDENCE = frozenset({"bulk", "list", "junk"})


@dataclass(frozen=True)
class PrefilterHit:
    action: str  # "label" oder "skip"
    reason: str
    category: str | None = None


def prefilter(
    message: MailMessage,
    *,
    categories: Collection[str],
    own_addresses: Collection[str] = (),
    own_label_ids: Collection[str] = (),
) -> PrefilterHit | None:
    """Gibt eine Entscheidung zurueck, oder None fuer "das Modell muss ran"."""

    if any(message.has_label(label) for label in own_label_ids):
        return PrefilterHit(action="skip", reason="bereits von JARVIS eingeordnet")

    if message.sender and message.sender.address in {a.lower() for a in own_addresses}:
        return PrefilterHit(action="skip", reason="von mir selbst gesendet")

    if message.auto_submitted and message.auto_submitted != "no":
        return _label_or_none(
            "benachrichtigung", categories, f"Auto-Submitted: {message.auto_submitted}"
        )

    if message.list_unsubscribe or (message.precedence in BULK_PRECEDENCE):
        grund = "List-Unsubscribe vorhanden" if message.list_unsubscribe else "Precedence: bulk"
        return _label_or_none("newsletter", categories, grund)

    if not message.subject.strip() and not message.body.strip():
        return _label_or_none("sonstiges", categories, "ohne Betreff und ohne Text")

    return None


def _label_or_none(category: str, categories: Collection[str], reason: str) -> PrefilterHit | None:
    """Nur einordnen, wenn die Kategorie auch konfiguriert ist.

    Sonst wuerde der Vorfilter ein Label erzwingen, das der Nutzer aus seiner
    Kategorienliste bewusst entfernt hat. Dann lieber das Modell fragen.
    """
    if category not in categories:
        return None
    return PrefilterHit(action="label", reason=reason, category=category)
