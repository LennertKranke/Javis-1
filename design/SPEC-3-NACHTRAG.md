# Vorschlag: SPEC-3-Nachtrag zur Dashboard-Aenderung

> **Hinweis vom 2026-09-02.** Dieses Dokument ist ein Nachweis, keine
> Beschreibung des heutigen Stands. Zwei Dinge haben sich seither geaendert:
>
> 1. Das Designsystem, auf das Abschnitt 5 verweist, liegt weiterhin unter
>    `design/JARVIS-DESIGN-SYSTEM.md`, ist aber seit Fassung 2.0 ein anderes
>    (dunkel, Orange, Kern). Die vier Anzeigen aus Abschnitt 4 -- Stufe
>    gewaehrt/verlangt, Zustandsmarke, Gatterleiter, Systemband -- bestehen
>    darin weiter.
> 2. Die **Vertrauensnaht** war bereits am 2026-08-31 zurueckgebaut worden
>    (Entscheidung des Nutzers, Weg A-teil; `render.vorgangsfakten()` zeigt
>    eine gemeinsame Liste). Die Zeile dazu in Abschnitt 4 und der Satz in
>    Abschnitt 9 waren beim Eintragen in SPEC-3 (Fassung 3.2) schon ueberholt.
>    SPEC-3 Abschnitt 12 fuehrt die Naht deshalb heute zu Unrecht als CURRENT;
>    die Korrektur gehoert dem Nutzer (SPEC-3 Abschnitt 27).

```
Status:   EINGEARBEITET -- am 2026-09-01 nach Freigabe des Nutzers als
          Fassung 3.2 in JARVIS-SPEC-3.md eingetragen. Dieses Dokument
          bleibt als Nachweis des Vorschlags liegen; verbindlich ist SPEC-3.
          Die Zahlen in Abschnitt 10 wurden beim Eintragen am aktuellen
          Stand neu gemessen (1063 Tests), nicht aus diesem Vorschlag
          uebernommen. Die Bemerkung zur Allowlist in der Tabelle "Was nicht
          geaendert werden muss" stammt von vor den SEC-Fixen: seit 3.1
          prueft der Freigabeweg die Allowlist; eine Allowlist-Sprosse in
          der Gatterleiter zeigt sie weiterhin nicht.
Fassung:  bei der Konsolidierung (2026-09-01) von 3.1 auf 3.2 umnummeriert --
          3.1 ist seither durch die SEC-Fixe vergeben, siehe Abschnitt 1
Anlass:   SPEC-3 Abschnitt 27, Change Management:
          "Codeaenderung -- betroffenen SPEC-Abschnitt mitziehen, im selben Commit"
Betrifft: commit b17edf0 (Dashboard: vier Anzeigen)
Grund der
Trennung: Die Aenderung der Spezifikation gehoert dem Nutzer. SPEC-3 wird nicht
          ohne ausdrueckliche Freigabe geaendert -- auch dann nicht, wenn die
          Spezifikation die Aenderung selbst verlangt.
Vollstaendigkeit:
          Eine erste Fassung dieses Vorschlags nannte vier Stellen. Beim
          tatsaechlichen Eintragen kamen fuenf weitere dazu, die von aussen
          nicht sichtbar waren. Diese Fassung ist vollstaendig und einmal
          durchgelaufen.
```

Neun Stellen. Der Text unten ist einsetzbar, wie er ist.

---

## 1. Kopfblock

Die erste Fassung dieses Nachtrags entstand neben der SEC-Behebung und nannte
sich selbst 3.1. Bei der Konsolidierung beider Straenge (2026-09-01) hat die
SEC-Behebung die 3.1 bekommen; dieser Nachtrag wird beim Eintragen zur **3.2**.

```
alt:  Version:               3.1
      Created:               2026-08-30
      Updated:               2026-08-31  --  SEC-1 und SEC-2 behoben, mit Regressionstests
      Repository state:      Nachfolger von fa568bb, Arbeitsbaum sauber

neu:  Version:               3.2
      Created:               2026-08-30  (Fassung 3.0, Stand commit 0b7b9b7)
      Updated:               2026-08-31  (Fassung 3.1) -- SEC-1 und SEC-2 behoben,
                             mit Regressionstests
      Changed:               (Fassung 3.2) -- OD-4 entschieden und
                             umgesetzt. Inhaltlich betroffen: 4.2, 12, 15, 23,
                             25, Anhang B. Nur Zahlen: 1, 3.4, 13, 28. Keine
                             Prinzipien, keine Roadmap, kein offener Befund
                             beruehrt
      Repository state:      beim Eintragen einsetzen (Commit auf main)
      Test state:            beim Eintragen einsetzen (gemessener Lauf)
```

Die Folgezeilen zu KI-8 bleiben unveraendert -- der zeitabhaengige Test
besteht weiter.

---

## 2. Abschnitt 4.2 — Das Gatter

**Einfuegen** nach *"Gemessen: Bei aktivem Trockenlauf bleibt ein freigegebener
Vorgang offen, mit Vermerk 'Trockenlauf global aktiv'."*

> **Zwei Eingaenge, eine Entscheidung.** `evaluate()` beantwortet "darf
> gehandelt werden" und schreibt dabei ins Protokoll und verbraucht Kontingent.
> `preview()` beantwortet ausschliesslich "woran haengt es gerade" -- fuer die
> Anzeige (Abschnitt 12). Es schreibt nichts, verbraucht nichts und erlaubt
> nichts.
>
> **MUST:** Die Vorschau darf nie etwas anderes sagen als die Auswertung. Weil
> sie die Reihenfolge ein zweites Mal abbildet, haelt ein Test beide ueber alle
> Lagen gegeneinander -- abgeschaltet, Stoppschalter, Stufe, Freigabe,
> Trockenlauf, Obergrenze. Ohne diesen Test waere die zweite Fassung eine
> Einladung zum Auseinanderdriften.

**Warum das hierher gehoert.** Das Gatter hat eine zweite oeffentliche Methode
bekommen. Wer 4.2 liest und sie nicht findet, koennte sie fuer einen zweiten
Entscheidungsweg halten -- genau das, was Abschnitt 12 als MUST NOT fuehrt.

---

## 3. Abschnitt 12 — Dashboard, erster Absatz

```
alt:  **CURRENT.** Lokale Instrumententafel: Zustand, Briefing, ...
neu:  **CURRENT.** Lokale Instrumententafel: Lage, Briefing, ...
```

Die Ansicht heisst jetzt so.

---

## 4. Abschnitt 12 — vier Anzeigen

**Einfuegen** vor dem Absatz *"Abweichung von SPEC-2 (HISTORICAL)"*:

> **Vier Anzeigen tragen mehr als Gestaltung** -- CURRENT seit der Umsetzung
> von OD-4:
>
> | Anzeige | Was sie sichtbar macht |
> |---|---|
> | **Stufe gewaehrt / verlangt** | Die Faehigkeitstabelle zeigt beide Zahlen. Nur die gewaehrte zu zeigen konnte den Fehlertyp aus 6.1 nicht anzeigen: `0 >= 0` ist wahr |
> | **Zustandsmarke** | Ein Protokollergebnis erscheint als Wort mit Form, nicht als Farbe allein. Nur bekannte Ergebnisse bekommen eine Marke; die vom Modell vorgeschlagene Aktion eines `decision`-Eintrags ist kein Zustand und bleibt Text |
> | **Gatterleiter** | Die fuenf Sprossen aus 4.2 in ihrer Reihenfolge, mit der haltenden markiert. Sie zeigt am Vorgang, dass eine Freigabe nur Sprosse 3 ersetzt -- Stoppschalter, Obergrenze und Trockenlauf gelten weiter |
> | **Vertrauensnaht** | `Decision.fields` links, `Decision.targets` rechts, getrennt ueber Linienart und Schriftart statt ueber Farbe. Macht P1 (3.2) am Vorgang pruefbar: ein Ziel links waere sofort zu sehen |
>
> **MUST:** Die Gatterleiter ist eine **Erklaerung, keine Entscheidung**. Sie
> kommt aus `Gate.preview()`, das die Reihenfolge lesend abbildet: kein
> Protokolleintrag, kein verbrauchtes Kontingent (4.2).

---

## 5. Abschnitt 12 — Abweichung von SPEC-2

**Ersetzen** die letzten Saetze des Absatzes:

```
alt:  ... Umgesetzt sind andere Farbwerte, Systemschriften und `meta refresh`.
      Das ist **bewusst offen** und keine Schuld: SPEC-2 ist nicht mehr
      verbindlich. Ob angeglichen wird, ist eine offene Entscheidung (OD-4).
```

> ... Angeglichen wurde **nicht** an SPEC-2, sondern an ein eigenes
> Designsystem (`design/JARVIS-DESIGN-SYSTEM.md`): Systemschriften, eigene
> Farbrollen, `meta refresh`. Das zweigeteilte Stromelement ist als
> Vertrauensnaht uebernommen, weil es die Vertrauensgrenze sichtbar macht --
> es ist die einzige Gestaltungsidee aus SPEC-2 §7, die uebernommen wurde
> (Abschnitt 25). Damit ist OD-4 entschieden.

**Achtung, Querbezug.** Nicht "siehe Abschnitt 25, Future-only" schreiben: nach
Aenderung 8 ist der Entscheidungsstrom dort nicht mehr Future-only. Beim ersten
Eintragen ist genau dieser Widerspruch entstanden.

---

## 6. Abschnitt 12 — Control-Plane-Tabelle

Die Tabelle selbst bleibt **unveraendert** bei sieben von fuenfzehn. Nur der
Absatz darunter:

```
alt:  Sieben von fuenfzehn. Die fehlenden acht sind kein Versaeumnis, sondern
      unentschieden: ob das Dashboard zur Control Plane ausgebaut wird und in
      welcher Form, ist OD-4. Vier der acht setzen ausserdem Faehigkeiten
      voraus, die es nicht gibt.
```

> Sieben von fuenfzehn -- **unveraendert nach OD-4**. Die Entscheidung hat
> vorhandene Bereiche mehr sagen lassen, aber keinen hinzugefuegt. Die
> fehlenden acht sind kein Versaeumnis: ob das Dashboard zur Control Plane
> ausgebaut wird, ist weiterhin offen und steht als Roadmap-Punkt 6 auf
> PLANNED. Vier der acht setzen ausserdem Faehigkeiten voraus, die es nicht
> gibt.

---

## 7. Abschnitt 15 — Current Capability Matrix

**Ersetzen** in der Zeile `Dashboard` die Spalte *Notes*:

```
alt:  Token, Origin, CSP, kein JS
neu:  Token, Origin, CSP, kein JS; Gatterleiter und Naht seit OD-4
```

---

## 8. Abschnitt 23 — OD-4

**Ersetzen** den Block durch:

```
### OD-4 — Dashboard-Gestaltung

Frage:    Wird das Dashboard an die Designfassung aus SPEC-2 angeglichen,
          oder wird die heutige Umsetzung die verbindliche?
Entscheidung: Keines von beidem. Ein eigenes Designsystem, abgeleitet aus
          dieser Spezifikation, liegt in design/JARVIS-DESIGN-SYSTEM.md.
          Umgesetzt wurde davon nur, was neue Information bringt: verlangte
          Stufe, Zustandsmarken, Gatterleiter, Vertrauensnaht, Systemband
          (Abschnitt 12). Keine neuen Bereiche -- der Ausbau zur Control
          Plane bleibt PLANNED und haengt weiter hinter den fuenf
          REQUIRED-Punkten.
Status:   ENTSCHIEDEN und umgesetzt
```

---

## 9. Abschnitt 25 — Future-only

**Ersetzen** die beiden Punkte durch:

> * Die Designfassung des Dashboards aus SPEC-2 §7. Sie war eine Vorlage und
>   ist kein Abnahmekriterium geworden: OD-4 hat sich fuer ein eigenes
>   Designsystem entschieden (`design/JARVIS-DESIGN-SYSTEM.md`), nicht fuer
>   eine Angleichung.
> * Der Entscheidungsstrom als Signaturelement (SPEC-2 §7.5) -- die Zweiteilung
>   "was das Modell entschied / was der Code tat" macht die Vertrauensgrenze
>   sichtbar. Das war die einzige gestalterische Idee, die aus SPEC-2
>   uebernommen wurde: sie steht seit OD-4 als Vertrauensnaht am Vorgang
>   (Abschnitt 12) und ist damit nicht mehr Future-only, sondern **CURRENT**.

---

## 10. Zahlen in 1, 3.4, 13 und 28

Gemessen am Stand b17edf0, nicht geschaetzt.

| Stelle | alt | neu |
|---|---|---|
| Abschnitt 1 | 15 882 Zeilen Quellcode, 12 062 Zeilen Tests, 1018 Tests -- davon 1017 | 16 517 Zeilen Quellcode, 12 337 Zeilen Tests, 1048 Tests -- davon 1047 |
| Abschnitt 3.4, Testability | 1018 Tests | 1048 Tests |
| Abschnitt 13 | 1018 Tests, Laufzeit rund 16 s, Verhaeltnis 0,76 : 1, **1017 davon** | 1048 Tests, Laufzeit rund 18 s, Verhaeltnis 0,75 : 1, **1047 davon** |
| Abschnitt 28, fuenf Saetze | getestet (1018 Tests) | getestet (1048 Tests) |
| Abschnitt 28, Schnellstart | `# 1018 Tests, siehe KI-8` | `# 1048 Tests, siehe KI-8` |

---

## 11. Anhang B — Self-Audit

**Ersetzen** die Zeile zu Phantom-Implementierungen:

```
alt:  nein -- weder die Spec-Erstellung noch die Nachtragsrunde hat Code geaendert
```

> nein -- die Spec-Erstellung und die Nachtragsrunde haben keinen Code
> geaendert. Fassung 3.2 begleitet eine Codeaenderung (OD-4), die
> ausschliesslich vorhandene Anzeigen betrifft: keine neue Faehigkeit, kein
> Stub, keine Tabelle, kein vorgezogenes PLANNED-Feature

---

## Was **nicht** geaendert werden muss, und warum

| Abschnitt | Warum unberuehrt |
|---|---|
| 3.2 P1-P4 | Kein Prinzip beruehrt. Die Naht *zeigt* P1, sie aendert es nicht |
| 4.6 Dashboard-Absicherung | Keine neue Route, kein neuer Aktionsweg, dieselbe Richtlinie, weiterhin kein JavaScript |
| 5.1, 5.2 Execution Model | Kein Weg zur Ausfuehrung veraendert. `preview` fuehrt nichts aus |
| 16 Security Matrix | Keine Sicherheitseigenschaft veraendert |
| 17 Known Issues | SEC-1 und SEC-2 bleiben offen und unberuehrt. Die Gatterleiter zeigt ausdruecklich **keine** Allowlist-Sprosse, weil der Freigabeweg sie nicht prueft |
| 18 TD-1 | Keine neue Route hinzugefuegt, also keine neue ungeschuetzte Flaeche |
| 19, 20 Zukunftsarchitektur | Kein PLANNED-Feature vorgezogen |
| 21 Roadmap | Keine Reihenfolge veraendert. Der Control-Plane-Ausbau bleibt Punkt 6, PLANNED |
| 26 Acceptance Criteria | Keines beruehrt |

## Testlage nach der Aenderung

```
1048 Tests gruen (vorher 1018; 30 neue)
ruff check und ruff format sauber
Zwei Mutationsproben bestanden:
  Vorschau ignoriert den Stoppschalter   -> Test faellt aus
  Vorschau verbraucht Kontingent         -> Test faellt aus
```
