"""HTML erzeugen.

Eine Regel, ausnahmslos: jeder Wert, der von aussen kommt, geht durch `esc`.
Das Protokoll zeigt Betreffzeilen aus fremden Mails an, und diese Seite kann
Entscheidungen freigeben -- ungefiltertes Markup waere hier kein Schoenheits-,
sondern ein Sicherheitsfehler.

Die Funktionen sind deshalb so geschnitten, dass man das Maskieren nicht
vergessen kann: `zeile` und `feld` bekommen rohe Werte und maskieren selbst.
Nur `seite` nimmt fertiges HTML entgegen, und das ist an ihrem Namen und ihrem
einen Parameter zu erkennen.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from html import escape

from jarvis.core.approvals import Approval

__all__ = ["esc", "fakten", "hinweis", "leer", "seite", "tabelle", "vorgang"]

# Zielfelder in der Reihenfolge, in der sie jemanden interessieren.
BEKANNTE_ZIELE: tuple[tuple[str, str], ...] = (
    ("to", "Empfaenger"),
    ("subject", "Betreff"),
    ("category", "Kategorie"),
    ("label_name", "Label"),
    ("message_id", "Nachricht"),
    ("draft_id", "Entwurf"),
)


def esc(wert: object) -> str:
    return escape(str(wert), quote=True)


def seite(
    titel: str,
    *,
    inhalt_html: str,
    aktiv: str,
    angehalten: bool,
    stopp_grund: str | None,
    offen: int,
    refresh: int = 0,
) -> str:
    """Der Rahmen. `inhalt_html` ist bereits fertiges, maskiertes HTML."""
    nachladen = f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else ""
    zustand = "ANGEHALTEN" if angehalten else "BETRIEB"
    knopf = "Freigeben" if angehalten else "Anhalten"
    ziel = "/weiter" if angehalten else "/stop"
    grund = esc(stopp_grund or "") if angehalten else ""
    klasse = "stop engaged" if angehalten else "stop"

    punkte = []
    ansichten = (
        ("/", "Zustand"),
        ("/briefing", "Briefing"),
        ("/entscheidungen", "Entscheidungen"),
        ("/protokoll", "Protokoll"),
    )
    for pfad, name in ansichten:
        marke = ' class="on"' if pfad == aktiv else ""
        zaehler = (
            f' <span class="count">{offen}</span>' if pfad == "/entscheidungen" and offen else ""
        )
        punkte.append(f'<a href="{pfad}"{marke}>{esc(name)}{zaehler}</a>')

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JARVIS -- {esc(titel)}</title>
<link rel="stylesheet" href="/jarvis.css">
{nachladen}
</head>
<body>
<div class="{klasse}">
  <div class="stop-inner">
    <span class="stop-state">{zustand}</span>
    <span class="stop-reason">{grund}</span>
    <form method="post" action="{ziel}">
      <button type="submit">{knopf}</button>
    </form>
  </div>
</div>
<div class="wrap">
<header><h1>JARVIS</h1></header>
<nav>{"".join(punkte)}</nav>
{inhalt_html}
<footer>Loopback, Einzelplatz. Durchlaeufe startet die Kommandozeile.</footer>
</div>
</body>
</html>
"""


def fakten(paare: Iterable[tuple[str, object]]) -> str:
    zeilen = "".join(f"<dt>{esc(name)}</dt><dd>{esc(wert)}</dd>" for name, wert in paare)
    return f'<dl class="facts">{zeilen}</dl>'


def tabelle(
    kopf: Sequence[str],
    zeilen: Iterable[Sequence[object]],
    *,
    mono: Sequence[int] = (),
) -> str:
    kopf_html = "".join(f"<th>{esc(name)}</th>" for name in kopf)
    koerper = []
    for zeile in zeilen:
        zellen = "".join(
            f'<td class="{"mono" if i in mono else ""}">{esc(wert)}</td>'
            for i, wert in enumerate(zeile)
        )
        koerper.append(f"<tr>{zellen}</tr>")
    if not koerper:
        return leer("Nichts vorhanden.")
    return f"<table><thead><tr>{kopf_html}</tr></thead><tbody>{''.join(koerper)}</tbody></table>"


def leer(text: str) -> str:
    return f'<p class="empty">{esc(text)}</p>'


def hinweis(text: str) -> str:
    return f'<p class="note">{esc(text)}</p>'


def vorgang(eintrag: Approval, *, ausfuehrbar: bool) -> str:
    """Ein anstehender Vorgang mit den zwei Knoepfen."""
    zeilen = [
        f'<div class="item-head">'
        f'<span class="item-skill">{esc(eintrag.skill)}</span>'
        f'<span class="dim">{esc(eintrag.action)}</span>'
        f'<span class="item-when">{esc(eintrag.created_at[:16].replace("T", " "))}</span>'
        f"</div>",
        f'<div class="item-summary">{esc(eintrag.summary)}</div>',
    ]

    paare = [
        (name, eintrag.targets[schluessel])
        for schluessel, name in BEKANNTE_ZIELE
        if eintrag.targets.get(schluessel)
    ]
    if eintrag.reason:
        paare.append(("Grund", eintrag.reason))
    if eintrag.decided_by:
        paare.append(("Entschieden von", eintrag.decided_by))
    if paare:
        zeilen.append(fakten(paare))

    koerper = eintrag.targets.get("body")
    if koerper:
        zeilen.append(f'<div class="item-body">{esc(koerper)}</div>')

    if eintrag.note:
        zeilen.append(hinweis(str(eintrag.note)))

    freigabe = (
        f'<form method="post" action="/entscheidungen/{eintrag.id}/freigeben">'
        f'<button type="submit" class="primary">Freigeben</button></form>'
        if ausfuehrbar
        else '<span class="dim">Freigabe wirkt erst ohne Trockenlauf</span>'
    )
    zeilen.append(
        f'<div class="actions">{freigabe}'
        f'<form method="post" action="/entscheidungen/{eintrag.id}/verwerfen">'
        f'<button type="submit">Verwerfen</button></form></div>'
    )
    return f'<div class="item">{"".join(zeilen)}</div>'
