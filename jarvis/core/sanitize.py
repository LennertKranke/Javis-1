"""Normalisierung unvertrauenswuerdiger Texte (Prinzip 2.3).

Alles, was von aussen kommt -- E-Mails, Webseiten, Kalendereinladungen --, geht
zuerst hier durch. Die Reihenfolge der Schritte ist nicht beliebig:

  1. NFKC-Normalisierung   loest Breitzeichen und Ligaturen in ihre schlichte
                           Form auf, damit ein getarntes Zeichen nicht spaeter
                           doch noch als Steuerzeichen gelesen wird
  2. HTML entfernen        samt Inhalt von script, style und head
  3. Unsichtbares loeschen Zero-Width-Zeichen, Bidi-Steuerzeichen und der
                           Unicode-Tags-Block -- die uebliche Art, Anweisungen
                           unsichtbar in Text zu legen
  4. Leerraum verdichten
  5. Kuerzen

Der Text bleibt danach Text. Das Modul verhindert keine Prompt-Injektion; das
tun die Prinzipien 2.1 und 2.2. Es nimmt ihr nur die Tarnung.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser

__all__ = ["SanitizedText", "collapse_whitespace", "remove_invisible", "sanitize", "strip_html"]

BEGIN_MARKER = "<<<UNTRUSTED-CONTENT"
END_MARKER = "<<<END-UNTRUSTED-CONTENT>>>"

_DROP_CONTENT = frozenset(
    {"script", "style", "head", "title", "noscript", "template", "svg", "iframe", "object", "embed"}
)
_BREAK_TAGS = frozenset(
    {
        "br",
        "p",
        "div",
        "tr",
        "li",
        "ul",
        "ol",
        "table",
        "blockquote",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }
)

_TAG_RE = re.compile(r"<[a-zA-Z/!][^>]{0,400}>")
_SPACES_RE = re.compile("[ \t\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+")
_NEWLINES_RE = re.compile(r"\n{3,}")
_TRAILING_RE = re.compile(r"[ \t]+\n")
_SOURCE_RE = re.compile(r"[^a-z0-9_.:-]+")

# Zusaetzlich zu den Unicode-Kategorien unten, weil die Einordnung dieser
# Zeichen je nach Unicode-Fassung schwankt.
_INVISIBLE_EXTRA = frozenset("\u200b\u200c\u200d\u2060\ufeff\u00ad\u180e\u061c")
_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Co", "Cs", "Cn"})
_KEEP_CONTROL = frozenset("\n\t")


@dataclass(frozen=True)
class SanitizedText:
    text: str
    original_length: int
    truncated: bool
    removed: dict[str, int] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.text)

    def as_untrusted_block(self, source: str = "unknown") -> str:
        """Rahmt den Text als Daten ein, bevor er an ein Modell geht.

        Der Rahmen ist eine Beschriftung, keine Garantie. Er hilft dem Modell,
        Inhalt von Auftrag zu unterscheiden; verlassen wird sich darauf nicht.
        Die Marker koennen im Text nicht vorkommen, weil `sanitize` jedes
        Vorkommen von "<<<" vorher aufbricht.
        """
        tag = _SOURCE_RE.sub("-", source.lower()) or "unknown"
        head = f'{BEGIN_MARKER} source="{tag}" truncated="{str(self.truncated).lower()}">>>'
        return f"{head}\n{self.text}\n{END_MARKER}"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.tags = 0
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        self.tags += 1
        if tag in _DROP_CONTENT:
            self._skip += 1
        elif tag in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        self.tags += 1
        if tag in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        self.tags += 1
        if tag in _DROP_CONTENT:
            self._skip = max(0, self._skip - 1)
        elif tag in _BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def strip_html(text: str) -> tuple[str, int]:
    """Entfernt Markup. Text ohne Tag-artige Stellen bleibt unberuehrt."""
    if not _TAG_RE.search(text):
        return text, 0
    parser = _TextExtractor()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        # Kaputtes Markup ist der Normalfall bei Fremdtext. Dann eben grob.
        return _TAG_RE.sub(" ", text), len(_TAG_RE.findall(text))
    return "".join(parser.parts), parser.tags


def remove_invisible(text: str) -> tuple[str, int]:
    """Loescht Zeichen, die man nicht sieht, aber ein Modell liest."""
    kept: list[str] = []
    removed = 0
    for ch in text:
        if ch in _KEEP_CONTROL:
            kept.append(ch)
            continue
        if ch in _INVISIBLE_EXTRA or unicodedata.category(ch) in _INVISIBLE_CATEGORIES:
            removed += 1
            continue
        kept.append(ch)
    return "".join(kept), removed


def collapse_whitespace(text: str) -> str:
    text = _SPACES_RE.sub(" ", text)
    text = _TRAILING_RE.sub("\n", text)
    text = _NEWLINES_RE.sub("\n\n", text)
    return text.strip()


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    cut = text[:max_chars]
    # Lieber an einer Wortgrenze abschneiden, wenn eine in Reichweite ist.
    space = cut.rfind(" ", max(0, max_chars - 200))
    if space > 0:
        cut = cut[:space]
    return cut.rstrip(), True


def sanitize(text: str, *, max_chars: int = 20000) -> SanitizedText:
    """Der einzige Weg, auf dem Fremdtext in JARVIS hineinkommt."""
    if max_chars < 1:
        raise ValueError("max_chars muss groesser als 0 sein")
    original_length = len(text)
    removed: dict[str, int] = {}

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFKC", text)

    # Vor allem anderen: die Rahmenmarker duerfen im Inhalt nicht vorkommen,
    # sonst kann fremder Text den Rahmen von innen schliessen und danach
    # weiterschreiben, als waere er wieder Auftrag. Fruehes Aufbrechen zaehlt
    # den Versuch auch dann, wenn ihn spaeter noch etwas anderes entfernt.
    marker_hits = text.count("<<<")
    if marker_hits:
        text = text.replace("<<<", "< <<")
        removed["marker"] = marker_hits

    text, tags = strip_html(text)
    if tags:
        removed["html_tags"] = tags

    residual = len(_TAG_RE.findall(text))
    if residual:
        # Kann nach dem Aufloesen von Entitaeten wieder auftauchen: aus
        # &lt;script&gt; wird beim Parsen wieder <script>.
        text = _TAG_RE.sub(" ", text)
        removed["html_tags"] = removed.get("html_tags", 0) + residual

    text, invisible = remove_invisible(text)
    if invisible:
        removed["invisible"] = invisible

    text = collapse_whitespace(text)
    text, truncated = _truncate(text, max_chars)

    return SanitizedText(
        text=text,
        original_length=original_length,
        truncated=truncated,
        removed=removed,
    )
