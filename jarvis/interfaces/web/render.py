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
  `kern`           Der Orb in der Mitte der Lage. Sein Zustand ist keine
                   Stimmung, sondern aus vier Tatsachen abgeleitet, die das
                   System wirklich fuehrt: Stoppschalter, Abweichungen, offene
                   Entscheidungen, sonst Betrieb. Siehe `zustand_ermitteln`.

Kein Inline-Stil, kein Skript, kein Bild: die Sicherheitsrichtlinie laesst
nichts davon zu, und nichts davon wird gebraucht. Symbole sind Inline-SVG --
Dokumentinhalt, kein Abruf.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from html import escape
from typing import Any

from jarvis.core.approvals import Approval
from jarvis.core.gate import GatePreview

__all__ = [
    "Zustand",
    "esc",
    "fakten",
    "gatterleiter",
    "hinweis",
    "kennzahl",
    "kern",
    "leer",
    "marke",
    "seite",
    "stufe",
    "tabelle",
    "tafel",
    "vorgang",
    "vorgang_kurz",
    "vorgangsfakten",
    "zaehler",
    "zustand_ermitteln",
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

#: Ausgang einer Gattersprosse -> Marke, Markenart, Zeilenklasse.
_SPROSSE: dict[str, tuple[str, str, str]] = {
    "weiter": ("Weiter", "erfolg", ""),
    "blockiert": ("Blockiert", "blockiert", "entschieden blockiert"),
    "trocken": ("Haelt", "trocken", "entschieden"),
    "act": ("Geht hinaus", "erfolg", "entschieden"),
    "offen": ("--", "", "offen"),
}

#: Die vier Ansichten. Mehr gibt es nicht, und die Leiste behauptet auch nicht
#: mehr: jeder Eintrag hier ist eine Route in `app.py`.
ANSICHTEN: tuple[tuple[str, str], ...] = (
    ("/", "Lage"),
    ("/entscheidungen", "Entscheidungen"),
    ("/briefing", "Briefing"),
    ("/protokoll", "Protokoll"),
)

# Zwei Symbole, beide als Dokumentinhalt. Sie stehen nie allein: der Knopf
# traegt sein Wort daneben.
_SYMBOL_HALT = (
    '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<path d="M5.2 1.5h5.6l4 4v5.6l-4 4H5.2l-4-4V5.5z" fill="none" '
    'stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>'
    '<path d="M5.4 8h5.2" stroke="currentColor" stroke-width="1.4"/></svg>'
)
_SYMBOL_WEITER = (
    '<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
    '<circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.4"/>'
    '<path d="M6.3 5.2v5.6L10.6 8z" fill="currentColor"/></svg>'
)


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


def vorgangsfakten(
    fields: Mapping[str, Any],
    targets: Mapping[str, Any],
    *,
    grund: str = "",
    entschieden_von: str = "",
    modell: str | None = None,
) -> str:
    """Alles, was ueber einen Vorgang bekannt ist, in einer Liste.

    Ziele zuerst, in der Reihenfolge, in der sie jemanden interessieren; dann
    die Felder der Modellentscheidung; dann Begruendung, Entscheider und
    Modell.

    `body` bleibt aussen vor: der Entwurfstext ist vom Modell geschriebene
    Prosa und wird darunter als Zitat gezeigt, nicht als Faktenzeile.
    """
    paare: list[tuple[str, object]] = [
        (name, targets[schluessel])
        for schluessel, name in BEKANNTE_ZIELE
        if targets.get(schluessel)
    ]
    weitere = sorted(
        k for k in targets if k not in {s for s, _ in BEKANNTE_ZIELE} and k != "body" and targets[k]
    )
    paare += [(k, targets[k]) for k in weitere]
    paare += [(k, v) for k, v in sorted(fields.items())]
    if grund:
        paare.append(("Grund", grund))
    if entschieden_von:
        paare.append(("Entschieden von", entschieden_von))
    if modell:
        paare.append(("Modell", modell))
    return fakten(paare) if paare else ""


# --------------------------------------------------------------------------- #
# Der Systemzustand und der Kern
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Zustand:
    """Was der Kern zeigt -- eine Klasse, ein Wort, ein Satz.

    `klasse` ist zugleich die CSS-Klasse des Kerns. Es gibt genau vier, und
    jede steht fuer eine Tatsache, die das System fuehrt.
    """

    klasse: str  # betrieb | wartet | abweichung | angehalten
    titel: str
    satz: str

    @property
    def art(self) -> str:
        """Farbrolle der Zustandsschrift: kalt fuer angehalten, fehler fuer Abweichung."""
        return {"angehalten": "kalt", "abweichung": "fehler"}.get(self.klasse, "")


def zustand_ermitteln(
    *,
    angehalten: bool,
    stopp_grund: str | None,
    offen: int,
    abweichungen: Sequence[str],
    trockenlauf: bool,
) -> Zustand:
    """Leitet den Zustand aus Tatsachen ab, in fester Rangfolge.

    Angehalten schlaegt alles: ein stehendes System hat keinen anderen
    Zustand. Dann Abweichungen, weil sie vor jeder Arbeit geklaert gehoeren.
    Dann Wartendes. Sonst Betrieb. Denken, Laufen, Offline gibt es nicht --
    der Kern kennt diese Zustaende nicht (SPEC-3 5.2), also zeigt sie auch
    niemand an.
    """
    if angehalten:
        return Zustand(
            "angehalten",
            "Angehalten",
            f"Stoppschalter gesetzt: {stopp_grund or 'ohne Angabe'}. "
            "Jede ausgehende Aktion ist blockiert.",
        )
    if abweichungen:
        weitere = len(abweichungen) - 1
        zusatz = {0: "", 1: " Und eine weitere."}.get(weitere, f" Und {weitere} weitere.")
        return Zustand("abweichung", "Abweichung", f"{abweichungen[0]}.{zusatz}")
    trocken = (
        "Trockenlauf an: Freigeben bewirkt nichts."
        if trockenlauf
        else "Trockenlauf AUS: eine Freigabe wirkt nach aussen."
    )
    if offen:
        wartet = "Eine Entscheidung wartet." if offen == 1 else f"{offen} Entscheidungen warten."
        return Zustand("wartet", "Wartet auf Freigabe", f"{wartet} {trocken}")
    ruhe = (
        "Nichts wartet, nichts weicht ab. Trockenlauf an: nichts verlaesst den Rechner."
        if trockenlauf
        else "Nichts wartet, nichts weicht ab. Trockenlauf AUS: Aktionen wirken nach aussen."
    )
    return Zustand("betrieb", "Betrieb", ruhe)


def kern(zustand: Zustand) -> str:
    """Der Orb. Reine Gestaltung, deshalb fuer Hilfsmittel unsichtbar -- der
    Zustand steht daneben als Text, und nur der zaehlt."""
    return (
        f'<div class="kern {esc(zustand.klasse)}" aria-hidden="true">'
        '<span class="kern-ring r2"></span>'
        '<span class="kern-ring r3"></span>'
        '<span class="kern-ring r1"></span>'
        '<span class="kern-bogen"></span>'
        '<span class="kern-glut"></span>'
        "</div>"
    )


def kennzahl(name: str, wert: object, *, art: str = "", zusatz: str = "") -> str:
    """Eine grosse Zahl mit ihrem Namen. `art` ist hebt, gefahr oder kalt."""
    klasse = f"kennzahl-wert {art}".strip()
    nachsatz = f'<span class="kennzahl-zusatz">{esc(zusatz)}</span>' if zusatz else ""
    return (
        f'<div class="kennzahl"><span class="kennzahl-name">{esc(name)}</span>'
        f'<span class="{klasse}">{esc(wert)}</span>{nachsatz}</div>'
    )


def tafel(titel: str, inhalt_html: str, *, fuss_html: str = "", klasse: str = "") -> str:
    """Eine Tafel mit Titel. `inhalt_html` und `fuss_html` sind fertiges HTML."""
    fuss = f'<p class="tafel-fuss">{fuss_html}</p>' if fuss_html else ""
    klassen = f"tafel {klasse}".strip()
    return f'<section class="{esc(klassen)}"><h2>{esc(titel)}</h2>{inhalt_html}{fuss}</section>'


# --------------------------------------------------------------------------- #
# Der Rahmen
# --------------------------------------------------------------------------- #


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
    meldung_html: str = "",
) -> str:
    """Der Rahmen. `inhalt_html` ist bereits fertiges, maskiertes HTML.

    Zuerst im Dokument steht das Systemband -- und darin der Stoppschalter,
    damit er auch im Tabfluss der erste Griff ist. Im Band stehen vier
    Tatsachen. Die ersten drei beantworten zusammen die Frage, die vor jeder
    Handlung zaehlt: *wird das, was ich gleich tue, wirklich passieren?*
    Auffaellig ist dabei der unsichere Zustand -- nicht "Trockenlauf an",
    sondern "Trockenlauf AUS", denn dann verlaesst echte Post den Rechner. Ein
    Mock, den man nicht sieht, ist aus demselben Grund hervorgehoben.
    """
    nachladen = f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else ""
    knopf = "Fortsetzen" if angehalten else "Anhalten"
    symbol = _SYMBOL_WEITER if angehalten else _SYMBOL_HALT
    ziel = "/weiter" if angehalten else "/stop"
    klasse = "systemband angehalten" if angehalten else "systemband"
    koerper = ' class="angehalten"' if angehalten else ""

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
    zustand, *weitere = tatsachen

    punkte = []
    for pfad, name in ANSICHTEN:
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
<body{koerper}>
<div class="{klasse}">
  <div class="systemband-inhalt">
    <span class="zustand"><span class="puls"></span>{zustand}</span>
    {"".join(weitere)}
    <form method="post" action="{ziel}">
      <button type="submit" class="stopp">{symbol}<span>{knopf}</span></button>
    </form>
  </div>
</div>
<header class="kopf">
  <h1><a href="/"><span class="wortmarke-kern"></span>JARVIS</a></h1>
  <nav>{"".join(punkte)}</nav>
</header>
<main class="{spur}">
{meldung_html}
{inhalt_html}
</main>
<footer>Loopback, Einzelplatz. Durchlaeufe startet die Kommandozeile.</footer>
</body>
</html>
"""


def _tatsache(name: str, wert: object, *, gefahr: bool = False) -> str:
    klasse = "tatsache-wert gefahr" if gefahr else "tatsache-wert hebt"
    return (
        f'<span class="tatsache"><span class="tatsache-name">{esc(name)}</span>'
        f'<span class="{klasse}">{esc(wert)}</span></span>'
    )


def fakten(paare: Iterable[tuple[str, object]]) -> str:
    zeilen = "".join(f"<dt>{esc(name)}</dt><dd>{esc(wert)}</dd>" for name, wert in paare)
    return f'<dl class="facts">{zeilen}</dl>'


def tabelle(
    kopf: Sequence[str],
    zeilen: Iterable[Sequence[object]],
    *,
    mono: Sequence[int] = (),
    roh: Sequence[int] = (),
    umbruch: Sequence[int] = (),
) -> str:
    """`roh` nennt Spalten, die bereits fertiges HTML enthalten -- Marken etwa.

    Alles andere geht durch `esc`. Die Ausnahme ist ausdruecklich zu nennen,
    damit sie nicht aus Versehen entsteht.

    Jede Zelle traegt ihren Spaltenkopf als `data-kopf`: im schmalen Fenster
    wird die Tabelle zu Bloecken, und die Beschriftung kommt aus diesem
    Attribut -- ohne Skript, nur ueber das Stylesheet.
    """
    kopf_html = "".join(f"<th>{esc(name)}</th>" for name in kopf)
    koerper = []
    for zeile in zeilen:
        zellen = []
        for i, wert in enumerate(zeile):
            inhalt = str(wert) if i in roh else esc(wert)
            klassen = " ".join(
                k for k, ja in (("mono", i in mono), ("umbruch", i in umbruch)) if ja
            )
            beschriftung = esc(kopf[i]) if i < len(kopf) else ""
            zellen.append(f'<td class="{klassen}" data-kopf="{beschriftung}">{inhalt}</td>')
        koerper.append(f"<tr>{''.join(zellen)}</tr>")
    if not koerper:
        return leer("Nichts vorhanden.")
    return (
        '<div class="tabelle"><table>'
        f"<thead><tr>{kopf_html}</tr></thead><tbody>{''.join(koerper)}</tbody>"
        "</table></div>"
    )


def leer(text: str) -> str:
    return f'<p class="empty">{esc(text)}</p>'


def hinweis(text: str, *, art: str = "") -> str:
    klasse = f"note {art}".strip()
    return f'<p class="{esc(klasse)}">{esc(text)}</p>'


def vorgang_kurz(eintrag: Approval) -> str:
    """Ein anstehender Vorgang in einer Zeile -- fuer die Lage.

    Kein Knopf: gehandelt wird nur in der Ansicht Entscheidungen, wo die
    Gatterleiter und der volle Vorgang danebenstehen. Die Lage zeigt, sie
    entscheidet nicht.
    """
    return (
        f"<li>"
        f'<span class="item-skill">{esc(eintrag.skill)}</span>'
        f'<span class="anstehend-satz">{esc(eintrag.summary)}</span>'
        f'<span class="anstehend-zeit">{esc(eintrag.action)} -- '
        f"{esc(eintrag.created_at[:16].replace('T', ' '))}</span>"
        f"</li>"
    )


def vorgang(eintrag: Approval, *, ausfuehrbar: bool, vorschau: GatePreview | None = None) -> str:
    """Ein anstehender Vorgang: Kopf, Satz, Fakten, Gatter, Handlung.

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
        vorgangsfakten(
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
        # Ziel -- deshalb nicht in der Faktenliste, sondern darunter, als
        # Zitat gekennzeichnet.
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
