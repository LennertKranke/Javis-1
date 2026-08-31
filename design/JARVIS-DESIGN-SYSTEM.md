# JARVIS Design System

```
Dokument:          JARVIS-DESIGN-SYSTEM (DESIGN-1)
Status:            DESIGNVORSCHLAG -- nicht verbindlich, nicht beschlossen
Version:           1.0
Erstellt:          2026-08-31
Geltungsbereich:   Gestaltung und Bedienung. Keine Architektur, keine
                   Anforderungen, keine Roadmap
Grundlage:         JARVIS-SPEC-3.md (CURRENT SOURCE OF TRUTH), vollstaendig gelesen
                   Repository-Stand: Zweig claude/jarvis-design-system-us1y4r,
                   Basis commit fa568bb, Arbeitsbaum sauber
                   jarvis/interfaces/web/ (style.py, render.py, app.py, security.py)
                   Anhang B von SPEC-3 (Self-Audit) und Abschnitt 17 (Known Issues)
Verhaeltnis zu
SPEC-3:            untergeordnet. Wo dieses Dokument SPEC-3 widerspricht,
                   gilt SPEC-3. Dieses Dokument aendert SPEC-3 nicht
Beantwortet:       OD-4 nicht. Es macht einen Vorschlag, den OD-4 annehmen
                   oder verwerfen kann
```

---

## Wie dieses Dokument zu lesen ist

SPEC-3 gibt **Anforderungen, Architektur und Prinzipien** vor. Sie gibt **kein
fertiges Bild** vor: keine Farbwerte, keine Schriften, keine Abstaende, keine
Komponenten. Abschnitt 27 von SPEC-3 sagt das ausdruecklich -- "welches
Schriftbild" steht dort in der Liste der Dinge, die **bewusst nicht**
festgeschrieben sind. Genau deshalb gibt es dieses Dokument: es ist der Ort, an
den solche Entscheidungen gehoeren.

Jede Aussage hier traegt eine von fuenf Marken. Sie werden nicht vermischt.

| Marke | Bedeutung |
|---|---|
| **CURRENT** | Im Repository vorhanden. Am Code geprueft, mit Fundstelle |
| **REQUIRED** | Von SPEC-3 als naechstes Ziel beschlossen. Nicht durch Design entstanden |
| **PLANNED** | Von SPEC-3 als Zukunft beschrieben. **Kein** Bauauftrag |
| **DESIGN** | Gestaltungsentscheidung dieses Dokuments. Vorschlag, nicht Vorgabe |
| **IDEA** | Optional, unverbindlich, nicht durch SPEC-3 veranlasst |

**Die goldene Regel gilt hier genauso** (SPEC-3, *Statusstufen*). Aus einer
PLANNED-Beschreibung entsteht nichts -- auch kein Dashboard-Element. Blaetter im
Ordner `prototyp/`, die einen PLANNED-Bereich zeigen, sind Entwuerfe zur
Anschauung und tragen die Marke im Blatt selbst. Sie sind ausdruecklich **kein**
Auftrag, den Bereich zu bauen.

**Was dieses Dokument nicht tut:**

* Es aendert SPEC-3 nicht, auch nicht in Nebensaetzen.
* Es erfindet keine Produktanforderung. Wo eine Gestaltung eine Faehigkeit
  braeuchte, die es nicht gibt, steht das da -- statt der Faehigkeit.
* Es repariert keine SPEC-3-Luecke. Eine Luecke, die SPEC-3 offen laesst, bleibt
  offen. Ein Designvorschlag dafuer ist ein Vorschlag, keine Schliessung
  (Abschnitt 3).
* Es aendert keinen Produktionscode. `jarvis/` ist unberuehrt; die produktive
  Fassung des Stylesheets steht weiterhin in `jarvis/interfaces/web/style.py`.

---

# Teil I -- Designgrundlage

## 1. Was SPEC-3 fuer die Oberflaeche verbindlich vorgibt

Diese Liste ist die eigentliche Grundlage. Jede spaetere Entscheidung dieses
Dokuments verweist auf eine Zeile daraus. Alles hier ist wortgetreu aus SPEC-3
gezogen, nicht ausgelegt.

| # | Vorgabe | Stufe | SPEC-3 |
|---|---|---|---|
| **B1** | Das Dashboard ist Oberflaeche, **nicht Sicherheitsinstanz**. Es ruft `execute_approval` auf und durchlaeuft dieselbe Kette wie jeder andere Weg | MUST | 4.6, 12 |
| **B2** | Ein Knopf darf **nie direkt** einen externen Dienst aufrufen | MUST | 4.6 |
| **B3** | Ein Ausbau darf **keinen zweiten Aktionsweg** schaffen | MUST NOT | 12 |
| **B4** | Bindung ausschliesslich an Loopback, Sitzungstoken, Origin-Pruefung, CSP `default-src 'none'`, `nosniff`, `no-store`, **kein JavaScript** | CURRENT | 4.6 |
| **B5** | Der Stoppschalter ist auf **jeder** Ansicht sichtbar | CURRENT | 12 |
| **B6** | Gatterreihenfolge: abgeschaltet, Stoppschalter, Stufe/Freigabe, Obergrenze, Ausfuehrung -- die Reihenfolge ist Absicht | MUST | 4.2 |
| **B7** | Eine Freigabe ersetzt **die Autonomiestufe -- sonst nichts**. Nicht Stoppschalter, nicht Ein-Aus, nicht Obergrenze, nicht Trockenlauf | MUST | 4.2, 28 |
| **B8** | Autonomie gilt **je Faehigkeit**, in vier Stufen 0-3, und entsteht nie implizit. Am Skill steht die **verlangte**, in der Konfiguration die **gewaehrte** Stufe | MUST | 4.3, 6.1 |
| **B9** | Ein Fehler **darf nie wie ein Erfolg aussehen** | MUST | 3.4, 5.2, 5.3 |
| **B10** | Acht Fragen muessen aus dem Protokoll beantwortbar sein; auch **abgelehnte** Aktionen stehen darin | MUST | 4.9 |
| **B11** | Protokolleintraege enthalten keine Geheimnisse; der Fremdtext selbst gehoert nicht ins Protokoll. Absender und Betreff stehen darin, **weil das Dashboard sie zum Einordnen braucht** | MUST / SHOULD | 4.9 |
| **B12** | Mailinhalte werden nicht gespeichert; von Mail bleiben Kennung, Thread, Kategorie | MUST | 8, 10 |
| **B13** | Fremde Inhalte sind Daten, keine Anweisungen -- auch in der Anzeige | MUST | 3.2 P3 |
| **B14** | Das Modell waehlt nie ein Ziel. `Decision.fields` (Modell) und `Decision.targets` (Code) sind getrennt | MUST | 3.2 P1 |
| **B15** | Neun konzeptionelle Aktionszustaende; **UNVERIFIED, OFFLINE und CANCELLED existieren nicht** | CURRENT | 5.2 |
| **B16** | Nachweisstufen BUILT / TESTED / MOCKED / LIVE VERIFIED / PLATFORM VERIFIED sind eine **eigene Leiter** und werden nicht vermischt | MUST | *Nachweisstufen*, 11 |
| **B17** | Kein externer Dienst wurde je erreicht, nichts lief je auf macOS. Keine Linux-Verifikation darf als macOS-Verifikation ausgegeben werden | MUST | *Nachweisstufen*, 11, 14 |
| **B18** | Keine Erfolgsmeldung darf **staerker formuliert sein als der tatsaechliche Nachweis** | MUST | 27 |
| **B19** | Kein Feature ohne Trockenlaufpfad; im Trockenlauf sagt die Oberflaeche, dass Freigeben nichts bewirkt | MUST / CURRENT | 22, 12 |
| **B20** | Dashboard bleibt lokal, ohne Anmeldung, ohne Nutzerverwaltung, **ohne Build-Schritt** | Retained aus SPEC-2 | 25 |
| **B21** | Keine Fake-Features, kein Stub, kein Dummy fuer eine PLANNED-Funktion | MUST NOT | 24, 19.3 |
| **B22** | Sprache ist Bedienweise ohne `act`-Pfad; ein Sprachbefehl hat nie mehr Rechte als derselbe Befehl als Text; anhalten per Sprache geht, fortsetzen nie | MUST | 19.5 Voice |
| **B23** | Sprache ist **nicht** der Hauptbedienweg. Text ist der Standard | Non-Goal | 24 |
| **B24** | Der Meldeweg einer kuenftigen Proaktivitaet darf **kein zweiter Aktionspfad** werden | MUST | 19.5 Proactive |
| **B25** | Das Gedaechtnis kennt heute **keinen Vertrauensgrad**; eine vom Nutzer gesagte und eine aus Fremdtext abgeleitete Tatsache sind nicht unterscheidbar | CURRENT-Luecke | 9.2, OD-2 |

## 2. Was SPEC-3 der Gestaltung ausdruecklich ueberlaesst

| Punkt | SPEC-3-Stelle | Folge |
|---|---|---|
| Schriftbild | 27: "Bewusst nicht festgeschrieben: welcher Webserver, welches Schriftbild, welche SQLite-Version, welches Modell" | Typografie ist eine Designentscheidung und gehoert **nicht** in SPEC-3 |
| Dashboard-Gestaltung insgesamt | 12, OD-4: "Ob angeglichen wird, ist eine offene Entscheidung" | Dieses Dokument macht einen Vorschlag zu OD-4; es entscheidet OD-4 nicht |
| Farbwerte, Abstaende, Komponenten | 12: SPEC-2 §7.2-7.8 sind "nicht mehr verbindlich, aber als Gestaltungsmaterial erhalten" | Material, keine Vorgabe |
| Ob das Dashboard Control Plane wird | 12: "Zielbild, **kein Arbeitsauftrag**"; Roadmap 6 = PLANNED | Die Informationsarchitektur darf das Ziel tragen, ohne es zu bauen |

**Der Entscheidungsstrom.** SPEC-3 fuehrt in Abschnitt 25 unter *Future-only*
eine Idee ausdruecklich weiter: "Der Entscheidungsstrom als Signaturelement
(SPEC-2 §7.5) -- die Zweiteilung 'was das Modell entschied / was der Code tat'
macht die Vertrauensgrenze sichtbar und bleibt eine starke Idee."

Das ist die einzige gestalterische Aussage, die SPEC-3 selbst positiv bewertet.
Sie ist **nicht verbindlich** (Future-only), aber sie ist der Grund, warum die
Vertrauensnaht in diesem Dokument zunaechst das Signaturelement wurde (DD-27) -- und warum
sie am 2026-08-31 zurueckgebaut wurde, siehe Abschnitt 51.

## 3. SPEC-3-Luecken, die dieses Design **nicht** schliesst

Das ist der wichtigste Abschnitt dieses Dokuments. Der Self-Audit von SPEC-3
(Anhang B) und Abschnitt 17 nennen offene Punkte. Ein Design kann sie sichtbar
machen -- schliessen kann es sie nicht. Wer eine Designloesung fuer eine
SPEC-Luecke haelt, hat die Luecke verloren.

| Luecke | SPEC-3 | Was das Design tut | Was es **nicht** tut |
|---|---|---|---|
| **SEC-1** -- eine Freigabe umgeht die Allowlist | 17, bestaetigt, OFFEN | Die Gatterleiter zeigt genau die Pruefungen, die der Code **tatsaechlich** durchlaeuft. Heute ist die Allowlist keine davon | Keine Allowlist-Sprosse anzeigen, solange `verify_targets` sie nicht prueft. Eine angezeigte Pruefung, die nicht stattfindet, ist schlimmer als keine |
| **SEC-2** -- kein atomarer Anspruch | 17, bestaetigt, OFFEN | Das Design haelt zwei Marken frei (*Beansprucht*, *Laeuft*) und benutzt sie nicht | Keine Zustandsmaschine festlegen. Das ist OD-1 |
| **OD-1** -- Zustandsmaschine fuer Aktionen | 23, OFFEN | Die Zustandsmarke ist so gebaut, dass zwei weitere Zustaende ohne Umbau hineinpassen | Nicht entscheiden, ob Zustandsspalte oder eigene Tabelle |
| **OD-2** -- Vertrauensgrad im Gedaechtnis | 23, OFFEN | Der Gedaechtnisentwurf hat eine Spalte *Herkunft* und zeigt heute ueberall denselben Wert, mit Hinweis warum | Kein Herkunftsmodell erfinden und keine Klassifikation vorschlagen, die SPEC-3 nicht kennt |
| **OD-3** -- feinere Vertraulichkeitssteuerung | 23, OFFEN | Die Modelltafel zeigt die Aufgabenzuordnung, wie sie ist | Keine Inhaltsklassifikation zeigen |
| **OD-4** -- Dashboard-Gestaltung | 23, OFFEN | Dieses Dokument ist der Vorschlag zu OD-4 | OD-4 nicht entscheiden. Das tut der Nutzer |
| **OD-5** -- Zielhost-Allowlist des Modellprozesses | 23, OFFEN | Die Modelltafel nennt die Trennungsstufe (`off`/`subprocess`/`sandbox`) | Nichts ueber Netzbegrenzung behaupten |
| **UNVERIFIED / OFFLINE / CANCELLED fehlen** | 5.2 | Musterblatt zeigt sie als *reserviert*, gepunktet, mit Begruendung | Sie **nicht** in die Oberflaeche nehmen |
| **8 von 15 Control-Plane-Bereichen fehlen** | 12 | Die Informationsarchitektur hat einen Platz fuer jeden | Keinen davon als vorhanden zeigen. Vier setzen Faehigkeiten voraus, die es nicht gibt |
| **KI-7** -- Kurzzeitkontext ohne Bedienweg | 17 | Der Gedaechtnisentwurf zeigt, wo ein solcher Weg saesse | Ihn nicht bauen und nicht als vorhanden zeigen |
| **Kein Fortschritt waehrend einer Ausfuehrung** | folgt aus 5.2 und OD-1 | Der Entwurf sagt ehrlich: die Seite kehrt zurueck, wenn es entschieden ist | Keine Fortschrittsanzeige erfinden. Sie braeuchte den Zustand `EXECUTING`, den es nicht gibt |

## 4. Was die Oberflaeche heute ist (CURRENT, am Code geprueft)

| Punkt | Stand | Fundstelle |
|---|---|---|
| Ansichten | vier: `/` Zustand, `/briefing`, `/entscheidungen`, `/protokoll` | `web/app.py` `routen` |
| Ausloesbare Handlungen | genau vier: freigeben, verwerfen, anhalten, fortsetzen | `web/app.py` |
| Durchlaeufe starten | **nicht** in der Oberflaeche, nur ueber die Kommandozeile | `web/app.py` Kopfkommentar, `briefing()` |
| Technik | serverseitiges HTML, `meta refresh`, ein Stylesheet als eigene Route, kein JavaScript | `render.py`, `style.py` |
| Farben heute | `--bg #0c0e10`, `--panel #111417`, `--line #1d2429`, `--text #ccd2d6`, `--dim #6d787e`, `--accent #67b8c7` | `style.py` |
| Schrift heute | Systemschrift fuer Text, `ui-monospace` fuer Zahlen und Zustaende | `style.py` |
| Breite heute | `max-width: 60rem` | `style.py` `.wrap` |
| Stoppschalter | eigenes Band ganz oben, faerbt sich bei gesetztem Schalter | `style.py` `.stop`, `render.py` `seite()` |
| Zielfelder im Vorgang | feste Reihenfolge: Empfaenger, Betreff, Kategorie, Label, Nachricht, Entwurf | `render.py` `BEKANNTE_ZIELE` |
| Maskierung | jeder Wert von aussen durch `esc`; nur `seite()` nimmt fertiges HTML | `render.py` Kopfkommentar |
| Inline-Stile | **keine** -- die gesamte Gestaltung steht im Stylesheet, passend zu `style-src 'self'` | `render.py`, `app.py`, nachgesehen |
| Rueckmeldungen | Codes in der Adresse, Text aus einer festen Tabelle -- nie freier Text aus der URL | `app.py` `MELDUNGEN` |

Die heutige Gestaltung ist damit bereits nahe an dem, was dieses Dokument
vorschlaegt. Das ist Absicht: SPEC-3 OD-4 empfiehlt, eine Angleichung erst zu
entscheiden, wenn ein Funktionsgewinn dahintersteht. Ein Design, das den
vorhandenen Stand wegwirft, waere teuer und durch nichts gedeckt.

## 5. Was historisch ist

SPEC-1 (`JARVIS-SPEC.md`, Abschnitt 7 "Oberflaeche") beschreibt die Aesthetik:
dunkel, eine Akzentfarbe, duenne Linien, Monospace fuer Zahlen, knappe Sprache,
keine Emojis, sichtbarer Stoppschalter, keine Animation. SPEC-3 Abschnitt 25
fuehrt SPEC-1 als **HISTORICAL**.

**Folge, und sie ist wichtig:** Diese Aesthetik ist nicht bindend. Sie wird in
diesem Dokument trotzdem weitergefuehrt -- aber als DESIGN mit eigener
Begruendung (Teil III), nicht als Erbe. Wo sie gegen einen sachlichen Grund
steht, gewinnt der sachliche Grund. Ein Beispiel steht in DD-06: die
Ein-Farben-Regel wird um zwei Funktionssignale erweitert, weil SPEC-3 3.4 (B9)
verlangt, dass ein Fehler nicht wie ein Erfolg aussieht.

## 6. Technische Randbedingungen, die die Form bestimmen

Diese vier sind CURRENT und nicht verhandelbar, solange SPEC-3 gilt. Sie
schliessen einen grossen Teil des ueblichen Gestaltungswerkzeugs aus -- und
genau daraus entsteht der Stil.

| Randbedingung | Folge fuer die Gestaltung |
|---|---|
| `default-src 'none'`, **kein JavaScript** (B4) | Keine Umschalter, keine Menues, keine Sortierung im Client, kein Dialogfenster, kein Fortschrittsbalken, keine Nachladen-Animation. Jede Auswahl ist eine Adresse, jede Handlung ein Formular |
| `img-src 'none'` (B4) | Keine Bilddateien, keine Symbolschrift, keine externen Schriften, kein Logo als Datei. Symbole nur als Inline-SVG; Schrift nur, was das System hat |
| `style-src 'self'` (B4) | **Kein `style`-Attribut.** Jede Gestaltung steht im Stylesheet; ein dynamischer Wert -- etwa ein Fuellstand -- wird auf eine Stufenklasse gerundet, statt inline gesetzt zu werden (DD-33) |
| Kein Build-Schritt (B20) | Handgeschriebenes CSS in einer Datei. Kein Praeprozessor, kein Framework, keine Werkzeugkette |
| `meta refresh` statt Ereignisstrom | Aktualisierung ist ein Neuladen. Die Seite muss ohne Zustand im Client vollstaendig sein, und ein Neuladen darf keine Handlung wiederholen (deshalb Umleitung nach jedem POST, CURRENT) |

**IDEA, nicht Teil dieses Vorschlags:** Ein Ereignisstrom (SSE) wuerde die
Sicherheitsrichtlinie aufweichen und braucht eine SPEC-Aenderung. Er steht hier
nur, damit klar ist, dass das Design ihn nicht voraussetzt.

---

# Teil II -- Designprinzipien

Acht Prinzipien. Jedes hat eine Zeile aus Abschnitt 1 als Grundlage; keines ist
Geschmack allein. Sie stehen in der Reihenfolge ihrer Verbindlichkeit.

### D1 -- Die Oberflaeche zeigt Zustand, sie behauptet keinen

*Grundlage: B18 (keine Erfolgsmeldung staerker als der Nachweis), B17, B9.*

Jede Anzeige nennt, woher sie weiss, was sie sagt: eine Zahl mit ihrem Bezug
(`12/60 in der Stunde`, nicht `12`), ein Ziel mit seiner Herkunft (`Kopffeld
From`, nicht nur die Adresse), ein Nachweis mit seiner Stufe (`built, tested,
mocked -- live: nie`, nicht `verbunden`). Wo nichts nachgewiesen ist, steht
`nie` und nicht `--`.

### D2 -- Die Sicherheitskette ist sichtbar, nicht spuerbar

*Grundlage: B1, B2, B3, B6, B7.*

Die Oberflaeche entscheidet nichts. Sie zeigt, **wer** entschieden hat und
**an welcher Sprosse**. Dafuer gibt es einen einzigen Baustein, die Gatterleiter,
und er behaelt immer die Reihenfolge aus SPEC-3 4.2. Ein Nutzer, der eine
Freigabe erteilt, soll auf demselben Bildschirm sehen koennen, dass sie nur die
Stufe ersetzt.

### D3 -- Die Vertrauensgrenze ist die Hauptachse der Gestaltung

*Grundlage: B14, B13, B11, und Abschnitt 25 (Future-only, Entscheidungsstrom).*

Ueberall, wo Modellausgabe und berechnete Werte nebeneinander stehen, trennt die
Gestaltung sie sichtbar: **gepunktete Linie und Satzschrift** fuer alles, was aus
Fremdtext oder Modell stammt, **durchgezogene Linie und Maschinenschrift** fuer
alles, was Code aus vertrauenswuerdiger Quelle gerechnet hat. Die Trennung wird
nicht ueber Farbe kodiert, damit sie in Graustufen und bei Farbfehlsichtigkeit
bestehen bleibt.

### D4 -- Der sichere Weg ist der voreingestellte

*Grundlage: B5, B7, B19, und die Leitregel "Security before Autonomy" (21).*

Der Stoppschalter ist auf jeder Ansicht erreichbar und braucht nie eine
Rueckfrage. Die Rueckfrage steht auf der anderen Seite: vor einer Aktion, die
den Rechner verlaesst. Hervorgehoben ist in einer Handlungszone nicht die
handelnde, sondern die ruhige Schaltflaeche.

### D5 -- Auffaellig ist der unsichere Zustand, nicht der sichere

*Grundlage: B19, B17, und der Kommentar in `cli.py`: "Ein Mock, den man nicht sieht, ist eine Falle."*

Umgekehrt zur Gewohnheit: **`Trockenlauf an` ist ruhig, `Trockenlauf AUS` ist
auffaellig.** Denn ohne Trockenlauf verlaesst echte Post den Rechner. Ebenso
traegt `Dienste: Mock` eine Warnfarbe -- nicht weil Mock schlecht ist, sondern
weil ein unbemerkter Mock alles gruen aussehen laesst, was nie stattgefunden hat.

### D6 -- Kein Zustand in der Oberflaeche, den das System nicht hat

*Grundlage: B15, B21, B18.*

Es gibt keine Marke fuer `Offline`, keine fuer `Abgebrochen`, keinen
Fortschrittsbalken fuer eine laufende Ausfuehrung -- weil es diese Zustaende im
System nicht gibt (SPEC-3 5.2). Das Design haelt Platz frei und beschriftet ihn
als frei. Eine Oberflaeche, die einen Zustand zeigt, den der Kern nicht kennt,
erzeugt Vertrauen ohne Deckung.

### D7 -- Eine Handlungszone je Seite

*Grundlage: B3 (kein zweiter Aktionsweg), B2.*

Handlungen sammeln sich in einer sichtbar abgesetzten Zone am Fuss des Objekts,
zu dem sie gehoeren -- nie verstreut, nie in einer Tabellenzeile ohne Kontext.
Es gibt genau vier ausloesbare Dinge (CURRENT), und das soll man der Oberflaeche
ansehen. Jede kuenftige Handlung geht durch `execute_approval` oder gehoert
nicht in die Oberflaeche.

### D8 -- Dichte vor Grosszuegigkeit, Ruhe vor Dichte

*Grundlage: SPEC-3 12 (Instrumententafel), 4.9 (acht Fragen aus einem Eintrag).*

Das ist eine Instrumententafel fuer eine Person auf einem Rechner, kein Produkt
fuer Fremde. Sie darf dicht sein. Aber sie darf nicht laut sein: keine Bewegung,
keine Verlaeufe, keine Schatten, keine Rundungen, keine Illustration. Wo Dichte
und Ruhe streiten, gewinnt Ruhe -- die Aufmerksamkeit gehoert den Abweichungen.

---

# Teil III -- Visuelle Identitaet

## 7. Gesamtaesthetik

**DESIGN.** *Instrumententafel, nicht Interface-Schaustueck.* Flaeche, Linie,
Schrift -- mehr Mittel gibt es nicht. Tiefe entsteht ueber genau drei
Flaechenwerte, nie ueber Schatten. Struktur entsteht ueber 1px-Linien, nie ueber
Kaesten mit Rand und Fuellung und Rundung.

Begruendung, warum das nicht nur Geschmack ist:

* Die Sicherheitsrichtlinie (B4) nimmt ohnehin Bilder, Schriften und Skript weg.
  Ein Stil, der auf Flaeche, Linie und Schrift beruht, arbeitet **mit** dieser
  Grenze statt gegen sie.
* Die Aufgabe ist Unterscheidung, nicht Ueberredung: gewaehrt gegen verlangt,
  Modell gegen Code, gemockt gegen live. Dekoration erschwert genau das.
* SPEC-3 3.4 (B9) verlangt, dass ein Fehler nicht wie ein Erfolg aussieht. In
  einer ruhigen Flaeche genuegt dafuer ein einziges farbiges Element. In einer
  lauten genuegt es nicht mehr.

**Was ausdruecklich nicht kommt** (DESIGN, in der Sache wie SPEC-1 §7, dort
HISTORICAL): keine Hologramm-Anmutung, keine Reaktoren, keine Ringe, keine
Klaenge, keine Bewegung, keine Emojis.

## 8. Farbwelt

**DESIGN.** Die dunkle Fassung fuehrt die vorhandenen Werte aus `style.py`
weiter und ordnet sie zu Rollen. Uebernommen wird die Familie, nicht jeder Wert:
Text und Linien sind leicht angehoben, weil die heutigen Werte auf hellen
Displays im Kontrast knapp sind.

### Rollen statt Farbnamen

| Marke | Dunkel | Hell | Rolle |
|---|---|---|---|
| `--grund` | `#0B0D0F` | `#F7F8F9` | Seitengrund |
| `--flaeche` | `#101417` | `#FFFFFF` | Baender, Karten, Tafeln |
| `--flaeche-hoch` | `#151A1E` | `#F1F3F4` | Kopfzeile, hervorgehobene Zeile |
| `--linie` | `#1D2429` | `#DFE4E7` | Standardtrennung |
| `--linie-stark` | `#2B353C` | `#C3CBD0` | Abschnittsgrenze, Rahmen, Marken |
| `--text` | `#D3D9DD` | `#14181B` | Vordergrund |
| `--text-zweit` | `#98A3AA` | `#4A555C` | Beschriftungen, zweite Ebene |
| `--text-gedaempft` | `#6C777E` | `#6C777E` | Herkunft, Zeit, dritte Ebene |
| `--akzent` | `#67B8C7` | `#1F6E7C` | Identitaet und "hier bist du gefragt" |
| `--signal-warnung` | `#D9A441` | `#8A6108` | angehalten, blockiert, Mock, Trockenlauf AUS |
| `--signal-fehler` | `#D9705E` | `#A8331F` | fehlgeschlagen |

### Die drei Farbregeln

**DD-05 -- Erfolg traegt keine Farbe.** Der Normalfall ist neutral. Farbe
bekommt nur, was Aufmerksamkeit verdient. Eine Tafel mit fuenfzehn gruenen Haken
macht den einen roten schwerer auffindbar, nicht leichter.

**DD-06 -- Ein Akzent, zwei Funktionssignale, mehr nicht.** SPEC-1 nennt eine
einzige Akzentfarbe; das reicht nicht, um B9 zu erfuellen (ein Fehler darf nicht
wie ein Erfolg aussehen), wenn zugleich der Akzent fuer Identitaet und offene
Vorgaenge steht. Deshalb: **ein** Akzent plus **zwei** Signale. Ein drittes
Signal (Erfolgsgruen) wird bewusst nicht eingefuehrt -- siehe DD-05.

**DD-07 -- Farbe nie allein.** Jede farbige Aussage traegt zusaetzlich ein Wort
und eine Form (Rahmen, Linienart, Muster). Pruefbar: das Musterblatt
`prototyp/08-zustaende.html` bleibt in Graustufen vollstaendig lesbar. Das ist
keine Kuer -- ohne diese Regel haengt B9 an der Farbwahrnehmung des Nutzers.

**Zuordnung der Signale**

| Erscheinung | Farbe | Warum |
|---|---|---|
| Stoppschalter gesetzt | Warnung, ganzes Band | Ein angehaltenes System soll man ohne Lesen erkennen (B5) |
| `BLOCKED` | Warnung, nur die Marke | Das System hat gehalten -- richtig, aber erklaerungsbeduerftig |
| `Dienste: Mock` | Warnung | "Ein Mock, den man nicht sieht, ist eine Falle" |
| `Trockenlauf AUS` | Warnung | D5: der unsichere Zustand ist der auffaellige |
| `FAILED` | Fehler | B9 |
| `PENDING` | Akzent | Das Einzige, was den Nutzer wirklich braucht |
| `SUCCESS`, `DRY_RUN`, `REJECTED` | neutral | DD-05 |

## 9. Typografie

**DESIGN.** SPEC-3 27 stellt das Schriftbild ausdruecklich frei; hier wird es
festgelegt, damit es nicht in SPEC-3 landet.

| Rolle | Schrift | Warum |
|---|---|---|
| Satz | `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", sans-serif` | macOS ist Zielplattform (SPEC-3 14). Systemschrift heisst: keine Ladezeit, kein Fremdzugriff, keine Verletzung von `default-src 'none'` |
| Maschine | `ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace` | Kennungen, Zahlen, Zustaende, Faehigkeitsnamen, Ziele |

**DD-08 -- Maschinenschrift fuer Gerechnetes, Satzschrift fuer Gelesenes.**

> **Eingeschraenkt seit dem Rueckbau der Naht (Abschnitt 51):** innerhalb der Faktenliste
> einer Vorgangskarte greift die Unterscheidung nicht mehr. Dort stehen alle Werte in
> Maschinenschrift, auch die des Modells. Die Regel gilt weiter fuer die Oberflaeche als
> Ganzes, aber sie traegt die Vertrauensgrenze nicht mehr -- das war an die Zweiteilung
> gebunden.

> Alles, was eine Maschine gerechnet hat, steht in Maschinenschrift.
> Alles, was ein Mensch als Satz liest, steht in Satzschrift.

Damit ist die Grenze aus D3 schon an der Schrift erkennbar, bevor eine Linie
oder eine Farbe hinzukommt. Praktische Folge: ein Empfaenger steht in
Maschinenschrift, eine Modellbegruendung in Satzschrift -- auch wenn beide in
derselben Faktenliste stehen.

**Groessen.** Grundzeile 15px / 1.55 (uebernommen aus `style.py`, gut lesbar auf
Retina wie auf externem Monitor).

| Rolle | Groesse | Auszeichnung |
|---|---|---|
| Bereichstitel `h1` | 1.05rem, Maschine, `letter-spacing: 0.22em` | Identitaet, nur "JARVIS" |
| Abschnittsmarke `h2` | 0.72rem, Versalien, `0.14em`, gedaempft, Linie darunter | Trennt, ohne Gewicht zu nehmen |
| Untertitel `h3` | 0.86rem, halbfett | Innerhalb einer Karte |
| Fliesstext | 0.95rem | Vorgangssatz, Briefing |
| Tabelle, Fakten | 0.84rem | Dichte |
| Marke, Tabellenkopf | 0.68-0.72rem, Versalien, `0.1-0.12em` | Muss klein sein, sonst schreit sie |

**Zahlen** stehen mit `font-variant-numeric: tabular-nums`. In einer Tafel, die
sich alle 30 Sekunden neu laedt, sollen Ziffern nicht springen.

**Keine Kursive, kein Fett im Fliesstext.** Auszeichnung geschieht ueber Marke,
Linie und Position. Fett bleibt Tabellenkoepfen und `h3` vorbehalten.

## 10. Formen

**DESIGN.**

* **Radius 0, ausnahmslos.** Die Geometrie traegt Bedeutung -- die Naht, die
  Leiter, die Marke. Runde Ecken weichen genau die Kanten auf, die lesbar
  bleiben sollen.
* **1px-Linien** als einziges Strukturmittel. `--linie` trennt innerhalb eines
  Bereichs, `--linie-stark` grenzt Bereiche ab.
* **Keine Schatten, keine Verlaeufe.** Tiefe kommt aus drei Flaechenwerten.
* **Linienart als Bedeutungstraeger:**
  * durchgezogen = deterministisch berechnet, vertrauenswuerdig
  * gepunktet = aus Fremdtext oder Modell abgeleitet
  * gestrichelt = verworfen oder ungueltig
  * schraffiert = Trockenlauf (etwas ist geschehen, aber nichts ist hinausgegangen)
* **Marken** sind Rechtecke mit 1px-Rahmen, 1px/6px Innenabstand, Versalien in
  Maschinenschrift. Nie gefuellt, ausser das ganze Band ist es (Stoppschalter).

## 11. Raster und Abstaende

**DESIGN.** 4px-Basisraster. Die Skala ist absichtlich kurz -- acht Werte, mehr
erzeugt nur Uneinheitlichkeit.

`4 / 8 / 12 / 16 / 24 / 32 / 48 / 64`

| Ort | Abstand |
|---|---|
| innerhalb einer Faktenzeile | 4 |
| zwischen Marke und Text | 8 |
| Innenabstand einer Karte | 16 |
| Spurrand | 24 |
| zwischen Abschnitten (`h2` oben) | 32 |
| vor dem Fuss | 48 |

**Zwei Spurbreiten** statt einer:

| Spur | Breite | Wofuer |
|---|---|---|
| Lesebreite | 60rem | Vorgaenge, Briefing, Einzelansichten, alles mit Prosa |
| Tafelbreite | 96rem | Lage, Protokoll, Dienste -- dichte Tabellen im weiten Fenster |

Begruendung: 60rem (heute fuer alles) ist fuer die Protokolltabelle mit sechs
Spalten zu eng; sie bricht dann in einem Fenster um, das eigentlich Platz haette.
Prosa dagegen wird ueber 60rem hinaus schlechter lesbar.

## 12. Hierarchie

**DESIGN.** Drei Ebenen, ueberall dieselbe Reihenfolge:

```
  Systemband        Was gerade fuer das ganze System gilt.  Immer sichtbar.
  Bereich           Wo bin ich.  Navigation plus Bereichstitel.
  Gegenstand        Ein Vorgang, ein Eintrag, eine Faehigkeit.
```

**Die Reihenfolge auf jeder Seite ist: Abweichung, dann Arbeit, dann Bestand.**
Konkret auf der Lage-Ansicht: erst was blockiert, angehalten oder fehlgeschlagen
ist; dann was auf eine Entscheidung wartet; dann die vollstaendigen Tabellen.
Grundlage ist D8 -- die Aufmerksamkeit gehoert den Abweichungen.

## 13. Symbole

**DESIGN.** Inline-SVG, 16px-Raster, 1.5px Strich, `currentColor`, kein Fuellen.
Keine Bilddatei und keine Symbolschrift -- `img-src 'none'` (B4) laesst beides
nicht zu, und ein Inline-SVG ist Dokumentinhalt, keine geladene Quelle.

Acht Symbole, mehr nicht: **halt, weiter, erledigt, verworfen, offen, achtung,
gesperrt, protokoll.**

**DD-13 -- Kein Symbol steht allein.** Jede Handlung und jeder Zustand traegt
sein Wort. Symbole sind Beschleuniger fuer das wiederholte Lesen, nie Traeger
der Bedeutung. Grundlage: B9 und B18 -- eine Bedeutung, die nur an einer Form
haengt, ist eine Behauptung ohne Text.

## 14. Helle und dunkle Fassung

**DESIGN.** Beide Fassungen, gesteuert ueber `prefers-color-scheme`. **Keinen
Umschalter** -- ohne JavaScript braeuchte er eine Route, ein Cookie und damit
Zustand im Server fuer eine reine Anzeigefrage. Das waere neue Funktion fuer
Gestaltung, und dieses Dokument darf keine erfinden.

Auf macOS ist das ausserdem das erwartete Verhalten: die Systemeinstellung
wechselt zur Daemmerung, die Tafel wechselt mit.

Die helle Fassung ist kein Aufhellen der dunklen. Die Signale werden dunkler und
gesaettigter, weil sie sonst auf Weiss nicht tragen; die Rollen bleiben
identisch.

**Verbindlichkeit:** SHOULD, nicht MUST. Wenn die Umsetzung gekuerzt werden
muss, ist die dunkle Fassung die, die bleibt (sie ist CURRENT).

## 15. Bewegung

**DESIGN.** **Keine.** Kein Uebergang, keine Blende, kein Pulsieren, kein
Skelett-Platzhalter. Zwei Gruende, und beide sind sachlich:

1. Ohne JavaScript gibt es ohnehin nichts, was Bewegung ehrlich anzeigen
   koennte -- eine Animation waeere Ausschmueckung, die Arbeit vortaeuscht,
   wo keine stattfindet (B18).
2. Die einzige Bewegung im System ist das Neuladen alle `refresh_seconds`.
   Eine Seite, die dabei aufblitzt, macht ein ruhiges System unruhig.

`prefers-reduced-motion` wird trotzdem beruecksichtigt -- als Zusage fuer
spaetere Ergaenzungen.

---

# Teil IV -- Statusdarstellung

## 16. Zwei Achsen, die nie vermischt werden

**DESIGN, Grundlage B15 und B16.**

SPEC-3 fuehrt zwei voellig verschiedene Leitern: die **Aktionszustaende** (5.2)
und die **Nachweisstufen** (Kopfabschnitt, 11, 14). Sie beantworten
verschiedene Fragen, und SPEC-3 sagt ausdruecklich, dass sie nicht vermischt
werden duerfen ("Sie ist im Code verankert und darf nicht vermischt werden").

```
   Achse 1  AKTIONSZUSTAND     Was ist mit diesem einen Vorgang passiert?
            Ausgefuehrt, Offen, Blockiert, Verworfen, Fehlgeschlagen, Dry Run

   Achse 2  NACHWEISSTAND      Wie weit ist dieser Weg ueberhaupt belegt?
            built, tested, mocked, live verified, platform verified
```

Der wichtigste Fall, den diese Trennung abfaengt: eine Aktion kann
**ausgefuehrt** sein, obwohl der Dienst dahinter **nie live verifiziert** wurde.
Genau das ist heute der Normalfall (B17). Eine einzige gemischte Anzeige --
etwa ein gruenes "verbunden" -- wuerde diesen Unterschied verschlucken. Deshalb
stehen die Achsen an verschiedenen Orten: der Aktionszustand am Vorgang, der
Nachweisstand am Dienst.

Das beantwortet zugleich, wohin `UNVERIFIED` gehoert: **auf Achse 2, nicht auf
Achse 1.** SPEC-3 5.2 sagt es so -- "Der Nachweisstand externer Dienste traegt
diese Bedeutung, aber nicht als Aktionszustand". Das Design macht daraus keinen
Aktionszustand.

## 17. Die neun Aktionszustaende

**Grundlage B15. Sechs sind CURRENT, drei existieren nicht.**

| Marke | Zustand | Herkunft im Code | Vorhanden | Farbe | Form |
|---|---|---|---|---|---|
| `Ausgefuehrt` | SUCCESS | `Result.performed = True` | CURRENT | keine | Rahmen normal |
| `Offen` | PENDING | `approvals.state = pending` | CURRENT | Akzent | Rahmen normal |
| `Blockiert` | BLOCKED | `Disposition.BLOCKED` | CURRENT | Warnung | Rahmen normal |
| `Verworfen` | REJECTED | `approvals.state = rejected` | CURRENT | keine, gedaempft | Rahmen **gestrichelt** |
| `Fehlgeschlagen` | FAILED | `Result.performed = False` | CURRENT | Fehler | Rahmen normal |
| `Dry Run` | DRY_RUN | `Disposition.DRY_RUN` | CURRENT | keine | **schraffiert** |
| `Unverified` | UNVERIFIED | -- | **nein** (5.2) | -- | Rahmen **gepunktet**, nur im Musterblatt |
| `Offline` | OFFLINE | -- | **nein** (5.2) | -- | dito |
| `Cancelled` | CANCELLED | -- | **nein** (5.2) | -- | dito |

**DD-14 -- Die drei fehlenden Zustaende erscheinen nicht in der Oberflaeche.**
Sie sind im Musterblatt sichtbar, gepunktet, mit dem Vermerk warum. In einer
Ansicht des Dashboards haben sie nichts zu suchen, solange der Kern sie nicht
kennt. Grundlage: D6, B18, B21.

**Was heute stattdessen erscheint** -- und wie es formuliert wird:

| Fall | Heutiger Zustand | Wortlaut (DESIGN) |
|---|---|---|
| Anbieter nicht erreichbar | `Fehlgeschlagen` | "Gmail war nicht erreichbar. Der Vorgang bleibt offen und ist unveraendert." |
| Nutzer verwirft im Dashboard | `Verworfen` | "Verworfen. Es ist nichts geschehen." |
| Dienst nie live erreicht | kein Aktionszustand | erscheint auf Achse 2 als `live: nie` |

**Reserviert, nicht belegt (OD-1).** SPEC-3 nennt unter SEC-2 die Kette
`PENDING -> CLAIMED -> EXECUTING -> SUCCEEDED | FAILED | CANCELLED` als Konzept
und laesst die Maschine ausdruecklich offen. Das Design haelt zwei Marken frei
-- `Beansprucht` und `Laeuft` -- und **benutzt sie nicht**. Es legt weder ihre
Namen noch ihre Uebergaenge fest; das ist OD-1 und wird nicht von der
Gestaltung entschieden.

## 18. Die Nachweisleiter

**DESIGN, Grundlage B16, B17.**

Fuenf Sprossen als kleine Balkenreihe, gefuellt = erreicht, plus Klartext.

```
  [#][#][#][ ][ ]  built . tested . mocked        live: nie
```

**DD-15 -- `nie` steht als Wort da, nicht als leeres Feld.** SPEC-3 nennt genau
das den wichtigsten Satz des Dokuments. Eine leere Zelle liest sich wie "noch
nicht erhoben"; `nie` liest sich wie das, was es ist. Die Angabe traegt
Warnfarbe, solange sie `nie` lautet.

Kein Dienst bekommt eine gruene Zusammenfassung wie "in Ordnung". Der Zustand
ist die Leiter selbst.

## 19. Autonomiestufe

**DESIGN, Grundlage B8.**

**DD-16 -- Immer beide Zahlen: gewaehrt / verlangt.**

```
   0 / 0   Schattenbetrieb          gewaehrt reicht
   0 / 1   verlangt Allowlist       gewaehrt reicht nicht  -> Warnfarbe auf der Zahl
```

Grundlage ist ein konkreter Vorfall: SPEC-3 6.1 haelt fest, dass `research` mit
`autonomy_level = 0` gebaut wurde und deshalb auf Stufe 0 handelte -- `0 >= 0`
ist wahr. Eine Oberflaeche, die nur eine der beiden Zahlen zeigt, kann diesen
Fehler nicht sichtbar machen. Die heutige Tafel zeigt nur die gewaehrte
(`app.py`, Spalte "Stufe"); das ist der einzige Punkt, an dem dieses Design der
CURRENT-Ansicht eine echte Information hinzufuegt, statt sie nur anders zu
setzen.

Die Bezeichnungen sind die aus dem Code: Schattenbetrieb, Allowlist, Freigegebene
Kategorien, Alles ausser Gesperrtes. Sie werden nicht uebersetzt oder geglaettet.

## 20. Die Gatterleiter

**DESIGN, Grundlage B6, B7, D2. Das zweitwichtigste Element nach der Naht.**

Fuenf Sprossen in der Reihenfolge aus SPEC-3 4.2, immer vollstaendig, nie
umsortiert. Markiert wird, welche Sprosse entschieden hat; darunter liegende
Sprossen werden als *nicht ausgewertet* gedaempft -- nicht als *bestanden*.

```
  1  Faehigkeit aktiv        ja                                    Weiter
  2  Stoppschalter           gesetzt: ueber das Dashboard          BLOCKIERT
  3  Stufe / Freigabe        nicht ausgewertet                     --
  4  Obergrenze              nicht ausgewertet, nichts verbraucht  --
  5  Ausfuehrung             nicht erreicht                        --
```

Was dieses Element leistet, das eine blosse Statusmeldung nicht leistet:

* Es macht **B7** sichtbar. Wer eine Freigabe erteilt, sieht, dass sie an
  Sprosse 3 wirkt -- und dass Sprosse 2 und 4 davon unberuehrt sind.
* Es macht die **Reihenfolge** sichtbar: dass der Stoppschalter vor der
  Obergrenze steht, ist im Bild zu sehen ("nichts verbraucht").
* Es beantwortet zwei der acht Fragen aus 4.9 ohne Zusatztext: welche Regel
  gegriffen hat, und ob blockiert wurde.

**DD-17 -- Die Leiter zeigt nur Pruefungen, die der Code wirklich durchlaeuft.**
Heute ist die Allowlist **keine** Sprosse, weil sie auf dem Freigabeweg nicht
ausgewertet wird (SEC-1, bestaetigt offen). Eine sechste Sprosse "Allowlist"
kommt erst dazu, wenn SEC-1 geschlossen ist. Eine angezeigte Pruefung, die nicht
stattfindet, waere die gefaehrlichste Anzeige im ganzen System.

## 21. Zaehler und Grenzen

**DESIGN, Grundlage D1.**

Eine Zahl steht nie allein. `12/60 Stunde` plus ein kurzer Balken. Der Balken
wechselt auf Warnfarbe, wenn die Grenze erreicht ist -- das ist dann derselbe
Zustand wie `Blockiert`, und er sieht auch so aus.

Im Trockenlauf wird nichts verbraucht (CURRENT, `gate.py`). Wo ein Zaehler in
einem Trockenlauf steht, nennt der Text das ausdruecklich: "nichts verbraucht".
SPEC-3 Q-3 hat genau hier eine zu starke Zusage gestrichen; die Oberflaeche darf
sie nicht wieder einfuehren.

---

# Teil V -- Bausteine

Zwoelf Bausteine, mehr braucht die Oberflaeche nicht. Jeder hat eine Aufgabe,
eine Fundstelle im Prototyp und eine Grundlage.

| # | Baustein | Aufgabe | Grundlage | Stand |
|---|---|---|---|---|
| K1 | **Systemband** | Drei Tatsachen und der Stoppschalter, auf jeder Ansicht | B5, B19, D5 | CURRENT erweitert |
| K2 | **Zustandsmarke** | Ein Aktionszustand, als Wort mit Form | B9, B15, DD-07 | DESIGN |
| K3 | **Nachweisleiter** | Fuenf Sprossen plus `live: nie` | B16, B17 | DESIGN |
| K4 | **Autonomieanzeige** | gewaehrt / verlangt, mit Bezeichnung | B8, DD-16 | DESIGN |
| K5 | **Gatterleiter** | Fuenf Sprossen in fester Reihenfolge | B6, B7 | DESIGN |
| K6 | ~~Vertrauensnaht~~ | **entfaellt.** Ersetzt durch `vorgangsfakten()`: eine Liste aus Zielen, Modellfeldern, Grund, Entscheider und Modell | Abschnitt 25 | zurueckgebaut |
| K7 | **Vorgangskarte** | Ein anstehender Vorgang mit seinen Handlungen | CURRENT `render.vorgang` | CURRENT erweitert |
| K8 | **Faktenliste** | Name/Wert-Paare, Wert in Maschinenschrift | CURRENT `render.fakten` | CURRENT |
| K9 | **Tabelle** | Dichte Liste, im schmalen Fenster zu Bloecken | CURRENT `render.tabelle` | CURRENT erweitert |
| K10 | **Rueckfrageseite** | Zweiter Schritt vor einer Aktion nach aussen | D4, B7 | DESIGN, neu |
| K11 | **Meldung** | Ergebnis der letzten Handlung, aus fester Tabelle | CURRENT `MELDUNGEN` | CURRENT |
| K12 | **Leerer Zustand** | Was nicht da ist, und der Weg dorthin | D1 | CURRENT erweitert |

## 22. Systemband (K1)

**Was darin steht** -- und warum genau diese vier:

| Tatsache | Warum sie oben steht |
|---|---|
| `Betrieb` / `ANGEHALTEN` | B5. Der Stoppschalter gehoert auf jede Ansicht |
| `Trockenlauf an` / `Trockenlauf AUS` | Entscheidet, ob ein Klick Wirkung nach aussen hat (B19) |
| `Dienste Mock` / `Live` | Entscheidet, ob ueberhaupt etwas Echtes geschieht (B17) |
| `Zugangsdaten` | SPEC-3 12 zaehlt die Zugangsdatenquelle ausdruecklich zum System Status |

Die ersten drei beantworten zusammen die Frage, die vor jeder Handlung zaehlt:
*wird das, was ich gleich tue, wirklich passieren?* Die vierte steht dabei, weil
SPEC-3 12 sie zum System Status zaehlt; weicht die Quelle von der Keychain ab,
traegt sie Warnfarbe -- `jarvis status` setzt in diesem Fall heute den
Rueckgabewert auf 1.

**Die Dateirechte gehoeren nicht ins Band.** SPEC-3 12 nennt sie ebenfalls unter
System Status, aber sie sind kein Zustand, der eine Handlung beeinflusst. Sie
stehen als Kopfzahl *Ablage* auf der Lage-Ansicht, und nur wenn etwas offen ist,
als Abweichungszeile.

**Angehalten faerbt das ganze Band.** Nicht nur die Marke. Ein angehaltenes
System ist der einzige Zustand, den man ohne Lesen erkennen soll.

**DD-18 -- Anhalten braucht nie eine Rueckfrage, Fortsetzen immer.** Anhalten
ist die sichere Richtung und muss in einer Bewegung erreichbar sein. Fortsetzen
gibt Wirkung nach aussen frei und geht deshalb ueber die Rueckfrageseite (K10).
Grundlage: D4, und die Asymmetrie, die SPEC-3 19.5 fuer Sprache ausdruecklich
festhaelt ("anhalten per Sprache moeglich, fortsetzen nie") -- dieselbe Logik,
anderer Bedienweg.

## 23. Vertrauensnaht (K6) -- ZURUECKGEZOGEN

> **Nicht mehr gueltig.** Dieser Abschnitt ist am 2026-08-31 zurueckgezogen worden.
> SPEC-3 25 fuehrt den Entscheidungsstrom als *"Future-only -- jetzt nur Bauplan"*; die
> Zweiteilung war damit nicht gedeckt. Er bleibt als Beschreibung dessen stehen, was
> entfernt wurde, und was der Rueckbau kostet -- siehe Abschnitt 51.
>
> **Was an seine Stelle tritt:** `render.vorgangsfakten()` -- eine gemeinsame Liste.
> Ziele zuerst, dann die Felder der Modellentscheidung, dann Grund, Entscheider, Modell.
> Die Information bleibt vollstaendig; nur die Trennung ist weg.

### Der zurueckgezogene Entwurf

Zwei Haelften nebeneinander, im schmalen Fenster untereinander.

```
  Modell entschied                 |  Code berechnete
  . . . . . . . . . . . . . . .    |  ---------------------------
  Kategorie      geschaeftlich     |  Empfaenger  anna.berger@...
  Dringlichkeit  normal            |  Herkunft    Kopffeld From
  Begruendung    Rueckfrage zu     |  Entwurf     Draft_a91f
                 einem Vorgang     |  Fingerabdruck sha256:4c1e...
  "Guten Tag, vielen Dank ..."     |  Versandzustand nicht gesendet
```

**Regeln:**

1. Links steht ausschliesslich, was aus `Decision.fields` und aus Fremdtext
   kommt. Rechts ausschliesslich, was aus `Decision.targets` kommt.
2. **Ein Ziel steht nie links.** Das ist keine Gestaltungsregel, sondern P1
   (B14). Die Gestaltung macht die Regel pruefbar: ein Ziel, das links
   auftaucht, ist sofort als Fehler erkennbar.
3. Rechts steht zu jedem Ziel seine **Herkunft** (`Kopffeld From`,
   `Antwortdatensatz`) -- nicht nur der Wert.
4. Fremdtext (Entwurfstext, Betreff) wird als Zitat gesetzt, mit gepunkteter
   Linie, in gedaempfter Farbe. Er ist Anzeige, nie Aussage der Oberflaeche
   (B13).
5. Die Trennung wird **nicht** durch Farbe kodiert.

**Warum das mehr ist als Gestaltung.** SPEC-3 3.2 P1 belegt die Trennung
vierfach im Code -- aber sie ist unsichtbar. Der Nutzer sieht heute eine
Faktenliste, in der Kategorie und Empfaenger gleich aussehen. Wenn er die
Grenze nicht sehen kann, kann er auch nicht bemerken, wenn sie einmal nicht
haelt. SPEC-3 25 nennt genau das eine "starke Idee" -- als Future-only, also
ohne Verbindlichkeit, weshalb dies hier DESIGN bleibt und nicht REQUIRED wird.

## 24. Vorgangskarte (K7)

Aufbau von oben nach unten, immer gleich:

```
  Kopf       Faehigkeit . Aktion . Zustandsmarke . Zeitpunkt
  Satz       Ein Satz in Prosa: was geschehen soll
  Naht       Modell entschied  |  Code berechnete
  Gatter     Fuenf Sprossen, markiert welche haelt
  Handlung   Eine Zone, hoechstens zwei Knoepfe
```

Die Reihenfolge folgt der Frage, die ein Mensch tatsaechlich stellt: *Was ist
das? Was soll passieren? Woher kommt das? Wer hat es aufgehalten? Was tue ich?*

**Was nicht in die Karte gehoert:** der volle Nachrichtentext der Quellmail. Er
wird nicht gespeichert (B12) und darf nicht ueber die Oberflaeche zurueckkehren.
Angezeigt werden Absender, Betreff und der **Entwurfstext** -- also das, was
JARVIS selbst geschrieben hat und was der Nutzer vor dem Senden lesen muss.

## 25. Rueckfrageseite (K10)

**Neu. DESIGN, Grundlage D4, B7.**

Ohne JavaScript gibt es keinen Dialog. Das ist kein Mangel: eine eigene Seite
kann zeigen, **was genau** hinausgeht -- Empfaenger, Betreff, Entwurfstext,
Fingerabdruck, das Kontingent danach. Ein Dialogfenster koennte das nicht.

**Wann sie erscheint** (DESIGN):

| Handlung | Rueckfrage? | Warum |
|---|---|---|
| Freigeben, wenn die Aktion Dritte erreicht **und** Trockenlauf aus ist | **ja** | Unumkehrbar. Der einzige Punkt, an dem echte Post den Rechner verlaesst |
| Freigeben im Trockenlauf | nein | Bewirkt nichts; die Karte sagt das bereits |
| Verwerfen | nein | Sichere Richtung, umkehrbar durch einen neuen Durchlauf |
| Anhalten | nein | Sichere Richtung, muss sofort gehen (DD-18) |
| Fortsetzen | **ja** | Gibt Wirkung nach aussen frei |
| Gedaechtnis vergessen | **ja**, wenn der Bereich je gebaut wird | Nicht wiederherstellbar |

Auf der Seite steht ausserdem der Satz, der B7 traegt: *"Die Freigabe ersetzt
nur die Autonomiestufe. Stoppschalter, Trockenlauf, Ein-Aus-Schalter und
Obergrenze gelten weiter."*

**Der ruhige Weg ist hervorgehoben.** "Zurueck, nichts tun" traegt den Akzent;
"Ja, senden" traegt die Warnfarbe. Das ist bewusst gegen die Gewohnheit -- die
Gewohnheit optimiert auf Abschluss, hier wird auf Umkehrbarkeit optimiert.

---

# Teil VI -- Hauptoberflaeche und Informationsarchitektur

## 26. Navigation

**DESIGN. Vier Punkte, dauerhaft.**

```
   Lage          Entscheidungen (3)          Briefing          Protokoll
```

Gegenueber heute wird nur "Zustand" zu "Lage" umbenannt (der Bereich zeigt mehr
als einen Zustand), sonst bleibt die Leiste, wie sie ist.

**DD-19 -- Die Navigation waechst nicht mit den Bereichen.** SPEC-3 12 nennt
fuenfzehn Bereiche einer Control Plane; acht fehlen. Waeren sie alle
Navigationspunkte, haette die Leiste fuenfzehn Eintraege -- und vier davon
zeigten auf Faehigkeiten, die es nicht gibt. Stattdessen ist **Lage ein
Verteiler**: dort steht je Bereich eine Tafel mit den zwei bis vier Zahlen, die
zaehlen, und ein Weg in die Tiefe.

Begruendung aus dem Ist-Zustand: die vier Punkte entsprechen den vier Fragen,
die ein Nutzer taeglich hat -- *Wie steht es? Was will etwas von mir? Was ist
heute los? Was ist passiert?* Bereiche wie Dienste, Modelle oder Gedaechtnis
sind Nachschlagewerke, keine taeglichen Ziele.

**Der Zaehler an "Entscheidungen"** bleibt (CURRENT). Er ist die einzige Stelle,
an der die Oberflaeche etwas einfordert.

## 27. Die vier Ansichten

### Lage

Reihenfolge nach D8 -- Abweichung, Arbeit, Bestand:

```
  1  Systemband                      immer
  2  Abweichungen                    nur wenn vorhanden:
                                     Kette gebrochen, offene Dateirechte,
                                     Zugangsdaten-Abweichung, fehlgeschlagene
                                     Aktionen der letzten 24 h
  3  Kopfzahlen                      offene Entscheidungen, Protokollgroesse,
                                     Kette, letzter Durchlauf, Ablage
  4  Faehigkeiten                    Name, gewaehrt/verlangt, erreicht Dritte,
                                     aktiv, Kontingent, letzter Lauf
  5  Bereichstafeln                  Dienste, Modelle, Gedaechtnis, Fehler
```

Punkt 2 ist neu (DESIGN) und die einzige Stelle, an der die Ansicht etwas
verbirgt, wenn es nichts zu zeigen gibt. Punkt 5 ist durchgehend PLANNED
(SPEC-3 12: "fehlt") und darf nicht gebaut werden, bevor Roadmap-Punkt 6
freigegeben ist.

**Faehigkeitstabelle:** zwei Spalten kommen zur heutigen Fassung hinzu --
`verlangt` (DD-16) und `letzter Lauf`. Die Spalte "Erreicht Dritte" behaelt
ihren Namen; SPEC-3 fuehrt ausdruecklich, dass "Ausgehend" irrefuehrend war
(Befund F).

### Entscheidungen

Liste von Vorgangskarten, neueste zuerst. Ist der Trockenlauf an, steht die
CURRENT-Meldung darueber und die Freigabeschaltflaeche entfaellt -- unveraendert
zu heute, weil sie genau richtig ist.

**Leerer Zustand:** "Nichts anstehend. Was von selbst durchging, steht im
Protokoll." (CURRENT-Wortlaut, uebernommen.)

### Briefing

Kopf mit Tag, Stand (heute/aelter), Quelle (Modellname oder "ohne Modell") und
Erstellzeit; darunter der Text als Prosa mit Akzentlinie; darunter frueher
erzeugte Briefings.

**Die Angabe "Quelle" ist nicht Schmuck.** Ein Briefing ohne Modell ist der
Rueckfall aus `briefing/skill.py`. Ob der Text vom Modell oder aus dem Rueckfall
stammt, aendert, wie sehr man ihm glauben darf -- also gehoert es sichtbar hin
(D1, B18).

### Protokoll

Dichte Tabelle, `Tafelbreite`. Spalten: Nr, Zeit (UTC), Faehigkeit, Art,
Ergebnis (Zustandsmarke), Grund. Die heutige `T`-Spalte fuer den Trockenlauf
wird durch die Marke `Dry Run` ersetzt -- dieselbe Information, ohne Legende.

**Sichten statt Filter** (DESIGN): `alle`, `Aktionen`, `blockiert`,
`fehlgeschlagen`, je Faehigkeit. Es sind Links mit Abfrageparameter, keine
Bedienelemente -- ohne JavaScript ist jede Auswahl eine Adresse. Vorteil: eine
Sicht ist ein Lesezeichen.

**Einzelansicht eines Eintrags** (DESIGN, neu, PLANNED-nah): gegliedert nach den
acht Fragen aus SPEC-3 4.9, in genau deren Reihenfolge. Das ist die direkteste
Umsetzung von B10, die es gibt -- die Ueberschriften **sind** die acht Fragen.

## 28. Die fuenfzehn Control-Plane-Bereiche

**Grundlage: SPEC-3 12, unveraendert uebernommen. Statusspalte aus SPEC-3.**

| Bereich | SPEC-3-Stand | Wo im Design | Baubar? |
|---|---|---|---|
| System Status | CURRENT | Systemband + Kopfzahlen | ja, CURRENT |
| Stop Switch | CURRENT | Systemband | ja, CURRENT |
| Skills | CURRENT | Lage, Faehigkeitstabelle | ja, CURRENT |
| Autonomy | CURRENT | Spalte gewaehrt/verlangt | ja, CURRENT |
| Approvals | CURRENT | Ansicht Entscheidungen | ja, CURRENT |
| Pending Actions | CURRENT | dieselbe Ansicht | ja, CURRENT |
| Audit | CURRENT | Ansicht Protokoll | ja, CURRENT |
| Integrations | **fehlt** | Tafel *Dienste* + Unterseite mit Nachweisleiter | **nein** -- PLANNED |
| Model Status | **fehlt** | Tafel *Modelle* | **nein** -- PLANNED |
| Provider Status | **fehlt** | dieselbe Tafel, Rueckfallkette und Trennung | **nein** -- PLANNED |
| Errors | **fehlt** | Tafel *Fehler* + Sicht im Protokoll | **nein** -- PLANNED |
| Events | **fehlt** | -- kein Platz vorgesehen | **nein**; `Event` wird nirgends abgelegt (SPEC-3 8) |
| Memory | **fehlt** | Tafel *Gedaechtnis* + Unterseite | **nein** -- PLANNED |
| Tasks | **fehlt**, weil es keine gibt | -- kein Platz vorgesehen | **nein** -- Feature ist PLANNED |
| Automations | **fehlt**, weil es keine gibt | -- kein Platz vorgesehen | **nein** -- Feature ist PLANNED |

**DD-20 -- Fuer die letzten drei ist kein Platz vorgesehen, und das ist Absicht.**
Ein leerer Bereich "Aufgaben" waere genau das Fake-Feature, das SPEC-3 24
ausschliesst. Das Design zeigt in Teil IX, **wie** ein solcher Bereich spaeter
einpasst -- es haelt keinen Platz warm.

## 29. Regeln fuer komplexe Information

**DESIGN.**

**R1 -- Genau drei Tiefen.** Jeder Gegenstand erscheint in hoechstens drei
Formen: Zeile in einer Liste, Karte mit den wichtigsten Feldern, Vollansicht.
Mehr Tiefen heisst: man findet nichts wieder.

**R2 -- Die Zusammenfassung ist ein Satz, kein Stichwort.** "Antwort an Anna
Berger auf 'Angebot Rahmenvertrag'" statt "mail_send: Draft_a91f". Die Kennung
steht darunter, in Maschinenschrift.

**R3 -- Jede Zahl mit Bezug** (Teil IV, Abschnitt 21).

**R4 -- Herkunft steht neben dem Wert**, nicht in einer Fussnote. Bei Zielen ist
das Pflicht (B14), sonst SHOULD.

**R5 -- Nichts wird ausgeblendet, was eine Abweichung ist.** Aufklappbares
(`<details>`, ohne JavaScript moeglich) ist erlaubt fuer Belege und lange
Fremdtexte, **nicht** fuer Fehler, Blockaden oder Gatterurteile.

**R6 -- Eine Ansicht laedt sich vollstaendig oder gar nicht.** Kein Nachladen,
kein Teilzustand. Folgt aus B4.

---

# Teil VII -- Interaktion

## 30. Die drei Bedienwege und ihre Rollen

**CURRENT, geordnet. Die Aufteilung stammt aus dem Code, nicht aus diesem Dokument.**

| Weg | Rolle | Was er darf | Fundstelle |
|---|---|---|---|
| **Kommandozeile** | Der eigentliche Befehlsweg | alles: Durchlaeufe starten, Gedaechtnis, Konfiguration, Dienste pruefen | 17 Befehle, `cli.py` |
| **Dashboard** | Beobachten und entscheiden | vier Dinge: freigeben, verwerfen, anhalten, fortsetzen | `web/app.py` |
| **Sprache** | Beilaeufig fragen, notfalls anhalten | sechs Absichten: `status`, `briefing`, `offen`, `anhalten`, `handeln`, `unbekannt` | `voice/intents.py` |

**DD-21 -- Diese Aufteilung bleibt.** Das Dashboard bekommt **kein**
Eingabefeld, mit dem sich Durchlaeufe starten lassen. Begruendung ist nicht
Geschmack:

* `web/app.py` haelt es ausdruecklich fest: "Jede Schaltflaeche ist eine
  Angriffsflaeche, und eine Oberflaeche, die Modellaufrufe ausloesen kann, ist
  etwas anderes als eine, die nur bestaetigt."
* B3 verbietet einen zweiten Aktionsweg. Ein Befehlsfeld waere die groesste
  denkbare Ausweitung der Angriffsflaeche einer Seite, die per Formular von
  jedem offenen Browser-Tab erreichbar ist (siehe `web/security.py`).

Ein Textgespraech mit JARVIS im Dashboard ist damit **nicht** Teil dieses
Designs. Es steht in Teil X als offene Designfrage (ODS-3) mit den Bedingungen,
die es erfuellen muesste.

## 31. Sprachbedienung

**CURRENT, gestalterisch nur bestaetigt.**

Sprache hat keine eigene Oberflaeche und bekommt keine. Sie ist eine
Bedienweise, keine Faehigkeit (`build_skill("voice")` scheitert absichtlich).

**Was das Design festhaelt** (Grundlage B22, B23):

* Es gibt **keine** Sprachschaltflaeche im Dashboard. Ein Mikrofonknopf waere
  ein zweiter Weg in dieselbe Handlung, ohne Gewinn.
* Die Asymmetrie bleibt sichtbar: **anhalten per Sprache ja, fortsetzen nie.**
  Wo eine Oberflaeche die Sprachwege auflistet, steht das dabei -- nicht als
  Einschraenkung formuliert, sondern als Eigenschaft.
* Weckwort und Dauerschleife sind PLANNED (SPEC-3 19.5). Sie erscheinen in
  keiner Ansicht, auch nicht ausgegraut.
* Antworten sind kurz genug, um gesprochen zu werden -- was ohnehin dem
  Wortlautstil entspricht (Abschnitt 34).

## 32. Rueckmeldung waehrend einer Verarbeitung

**Hier ist das Design ehrlich statt hilfreich, und das ist Absicht.**

Was heute passiert (CURRENT, `app.py` `freigeben`): der POST laeuft
durch `execute_approval`, die Seite antwortet erst danach mit einer Umleitung.
Es gibt keinen Zwischenzustand -- weder im Code noch in der Datenbank.

**DD-22 -- Keine erfundene Fortschrittsanzeige.** Ein Balken oder ein "wird
ausgefuehrt..." wuerde einen Zustand behaupten, den das System nicht fuehrt
(B15: `EXECUTING` existiert nicht; SEC-2: es gibt nicht einmal einen atomaren
Anspruch). Er waere genau die Erfolgsmeldung, die staerker ist als der Nachweis
(B18).

**Was das Design stattdessen tut:**

| Fall | Gestaltung |
|---|---|
| Handlung laeuft | Die Seite kehrt zurueck, wenn entschieden ist. Der Knopf ist waehrenddessen die einzige Aktion auf der Seite (D7) |
| Handlung dauert | Die Rueckfrageseite sagt vorher, was passieren wird und dass es einen Moment dauern kann |
| Passive Aktualisierung | `meta refresh` mit `refresh_seconds` (CURRENT, konfigurierbar, Standard 0 = aus) |
| Ergebnis | Meldung aus der festen Tabelle, oben in der Zielansicht (CURRENT) |

**Was fehlt, und wo es hingehoert:** Eine ehrliche Fortschrittsanzeige braucht
`CLAIMED`/`EXECUTING`. Das ist OD-1 und SEC-2, also Roadmap-Punkte 1 und 4 --
nicht Gestaltung. Sobald diese Zustaende existieren, sind die zwei reservierten
Marken aus Abschnitt 17 dafuer vorgesehen.

## 33. Bestaetigung und sicherheitsrelevante Aktionen

Die Regeln stehen in Abschnitt 25 (K10). Ergaenzend drei Punkte:

**DD-23 -- Kein Doppelklick-Schutz durch Gestaltung.** Es waere naheliegend, den
Freigabeknopf nach dem Klick auszugrauen. Ohne JavaScript geht das nicht -- und
das ist gut so: SEC-2 ist eine **Serverluecke** (doppelte Freigabe erzeugt
doppelte Wirkung, gemessen). Ein Schutz in der Anzeige haette sie kaschiert,
ohne sie zu schliessen. Die Oberflaeche darf das nicht.

**DD-24 -- Die Rueckfrage nennt die Wirkung, nicht die Aktion.** Nicht "Vorgang
41 freigeben?", sondern "Eine E-Mail geht an anna.berger@example.com. Danach
laesst sie sich nicht zurueckholen." Grundlage: B18.

**DD-25 -- Umleitung nach jeder veraendernden Anfrage bleibt** (CURRENT). Ein
Neuladen darf keine Freigabe wiederholen. Das ist heute so umgesetzt und ist
gestalterisch relevant, weil daraus die Meldung-per-Code folgt.

## 34. Wortlaut

**DESIGN, Grundlage B18 -- und damit die einzige Sprachregel mit MUST-Bezug.**

| Regel | Beispiel gut | Beispiel schlecht |
|---|---|---|
| Sagen, was ist, nicht was gelungen ist | "Gesendet an anna.berger@example.com" | "Erfolgreich versendet!" |
| Nachweisstufe nicht ueberschreiten | "built, tested, mocked -- live: nie" | "Gmail verbunden" |
| Fehler nennt Ursache, Stand und Weg | "Gmail war nicht erreichbar. Der Vorgang bleibt offen und ist unveraendert." | "Ein Fehler ist aufgetreten." |
| Kein Ausrufezeichen, keine Emojis, keine Beteuerung | "Verworfen. Es ist nichts geschehen." | "Kein Problem, alles erledigt!" |
| Zahlen mit Bezug | "10/10 am Tag erreicht" | "Limit erreicht" |
| Der Nutzer wird nicht gelobt | "Freigegeben und ausgefuehrt." | "Gute Wahl!" |
| Zustaende heissen wie im Code | "Schattenbetrieb" | "Sicherer Modus" |

Die heutigen Wortlaute in `MELDUNGEN` (`app.py`) erfuellen das bereits und
werden unveraendert uebernommen. Sie sind der Massstab, nicht der Entwurf.

**Zu Persoenlichkeit.** SPEC-1 §7 formuliert es treffend und die Sache gilt
weiter, auch wenn das Dokument historisch ist: Persoenlichkeit entsteht durch
Wortwahl und Reaktionszeit, nicht durch Grafik. Das Design fuegt dem nichts
hinzu -- kein Begruessungstext, keine Sprechblase, keine Ansprache.

---

# Teil VIII -- Groessenverhalten und macOS

## 35. Was SPEC-3 ueber die Plattform sagt -- und was nicht

**Wichtig, damit hier nichts erfunden wird:**

* SPEC-3 14 fuehrt macOS als **Zielplattform**, aber `PLATFORM VERIFIED = NO,
  ausnahmslos`. Nichts ist je auf macOS gelaufen (B17).
* SPEC-3 kennt **keine native macOS-Anwendung**. Das Dashboard ist eine
  Browser-Seite auf Loopback (4.6). Eine Fensteranwendung, ein Menuleisten-Symbol
  oder ein Dock-Eintrag steht in **keiner** Zeile von SPEC-3.
* SPEC-3 25 (Retained) haelt fest: lokal, ohne Anmeldung, ohne Nutzerverwaltung,
  ohne Build-Schritt.

**Folge:** "macOS-orientiertes Verhalten" heisst in diesem Design *Safari und
das macOS-Fensterverhalten gut bedienen*, nicht *eine Mac-App entwerfen*. Alles
zu einer nativen Huelle steht als IDEA in Abschnitt 38 und ist ausdruecklich
nicht Teil des Vorschlags.

## 36. Fenster und Groessenstufen

**DESIGN.** Drei Stufen. Ohne JavaScript gibt es keine Umschaltung -- also muss
jede Stufe fuer sich vollstaendig sein, nicht eine gekuerzte Fassung der
naechstgroesseren.

| Stufe | Breite | Verhalten |
|---|---|---|
| **Weit** | > 70rem (ca. 1120px) | Tafelbreite fuer Tabellen, Bereichstafeln zweispaltig |
| **Standard** | 46-70rem | Eine Spalte, Tabellen vollstaendig, Naht nebeneinander bis 46rem |
| **Schmal** | < 46rem (ca. 736px) | Tabellen werden zu Bloecken (`data-kopf` vor jedem Wert), Naht untereinander, Faktenlisten einspaltig |

**Zielgroessen** (DESIGN):

* Voreingestelltes Fenster: **1100 x 760**. Passt auf ein 13-Zoll-MacBook ohne
  Vollbild und zeigt die Lage-Ansicht vollstaendig.
* Kleinste sinnvolle Breite: **380px**. Ein schmales Fenster am Bildschirmrand,
  in dem Systemband, offene Entscheidungen und Stoppschalter lesbar bleiben.
  Das ist der Fall, den die Stufe *Schmal* wirklich bedienen muss -- nicht ein
  Telefon; das Dashboard bindet an Loopback und ist von aussen nicht erreichbar.
* Ab 96rem waechst nur der Rand, nicht die Zeilenlaenge.

## 37. macOS-Eigenheiten, die das Design beruecksichtigt

| Eigenheit | Umgang | Grundlage |
|---|---|---|
| Systemschrift SF Pro / SF Mono | Erste Position in beiden Schriftketten | Abschnitt 9 |
| Hell/Dunkel-Umschaltung des Systems | `prefers-color-scheme`, kein eigener Umschalter | DD-11 |
| `prefers-reduced-motion` | beruecksichtigt; es gibt ohnehin keine Bewegung | Abschnitt 15 |
| Ueberlagernde Rollbalken | Kein fester Platz fuer Rollbalken eingeplant, keine eigenen Rollbalken | -- |
| Cmd-F | Ohne JavaScript ist alles im Dokument -- die Browsersuche findet den ganzen Inhalt | folgt aus B4 |
| Cmd-P | Eigene Druckfassung: Bedienelemente verschwinden, Farbe wird Linie. Ein Protokollauszug soll sich als Beleg ablegen lassen | DESIGN |
| Tastaturbedienung, Vollzugriff | Sichtbarer Fokusring in Akzentfarbe, sinnvolle Tabfolge durch die reine Dokumentstruktur | DESIGN |
| Zoom bis 200% | Alle Groessen in `rem`, Umbruchstufen in `rem` -- Zoom verhaelt sich wie ein schmaleres Fenster | DESIGN |

**DD-26 -- Bedienbarkeit ist Teil der Sicherheitsanforderung, nicht Kuer.**
Der Stoppschalter muss ohne Maus, ohne Farbe und bei 200% Zoom erreichbar sein.
Er ist das erste Element im Dokument (nicht nur optisch oben), also auch das
erste im Tabfluss.

## 38. Native Huelle -- IDEA, nicht Teil des Vorschlags

Eine Menuleisten-Anwendung (Zustand, offene Entscheidungen, Stoppschalter),
eine Fensteranwendung um dieselbe Seite, ein Dock-Eintrag: alles denkbar,
**nichts davon steht in SPEC-3**. Wuerde es kommen, gaelten drei Bedingungen
aus dem Bestand:

1. Sie duerfte keinen zweiten Aktionsweg schaffen (B3) -- also dieselbe Seite
   zeigen, nicht eigene Knoepfe bauen.
2. Der Stoppschalter muesste auch dort auf jeder Ansicht liegen (B5).
3. Sie waere eine neue Abhaengigkeit und braeuchte eine Begruendung (SPEC-3 22).

Aufgefuehrt ist das hier nur, damit ein spaeterer Vorschlag nicht bei null
anfaengt -- nicht als Empfehlung.

---

# Teil IX -- Zukunftsfaehigkeit

## 39. Wie das Design mit kuenftigen Faehigkeiten umgeht

**Der Grundsatz, und er ist aus SPEC-3 19.4 uebernommen:** Bei jeder
Gestaltungsentscheidung wird gefragt, ob sie eine geplante Faehigkeit
blockiert. Wenn ja, wird die Entscheidung geaendert -- **nicht** die Faehigkeit
vorgezogen.

Das Design haelt dafuer drei Steckplaetze bereit. Ein Steckplatz ist eine
**Regel, wie etwas spaeter einpasst**, kein leerer Platz in der Oberflaeche.

| Steckplatz | Regel | Wer passt hinein |
|---|---|---|
| **S1 -- Faehigkeitszeile** | Jede Faehigkeit ist eine Zeile in der Lage-Tabelle: Name, gewaehrt/verlangt, erreicht Dritte, aktiv, Kontingent, letzter Lauf. Keine Spalte ist mailspezifisch | Tasks, Documents, Files, Home Automation |
| **S2 -- Vorgangskarte** | Jeder freigabepflichtige Vorgang ist eine Karte mit Kopf, Satz, Naht, Gatter, Handlung. Die Naht traegt beliebige Zielarten, weil sie nur zwischen *Modell* und *Code* trennt | Dateipfade, Geraetebefehle, Aufgabenaenderungen |
| **S3 -- Bereichstafel** | Ein neuer Nachschlagebereich ist eine Tafel auf Lage mit zwei bis vier Zahlen und einem Weg in die Tiefe. Die Navigation waechst nicht (DD-19) | Dienste, Modelle, Gedaechtnis, Fehler, spaeter Aufgaben |

## 40. Kompatibilitaetspruefung je PLANNED-Faehigkeit

Aufgebaut wie SPEC-3 19.4. **Spalte "Blockiert das Design?" ist die eigentliche
Aussage.** Nichts davon ist ein Bauauftrag.

| Faehigkeit (SPEC-3) | Blockiert das Design? | Wo sie einpasst | Was das Design **jetzt** nicht tut |
|---|---|---|---|
| **Tasks** (19.5, PLANNED) | nein | S1 als Faehigkeitszeile, S3 als Tafel, Aufgaben im Briefing als weiterer Absatz | Kein Bereich "Aufgaben", kein Zaehler, kein leerer Platz |
| **Documents** (19.5, PLANNED) | nein | S2: ein Dokument ist Fremdtext und steht links in der Naht, das Ergebnis rechts. Die Zitatform fuer Fremdtext ist bereits da | Kein Ablagefeld, keine Vorschau, kein Dokumentbereich |
| **Files** (19.5, PLANNED) | nein | S2: ein Pfad ist ein Ziel und steht rechts, mit Herkunft. Die Rueckfrageseite traegt "verlaesst den Rechner" bereits | Keine Pfadanzeige, kein Dateibaum |
| **Voice-Komfort** (19.5, PLANNED) | nein | Keine Oberflaeche noetig -- Sprache bleibt ohne Bildschirm | Kein Mikrofonknopf, keine Weckwortanzeige |
| **Home Automation** (19.5, PLANNED) | **teilweise -- Befund** | S1/S2 tragen sie. Aber: eine Geraeteadresse ist eine andere Zielart als eine E-Mail-Adresse, und die Vorgangskarte hat heute eine feste Zielreihenfolge (`render.BEKANNTE_ZIELE`) | Empfehlung: die Zielliste bleibt datengetrieben und wird **nicht** um Geraetefelder erweitert, bevor SPEC-3 19.4 den Zielarten-Punkt loest. Kein Geraetebereich |
| **Proactive Agent** (19.5, PLANNED) | **teilweise -- Befund** | Eine Meldung braucht einen Ort. Naheliegend waere ein Bereich "Meldungen" -- der aber leicht zu einem zweiten Handlungsweg wird (B24) | Empfehlung: Meldungen erscheinen als Abweichungszeile auf *Lage* (Punkt 2), **ohne** eigene Handlung. Jede Handlung daraus fuehrt zur Vorgangskarte. Nicht jetzt bauen |
| **Always-On / Daemon** (19.5, PLANNED) | nein | "Letzter Lauf" je Faehigkeit ist bereits vorgesehen; ein Gesundheitszustand waere eine weitere Kopfzahl | Keine Ueberwachungsansicht, kein Gesundheitsendpunkt |
| **Weitere Anbieter** (20, PLANNED) | nein | Tafel *Modelle* listet Ketten, nicht feste Anbieter | Keine Anbieterlogos (waeren ohnehin Bilddateien, B4) |
| **Kostenbasiertes Routing** (20, PLANNED) | nein | Eine weitere Zeile in der Modelltafel | Keine Kostenanzeige, keine Waehrung |
| Smartphone, Telefon, Social Media, Trading (20, IDEA) | -- | -- | Nichts. IDEA bleibt IDEA |

**Zwei Befunde, kein Auftrag** -- so wie SPEC-3 19.4 es handhabt. Beide sind in
Abschnitt 43 als offene Designfragen verzeichnet.

## 41. Was das Design bewusst nicht vorwegnimmt

| Punkt | Warum nicht |
|---|---|
| Zustandsnamen fuer `CLAIMED` / `EXECUTING` | OD-1 ist offen. Das Design haelt zwei Marken frei, benennt sie aber nicht verbindlich |
| Darstellung eines Vertrauensgrads im Gedaechtnis | OD-2 ist offen. Die Spalte existiert im Entwurf, ihr Wertebereich nicht |
| Klassifikation je Inhalt (vertraulich/nicht) | OD-3 ist offen |
| Ob das Dashboard ueberhaupt Control Plane wird | OD-4 ist offen. Dieses Dokument ist Vorschlag, nicht Entscheidung |
| Anzeige einer Netzbegrenzung des Modellprozesses | OD-5 ist offen |
| Ein Bereich fuer Ereignisse | `Event` wird nirgends abgelegt (SPEC-3 8). Es gibt nichts anzuzeigen |
| Eine Allowlist-Sprosse in der Gatterleiter | SEC-1 ist offen. Sie kommt, wenn die Pruefung kommt -- nicht davor |
| Mehrbenutzerbetrieb, Rollen, Anmeldung | SPEC-3 25 Retained: ohne Anmeldung, ohne Nutzerverwaltung |
| Mobile Bedienung | Loopback-Bindung. Es gibt keinen Zugang von aussen, und das soll so bleiben |

---

# Teil X -- Register

## 42. Design Decisions

Vollstaendige Liste. Spalte *Grundlage* verweist auf Abschnitt 1 (B-Nummern)
oder direkt auf SPEC-3. Spalte *Art* trennt, was aus einer Vorgabe folgt, von
dem, was freie Wahl ist.

| # | Entscheidung | Grundlage | Art | Abschnitt |
|---|---|---|---|---|
| **DD-01** | Instrumententafel aus Flaeche, Linie, Schrift; keine Schatten, Verlaeufe, Illustrationen | B4, D8 | folgt aus der Randbedingung | 7 |
| **DD-02** | Farbfamilie aus `style.py` fortgefuehrt, aber zu Rollen geordnet; Text und Linien leicht angehoben | OD-4 ("Angleichung jetzt waere Aufwand ohne Funktionsgewinn") | freie Wahl, sparsam | 8 |
| **DD-03** | Zwei Spurbreiten: 60rem fuer Prosa, 96rem fuer dichte Tabellen | B10 (acht Fragen brauchen Platz) | freie Wahl | 11 |
| **DD-04** | Radius 0; Linienart traegt Bedeutung (durchgezogen/gepunktet/gestrichelt/schraffiert) | B14, B9 | freie Wahl mit Zweck | 10 |
| **DD-05** | Erfolg traegt keine Farbe | B9 | folgt aus der Vorgabe | 8 |
| **DD-06** | Ein Akzent, zwei Funktionssignale, kein Erfolgsgruen | B9 gegen SPEC-1 §7 (HISTORICAL) | begruendete Abweichung | 8 |
| **DD-07** | Farbe nie allein; immer Wort plus Form | B9 | folgt aus der Vorgabe | 8 |
| **DD-08** | Maschinenschrift fuer Gerechnetes, Satzschrift fuer Gelesenes | B14, B13 | freie Wahl mit Zweck | 9 |
| **DD-09** | Ausschliesslich Systemschriften, keine Webfonts | B4 (`default-src 'none'`), SPEC-3 27 | folgt aus der Randbedingung | 9 |
| **DD-10** | 4px-Raster, acht Abstandswerte, mehr nicht | -- | freie Wahl | 11 |
| **DD-11** | Helle Fassung ueber `prefers-color-scheme`, **kein** Umschalter | B4 (kein JavaScript), keine neue Funktion erfinden | folgt aus der Randbedingung | 14 |
| **DD-12** | Keine Bewegung, keine Uebergaenge | B18 | folgt aus der Vorgabe | 15 |
| **DD-13** | Kein Symbol ohne Wort; Symbole nur als Inline-SVG | B4, B9, B18 | folgt aus der Randbedingung | 13 |
| **DD-14** | `Unverified`, `Offline`, `Cancelled` erscheinen **nicht** in der Oberflaeche | B15, B18, B21 | folgt aus der Vorgabe | 17 |
| **DD-15** | Fehlender Nachweis steht als Wort `nie`, mit Warnfarbe | B17, B18 | folgt aus der Vorgabe | 18 |
| **DD-16** | Autonomie immer als gewaehrt / verlangt | B8, SPEC-3 6.1 (Research-Fehler) | folgt aus der Vorgabe | 19 |
| **DD-17** | Die Gatterleiter zeigt nur Pruefungen, die der Code wirklich durchlaeuft -- heute **keine** Allowlist-Sprosse | SEC-1 (offen), B18 | folgt aus dem Befund | 20 |
| **DD-18** | Anhalten ohne Rueckfrage, Fortsetzen mit Rueckfrage | B5, B7, SPEC-3 19.5 (Sprachasymmetrie) | folgt aus der Vorgabe | 22 |
| **DD-19** | Die Navigation bleibt bei vier Punkten; Lage ist der Verteiler | SPEC-3 12 (8 von 15 fehlen) | freie Wahl mit Begruendung | 26 |
| **DD-20** | Kein Platz fuer Tasks, Automations, Events | B21, SPEC-3 8, 24 | folgt aus der Vorgabe | 28 |
| **DD-21** | Kein Befehls- oder Eingabefeld im Dashboard | B3, `web/app.py`, `web/security.py` | folgt aus der Vorgabe | 30 |
| **DD-22** | Keine Fortschrittsanzeige waehrend einer Ausfuehrung | B15, B18, SEC-2, OD-1 | folgt aus der Luecke | 32 |
| **DD-23** | Kein Doppelklick-Schutz in der Anzeige | SEC-2 ist eine Serverluecke | folgt aus dem Befund | 33 |
| **DD-24** | Die Rueckfrage nennt die Wirkung, nicht die Aktion | B18 | folgt aus der Vorgabe | 33 |
| **DD-25** | Umleitung nach jeder veraendernden Anfrage bleibt | CURRENT, `app.py` | Bestand bestaetigt | 33 |
| **DD-26** | Stoppschalter erstes Element im Dokument, ohne Maus und ohne Farbe erreichbar | B5 | folgt aus der Vorgabe | 37 |
| **DD-27** | ~~Die Vertrauensnaht ist das Signaturelement~~ **ZURUECKGEZOGEN 2026-08-31.** SPEC-3 25 fuehrt den Entscheidungsstrom als Bauplan; die Zweiteilung ist entfernt. Die Vorgangskarte zeigt eine gemeinsame Faktenliste | SPEC-3 25 | zurueckgebaut, siehe 51 | 23 |
| **DD-28** | Systemband mit vier Tatsachen: Betrieb, Trockenlauf, Dienste, Zugangsdaten; Dateirechte gehoeren auf die Lage-Ansicht | B5, B17, B19, SPEC-3 12 | folgt aus der Vorgabe | 22 |
| **DD-29** | Aktionszustand und Nachweisstand sind getrennte Achsen an getrennten Orten | B15, B16 | folgt aus der Vorgabe | 16 |
| **DD-30** | Wortlaut nennt Tatsachen, nie Erfolge; Zustaende heissen wie im Code | B18 | folgt aus der Vorgabe | 34 |
| **DD-31** | Der unsichere Zustand ist der auffaellige (`Trockenlauf AUS`, `Mock`) | B17, B19, `cli.py` | freie Wahl mit Begruendung | 8, D5 |
| **DD-32** | Drei Groessenstufen, jede fuer sich vollstaendig; Zielfenster 1100x760, kleinste Breite 380px | B4 | freie Wahl | 36 |
| **DD-33** | Kein `style`-Attribut. Dynamische Werte werden auf Stufenklassen gerundet (Fuellstand in Fuenferschritten) | B4 (`style-src 'self'`) | folgt aus der Randbedingung | 6 |

**Zweiundzwanzig der dreiunddreissig folgen aus einer SPEC-3-Vorgabe oder einer
Randbedingung.** Das ist der Punkt: das Design ist zu einem grossen Teil nicht
frei -- es macht sichtbar, was der Kern ohnehin verlangt.

## 43. CURRENT vs REQUIRED vs PLANNED vs DESIGN -- Uebersicht

Damit auf einen Blick klar ist, was heute existiert, was SPEC-3 fordert, was
SPEC-3 fuer spaeter beschreibt, und was dieses Dokument beisteuert.

| Gegenstand | CURRENT | REQUIRED (SPEC-3 21) | PLANNED (SPEC-3) | DESIGN (dieses Dokument) |
|---|---|---|---|---|
| Vier Ansichten | ja | -- | -- | umbenannt: Zustand -> Lage |
| Stoppschalter auf jeder Ansicht | ja | -- | -- | faerbt das ganze Band |
| Trockenlauf-Hinweis | ja | -- | -- | als Tatsache ins Systemband |
| Faehigkeitstabelle | ja, mit gewaehrter Stufe | -- | -- | zusaetzlich verlangte Stufe, letzter Lauf |
| Freigeben / Verwerfen | ja | -- | -- | Rueckfrageseite davor |
| Protokollliste | ja | -- | -- | Zustandsmarken, Sichten als Links |
| Protokoll-Einzelansicht | **nein** | -- | Teil von 12 (PLANNED) | Gliederung nach den acht Fragen (4.9) |
| Vertrauensnaht | **nein** | -- | 25, Future-only | zurueckgebaut, siehe 51 |
| Gatterleiter | **nein** | -- | -- | K5, macht 4.2 sichtbar |
| Nachweisleiter / Dienste | **nein** (nur CLI) | -- | 12: "Integrations fehlt" | K3, Entwurf `06-dienste.html` |
| Modelle / Anbieter | **nein** (nur CLI) | -- | 12: "fehlt" | Tafel auf Lage |
| Gedaechtnis | **nein** (nur CLI) | -- | 12: "fehlt" | Tafel + Entwurf `07-gedaechtnis.html` |
| Fehleransicht | **nein** | -- | 12: "fehlt" | Tafel + Protokollsicht |
| Aufgaben, Automationen, Ereignisse | **nein** | -- | 12, 19.5; Feature fehlt | **kein Platz vorgesehen** (DD-20) |
| Allowlist-Sprosse im Gatter | **nein** | SEC-1 schliessen (Roadmap 1) | -- | kommt erst mit SEC-1 (DD-17) |
| `CLAIMED` / `EXECUTING` | **nein** | SEC-2, Execution Layer (Roadmap 1, 4) | -- | zwei Marken reserviert, nicht benannt |
| Live-Nachweis der Dienste | **nein** (`nie`) | erste echte Verbindung (Roadmap 2) | -- | Anzeige `live: nie` mit Warnfarbe |
| macOS-Verifikation | **nein** | Roadmap 3 | -- | Plattformverhalten entworfen, nichts behauptet |

## 44. Offene Designentscheidungen

Bewusst nicht entschieden. Jede braucht entweder den Nutzer oder eine
SPEC-3-Entscheidung.

### ODS-1 -- Wird das Dashboard ueberhaupt angeglichen?  [ENTSCHIEDEN]

```
Frage:     Wird die vorhandene Oberflaeche auf dieses Design umgestellt, und
           wann?
Bezug:     SPEC-3 OD-4, Roadmap 6 (PLANNED)
Optionen:  A  gar nicht -- die heutige Fassung bleibt verbindlich
           B  nur die Teile, die neue Information bringen (verlangte Stufe,
              Zustandsmarken, Gatterleiter, Naht) -- ohne neue Bereiche
           C  vollstaendig, zusammen mit dem Ausbau zur Control Plane
Entscheidung: B, vom Nutzer am 2026-08-31. Umgesetzt.
Status:    ENTSCHIEDEN und umgesetzt -- siehe Abschnitt 48
```

### ODS-2 -- Wie werden Meldungen einer kuenftigen Proaktivitaet dargestellt?

```
Frage:     Wo erscheint eine Meldung, ohne ein zweiter Handlungsweg zu werden?
Bezug:     SPEC-3 19.5 Proactive Agent (B24), 19.4
Vorschlag: Als Abweichungszeile auf Lage, ohne eigene Handlung. Jede Handlung
           daraus fuehrt zur Vorgangskarte und damit durch execute_approval.
Status:    OFFEN, und ausdruecklich kein Bauauftrag. Die Faehigkeit ist PLANNED
```

### ODS-3 -- Gibt es je eine Texteingabe im Dashboard?

```
Frage:     Soll das Dashboard eine Eingabe bekommen, mit der sich JARVIS
           ansprechen laesst?
Bezug:     B3, web/app.py, web/security.py
Bedingungen, die erfuellt sein muessten:
           1. Kein neuer Aktionsweg -- die Eingabe darf hoechstens dieselben
              Faehigkeiten anstossen, die die CLI anstoesst, durch dasselbe Gatter
           2. Der Eingabetext ist Fremdtext und geht durch sanitize()
           3. Kein Ziel darf aus der Eingabe stammen (P1)
           4. Die Angriffsflaeche gegenueber einem fremden Browser-Tab muss
              gleich bleiben -- Token und Origin-Pruefung reichen dafuer heute
              fuer Formulare, aber die Folgen einer Modellaufruf-ausloesenden
              Route sind nicht bewertet
Empfehlung: Nein, solange SPEC-3 das Dashboard als bestaetigende Oberflaeche
           fuehrt. Die Kommandozeile ist der Befehlsweg.
Status:    OFFEN
```

### ODS-4 -- Wie werden Zielarten jenseits von E-Mail dargestellt?

```
Frage:     Eine Geraeteadresse oder ein Dateipfad ist ein Ziel anderer Art.
           Bleibt die feste Zielreihenfolge (render.BEKANNTE_ZIELE)?
Bezug:     SPEC-3 19.4 ("es gibt kein Modell fuer Zielarten"), 19.5 Files,
           Home Automation
Vorschlag: Zielliste datengetrieben halten und **nicht** um Geraete- oder
           Pfadfelder erweitern, bevor SPEC-3 den Zielarten-Punkt loest.
Status:    OFFEN -- haengt an einer Architekturentscheidung, nicht an Gestaltung
```

### ODS-5 -- Druckfassung: Beleg oder Nebensache?

```
Frage:     Soll ein Protokollauszug als ablegbarer Beleg gestaltet sein
           (Kette, Pruefsumme, Zeitraum im Kopf)?
Bezug:     SPEC-3 4.9, 3.2 P4
Vorschlag: Ja, aber klein: eine Druckfassung im Stylesheet, kein eigener Weg,
           keine Ausgabefunktion.
Status:    OFFEN, niedrige Dringlichkeit
```

### ODS-6 -- Bleibt die helle Fassung im Umfang?

```
Frage:     Wird die helle Fassung mitgebaut oder erst spaeter?
Bezug:     Abschnitt 14 (SHOULD, nicht MUST)
Vorschlag: Mitbauen -- sie kostet einen Medienblock mit elf Werten. Wenn
           gekuerzt werden muss, faellt sie zuerst.
Status:    OFFEN
```

## 45. Bewusst nicht festgelegt

Damit spaetere Sitzungen nicht in eine dieser Luecken hineininterpretieren:

* **Kein Logo, keine Wortmarke ausser dem Schriftzug "JARVIS"** in
  Maschinenschrift. Eine Bilddatei ist ohnehin ausgeschlossen (B4).
* **Keine Namen fuer Zustaende, die es nicht gibt** (OD-1).
* **Kein Wertebereich fuer eine Herkunftsklasse** im Gedaechtnis (OD-2).
* **Keine Aussage zur Reihenfolge der Umsetzung** -- die Roadmap steht in
  SPEC-3 21 und wird von diesem Dokument nicht angetastet.
* **Keine Zahl fuer `refresh_seconds`.** Das ist Konfiguration, keine
  Gestaltung; Standard ist heute 0.
* **Keine Vorgabe zur Datenbank, zum Webserver, zur Bibliothek.** SPEC-3 27
  haelt fest, wo solche Dinge hingehoeren, und das ist nicht hier.
* **Keine Zusage zu Barrierefreiheitsstufen** (etwa WCAG-Konformitaet). Das
  Design nennt konkrete Eigenschaften -- Kontrast, Fokus, Farbe-nie-allein,
  Zoom -- aber verspricht keine Zertifizierung, die niemand geprueft hat (B18).

## 46. Naechste Schritte fuer eine spaetere Umsetzung

**Kein Auftrag.** Eine Reihenfolge, falls und wenn umgesetzt wird. Die
SPEC-3-Roadmap hat Vorrang: die fuenf REQUIRED-Punkte stehen vor jeder
Gestaltungsarbeit, und Roadmap 6 (Control Plane) ist PLANNED.

**Stufe 0 -- Entscheidung, kostet keinen Code**

1. ODS-1 beantworten. Ohne diese Antwort ist alles Weitere unbestimmt.
2. Falls B oder C: SPEC-3 OD-4 entsprechend fortschreiben -- **durch den
   Nutzer**, im Rahmen von Abschnitt 27 Change Management.

**Stufe 1 -- Informationsgewinn ohne neue Bereiche** *(setzt ODS-1 = B oder C voraus)*

3. Verlangte Stufe in die Faehigkeitstabelle aufnehmen (DD-16). Einzige
   Aenderung mit echtem Sicherheitswert: sie macht den Research-Fehlertyp
   sichtbar.
4. Zustandsmarken im Protokoll statt der `T`-Spalte (DD-14, DD-07).
5. Systemband um Trockenlauf und Dienstemodus erweitern (DD-28, DD-31).
6. Rueckfrageseite vor Freigaben, die Dritte erreichen (K10, DD-24).
   **Erst sinnvoll, wenn `dry_run = false` je vorkommt** -- also nach
   Roadmap-Punkt 2.
7. Tokens und Bausteine aus `prototyp/jarvis-prototyp.css` in
   `jarvis/interfaces/web/style.py` uebernehmen; Struktur von `render.py`
   bleibt unveraendert.

**Stufe 2 -- Sichtbarkeit der Kette** *(unabhaengig von neuen Bereichen)*

8. ~~Vertrauensnaht in der Vorgangskarte~~ **entfaellt** (Abschnitt 51). Der Hinweis bleibt
   stehen, weil er die Datenlage richtig beschreibt:
   `fields` und `targets` liegen getrennt in `approvals` vor.
9. Gatterleiter in der Vorgangskarte (K5). Braucht `granted_level`,
   `required_level` und `reason` -- alles bereits im Protokolldetail.
10. Protokoll-Einzelansicht nach den acht Fragen (B10). Neue Route, dieselbe
    Schutzregel wie alle anderen -- und **TD-1 beachten**: der Schutz ist heute
    ein Dekorator, eine neue Route ohne ihn waere still offen.

**Stufe 3 -- neue Bereiche** *(erst nach Roadmap 6, also PLANNED)*

11. Dienste, Modelle, Gedaechtnis, Fehler als Tafeln und Unterseiten.
12. Fuer Gedaechtnis: OD-2 muss vorher entschieden sein, sonst zeigt die Spalte
    *Herkunft* eine Klasse, die es nicht gibt.

**Querschnitt, unabhaengig von der Stufe**

13. Jede neue Route braucht einen Test, dass sie geschuetzt ist (TD-1, SPEC-3 13
    "Bekannte Testluecken").
14. Jede neue Anzeige eines Fremdwerts geht durch `esc` (`render.py`).
15. Keine neue Abhaengigkeit, kein Build-Schritt (B20, SPEC-3 22).
16. Kein `style`-Attribut in einer neuen Ansicht (DD-33). Es wuerde ohne
    sichtbaren Fehler wirkungslos bleiben -- die Richtlinie verwirft es still.
    Beim Erstellen der Entwuerfe ist genau dieser Fehler passiert und wurde
    beim Gegenlesen behoben.

## 47. Selbstpruefung dieses Dokuments

Gegen die Regeln des Auftrags und gegen SPEC-3.

| Pruefung | Ergebnis |
|---|---|
| Wurde SPEC-3 vollstaendig gelesen? | ja -- 1958 Zeilen, alle 28 Abschnitte plus Anhang A und B |
| Wird SPEC-3 veraendert? | nein. `JARVIS-SPEC-3.md` ist unveraendert |
| Wird Produktionscode veraendert? | nein. `jarvis/` ist unveraendert; alles Neue liegt unter `design/` |
| Werden CURRENT, REQUIRED, PLANNED, DESIGN, IDEA getrennt? | ja -- jede Aussage traegt eine Marke, Abschnitt 43 stellt sie gegenueber |
| Werden PLANNED-Faehigkeiten als vorhanden dargestellt? | nein. Entwuerfe fuer PLANNED-Bereiche tragen die Marke im Blatt |
| Werden SPEC-3-Luecken durch Design "repariert"? | nein -- Abschnitt 3 zaehlt elf Luecken auf und sagt zu jeder, was das Design **nicht** tut |
| Wird eine Produktanforderung erfunden? | nein. Zwei Stellen, an denen es naheliegend waere (Texteingabe, Meldungen), stehen als ODS-3 und ODS-2 offen |
| Ignoriert das Design eine SPEC-3-Vorgabe? | nein. Abschnitt 1 listet 25 Vorgaben; jede ist in Teil III-VIII umgesetzt oder ausdruecklich unberuehrt |
| Wird eine Architekturentscheidung eingeschraenkt? | nein. OD-1 bis OD-5 bleiben offen; Abschnitt 41 zaehlt auf, was bewusst nicht vorweggenommen wird |
| Ist eine Aussage staerker als ihr Nachweis? | geprueft. Nichts wird als macOS-erprobt bezeichnet; die Entwuerfe sind gegen keinen Browser getestet, sondern von Hand geschrieben -- siehe Einschraenkung unten |
| Bleibt bestehende Funktionalitaet unberuehrt? | ja. Kein Produktionscode angefasst; Tests unveraendert |

**Einschraenkung, die zu diesem Dokument gehoert.** Die Entwuerfe im Ordner
`prototyp/` sind von Hand geschriebenes HTML und CSS. Sie sind **in keinem
Browser dargestellt worden** -- die Umgebung dieser Sitzung ist Linux ohne
Bildschirm, und Safari auf macOS gab es hier nie. Der gleiche Satz gilt fuer
das Design, den SPEC-3 fuer den Code festhaelt: gebaut ist nicht geprueft.
Wer die Blaetter oeffnet, sollte mit kleinen Abweichungen rechnen, besonders
bei der hellen Fassung und im schmalen Fenster.

---

## Anhang -- Abdeckung des Designauftrags

| Auftragspunkt | Wo im Dokument |
|---|---|
| 1 Visuelle Identitaet: Aesthetik, Farbe, Typografie, Formen, Abstaende, Hierarchie, Icons, Status, Hell/Dunkel | Teil III (7-15), Teil IV (16-21) |
| 2 Hauptoberflaeche: Navigation, Dashboard, Status, Ausfuehrungen, Skills, Memory, Integrationen, Systeminformationen | Teil VI (26-29), Entwuerfe 01, 06, 07 |
| 3 Interaktion: Text/Sprache, Rueckmeldung, Zustaende, Bestaetigungen | Teil VII (30-34), Teil IV (17), Entwuerfe 02, 02b, 08, 09 |
| 4 Informationsarchitektur: was wo, primaer/sekundaer, Komplexitaet, Zukunft | Teil VI (26-29), Teil IX (39-41) |
| 5 Responsive / macOS | Teil VIII (35-38) |
| 6 Zukunftsfaehigkeit ohne Vorwegnahme | Teil IX, DD-20, Abschnitt 41 |
| Design Decisions | Abschnitt 42 |
| SPEC-3-Basis je Entscheidung | Abschnitt 1 (B1-B25) und Spalte *Grundlage* in 42 |
| CURRENT vs REQUIRED vs FUTURE | Abschnitt 43 |
| Offene Designentscheidungen | Abschnitt 44 |
| Bewusst nicht festgelegt | Abschnitt 45 |
| Naechste Schritte | Abschnitt 46 |


---

## 48. Umgesetzt am 2026-08-31 (ODS-1, Weg B)

Was aus diesem Dokument in `jarvis/interfaces/web/` und `jarvis/core/gate.py`
eingegangen ist. **CURRENT**, mit Tests belegt.

| Element | Stand | Wo | Tests |
|---|---|---|---|
| Marken und Bausteine (DD-01 bis DD-13, DD-31) | umgesetzt | `web/style.py` | Stylesheet wird ausgeliefert |
| Systemband mit vier Tatsachen (DD-28, DD-31) | umgesetzt | `render.seite` | Trockenlauf ruhig/auffaellig, Mock benannt, angehaltenes Band |
| Stufe gewaehrt / verlangt (DD-16) | umgesetzt | `render.stufe`, `app.lage` | verlangte Stufe sichtbar, `voice` ohne verlangte Stufe |
| Zustandsmarken im Protokoll (DD-14, DD-07) | umgesetzt | `render.zustandsmarke` | Marke nur fuer Zustaende, nicht fuer vorgeschlagene Aktionen |
| Gatterleiter (K5, DD-17) | umgesetzt | `core.Gate.preview`, `render.gatterleiter` | fuenf Sprossen, Stoppschalter haelt trotz Freigabe, Trockenlauf haelt |
| ~~Vertrauensnaht~~ | **zurueckgebaut 2026-08-31** | `render.vorgangsfakten` | gemeinsame Liste, Ziele zuerst; Entwurfstext ausserhalb |
| Zaehler mit Bezug und Balken (Abschnitt 21, DD-33) | umgesetzt | `render.zaehler` | keine Inline-Stile im erzeugten HTML |
| Zwei Spurbreiten (DD-03) | umgesetzt | `render.seite(weit=...)` | -- |
| Helle Fassung (DD-11) | umgesetzt | `web/style.py` | -- |

**Bewusst nicht umgesetzt**, obwohl im Design beschrieben:

| Element | Warum nicht |
|---|---|
| Rueckfrageseite (K10) | Sie wird erst gebraucht, wenn `dry_run = false` je vorkommt -- also nach Roadmap-Punkt 2. Vorher waere sie eine Rueckfrage vor einer Handlung, die nichts bewirkt |
| Protokoll-Einzelansicht (acht Fragen, B10) | Neue Route. TD-1 (Schutz ist ein Dekorator) waere vorher zu schliessen |
| Sichten im Protokoll (Filter als Links) | Neue Abfrageparameter, kein Informationsgewinn ueber das hinaus, was die Liste schon zeigt |
| Dienste, Modelle, Gedaechtnis, Fehler | Neue Bereiche. Weg B schliesst sie aus; sie bleiben PLANNED hinter Roadmap 6 |
| Umbenennung "Zustand" zu "Lage" | *doch* umgesetzt -- eine Beschriftung, kein Bereich |

### 48.1 Ein Befund aus der Umsetzung

**Die Naht kann die Herkunft eines Ziels nicht nennen.** Abschnitt 23 verlangt:
"Rechts steht zu jedem Ziel seine Herkunft (`Kopffeld From`,
`Antwortdatensatz`) -- nicht nur der Wert." Das laesst sich heute nicht
erfuellen: `Decision.targets` ist eine flache Abbildung von Name auf Wert, die
Herkunft je Ziel wird nirgends gespeichert. SPEC-3 verlangt sie auch nicht.

Erfunden wurde deshalb nichts. Die Naht zeigt die Ziele ohne Herkunftsangabe.
Wer sie will, braucht ein Feld in `Decision` -- das waere eine
Architekturaenderung und gehoert nach SPEC-3 §27 vor die Implementierung, nicht
in eine Anzeige.

**Offen als ODS-7.**

### 48.2 Was SPEC-3 §27 jetzt verlangt

SPEC-3 Abschnitt 27 (Change Management) sagt: *"Codeaenderung -- betroffenen
SPEC-Abschnitt mitziehen, im selben Commit."* Diese Aenderung beruehrt vier
Stellen. Der Wortlaut steht in `design/SPEC-3-NACHTRAG.md` als Vorschlag; er
ist **nicht** in SPEC-3 eingetragen, weil die Aenderung der Spezifikation dem
Nutzer gehoert.

### ODS-7 -- Traegt ein Ziel seine Herkunft?

```
Frage:     Soll Decision.targets je Ziel festhalten, woraus es berechnet wurde?
Bezug:     SPEC-3 3.2 P1, 6.1 (Definierte Targets); Abschnitt 23 dieses Dokuments
Wirkung:   Die Vertrauensnaht koennte "Empfaenger -- aus Kopffeld From" zeigen
           statt nur den Wert. Ohne das bleibt die rechte Haelfte eine Liste
           von Werten, deren Vertrauenswuerdigkeit man glauben muss.
Kosten:    Aenderung an Decision, an jeder Faehigkeit, die Ziele baut, und an
           der Freigabetabelle. Architekturaenderung nach SPEC-3 27.
Empfehlung: Nicht jetzt. Erst wenn eine zweite Zielart dazukommt (Dateipfad,
           Geraet) -- dann zahlt sie sich aus und wird zugleich noetig, siehe
           ODS-4.
Status:    OFFEN
```


---

## 49. Das Blaetterwerk (`design/designsystem.html`)

**CURRENT.** Das vollstaendige Design als eine in sich geschlossene Datei: 25 Tafeln,
eigenes Stylesheet, keine Nachbardateien. Sie laesst sich lokal direkt oeffnen und ist
zugleich als Artefakt veroeffentlicht.

| Teil | Tafeln | Inhalt |
|---|---|---|
| **A -- Grundlagen** | G1-G8 | Farbwelt, Typografie, Formen, Raster und Abstaende, Hierarchie, helle und dunkle Fassung, Groessenstufen, Bewegung/Tastatur/Druck |
| **B -- Oberflaechen** | O1-O12 | Lage, Entscheidungen, Rueckfrage, Angehalten, Protokoll, Protokolleintrag, Briefing, Dienste, Gedaechtnis, Sprache, Meldungen, Musterblatt |
| **C -- Abdeckung** | C1-C3 | B1-B25 je Tafel; was sich nicht zeigen laesst; was Bild ist und was Code |
| **D -- Abweichungen** | D1-D2 | wo das Design von SPEC-3 abweicht; wo SPEC-3 dem Stand hinterherhaengt |

**Abdeckung der 25 Vorgaben:** 18 auf einer Tafel sichtbar, 3 mittelbar, 4 nicht zeigbar.
B14 ist seit dem Rueckbau der Naht (Abschnitt 51) nicht mehr am Vorgang sichtbar und steht
jetzt unter *mittelbar*.
Die vier -- B2, B3, B12, B20 -- sind Abwesenheiten; C2 nennt zu jeder, woran man ihre
Einhaltung trotzdem erkennt.

### 49.1 Im Browser geprueft

Erstmals nicht nur geschrieben, sondern **gerendert und gemessen** (Chromium ueber
Playwright, 1280px und 420px, helle und dunkle Fassung):

| Pruefung | Ergebnis |
|---|---|
| Horizontaler Seitenueberlauf | keiner, in keiner Breite und keinem Thema |
| Ueberlauf im Tafelkopf | keiner bei 1280px und 900px |
| Kontrast unter 3:1 im Specimen | **keiner**, nachdem zwei Fehler behoben waren |
| Verschachtelung, offene Elemente | sauber |
| Anker des Inhaltsverzeichnisses | 25 Verweise, 25 Ziele, keine Waise |
| Breite Inhalte | scrollen innerhalb ihres Rahmens (`overflow-x:auto`), nie die Seite |

**Zwei Fehler, die nur das Rendern gezeigt hat:**

1. **Quirks-Modus.** Die Datei traegt kein `<!doctype>` -- das setzt der Artefaktdienst
   beim Veroeffentlichen davor, die lokale Datei bekommt keines. Ohne doctype rendert
   Chromium im Quirks-Modus, und dort **erben Tabellenzellen die Textfarbe nicht**: sie
   nehmen die von `body`, also die der Praesentationsebene. Vier Beschriftungen standen
   dadurch mit Kontrast 1,05 : 1 auf dem Specimen-Grund -- praktisch unsichtbar. Behoben
   durch explizite Farben auf `.j table, .j td` und `.btab, .btab td`, statt sie der
   Vererbung zu ueberlassen. Damit rendern beide Faelle gleich.
2. **`.m` wirkte nur im Kontext.** Die Klasse fuer Maschinenschrift war nur unterhalb von
   `.btab` und `.j` definiert. In Bildunterschriften und Fliesstext blieb sie ohne Wirkung
   -- Bezeichner wie `--linie-stark` standen in Serifenschrift und brachen am Bindestrich
   mitten im Wort um. Behoben durch eine Regel auf der Praesentationsebene, mit
   `white-space: nowrap`.

**Nicht geprueft:** Safari auf macOS. Die Sitzung laeuft unter Linux; geprueft wurde in
Chromium. Das ist mehr als vorher, aber nicht die Zielplattform.

**Kein Netz beim Rendern.** Die Webfonts der Praesentationsebene (IBM Plex) waren nicht
erreichbar -- der Rueckfall auf Georgia und Systemschrift wurde damit unfreiwillig
mitgetestet und traegt: alle Tafeln bleiben lesbar.

---

## 50. Abweichungen von SPEC-3

Vollstaendige Liste. Sie steht auch im Blaetterwerk als Teil D, weil eine Abweichung, die
nirgends auftaucht, zur Regel wird.

### 50.1 Wo das Design von SPEC-3 abweicht

| # | Abweichung | SPEC-3 sagt | Bewertung |
|---|---|---|---|
| **A-1** | ~~Die Vertrauensnaht wurde gebaut~~ | Abschnitt 25 fuehrt den Entscheidungsstrom unter *"Future-only -- jetzt nur Bauplan"* | **ERLEDIGT 2026-08-31** durch Teilrueckbau. Siehe Abschnitt 51 |
| **A-2** | Ein Akzent **plus zwei Funktionssignale** | SPEC-1 §7: "eine einzige Akzentfarbe" | zulaessig -- SPEC-1 ist HISTORICAL. Begruendet aus SPEC-3 3.4: mit einer Farbe fuer Identitaet *und* offene Vorgaenge laesst sich "ein Fehler darf nie wie ein Erfolg aussehen" nicht erfuellen |
| **A-3** | "Zustand" heisst "Lage" | Abschnitt 12 nennt die Ansicht "Zustand" | kosmetisch; im Nachtrag als Aenderung 3 erfasst |
| **A-4** | Die Naht nennt **keine Herkunft je Ziel** | SPEC-3 verlangt sie nicht -- **dieses Dokument** verlangt sie in Abschnitt 23 | Abweichung des Designs von sich selbst. Nicht erfunden, offen als ODS-7 |

**Zu A-1, weil es die schwerste ist.** Was den Vorgriff abmildert, aber nicht aufhebt: die
Naht schafft keine Faehigkeit. Sie legt kein Feld an, keine Tabelle, keine Route, keinen
Aktionsweg. Sie ordnet Daten anders an, die ohnehin getrennt in der Freigabetabelle liegen
-- `fields` und `targets`. Die goldene Regel zaehlt fuenfzehn verbotene Artefakte auf;
keines davon ist entstanden.

**Was daraus folgt:** entweder SPEC-3 zieht nach -- der Wortlaut liegt in
`design/SPEC-3-NACHTRAG.md`, Aenderung 9 -- oder die Naht wird zurueckgebaut. Das ist eine
Entscheidung des Nutzers, keine des Designs.

### 50.2 Wo SPEC-3 dem Stand hinterherhaengt

**Fuenf Stellen** offen, alle im Nachtrag mit fertigem Wortlaut: Abschnitt 4.2
(`Gate.preview()` ist dort nicht benannt), Abschnitt 12 (die drei verbliebenen Anzeigen
fehlen), Abschnitt 15 (Zeile Dashboard), OD-4 (steht OFFEN, ist entschieden), und die
Testzahlen in 1, 3.4, 13 und 28.

**Eine Stelle hat sich erledigt:** Abschnitt 25 fuehrte den Entscheidungsstrom als
Future-only, waehrend er gebaut war. Durch den Rueckbau (Abschnitt 51) stimmt der Abschnitt
wieder, ohne dass eine Zeile daran geaendert wurde.

**Unberuehrt:** die vier Prinzipien (3.2), das Ausfuehrungsmodell (5), die Sicherheitsmatrix
(16), die offenen Befunde (17 -- **SEC-1 und SEC-2 bleiben unveraendert offen**), die
technischen Schulden (18), die Zukunftsarchitektur (19-20), die Roadmap (21) und die
Abnahmekriterien (26).

---

## 51. Rueckbau der Vertrauensnaht (Weg A-teil)

**Entscheidung des Nutzers am 2026-08-31.** Von den vier Wegen -- Vollrueckbau,
Teilrueckbau, SPEC-3 anpassen, Abweichung akzeptieren -- wurde **A-teil** gewaehlt:
die Zweiteilung entfaellt, die zusaetzliche Information bleibt. **SPEC-3 wurde nicht
geaendert.**

### 51.1 Was entfernt wurde

| Datei | Was | Umfang |
|---|---|---|
| `jarvis/interfaces/web/render.py` | `naht()` und `_halb()` ersetzt durch `vorgangsfakten()` | -48 / +38 Zeilen |
| `jarvis/interfaces/web/render.py` | Parameter `satz=` an `fakten()` -- er hatte nur einen Nutzer | entfernt |
| `jarvis/interfaces/web/style.py` | `.naht`, `.naht-halb`, `.naht-kopf`, `.facts.satz`, Umbruchregel | 7 Regeln |
| `tests/test_web.py` | zwei Tests umgeschrieben statt geloescht | siehe 51.3 |

### 51.2 Was bleibt

`vorgangsfakten()` baut **eine** Liste, in dieser Reihenfolge:

1. Ziele aus `Decision.targets`, in der Reihenfolge von `BEKANNTE_ZIELE`
2. weitere Ziele, alphabetisch
3. Felder aus `Decision.fields` -- **die Information, die vor der Naht nirgends sichtbar war**
4. Grund, Entschieden von, Modell

`body` bleibt aussen vor und steht als Zitat darunter. Die Gatterleiter, die Stufenanzeige
und die Zustandsmarken sind unberuehrt -- keines dieser Elemente haengt an der Naht
(gemessen: 0 Referenzen).

### 51.3 Die Tests

Beide Tests wurden **umgeschrieben, nicht geloescht** -- sie pruefen jetzt das Gegenteil:

| Test | Prueft |
|---|---|
| `test_vorgang_zeigt_ziele_und_modellfelder_in_einer_liste` | dass "Modell entschied", "Code berechnete" und `class="naht` **nicht** vorkommen; dass Ziele und Modellfelder in derselben `dl.facts` stehen; dass die Ziele zuerst kommen |
| `test_entwurfstext_steht_ausserhalb_der_faktenliste` | dass der Entwurfstext nicht in die Faktenliste rutscht |

Der erste Test faengt einen Rueckfall: wer die Zweiteilung wieder einbaut, laesst ihn
scheitern.

### 51.4 Was der Rueckbau kostet

Ehrlich benannt, weil es die Folge einer bewussten Entscheidung ist:

* **B14 ist nicht mehr sichtbar.** Die Trennung von `fields` und `targets` ist im Code
  vierfach abgesichert (SPEC-3 3.2 P1), aber die Oberflaeche zeigt sie nicht mehr. In der
  Abdeckungskarte steht B14 jetzt unter *mittelbar* statt *sichtbar*: 18 statt 19.
* **DD-08 greift nicht mehr innerhalb der Faktenliste.** Dort stehen alle Werte in
  Maschinenschrift, auch die des Modells. Die Schriftregel gilt weiter fuer die Oberflaeche
  als Ganzes, traegt aber die Vertrauensgrenze nicht mehr.
* **DD-27 ist zurueckgezogen**, K6 entfaellt aus dem Bausteinkatalog, Abschnitt 23 ist als
  nicht mehr gueltig gekennzeichnet.

### 51.5 Was er einbringt

Kein Element der Oberflaeche geht ueber das hinaus, was SPEC-3 3.0 vorsieht. Das war der
Zweck, und er ist erreicht.
