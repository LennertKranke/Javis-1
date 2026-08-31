# Vorschlag: SPEC-3-Nachtrag zur Dashboard-Aenderung

```
Status:   VORSCHLAG -- nicht in JARVIS-SPEC-3.md eingetragen
Anlass:   SPEC-3 Abschnitt 27, Change Management:
          "Codeaenderung -- betroffenen SPEC-Abschnitt mitziehen, im selben Commit"
Grund der
Trennung: Die Aenderung der Spezifikation gehoert dem Nutzer. Der Auftrag zu
          diesem Zweig lautete ausdruecklich, SPEC-3 nicht eigenmaechtig zu
          veraendern. Der Wortlaut steht deshalb hier und wartet.
```

Vier Stellen sind betroffen. Der Text unten ist einsetzbar, wie er ist.

---

## 1. Abschnitt 4.2 — Das Gatter

**Einfuegen** nach dem Absatz *"Gemessen: Bei aktivem Trockenlauf bleibt ein
freigegebener Vorgang offen, mit Vermerk 'Trockenlauf global aktiv'."*

> **Zwei Eingaenge, eine Entscheidung.** `evaluate()` beantwortet "darf
> gehandelt werden" und schreibt dabei ins Protokoll und verbraucht Kontingent.
> `preview()` beantwortet ausschliesslich "woran haengt es gerade" -- fuer die
> Anzeige (§12). Es schreibt nichts, verbraucht nichts und erlaubt nichts.
>
> **MUST:** Die Vorschau darf nie etwas anderes sagen als die Auswertung. Weil
> sie die Reihenfolge ein zweites Mal abbildet, haelt ein Test beide ueber alle
> Lagen gegeneinander -- abgeschaltet, Stoppschalter, Stufe, Freigabe,
> Trockenlauf, Obergrenze. Ohne diesen Test waere die zweite Fassung eine
> Einladung zum Auseinanderdriften.

**Warum das hierher gehoert.** Das Gatter hat eine zweite oeffentliche Methode
bekommen. Wer §4.2 liest und sie nicht findet, koennte sie fuer einen zweiten
Entscheidungsweg halten -- genau das, was §12 als MUST NOT fuehrt.

---

## 2. Abschnitt 12 — Dashboard

**Ersetzen:** "Lokale Instrumententafel: Zustand, Briefing, ..." durch
"Lokale Instrumententafel: **Lage**, Briefing, ...". Die Ansicht heisst jetzt so.

**Einfuegen** vor dem Absatz *"Abweichung von SPEC-2 (HISTORICAL)"*:

> **Vier Anzeigen tragen mehr als Gestaltung** -- CURRENT seit der Umsetzung
> von OD-4:
>
> | Anzeige | Was sie sichtbar macht |
> |---|---|
> | **Stufe gewaehrt / verlangt** | Die Faehigkeitstabelle zeigt beide Zahlen. Nur die gewaehrte zu zeigen konnte den Fehlertyp aus §6.1 nicht anzeigen: `0 >= 0` ist wahr |
> | **Zustandsmarke** | Ein Protokollergebnis erscheint als Wort mit Form, nicht als Farbe allein. Nur bekannte Ergebnisse bekommen eine Marke; die vom Modell vorgeschlagene Aktion eines `decision`-Eintrags ist kein Zustand und bleibt Text |
> | **Gatterleiter** | Die fuenf Sprossen aus §4.2 in ihrer Reihenfolge, mit der haltenden markiert. Sie zeigt am Vorgang, dass eine Freigabe nur Sprosse 3 ersetzt -- Stoppschalter, Obergrenze und Trockenlauf gelten weiter |
> | **Vertrauensnaht** | `Decision.fields` links, `Decision.targets` rechts, getrennt ueber Linienart und Schriftart statt ueber Farbe. Macht P1 (§3.2) am Vorgang pruefbar: ein Ziel links waere sofort zu sehen |
>
> **MUST:** Die Gatterleiter ist eine **Erklaerung, keine Entscheidung**. Sie
> kommt aus `Gate.preview()`, das die Reihenfolge lesend abbildet: kein
> Protokolleintrag, kein verbrauchtes Kontingent (§4.2).

**Ersetzen** im Absatz *"Abweichung von SPEC-2 (HISTORICAL)"* die beiden
letzten Saetze durch:

> Angeglichen wurde **nicht** an SPEC-2, sondern an ein eigenes Designsystem
> (`design/JARVIS-DESIGN-SYSTEM.md`): Systemschriften, eigene Farbrollen,
> `meta refresh`. Das zweigeteilte Stromelement ist als Vertrauensnaht
> uebernommen, weil es die Vertrauensgrenze sichtbar macht -- siehe §25,
> Future-only. Damit ist OD-4 entschieden.

**Unveraendert bleibt** die Tabelle *"Was es heute zeigt, und was eine Control
Plane zeigen muesste"*. Es sind weiterhin sieben von fuenfzehn Bereichen: die
Aenderung hat keinen Bereich hinzugefuegt, sondern vorhandene Bereiche mehr
sagen lassen.

---

## 3. Abschnitt 15 — Current Capability Matrix

**Ersetzen** in der Zeile `Dashboard` die Spalte *Notes*:

```
alt:  Token, Origin, CSP, kein JS
neu:  Token, Origin, CSP, kein JS; Gatterleiter und Naht seit OD-4
```

---

## 4. Abschnitt 23 — OD-4

**Ersetzen** den ganzen Block durch:

```
### OD-4 — Dashboard-Gestaltung

Frage:    Wird das Dashboard an die Designfassung aus SPEC-2 angeglichen,
          oder wird die heutige Umsetzung die verbindliche?
Entscheidung: Keines von beidem. Ein eigenes Designsystem, abgeleitet aus
          dieser Spezifikation, liegt in design/JARVIS-DESIGN-SYSTEM.md.
          Umgesetzt wurde davon nur, was neue Information bringt: verlangte
          Stufe, Zustandsmarken, Gatterleiter, Vertrauensnaht, Systemband
          (Abschnitt 12). Keine neuen Bereiche -- der Ausbau zur Control Plane
          bleibt PLANNED und haengt weiter hinter den fuenf REQUIRED-Punkten.
Status:   ENTSCHIEDEN und umgesetzt
```

---

## Was **nicht** geaendert werden muss, und warum

| Abschnitt | Warum unberuehrt |
|---|---|
| 3.2 P1-P4 | Kein Prinzip beruehrt. Die Naht *zeigt* P1, sie aendert es nicht |
| 4.6 Dashboard-Absicherung | Keine neue Route, kein neuer Aktionsweg, dieselbe Richtlinie, weiterhin kein JavaScript |
| 5.1, 5.2 Execution Model | Kein Weg zur Ausfuehrung veraendert. `preview` fuehrt nichts aus |
| 17 Known Issues | SEC-1 und SEC-2 bleiben offen und unberuehrt. Die Gatterleiter zeigt ausdruecklich **keine** Allowlist-Sprosse, weil der Freigabeweg sie nicht prueft |
| 18 TD-1 | Keine neue Route hinzugefuegt, also keine neue ungeschuetzte Flaeche |
| 20, 21 Roadmap | Keine PLANNED-Faehigkeit vorgezogen, keine Reihenfolge veraendert |
| 26 Acceptance Criteria | Keines beruehrt |

## Testlage nach der Aenderung

```
1048 Tests gruen (vorher 1018; 30 neue)
ruff check und ruff format sauber
Zwei Mutationsproben bestanden:
  Vorschau ignoriert den Stoppschalter   -> Test faellt aus
  Vorschau verbraucht Kontingent         -> Test faellt aus
```
