"""Zugang zum Dashboard.

Die Oberflaeche kann Entscheidungen freigeben, also auch E-Mails senden. Eine
Bindung an 127.0.0.1 allein reicht dafuer nicht: jede beliebige Webseite in
deinem Browser darf ein Formular an localhost abschicken, und der Browser tut
es. Der Angriff braucht keinen Zugriff auf deinen Rechner, nur einen offenen
Tab.

Zwei Schranken dagegen:

  Sitzungstoken   Beim Start entsteht ein Zufallswert, er liegt in
                  ~/.jarvis/web-token mit Rechten 0600. Ohne ihn beantwortet
                  der Server nichts. Ein fremdes Formular kennt ihn nicht.
  Herkunft        Jede veraendernde Anfrage muss einen Origin- oder
                  Referer-Kopf tragen, der auf den eigenen Server zeigt. Fehlt
                  beides, wird abgelehnt -- bei einem Knopf, der senden kann,
                  ist Ablehnen die richtige Richtung.

Dazu Kopfzeilen, die dem Browser die Mittel nehmen: keine Skripte, keine
fremden Quellen, kein Einbetten in einen fremden Rahmen.
"""

from __future__ import annotations

import hmac
import secrets
from pathlib import Path

__all__ = [
    "COOKIE_NAME",
    "SECURITY_HEADERS",
    "TOKEN_FILE",
    "load_or_create_token",
    "origin_is_own",
    "token_matches",
]

COOKIE_NAME = "jarvis_token"
TOKEN_FILE = "web-token"

# Kein Skript, keine fremde Quelle, kein fremder Rahmen. Das Protokoll zeigt
# Betreffzeilen aus fremden Mails an; sollte trotz aller Maskierung je Markup
# durchkommen, hat es hier nichts, womit es etwas anfangen koennte.
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'; img-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def load_or_create_token(home: Path) -> str:
    """Liest den Token oder legt einen an. Datei nur fuer den Eigentuemer lesbar."""
    pfad = home / TOKEN_FILE
    if pfad.exists():
        vorhanden = pfad.read_text(encoding="utf-8").strip()
        if vorhanden:
            return vorhanden
    token = secrets.token_urlsafe(32)
    home.mkdir(parents=True, exist_ok=True)
    pfad.write_text(token + "\n", encoding="utf-8")
    pfad.chmod(0o600)
    return token


def token_matches(erwartet: str, gegeben: str | None) -> bool:
    """Vergleich in gleichbleibender Zeit -- ein Token errät man sonst zeichenweise."""
    if not gegeben:
        return False
    return hmac.compare_digest(erwartet, gegeben)


def origin_is_own(header: str | None, referer: str | None, erlaubt: set[str]) -> bool:
    """Kommt die Anfrage von der eigenen Seite?

    Fehlt beides, gilt sie als fremd. Bei einer veraendernden Anfrage ist das
    die sichere Richtung: ein Formular auf einer fremden Seite schickt einen
    Origin mit, der nicht passt, und ein Aufruf ohne beides ist kein Klick auf
    dieser Oberflaeche.
    """
    if header:
        return header.rstrip("/") in erlaubt
    if referer:
        return any(referer.startswith(f"{quelle}/") or referer == quelle for quelle in erlaubt)
    return False
