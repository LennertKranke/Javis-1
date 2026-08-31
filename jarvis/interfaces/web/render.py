"""HTML erzeugen.

Eine Regel, ausnahmslos: jeder Wert, der von aussen kommt, geht durch `esc`.
Das Protokoll zeigt Betreffzeilen aus fremden Mails an, und diese Seite kann
Entscheidungen freigeben -- ungefiltertes Markup waere hier kein Schoenheits-,
sondern ein Sicherheitsfehler.

Die Funktionen sind deshalb so geschnitten, dass man das Maskieren nicht
vergessen kann: `zeile` und `feld` bekommen rohe Werte und maskieren selbst.
Nur `seite` nimmt fertiges HTML entgegen, und das ist an ihrem Namen und ihrem
einen Parameter zu erkennen.

Drei Bausteine tragen mehr als Gestaltung:

  `zustandsmarke`  Ein Zustand als Wort mit Form, nicht als Farbe allein. Nur
                   bekannte Ergebnisse bekommen eine Marke -- was ein Modell
                   als Aktion vorgeschlagen hat, ist kein Zustand.
  `gatterleiter`   Die Reihenfolge aus Abschnitt 4.2, sichtbar. Sie zeigt, an
                   welcher Sprosse es haengt -- und dass eine Freigabe nur auf
                   Sprosse 3 wirkt.
  `naht`           Was das Modell entschied, links; was der Code berechnete,
                   rechts. Die Grenze aus Prinzip 2.1, unterscheidbar gemacht
                   ueber Linienart und Schriftart, nicht ueber Farbe.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from html import escape
from typing import Any

from jarvis.core.approvals import Approval
from jarvis.core.gate import GatePreview

__all__ = [
    "esc",
    "fakten",
    "gatterleiter",
    "hinweis",
    "leer",
    "marke",
    "naht",
    "seite",
    "stufe",
    "tabelle",
    "vorgang",
    "zustandsmarke",
]

# Zielfelder in der Reihenfolge, in der sie jemanden interessieren.
BEKANNTE_ZIELE: tuple[tuple[str, str], ...] = (
    ("to", "Empfaenger"),
    ("subject", "Betreff"),
    ("category", "Kategorie"),
    ("label_name", "Label"),
    ("message_id", "Nachricht"),
    ("draft_id", "Entwurf"),
)

#: Ergebnisse, die ein Zustand sind -- und wie sie heissen.
#:
#: Bewusst unvollstaendig. Ein `decision`-Eintrag traegt als `outcome` die
#: vorgeschlagene Aktion ("draft", "send", "label"); das ist kein Zustand und
#: bekommt deshalb keine Marke, sondern bleibt schlichter Text. Eine Marke fuer
#: etwas zu vergeben, das keiner ist, waere eine Aussage ohne Deckung.
ZUSTAENDE: dict[str, tuple[str, str]] = {
    "performed": ("Ausgefuehrt", "erfolg"),
    "failed": ("Fehlgeschlagen", "fehler"),
    "blocked": ("Blockiert", "blockiert"),
    "dry_run": ("Dry Run", "trocken"),
    "act": ("Durchgelassen", "erfolg"),
    "rejected": ("Verworfen", "verworfen"),
    "refused": ("Verweigert", "blockiert"),
    "stop_engaged": ("Angehalten", "blockiert"),
    "stop_released": ("Fortgesetzt", ""),
}

#: Ausgang einer Gattersprosse -> Marke und Zeilenklasse.
_SPROSSE: dict[str, tuple[str, str, str]] = {
    "weiter": ("Weiter", "erfolg", ""),
    "blockiert": ("Blockiert", "blockiert", "entschieden"),
    "trocken": ("Haelt", "trocken", "entschieden"),
    "act": ("Geht hinaus", "erfolg", "entschieden"),
    "offen": ("--", "", "offen"),
}


def esc(wert: object) -> str:
    return escape(str(wert), quote=True)


def marke(text: str, art: str = "") -> str:
    """Ein Zustand als Wort mit Form. Farbe kommt obendrauf, nie allein."""
    klasse = f"marke {art}".strip()
    return f'<span class="{esc(klasse)}">{esc(text)}</span>'


def zustandsmarke(outcome: str, *, dry_run: bool = False) -> str:
    """Marke fuer ein Protokollergebnis, oder schlichter Text.

    `dry_run` schlaegt das Ergebnis nicht -- es ergaenzt es: eine Aktion kann
    ausgefuehrt *und* nur im Trockenlauf geschehen sein, und beides gehoert
    dann nebeneinander.
    """
    eintrag = ZUSTAENDE.get(outcome)
    if eintrag is None:
        teile = [f'<span class="dim">{esc(outcome)}</span>']
    else:
        name, art = eintrag
        teile = [marke(name, art)]
    if dry_run and outcome != "dry_run":
        teile.append(marke("Dry Run", "trocken"))
    return " ".join(teile)


def stufe(gewaehrt: int, verlangt: int | None, bezeichnung: str = "") -> str:
    """Autonomiestufe -- immer beide Zahlen.

    Nur die gewaehrte zu zeigen war die alte Fassung, und genau diese
    Verwechslung hat im Audit eine Faehigkeit auf Stufe 0 handeln lassen:
    `0 >= 0` ist wahr. Nebeneinander faellt es auf.

    `verlangt = None` heisst: es gibt keine Faehigkeit zu diesem Eintrag --
    `voice` etwa ist eine Bedienweise und hat keinen `act`-Pfad.
    """
    if verlangt is None:
        zahlen = f'<span class="gewaehrt">{int(gewaehrt)}</span> <span class="verlangt">/ --</span>'
        klasse = "stufe"
    else:
        knapp = " reicht-nicht" if int(gewaehrt) < int(verlangt) else ""
        klasse = f"stufe{knapp}"
        zahlen = (
            f'<span class="gewaehrt">{int(gewaehrt)}</span> '
            f'<span class="verlangt">/ {int(verlangt)}</span>'
        )
    name = f' <span class="stufe-name">{esc(bezeichnung)}</span>' if bezeichnung else ""
    return f'<span class="{klasse}">{zahlen}</span>{name}'


def zaehler(paare: Iterable[tuple[str, int, int]]) -> str:
    """Benutzt/Grenze mit Balken. Eine Zahl ohne Bezug ist keine Auskunft.

    Der Fuellstand kommt als Stufenklasse in Fuenferschritten: ein `style`-
    Attribut waere unter `style-src 'self'` wirkungslos, und zwar lautlos.
    """
    teile = []
    for fenster, benutzt, grenze in paare:
        anteil = 0 if grenze <= 0 else min(100, round(benutzt * 100 / grenze / 5) * 5)
        voll = " voll" if grenze > 0 and benutzt >= grenze else ""
        teile.append(
            f'<span class="zaehler">{esc(benutzt)}/{esc(grenze)} '
            f'<span class="balken{voll}"><span class="f-{anteil}"></span></span> '
            f'<span class="dim">{esc(fenster)}</span></span>'
        )
    return " ".join(teile) or '<span class="dim">--</span>'


def gatterleiter(vorschau: GatePreview, *, ueberschrift: str = "") -> str:
    """Die fuenf Sprossen aus Abschnitt 4.2, in ihrer Reihenfolge.

    Was nach der haltenden Sprosse kommt, steht als "nicht ausgewertet" da und
    nicht als "bestanden" -- der Unterschied ist der ganze Sinn der Anzeige.
    """
    zeilen = []
    for nr, schritt in enumerate(vorschau.steps, start=1):
        text, art, klasse = _SPROSSE.get(schritt.outcome, ("--", "", ""))
        zeilen.append(
            f'<div class="gatter-sprosse {klasse}">'
            f'<span class="gatter-nr">{nr}</span>'
            f'<span class="gatter-name">{esc(schritt.name)}</span>'
            f'<span class="gatter-wert">{esc(schritt.value)}</span>'
            f"{marke(text, art)}"
            f"</div>"
        )
    kopf = f"<h3>{esc(ueberschrift)}</h3>" if ueberschrift else ""
    return f'{kopf}<div class="gatter">{"".join(zeilen)}</div>'


def _halb(klasse: str, kopf: str, paare: Sequence[tuple[str, object]], *, satz: bool) -> str:
    inhalt = fakten(paare, satz=satz) if paare else leer("Nichts vermerkt.")
    return f'<div class="naht-halb {klasse}"><div class="naht-kopf">{esc(kopf)}</div>{inhalt}</div>'


def naht(
    fields: Mapping[str, Any],
    targets: Mapping[str, Any],
    *,
    grund: str = "",
    entschieden_von: str = "",
    modell: str | None = None,
) -> str:
    """Was das Modell entschied, und was der Code berechnete.

    Die Trennung ist nicht Gestaltung, sondern Prinzip 2.1: ein Ziel steht
    ausschliesslich rechts. Taucht eines links auf, ist das an der Anzeige
    sofort zu sehen -- und ein Fehler.

    Kodiert wird die Grenze ueber Linienart (gepunktet gegen durchgezogen) und
    Schriftart (Satz gegen Maschine), nicht ueber Farbe: so haelt sie auch in
    Graustufen und bei Farbfehlsichtigkeit.
    """
    links: list[tuple[str, object]] = [(k, v) for k, v in sorted(fields.items())]
    if grund:
        links.append(("Begruendung", grund))
    if entschieden_von:
        links.append(("Entschieden von", entschieden_von))
    if modell:
        links.append(("Modell", modell))

    rechts = [
        (name, targets[schluessel])
        for schluessel, name in BEKANNTE_ZIELE
        if targets.get(schluessel)
    ]
    weitere = sorted(
        k for k in targets if k not in {s for s, _ in BEKANNTE_ZIELE} and k != "body" and targets[k]
    )
    rechts += [(k, targets[k]) for k in weitere]

    return (
        '<div class="naht">'
        + _halb("modell", "Modell entschied", links, satz=True)
        + _halb("code", "Code berechnete", rechts, satz=False)
        + "</div>"
    )


def seite(
    titel: str,
    *,
    inhalt_html: str,
    aktiv: str,
    angehalten: bool,
    stopp_grund: str | None,
    offen: int,
    refresh: int = 0,
    trockenlauf: bool = True,
    dienste_mock: bool = False,
    zugangsdaten: str = "",
    weit: bool = False,
) -> str:
    """Der Rahmen. `inhalt_html` ist bereits fertiges, maskiertes HTML.

    Im Systemband stehen vier Tatsachen. Die ersten drei beantworten zusammen
    die Frage, die vor jeder Handlung zaehlt: *wird das, was ich gleich tue,
    wirklich passieren?* Auffaellig ist dabei der unsichere Zustand -- nicht
    "Trockenlauf an", sondern "Trockenlauf AUS", denn dann verlaesst echte Post
    den Rechner. Ein Mock, den man nicht sieht, ist aus demselben Grund
    hervorgehoben.
    """
    nachladen = f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else ""
    knopf = "Freigeben" if angehalten else "Anhalten"
    ziel = "/weiter" if angehalten else "/stop"
    klasse = "systemband angehalten" if angehalten else "systemband"

    if angehalten:
        tatsachen = [
            marke("Angehalten", ""),
            _tatsache("Grund", stopp_grund or "ohne Angabe"),
            _tatsache("Wirkung", "jede ausgehende Aktion blockiert"),
        ]
    else:
        tatsachen = [
            marke("Betrieb", ""),
            _tatsache("Trockenlauf", "an" if trockenlauf else "AUS", gefahr=not trockenlauf),
            _tatsache("Dienste", "Mock" if dienste_mock else "Live", gefahr=dienste_mock),
        ]
        if zugangsdaten:
            tatsachen.append(_tatsache("Zugangsdaten", zugangsdaten))

    punkte = []
    ansichten = (
        ("/", "Lage"),
        ("/briefing", "Briefing"),
        ("/entscheidungen", "Entscheidungen"),
        ("/protokoll", "Protokoll"),
    )
    for pfad, name in ansichten:
        auszeichnung = ' class="on"' if pfad == aktiv else ""
        zahl = f' <span class="count">{offen}</span>' if pfad == "/entscheidungen" and offen else ""
        punkte.append(f'<a href="{pfad}"{auszeichnung}>{esc(name)}{zahl}</a>')

    spur = "wrap weit" if weit else "wrap"
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
  <div class="systemband-inhalt">
    {"".join(tatsachen)}
    <form method="post" action="{ziel}">
      <button type="submit">{knopf}</button>
    </form>
  </div>
</div>
<div class="{spur}">
<header><h1>JARVIS</h1></header>
<nav>{"".join(punkte)}</nav>
{inhalt_html}
<footer>Loopback, Einzelplatz. Durchlaeufe startet die Kommandozeile.</footer>
</div>
</body>
</html>
"""


def _tatsache(name: str, wert: object, *, gefahr: bool = False) -> str:
    klasse = "tatsache-wert gefahr" if gefahr else "tatsache-wert hebt"
    return (
        f'<span class="tatsache"><span class="tatsache-name">{esc(name)}</span>'
        f'<span class="{klasse}">{esc(wert)}</span></span>'
    )


def fakten(paare: Iterable[tuple[str, object]], *, satz: bool = False) -> str:
    klasse = "facts satz" if satz else "facts"
    zeilen = "".join(f"<dt>{esc(name)}</dt><dd>{esc(wert)}</dd>" for name, wert in paare)
    return f'<dl class="{klasse}">{zeilen}</dl>'


def tabelle(
    kopf: Sequence[str],
    zeilen: Iterable[Sequence[object]],
    *,
    mono: Sequence[int] = (),
    roh: Sequence[int] = (),
) -> str:
    """`roh` nennt Spalten, die bereits fertiges HTML enthalten -- Marken etwa.

    Alles andere geht durch `esc`. Die Ausnahme ist ausdruecklich zu nennen,
    damit sie nicht aus Versehen entsteht.
    """
    kopf_html = "".join(f"<th>{esc(name)}</th>" for name in kopf)
    koerper = []
    for zeile in zeilen:
        zellen = []
        for i, wert in enumerate(zeile):
            inhalt = str(wert) if i in roh else esc(wert)
            zellen.append(f'<td class="{"mono" if i in mono else ""}">{inhalt}</td>')
        koerper.append(f"<tr>{''.join(zellen)}</tr>")
    if not koerper:
        return leer("Nichts vorhanden.")
    return f"<table><thead><tr>{kopf_html}</tr></thead><tbody>{''.join(koerper)}</tbody></table>"


def leer(text: str) -> str:
    return f'<p class="empty">{esc(text)}</p>'


def hinweis(text: str, *, art: str = "") -> str:
    klasse = f"note {art}".strip()
    return f'<p class="{esc(klasse)}">{esc(text)}</p>'


def vorgang(eintrag: Approval, *, ausfuehrbar: bool, vorschau: GatePreview | None = None) -> str:
    """Ein anstehender Vorgang: Kopf, Satz, Naht, Gatter, Handlung.

    Die Reihenfolge folgt der Frage, die ein Mensch tatsaechlich stellt: Was
    ist das? Was soll passieren? Woher kommt das? Wer haelt es auf? Was tue ich?
    """
    kopf = (
        f'<div class="item-head">'
        f'<span class="item-skill">{esc(eintrag.skill)}</span>'
        f'<span class="dim">{esc(eintrag.action)}</span>'
        f"{marke('Offen', 'offen')}"
        f'<span class="item-when">{esc(eintrag.created_at[:16].replace("T", " "))}</span>'
        f"</div>"
    )

    koerper = [f'<p class="item-summary">{esc(eintrag.summary)}</p>']
    koerper.append(
        naht(
            eintrag.fields,
            eintrag.targets,
            grund=eintrag.reason,
            entschieden_von=eintrag.decided_by,
            modell=eintrag.model,
        )
    )

    entwurf = eintrag.targets.get("body")
    if entwurf:
        # Vom Modell geschriebene Prosa. Sie steht in `targets`, ist aber kein
        # Ziel -- deshalb weder links noch rechts in der Naht, sondern
        # darunter, als Zitat gekennzeichnet.
        koerper.append("<h3>Entwurfstext</h3>")
        koerper.append(f'<div class="item-body">{esc(entwurf)}</div>')

    if vorschau is not None:
        koerper.append(gatterleiter(vorschau, ueberschrift="Wenn du jetzt freigibst"))

    if eintrag.note:
        koerper.append(hinweis(str(eintrag.note), art="warnung"))

    if ausfuehrbar:
        handlung = (
            f'<form method="post" action="/entscheidungen/{eintrag.id}/freigeben">'
            f'<button type="submit" class="primary">Freigeben</button></form>'
        )
    else:
        handlung = '<span class="knapp">Freigabe wirkt erst ohne Trockenlauf.</span>'

    fuss = (
        f'<div class="actions">{handlung}'
        f'<form method="post" action="/entscheidungen/{eintrag.id}/verwerfen">'
        f'<button type="submit">Verwerfen</button></form></div>'
    )
    return (
        f'<div class="item">{kopf}<div class="item-body-wrap">{"".join(koerper)}</div>{fuss}</div>'
    )
