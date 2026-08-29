"""Eine Gmail-Antwort in ihre vertrauenswuerdigen und unvertrauenswuerdigen
Teile zerlegen.

Die Trennung laeuft quer durch eine E-Mail, nicht zwischen Nachrichten:

  vertrauenswuerdig   Gmail-Kennungen, vorhandene Labels, die Adressen aus den
                      Headern. Nur daraus darf spaeter ein Ziel entstehen.
  unvertrauenswuerdig Betreff, Text, Dateinamen von Anhaengen. Alles davon ist
                      vom Absender frei waehlbar und geht nur normalisiert und
                      gerahmt weiter.

Der Betreff steht bewusst auf der zweiten Seite. Er sieht wie ein Kopffeld aus,
ist aber genauso frei bestimmbar wie der Nachrichtentext -- und ist damit der
naheliegendste Ort, um eine Anweisung zu verstecken.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr

__all__ = ["Attachment", "MailAddress", "MailMessage", "headers_of", "parse_message"]

_B64URL_RE = re.compile(r"^[A-Za-z0-9_=-]*$")

_TEXT_PLAIN = "text/plain"
_TEXT_HTML = "text/html"


@dataclass(frozen=True)
class MailAddress:
    name: str
    address: str

    @property
    def domain(self) -> str:
        _, _, domain = self.address.rpartition("@")
        return domain.lower()

    def __str__(self) -> str:
        return self.address


@dataclass(frozen=True)
class Attachment:
    filename: str
    mime_type: str
    size: int


@dataclass(frozen=True)
class MailMessage:
    # --- vertrauenswuerdig --------------------------------------------------
    message_id: str
    thread_id: str
    label_ids: tuple[str, ...] = ()
    sender: MailAddress | None = None
    reply_to: MailAddress | None = None
    recipients: tuple[MailAddress, ...] = ()
    rfc_message_id: str | None = None
    references: str | None = None
    internal_date: int = 0
    list_unsubscribe: bool = False
    auto_submitted: str | None = None
    precedence: str | None = None
    # --- unvertrauenswuerdig ------------------------------------------------
    subject: str = ""
    body: str = ""
    snippet: str = ""
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)

    @property
    def untrusted_text(self) -> str:
        """Betreff und Text zusammen -- alles, was der Absender bestimmt."""
        return f"Betreff: {self.subject}\n\n{self.body}".strip()

    def has_label(self, label_id: str) -> bool:
        return label_id in self.label_ids


def _decode_header_value(value: str) -> str:
    """Loest =?UTF-8?B?...?= auf. Kaputte Kodierung darf nichts umwerfen."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except (UnicodeDecodeError, LookupError, ValueError):
        return value


def _headers(payload: dict) -> dict[str, str]:
    """Kopffelder als Abbildung, Namen klein geschrieben. Das erste zaehlt.

    Bei doppelten Kopffeldern gewinnt das erste, weil ein zweites From nach
    einem gueltigen From der uebliche Weg ist, einen Parser zu verwirren.
    """
    out: dict[str, str] = {}
    for header in payload.get("headers") or []:
        name = str(header.get("name", "")).lower()
        if name and name not in out:
            out[name] = str(header.get("value", ""))
    return out


def headers_of(raw: dict) -> dict[str, str]:
    """Kopffelder einer Gmail-Antwort, klein geschrieben. Erstes Vorkommen zaehlt."""
    return _headers(raw.get("payload") or {})


def _decode_body(data: str) -> str:
    """base64url mit fehlender Auffuellung, wie Gmail sie liefert.

    Das Alphabet wird vorher geprueft. Ohne das ueberliest base64 ungueltige
    Zeichen einfach und macht aus Unsinn Datenmuell -- der dann aussieht wie
    ein Nachrichtentext und im Klassifizierer landet. Lieber ein leerer
    Koerper, den man im Protokoll sieht, als stille Zeichensuppe.
    (`urlsafe_b64decode` kennt kein validate=, deshalb der eigene Test.)
    """
    if not data or not _B64URL_RE.match(data):
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded)
    except (binascii.Error, ValueError):
        return ""
    return raw.decode("utf-8", errors="replace")


def _walk(part: dict, texte: dict[str, list[str]], anhaenge: list[Attachment]) -> None:
    mime = str(part.get("mimeType", "")).lower()
    filename = str(part.get("filename", "") or "")
    body = part.get("body") or {}

    if filename:
        anhaenge.append(
            Attachment(
                filename=filename[:200],
                mime_type=mime,
                size=int(body.get("size") or 0),
            )
        )
        return

    for unterteil in part.get("parts") or []:
        _walk(unterteil, texte, anhaenge)

    if mime in (_TEXT_PLAIN, _TEXT_HTML):
        text = _decode_body(str(body.get("data") or ""))
        if text:
            texte.setdefault(mime, []).append(text)


def parse_message(raw: dict) -> MailMessage:
    """Baut eine `MailMessage` aus einer Gmail-Antwort mit `format=full`."""
    payload = raw.get("payload") or {}
    headers = _headers(payload)

    name, address = parseaddr(headers.get("from", ""))
    sender = (
        MailAddress(name=_decode_header_value(name), address=address.lower()) if address else None
    )
    antwort_name, antwort_adresse = parseaddr(headers.get("reply-to", ""))
    reply_to = (
        MailAddress(name=_decode_header_value(antwort_name), address=antwort_adresse.lower())
        if antwort_adresse
        else None
    )

    empfaenger = tuple(
        MailAddress(name=_decode_header_value(n), address=a.lower())
        for n, a in getaddresses([headers.get("to", ""), headers.get("cc", "")])
        if a
    )

    texte: dict[str, list[str]] = {}
    anhaenge: list[Attachment] = []
    _walk(payload, texte, anhaenge)

    # Reintext hat Vorrang. HTML wird erst in sanitize() entschaerft, hier
    # geht es nur darum, den aussagekraeftigsten Teil zu waehlen.
    koerper = "\n".join(texte.get(_TEXT_PLAIN) or texte.get(_TEXT_HTML) or [])

    auto = headers.get("auto-submitted")
    return MailMessage(
        message_id=str(raw.get("id", "")),
        thread_id=str(raw.get("threadId", "")),
        label_ids=tuple(raw.get("labelIds") or []),
        sender=sender,
        reply_to=reply_to,
        recipients=empfaenger,
        rfc_message_id=headers.get("message-id"),
        references=headers.get("references"),
        internal_date=int(raw.get("internalDate") or 0),
        list_unsubscribe=bool(headers.get("list-unsubscribe")),
        auto_submitted=auto.lower() if auto else None,
        precedence=(headers.get("precedence") or "").lower() or None,
        subject=_decode_header_value(headers.get("subject", "")),
        body=koerper,
        snippet=str(raw.get("snippet", "")),
        attachments=tuple(anhaenge),
    )
