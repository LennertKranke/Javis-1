"""Die Antwort zusammenbauen. Deterministisch, ohne Modell.

Das ist Prinzip 2.1 an der Stelle, wo es zaehlt. Der Empfaenger wird hier
berechnet -- aus Reply-To, ersatzweise aus From der Originalnachricht. Das
Modell liefert ausschliesslich den Fliesstext; es sieht diese Datei nie und
kann nichts an ihr vorbeireichen.

Die gefaehrlichste Zeile ist der Betreff. Er stammt vom Absender und wird in
einen Kopf zurueckgeschrieben. Steht darin ein Zeilenumbruch, waere die Zeile
danach ein neuer Kopf -- ein Betreff mit eingebautem "Bcc:" schickt sonst eine
Blindkopie an den Angreifer mit. `_header_wert` entfernt deshalb aus jedem
Wert, der in einen Kopf geht, alles was eine Zeile beenden koennte, bevor
irgendetwas anderes passiert.

Der Fingerabdruck am Ende ist der Grund, warum sich Trockenlauf und
tatsaechlicher Entwurf spaeter vergleichen lassen: er deckt genau die Teile ab,
die die Nachricht ausmachen, und nichts Zeitabhaengiges.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from email.message import EmailMessage
from email.policy import SMTP

from jarvis.skills.mail.message import MailMessage, headers_of, parse_message

__all__ = [
    "ComposeError",
    "ReplyTarget",
    "antwort_betreff",
    "build_message",
    "fingerprint",
    "fingerprint_of_draft",
    "raw_for_gmail",
    "reply_target",
]

# Alles, was in einem Kopffeld eine neue Zeile beginnen koennte. Neben CR und
# LF auch NEL, Zeilen- und Absatztrenner -- manche Bibliotheken behandeln die
# wie einen Umbruch, und darauf soll es nicht ankommen.
_STEUERZEICHEN = re.compile(r"[\r\n\x00\x0b\x0c\x85\u2028\u2029]+")
_PRAEFIX = re.compile(r"^(?:\s*(?:re|aw|antw|wg|fwd|fw)\s*(?:\[\d+\])?\s*:\s*)+", re.IGNORECASE)
# Im Koerper sind Zeilenumbrueche erlaubt und noetig -- dort darf nur weg, was
# unsichtbar oder kaputt ist. Der Kopfzeilen-Reiniger wuerde hier Absaetze
# zusammenziehen und die Antwort zu einem Block machen.
_KOERPER_MUELL = re.compile(r"[\x00\x0b\x0c\x85\u2028\u2029]+")
_LEERZEILEN = re.compile(r"\n{3,}")
_MEHRFACH_LEERRAUM = re.compile(r"\s+")

MAX_SUBJECT = 200
MAX_BODY = 20000


class ComposeError(ValueError):
    """Die Antwort laesst sich nicht adressieren oder nicht bauen."""


@dataclass(frozen=True)
class ReplyTarget:
    """Wohin die Antwort geht. Ausschliesslich aus den Originalkopffeldern."""

    to: str
    thread_id: str
    subject: str
    in_reply_to: str | None = None
    references: str | None = None


def _header_wert(wert: str, *, grenze: int = MAX_SUBJECT) -> str:
    """Macht fremden Text kopffeldtauglich.

    Erst raus, was eine Zeile beenden koennte, dann Leerraum verdichten, dann
    kuerzen. Die Reihenfolge zaehlt: erst kuerzen und dann saeubern liesse
    einen Umbruch stehen, der genau auf der Schnittkante liegt.
    """
    ohne_steuerzeichen = _STEUERZEICHEN.sub(" ", wert or "")
    verdichtet = _MEHRFACH_LEERRAUM.sub(" ", ohne_steuerzeichen).strip()
    return verdichtet[:grenze]


def _koerper_wert(body: str) -> str:
    """Bereinigt den Nachrichtentext, ohne seine Gliederung zu zerstoeren.

    Der Koerper steht hinter der Leerzeile und kann kein Kopffeld erzeugen --
    Zeilenumbrueche sind hier also unbedenklich und tragen die Absaetze.
    Entfernt wird nur, was ohnehin nicht hingehoert.
    """
    vereinheitlicht = body.replace("\r\n", "\n").replace("\r", "\n")
    ohne_muell = _KOERPER_MUELL.sub("", vereinheitlicht)
    return _LEERZEILEN.sub("\n\n", ohne_muell)[:MAX_BODY].strip()


def antwort_betreff(original: str) -> str:
    """Setzt "Re: " genau einmal, egal wie oft es vorher schon dastand."""
    kern = _PRAEFIX.sub("", _header_wert(original)).strip()
    if not kern:
        return "Re:"
    return f"Re: {kern}"[:MAX_SUBJECT]


def reply_target(message: MailMessage) -> ReplyTarget:
    """Berechnet Empfaenger und Kopffelder der Antwort.

    Reply-To hat Vorrang vor From -- so will es RFC 5322. Beide stammen aus
    derselben vertrauenswuerdigen Quelle: den Kopffeldern der Originalnachricht,
    nie aus ihrem Text.
    """
    zieladresse = message.reply_to or message.sender
    if zieladresse is None or "@" not in zieladresse.address:
        raise ComposeError(
            f"Nachricht {message.message_id}: weder Reply-To noch From enthalten eine "
            f"brauchbare Adresse. Ohne Ziel wird nicht geantwortet."
        )

    verweise = " ".join(
        teil
        for teil in (_header_wert(message.references or "", grenze=800), message.rfc_message_id)
        if teil
    ).strip()

    return ReplyTarget(
        to=_header_wert(zieladresse.address, grenze=320),
        thread_id=message.thread_id,
        subject=antwort_betreff(message.subject),
        in_reply_to=_header_wert(message.rfc_message_id or "", grenze=400) or None,
        references=_header_wert(verweise, grenze=800) or None,
    )


def build_message(target: ReplyTarget, body: str, *, from_address: str) -> EmailMessage:
    """Baut die fertige Nachricht. Reintext, sonst nichts."""
    if not body.strip():
        raise ComposeError("Leerer Antworttext")

    nachricht = EmailMessage(policy=SMTP)
    nachricht["To"] = _header_wert(target.to, grenze=320)
    nachricht["From"] = _header_wert(from_address, grenze=320)
    nachricht["Subject"] = target.subject
    if target.in_reply_to:
        nachricht["In-Reply-To"] = target.in_reply_to
    if target.references:
        nachricht["References"] = target.references
    # Kein HTML. Reintext laesst sich nicht mit unsichtbarem Inhalt fuellen,
    # und eine Antwort braucht keine Formatierung.
    nachricht.set_content(_koerper_wert(body) + "\n")
    return nachricht


def raw_for_gmail(nachricht: EmailMessage) -> str:
    """base64url, wie die Gmail-API es erwartet."""
    return base64.urlsafe_b64encode(nachricht.as_bytes()).decode("ascii")


def _normalisiere_koerper(body: str) -> str:
    """Dieselbe Form wie im gebauten Entwurf -- sonst passt kein Abgleich."""
    return _koerper_wert(body)


def fingerprint(target: ReplyTarget, body: str) -> str:
    """Deckt genau das ab, was die Antwort ausmacht.

    Bewusst ohne Zeitstempel: der Fingerabdruck muss beim zweiten Berechnen
    gleich herauskommen, sonst laesst sich ein Trockenlauf nicht mit dem
    spaeter tatsaechlich entstandenen Entwurf vergleichen.

    Der Koerper wird auf einfache Zeilenumbrueche gebracht. Unterwegs macht
    SMTP daraus CRLF, und beim Zurueckholen kaeme sonst ein anderer Wert
    heraus -- der Abgleich wuerde dann jeden Entwurf beanstanden, obwohl
    inhaltlich nichts abweicht.
    """
    material = json.dumps(
        {**asdict(target), "body": _normalisiere_koerper(body)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def target_of_raw(raw_message: dict) -> ReplyTarget:
    """Baut den Zielsatz aus einer bereits verschickten oder entworfenen Nachricht."""
    kopf = headers_of(raw_message)
    return ReplyTarget(
        to=_header_wert(kopf.get("to", ""), grenze=320),
        thread_id=str(raw_message.get("threadId", "")),
        subject=_header_wert(kopf.get("subject", "")),
        in_reply_to=_header_wert(kopf.get("in-reply-to", ""), grenze=400) or None,
        references=_header_wert(kopf.get("references", ""), grenze=800) or None,
    )


def fingerprint_of_draft(raw_draft: dict) -> str:
    """Rechnet den Fingerabdruck aus dem nach, was tatsaechlich im Postfach liegt.

    Das ist die Probe aufs Exempel aus Abschnitt 6: stimmt der Wert mit dem
    ueberein, den der Trockenlauf protokolliert hat, ist der Entwurf genau der
    angekuendigte -- und nicht ein zweiter, der unterwegs entstanden ist.
    """
    nachricht = raw_draft.get("message") or {}
    return fingerprint(target_of_raw(nachricht), parse_message(nachricht).body)
