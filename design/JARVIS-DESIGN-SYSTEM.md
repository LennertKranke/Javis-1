# JARVIS Design System

```
Dokument:          JARVIS-DESIGN-SYSTEM
Status:            SOURCE OF TRUTH fuer die Gestaltung des Dashboards
Fassung:           2.2
Stand:             2026-09-02 (2.2: Kern raeumlich, Glas, Feinschliff)
Geltungsbereich:   Gestaltung und Bedienung von jarvis/interfaces/web/.
                   Keine Architektur, keine Anforderungen, keine Roadmap
Grundlage:         JARVIS-SPEC-3.md (CURRENT SOURCE OF TRUTH), Abschnitte
                   3.2, 4.2, 4.6, 5.2, 12, 24, 27
Verhaeltnis zu
SPEC-3:            untergeordnet. Wo dieses Dokument SPEC-3 widerspricht,
                   gilt SPEC-3. Dieses Dokument aendert SPEC-3 nicht
Verhaeltnis zum
Code:              Dieses Dokument beschreibt, was jarvis/interfaces/web/
                   style.py, render.py und app.py tun. Weicht der Code ab,
                   ist das Dokument falsch -- nicht der Code
Ersetzt:           Fassung 1.0 (Designvorschlag vom 2026-08-31, tuerkis,
                   hell/dunkel, ohne Bewegung) samt Blaetterwerk und
                   Entwurfsblaettern. Alles davon liegt in der Git-Geschichte
```

---

## 0. Ein Satz

JARVIS ist dunkel, warm und ruhig. In der Mitte ein leuchtender Kern, der
den Zustand des Systems traegt; darum herum Glas, duenne Linien und
Maschinenschrift. Nichts blinkt, nichts behauptet etwas, das der Kern nicht
weiss.

---

## 1. Was SPEC-3 der Gestaltung vorgibt

Diese Zeilen sind die Grundlage. Jede Entscheidung weiter unten verweist auf
eine davon oder sagt, dass sie freie Wahl ist.

| # | Vorgabe | SPEC-3 |
|---|---|---|
| **B1** | Das Dashboard ist Oberflaeche, nicht Sicherheitsinstanz. Jede Handlung geht durch `execute_approval` | 4.6, 12 |
| **B2** | Ein Knopf ruft nie direkt einen externen Dienst auf; kein zweiter Aktionsweg | 4.6, 12 |
| **B3** | Loopback, Sitzungstoken, Origin-Pruefung, CSP `default-src 'none'`, kein JavaScript | 4.6 |
| **B4** | Der Stoppschalter ist auf jeder Ansicht sichtbar | 12 |
| **B5** | Gatterreihenfolge: Faehigkeit, Stoppschalter, Stufe/Freigabe, Obergrenze, Ausfuehrung | 4.2 |
| **B6** | Eine Freigabe ersetzt die Autonomiestufe -- sonst nichts | 4.2 |
| **B7** | Autonomie je Faehigkeit; am Skill die verlangte, in der Konfiguration die gewaehrte Stufe | 4.3, 6.1 |
| **B8** | Ein Fehler darf nie wie ein Erfolg aussehen | 3.4, 5.2 |
| **B9** | Fremde Inhalte sind Daten, auch in der Anzeige | 3.2 P3 |
| **B10** | Keine Erfolgsmeldung staerker als der Nachweis | 27 |
| **B11** | Kein Fake-Feature, kein Stub, kein Dashboard-Element fuer PLANNED | Statusstufen, 24 |
| **B12** | Zustaende, die das System nicht kennt -- EXECUTING, OFFLINE, CANCELLED -- gibt es nicht | 5.2 |
| **B13** | Das Dashboard bekommt kein Eingabefeld: Text ist Fremdtext, Durchlaeufe startet die Kommandozeile | 12, `web/app.py` |

Was SPEC-3 der Gestaltung ausdruecklich ueberlaesst (27): Schriftbild, Farben,
Abstaende, Komponenten. Alles, was folgt, ist Gestaltung -- ausser den
Sicherheitsfolgen aus B3, die als **Randbedingungen** wirken (Abschnitt 2).

---

## 2. Randbedingungen, die die Form bestimmen

Die Sicherheitsrichtlinie nimmt der Gestaltung das uebliche Werkzeug weg. Der
Stil entsteht aus dem, was bleibt.

| Randbedingung | Folge |
|---|---|
| `default-src 'none'`, kein JavaScript | Kein Umschalter, kein Menue, kein Dialog, kein Nachladen. Jede Auswahl ist eine Adresse, jede Handlung ein Formular, jede Aktualisierung ein Neuladen (`meta refresh`, Standard aus) |
| `img-src 'none'` | Kein Bild, keine Symbolschrift, keine Webfont, kein `url()` im Stylesheet -- auch keine Daten-URI, auch nicht in `mask`. Der Kern und jedes Muster sind **Gradienten**; Symbole sind Inline-SVG (Dokumentinhalt, kein Abruf) |
| `style-src 'self'` | Kein `style`-Attribut. Ein dynamischer Wert wird auf eine Stufenklasse gerundet (`.f-40` fuer den Fuellstand) |
| Kein Build-Schritt | Ein handgeschriebenes Stylesheet in `style.py`, als eigene Route `/jarvis.css` ausgeliefert |

Zwei Tests halten das fest: `test_kein_inline_stil_in_keiner_ansicht` und
`test_das_stylesheet_laedt_nichts_nach`. Ein Verstoss faellt nicht im
Browser auf -- er wird dort still verworfen -- sondern im Test.

---

## 3. Farbwelt

**Dunkel, ausschliesslich.** Das Dashboard hat keine helle Fassung mehr.
JARVIS ist eine dunkle Oberflaeche; eine helle waere ein zweites Design.
`color-scheme: dark` sagt das auch dem Browser.

### Rollen statt Farbnamen

Alle Werte stehen als `--marke` in `:root` von `style.py`. Wer eine Farbe
aendert, soll sehen, wofuer sie steht.

| Marke | Wert | Rolle |
|---|---|---|
| `--grund` | `#0a0806` | Seitengrund, warmes Schwarz |
| `--glas` | `rgba(255,150,70,.045)` | Tafeln: Glas auf dem Grund, keine eigene Flaeche |
| `--glas-hoch` | `rgba(255,150,70,.075)` | Kopfzeilen, aktive Zeile, aktiver Navigationspunkt |
| `--linie` | `rgba(255,165,90,.14)` | Standardtrennung |
| `--linie-stark` | `rgba(255,165,90,.32)` | Rahmen, Marken, Tabellenkopf |
| `--text` | `#f1e8da` | Vordergrund |
| `--text-zweit` | `#c4b29c` | Beschriftungen, zweite Ebene |
| `--text-gedaempft` | `#8e7e6a` | Herkunft, Zeit, dritte Ebene (Kontrast rund 5:1) |
| `--akzent` | `#ff9a3d` | **Der** Akzent: Identitaet, Fokus, "hier bist du gefragt" |
| `--akzent-hell` | `#ffc37c` | Hervorgehobene Schrift, Aufmerksamkeit (Trockenlauf AUS, Mock) |
| `--akzent-tief` | `#d9671c` | Kern-Rand, Fuellstand |
| `--glut`, `--glut-weit` | `rgba(255,150,60,.45)`, `rgba(255,120,30,.22)` | Leuchten, nah und weit |
| `--kalt`, `--kalt-tief` | `#a4b8cc`, `#52677c` | Angehalten, blockiert; Band und Grund im Stopp werden aus diesen Werten gemischt |
| `--kalt-glut` | `rgba(120,150,185,.22)` | Leuchten im angehaltenen Zustand |
| `--signal-fehler`, `--fehler-glut` | `#ff5f5f`, `rgba(255,95,95,.35)` | Fehlgeschlagen, Abweichung |

### Die vier Farbregeln

**F1 -- Erfolg traegt keine Farbe.** Der Normalfall ist neutral. Farbe
bekommt nur, was Aufmerksamkeit verdient. Es gibt kein Erfolgsgruen.

**F2 -- Farbe nie allein.** Jede farbige Aussage traegt zusaetzlich ein Wort
und eine Form (Rahmen, Linienart, Muster). Grundlage B8: sonst haengt "ein
Fehler darf nie wie ein Erfolg aussehen" an der Farbwahrnehmung.

**F3 -- Warm heisst lebendig, kalt heisst angehalten.** Orange ist der
Betrieb. Ein angehaltenes oder blockiertes System ist kalt und ohne Glut --
man erkennt es, bevor man liest (B4). Rot ist allein dem Fehlgeschlagenen und
der Abweichung vorbehalten.

**F4 -- Linienart bedeutet etwas.** Durchgezogen = vom Code berechnet;
gepunktet = aus Fremdtext oder Modell (Entwurfstext); gestrichelt = verworfen
oder leer; schraffiert = Trockenlauf.

| Erscheinung | Farbe | Form |
|---|---|---|
| Betrieb, Kern, Identitaet | Akzent | Glut |
| `Offen` (wartet auf dich) | Akzent-hell | Rahmen, leichtes Leuchten |
| `Trockenlauf AUS`, `Dienste Mock` | Akzent-hell | Schrift mit Leuchten -- der unsichere Zustand ist der auffaellige |
| `Angehalten`, `Blockiert`, Band und Kern im Stopp | Kalt | Rahmen; Kern ohne Glut, ohne Bewegung |
| `Fehlgeschlagen`, `Abweichung` | Fehler | Rahmen; roter Ring am Kern |
| `Ausgefuehrt`, `Durchgelassen`, `Fortgesetzt` | neutral | Rahmen |
| `Verworfen` | gedaempft | gestrichelter Rahmen |
| `Dry Run`, `Haelt` | neutral | schraffiert |

---

## 4. Typografie

Systemschriften, keine Webfonts (Randbedingung `img-src 'none'` und
`default-src 'none'`). Auf macOS sind das SF Pro und SF Mono.

| Rolle | Schrift | Wofuer |
|---|---|---|
| `--satz` | `-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", sans-serif` | Prosa: Vorgangssatz, Briefing, Grund, Hinweise |
| `--masch` | `ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace` | Alles Gerechnete und alles Technische: Zahlen, Kennungen, Zustaende, Beschriftungen, Navigation, Knoepfe |

**Grundzeile** 15px / 1.55, `font-variant-numeric: tabular-nums` -- Ziffern
springen beim Neuladen nicht.

| Rolle | Groesse | Auszeichnung |
|---|---|---|
| Wortmarke `h1` | 0.95rem Maschine | `letter-spacing .34em`, Akzent-hell, leichtes Leuchten, mit Kern-Punkt |
| Zustandsschrift unter dem Kern | 0.84rem Maschine | Versalien, `.36em`, Leuchten in der Zustandsfarbe |
| Abschnittsmarke `h2` | 0.68rem Maschine | Versalien, `.2em`, gedaempft, Linie nach rechts auslaufend |
| Untertitel `h3` | 0.66rem Maschine | Versalien, `.16em` |
| Kennzahl | 1.45rem Maschine | die grosse Zahl der Lage |
| Fliesstext | 0.92-1rem Satz | Vorgangssatz, Briefing, Zustandssatz |
| Tabelle, Fakten | 0.84rem | Dichte |
| Marke, Tabellenkopf, Beschriftung | 0.64rem Maschine | Versalien, `.14em`; muss klein sein, sonst schreit sie |

**Keine Kursive, kein Fett im Fliesstext.** Auszeichnung geschieht ueber Marke,
Linie, Position und Leuchten. Die HUD-Anmutung entsteht aus Versalien in
Maschinenschrift mit weiter Laufweite -- nicht aus Grafik.

---

## 5. Formen, Linien, Glas, Glut

* **Radius 3px** auf Tafeln, Knoepfen und Navigationspunkten; 2px auf
  Marken; der Kern ist rund. Kein anderer Radius.
* **Tafel** (`.tafel`): Glas (`--glas`) mit 1px `--linie` und
  `backdrop-filter: blur(8px)` -- der Lichtkegel des Grunds scheint weich
  hindurch; ein diagonaler Schimmer von oben links
  (`linear-gradient(135deg, rgba(255,190,120,.05), transparent 28%)`) ist
  die orange Reflexion; oben eine **Lichtkante** -- ein 1px-Schimmer (`inset 0 1px 0 rgba(255,195,130,.14)`)
  und ein Verlauf, der in den ersten 38% der Hoehe von `rgba(255,165,90,.05)`
  auf transparent ausklingt --, darunter ein weicher Schatten. So liest sich
  die Tafel als Scheibe, die von oben Licht bekommt, nicht als Karte. Zwei
  **Eckwinkel** aus 11px-Pseudoelementen (oben links, unten rechts) in
  `--linie-stark` -- das eine HUD-Zitat, das die Tafel traegt. Eine
  Vorgangskarte (`.item`) hat dieselbe Lichtkante und nur den Winkel oben
  links, in Akzent.
* **Linien**: 1px, ausschliesslich. `--linie` trennt innerhalb, `--linie-stark`
  grenzt ab. Die Abschnittsmarke `h2` laeuft in eine Linie aus, die nach
  rechts in Transparenz verlaeuft.
* **Glut** (Glow) nur an drei Orten: am Kern (immer), an der Wortmarke und
  dem Puls im Band (leicht), an Marken und Zahlen, die Aufmerksamkeit wollen
  (`Offen`, `reicht-nicht`, `Trockenlauf AUS`, Zaehler in Navigation). Nie
  auf Flaechen, nie auf Text, der nur gelesen wird.
* **Grund**: ein warmes Schwarz mit einem weichen Lichtkegel von oben und
  einem sehr feinen Raster (56px, Alpha .028), das zur Mitte hin
  ausgeblendet ist. Es soll gespuert werden, nicht gesehen. Im angehaltenen
  Zustand wird Lichtkegel und Raster kalt.

---

## 6. Raster und Abstaende

`rem`-basiert, damit Zoom sich wie ein schmaleres Fenster verhaelt.

| Ort | Abstand |
|---|---|
| innerhalb einer Faktenzeile | 0.35rem |
| zwischen Marke und Text | 0.5-0.9rem |
| Innenabstand Tafel | 1.3rem / 1.5rem (schmal: 1rem) |
| zwischen Tafeln | 1.4rem; zwischen Kern-Abschnitt und Tafeln 2.2rem |
| Spurrand | 1.5rem (schmal: 1rem) |
| Abschnittsmarke oben | 2.2rem |
| vor dem Fuss | 3rem |

**Zwei Spurbreiten**: 60rem fuer Prosa (Entscheidungen, Briefing), 96rem fuer
Tafeln (Lage, Protokoll). Ab 96rem waechst nur der Rand.

---

## 7. Der Kern

Das visuelle Zentrum. Ein Orb aus Gradienten, gesetzt in `render.kern()`
und gestaltet in `style.py` unter `.kern`, von aussen nach innen:

```
  .kern::before        weiter Lichthof, leicht nach unten versetzt   steht
  .kern-ring.r0        sehr blasser Aussenring                       steht
  .kern-ring.r2        gestrichelter Ring                            dreht, 110 s
  .kern-ring.r1        durchgezogener Ring                           steht; pulsiert bei "wartet"
  .kern-ring.r3        Skalenring aus 48 Strichen                    dreht gegenlaeufig, 140 s
                       (repeating-conic-gradient, Maske als radial-gradient)
  .kern-bogen          ein heller Bogen                              laeuft um, 26 s
  .kern::after         der Impuls: ein Ring, der von der Kugel       alle 9 s, verklingt
                       ausgeht                                       nach aussen
  .kern-glut           die Kugel                                     atmet, 7 s
    ::before           Glanzlicht oben links                         steht
    ::after            feine konzentrische Schichten                 steht
```

**Die Kugel ist eine Kugel, keine Scheibe.** Die Lichtquelle sitzt oben
links (`circle at 40% 34%`), der Rand wird nach unten rechts dunkel
(`#7a2a06` bis `#3a1203`), eine innere Schattenkante und ein Glanzlicht
stuetzen das; darunter liegt ein weicher, nach unten versetzter Schein --
der Kern steht ueber dem Grund, er klebt nicht darauf. Die Schichten im
Glas (`repeating-radial-gradient`, Alpha .045) geben ihm Struktur, ohne
Muster zu werden.

Groesse `--kern-groesse`: 17rem weit, 13rem standard, 11rem schmal. Fuer
Hilfsmittel ist der Kern `aria-hidden`; der Zustand steht daneben als Text,
und nur der zaehlt.

### Zustaende

Der Zustand ist keine Stimmung. `render.zustand_ermitteln()` leitet ihn aus
Tatsachen ab, in fester Rangfolge, und `app.lage()` liefert die Tatsachen aus
denselben Pruefungen wie `jarvis status`:

| Klasse | Wort | Tatsache | Erscheinung |
|---|---|---|---|
| `angehalten` | Angehalten | Stoppschalter gesetzt | Kern kalt, ohne Glut, **ohne Bewegung**, kein Impuls; Band und Wortmarke kalt; Grund wird kalt |
| `abweichung` | Abweichung | Kette gebrochen, Ablage offen oder Zugangsdaten abweichend | roter Ring, rote Glut, roter Impuls; Liste der Abweichungen unter dem Kern |
| `wartet` | Wartet auf Freigabe | offene Entscheidungen > 0 | innerer Ring pulsiert und leuchtet |
| `betrieb` | Betrieb | nichts davon | Glut atmet, Ringe drehen |

Angehalten schlaegt alles: ein stehendes System hat keinen anderen Zustand.
Der Satz unter dem Wort nennt die Tatsache (Grund des Stopps, erste
Abweichung, Anzahl wartender Entscheidungen) und immer den Trockenlauf.

**Was der Kern nicht zeigt, und warum nicht.** Denken, Laufen, Ausfuehren,
Offline: SPEC-3 5.2 kennt diese Zustaende nicht (B12), also zeigt sie auch
niemand an. Es gibt keine CSS-Klasse dafuer -- kein toter Code, der auf
etwas wartet. Kommt ein solcher Zustand je in den Kern (Execution Layer,
SPEC-3 19.2, OD-1), ist der Weg vorgezeichnet: eine weitere Tatsache in
`zustand_ermitteln()`, eine weitere Klasse `.kern.<name>`, ein Test wie
`test_der_kern_zeigt_den_zustand_den_das_system_hat`. Die Farbrolle waere
Akzent (arbeitet) oder Kalt (steht) -- nichts Neues.

---

## 8. Bewegung

Wenig, langsam, funktional. Was sich bewegt, hat einen Grund:

| Bewegung | Dauer | Grund |
|---|---|---|
| Glut atmet (`atmen`) | 7 s | das System lebt |
| Puls im Band atmet | 4 s | dasselbe, in klein, auf jeder Ansicht |
| Ringe drehen (`drehen`, `gegendrehen`) | 110 s, 140 s | Praezision, kaum wahrnehmbar |
| Bogen laeuft um | 26 s | ein Blick, der wandert |
| Impuls (`impuls`) | 9 s | ein Ring geht von der Kugel aus und verklingt: das System lebt, ohne dass etwas blinkt |
| Innerer Ring pulsiert (`puls`) | 3.2 s | nur bei `wartet`: etwas will etwas von dir |
| Knopf, Navigation | 0.15 s Uebergang | Rueckmeldung |

**Angehalten steht still.** Alle Animationen des Kerns und des Pulses sind
im Stoppzustand aus. **`prefers-reduced-motion: reduce`** schaltet jede
Animation und jeden Uebergang ab -- eine Regel am Anfang des Stylesheets,
mit `!important`, damit keine spaetere Ergaenzung sie unterlaeuft. Nichts
blinkt, nichts springt, nichts wackelt.

---

## 9. Bausteine

| Baustein | Wo | Aufgabe |
|---|---|---|
| **Systemband** `.systemband` | `render.seite` | erstes Element im Dokument; Zustandspunkt, Marke `Betrieb`/`Angehalten`, drei Tatsachen (Trockenlauf, Dienste, Zugangsdaten bzw. Grund und Wirkung), Stoppschalter. Klebt oben (`sticky`), Glas mit Weichzeichner; im schmalen Fenster statisch |
| **Stoppschalter** `button.stopp` | Band | `Anhalten` mit Achteck-Symbol, im Stopp `Fortsetzen` mit Kreis-Symbol. Beides Formulare (`/stop`, `/weiter`). Erstes Formular im Dokument, also erster Griff im Tabfluss |
| **Kopf** `.kopf` | `render.seite` | Wortmarke mit Kern-Punkt, Navigation rechts |
| **Navigation** `nav` | `render.ANSICHTEN` | genau vier Punkte, Versalien; der aktive traegt eine 1px-Akzentlinie unten und leuchtet leicht -- kein Kasten; Zaehler offener Entscheidungen als gefuellte Marke |
| **Meldung** `.note.meldung` | `app.MELDUNGEN` | Ergebnis der letzten Handlung, aus fester Tabelle, nie aus der Adresszeile |
| **Kern** `.kern` | `render.kern` | Abschnitt 7 |
| **Kennzahl** `.kennzahl` | `render.kennzahl` | grosse Zahl mit Name und Zusatz; `hebt` Akzent, `gefahr` Rot, `kalt`; `klein` fuer Worte statt Zahlen (die Systemtatsachen rechts vom Kern) |
| **Faktenliste** `dl.facts` | `render.fakten` | Name/Wert, Wert in Maschinenschrift, bricht ueberall um |
| **Tafel** `.tafel` | `render.tafel` | Glas mit Titel, Eckwinkeln und optionalem Fuss (der Weg in die Tiefe) |
| **Tabelle** `.tabelle > table` | `render.tabelle` | rollt in ihrem Rahmen, nie die Seite; jede Zelle traegt `data-kopf`, im schmalen Fenster wird sie zu Bloecken; Werte in Maschinenschrift, keine Zeilenhervorhebung beim Ueberfahren -- eine Tafel, kein Formular |
| **Zustandsmarke** `.marke` | `render.zustandsmarke` | Wort mit Form; nur bekannte Ergebnisse, alles andere bleibt Text (`.dim`) |
| **Autonomiestufe** `.stufe` | `render.stufe` | immer beide Zahlen, gewaehrt / verlangt; reicht die gewaehrte nicht, leuchtet sie |
| **Zaehler** `.zaehler` | `render.zaehler` | benutzt/Grenze mit Balken in Fuenferstufen; voll = kalt |
| **Gatterleiter** `.gatter` | `render.gatterleiter` | fuenf Sprossen in der Reihenfolge aus 4.2; die entscheidende Sprosse ist Glas mit Akzentkante (kalt, wenn blockiert); nicht ausgewertete stehen gedaempft |
| **Vorgangskarte** `.item` | `render.vorgang` | Kopf (Faehigkeit, Aktion, `Offen`, Zeit), Satz, Faktenliste, Entwurfstext als gepunktetes Zitat, Gatterleiter, Vermerk, Handlungszone |
| **Kurzvorgang** `.anstehend` | `render.vorgang_kurz` | eine Zeile je Vorgang auf der Lage, ohne Knopf |
| **Leerer Zustand** `.empty` | `render.leer` | gestrichelter Rahmen, sagt, was fehlt und wo es herkommt |
| **Knopf** `button` | -- | Versalien in Maschinenschrift, Rahmen; `primary` gefuellt in Akzent mit Glut |

---

## 10. Die vier Ansichten

Die Navigation waechst nicht mit Wunschbereichen (B11). Jeder Punkt ist eine
Route in `app.py`, und ein Test haelt die Menge fest.

### Lage (`/`, Tafelbreite)

Die Leitstelle. Reihenfolge: **Zustand, Zahlen, Arbeit, Bestand.**

```
  1  Systemband
  2  Kern mit Zustand         links drei Zahlen: offene Entscheidungen,
                              Protokoll (Eintraege, Kette), letzter Eintrag
                              rechts drei Tatsachen, gleiche Form, rechts-
                              buendig (gespiegelt; unter 70rem linksbuendig):
                              Zugangsdaten, Ablage, Modellprozess
                              (rot, wenn die Ablage offen oder die Trennung
                              aus ist). Keine Pfade -- die nennt
                              `jarvis status`
  3  Abweichungen             nur wenn vorhanden, rot gerahmt
  4  Anstehend                bis vier Vorgaenge, Weg zu Entscheidungen
     Zuletzt im Protokoll     acht Eintraege mit Marke, Weg zum Protokoll
  5  Faehigkeiten             Name, gewaehrt/verlangt, erreicht Dritte, aktiv,
                              Kontingent, letzter Lauf (Daemon)
```

Alles auf der Lage ist gelesen. Das einzige Formular ist der Stoppschalter;
ein Test (`test_die_lage_hat_keine_handlung_ausser_dem_stoppschalter`) und
ein zweiter, dass zehnmal Laden weder Protokoll noch Kontingent veraendert,
halten das fest.

### Entscheidungen (`/entscheidungen`, Lesebreite)

Vorgangskarten, aelteste zuerst. Im Trockenlauf ein Hinweis darueber und statt
des Freigabeknopfs der Satz "Freigabe wirkt erst ohne Trockenlauf." Die
Gatterleiter jeder Karte beantwortet vor dem Klick, woran es haengen wird --
lesend, aus `Gate.preview()`.

**Freigeben** ist der gefuellte Knopf, **Verwerfen** der ruhige. Beide sind
Formulare an Routen, die durch `execute_approval` bzw. `reject_approval`
gehen; die Oberflaeche entscheidet nichts (B1, B2).

### Briefing (`/briefing`, Lesebreite)

Eine Tafel mit Tag, Stand (heute/aelter), Quelle (Modell oder "ohne Modell")
und Erstellzeit; der Text als Prosa mit Akzentlinie. Aeltere Briefings als
zweite Tafel. Erzeugt wird hier nichts.

### Protokoll (`/protokoll`, Tafelbreite)

Die letzten 60 Eintraege: Nr, Zeit (UTC), Faehigkeit, Art, Ergebnis als
Marke, Grund. Im Fuss die Gesamtzahl und der Zustand der Kette.

---

## 11. Zustaende der Oberflaeche

| Zustand | Wie er aussieht |
|---|---|
| **Leer** | gestrichelter Rahmen mit Satz: "Nichts anstehend. Was von selbst durchging, steht im Protokoll." / "Noch kein Briefing abgelegt. Erzeugen: jarvis briefing --neu" |
| **Trockenlauf an** (Standard) | ruhig: `Trockenlauf an` in normaler Schrift; Kern-Satz sagt "Freigeben bewirkt nichts" |
| **Trockenlauf AUS** | auffaellig: `AUS` in Akzent-hell mit Leuchten im Band; Freigabeknoepfe erscheinen; Gatterleiter endet auf `Geht hinaus` |
| **Dienste Mock** | `Mock` in Akzent-hell -- ein Mock, den man nicht sieht, ist eine Falle |
| **Angehalten** | Band kalt mit Grund ("ueber das Dashboard (web, seit 21:31 UTC)" -- aus der Stoppdatei gelesen, nicht die Rohzeile) und Wirkung, Knopf `Fortsetzen`; Kern kalt und still; Grund und Wortmarke kalt; `<body class="angehalten">` |
| **Abweichung** | Kern mit rotem Ring, Wort `Abweichung`, rote Tafel mit der Liste; Protokoll-Kennzahl rot |
| **Fehler eines Vorgangs** | Marke `Fehlgeschlagen` rot im Protokoll; der Vorgang bleibt offen und traegt den Grund als Vermerk (`.note.warnung`) |
| **Meldung nach Handlung** | Hinweis oben in der Zielansicht, Text aus `MELDUNGEN` |
| **Laden** | gibt es nicht: eine Handlung antwortet mit einer Umleitung, wenn sie entschieden ist. Eine Fortschrittsanzeige wuerde einen Zustand behaupten, den der Kern nicht fuehrt (B12) |

---

## 12. Groessenstufen

Drei Stufen, jede fuer sich vollstaendig; ohne JavaScript gibt es keine
Umschaltung.

| Stufe | Breite | Verhalten |
|---|---|---|
| **Weit** | > 70rem (1120px) | Lage dreispaltig: Zahlen, Kern, System; zwei Tafeln nebeneinander; Kern 15rem |
| **Standard** | 46-70rem | Lage einspaltig, Kern zuerst; Kennzahlen als Dreierreihe; Tafeln untereinander; Tabellenkoepfe duerfen umbrechen, breite Tabellen rollen im Rahmen; Kern 13rem |
| **Schmal** | < 46rem (736px) | Band statisch, Stoppschalter volle Breite; Navigation umbrechend; Tabellen als Bloecke mit `data-kopf`-Beschriftung; Faktenlisten einspaltig; Kern 11rem |

Gemessen (Chromium, Playwright): 1440, 1100, 820 und 390px, alle vier
Ansichten, kein horizontaler Ueberlauf der Seite. Das Dashboard bindet an
Loopback; ein Telefon erreicht es nicht. Die schmale Stufe ist fuer ein
schmales Fenster am Bildschirmrand da -- und sie bricht auch auf 390px
nicht.

---

## 13. Zugaenglichkeit

* **Kontrast**: Text auf Grund mindestens 5:1 (`--text-gedaempft`), Normaltext
  ueber 9:1; Knopfschrift auf Akzent 9:1.
* **Farbe nie allein** (F2): jede Marke ist ein Wort mit Form.
* **Fokus**: sichtbarer 2px-Ring in Akzent auf allem, was Fokus nimmt
  (`:focus-visible`).
* **Tabfolge**: Stoppschalter zuerst (erstes Formular im Dokument), dann
  Navigation, dann Inhalt. Ein Test haelt die Reihenfolge fest.
* **Kern** ist `aria-hidden`; der Zustand steht als Text daneben.
* **Symbole** sind `aria-hidden`; der Knopf traegt sein Wort.
* **Bewegung** endet mit `prefers-reduced-motion`.
* **Zoom** bis 200%: alle Umbruchstufen in `rem`.
* **Druck**: Band, Navigation, Handlungen und Kern verschwinden; Farbe wird
  Linie. Ein Protokollauszug laesst sich als Beleg ablegen.

Keine Zusage zu einer Konformitaetsstufe (WCAG o. ae.): das waere eine
Behauptung ohne Pruefung (B10).

---

## 14. Wortlaut

Sagen, was ist -- nicht, was gelungen ist. Zustaende heissen wie im Code
(`Schattenbetrieb`, nicht "sicherer Modus"). Kein Ausrufezeichen, kein Emoji,
kein Lob; ein Test prueft den sichtbaren Text jeder Ansicht darauf. Zahlen
mit Bezug (`0/20 hour`, nicht `0`). Der Fehler nennt Ursache, Stand und Weg:
"Gmail war nicht erreichbar. Der Vorgang bleibt offen."

---

## 15. Was das Design bewusst nicht enthaelt

| Nicht enthalten | Warum |
|---|---|
| **Chat / Eingabefeld** | B13. Ein Textgespraech waere ein zweiter Aktionsweg und eine Route, die Modellaufrufe ausloest -- von jedem offenen Browser-Tab per Formular erreichbar. SPEC-3 fuehrt das Dashboard als bestaetigende Oberflaeche; die Kommandozeile (`jarvis voice ask`) ist der Befehlsweg |
| **Skills, Tasks, Memory, Settings als Seiten** | Skills stehen auf der Lage (CURRENT); Tasks gibt es nicht (PLANNED); Memory und Dienste sind Control-Plane-Bereiche unter Roadmap 6 (PLANNED, B11); Einstellungen sind eine TOML-Datei, kein Formular |
| **Zustaende Laeuft / Denkt / Offline** | B12 |
| **Fortschrittsanzeige** | dito -- die Seite kehrt zurueck, wenn entschieden ist |
| **Helle Fassung** | ein zweites Design; JARVIS ist dunkel |
| **Webfonts, Bilder, Icons als Dateien** | Randbedingung `img-src 'none'` |
| **Mikrofonknopf** | Sprache ist eine Bedienweise der Kommandozeile ohne `act`-Pfad und braucht keine Oberflaeche |
| **Mock-Daten** | keine. Alles auf der Seite kommt aus Konfiguration, Datenbank und Stoppdatei |

---

## 16. Erweiterung ohne Vorwegnahme

Regeln, wie Kuenftiges einpasst -- kein Platz, der warmgehalten wird.

| Was kommt | Wo es einpasst |
|---|---|
| Eine neue Faehigkeit | eine Zeile in der Faehigkeitstabelle, automatisch aus `[capabilities]`; ihre Vorgaenge sind Vorgangskarten; die Zielliste ist datengetrieben (`render.BEKANNTE_ZIELE` plus alles Weitere alphabetisch) |
| Ein neuer Zustand des Kerns | Abschnitt 7: Tatsache, Klasse, Test |
| Ein neuer Bereich (nach Roadmap 6) | eine Tafel auf der Lage mit zwei bis vier Zahlen und einem Weg in die Tiefe; eine Route mit `@geschuetzt` -- `test_jede_route_ausser_dem_stylesheet_verlangt_den_token` prueft jede registrierte Route, nicht eine Liste |
| Eine neue Marke | `render.ZUSTAENDE` plus eine Farbrolle aus Abschnitt 3 -- keine neue Farbe |

---

## 17. Entscheidungen

| # | Entscheidung | Grundlage |
|---|---|---|
| **DD-01** | Dunkel, warm, ein Akzent Orange; keine helle Fassung | Identitaet; freie Wahl |
| **DD-02** | Glas statt Flaeche; Tiefe aus Alpha auf dem Grund, nicht aus Schatten | freie Wahl mit Zweck: Ruhe |
| **DD-03** | Der Kern ist das Zentrum der Lage und traegt nur Zustaende, die das System fuehrt | B10, B12 |
| **DD-04** | Warm = lebendig, kalt = angehalten; Rot nur fuer Fehler und Abweichung | B4, B8 |
| **DD-05** | Erfolg traegt keine Farbe; Farbe nie allein | B8 |
| **DD-06** | Bewegung ja, aber langsam, funktional, im Stopp aus, mit `prefers-reduced-motion` abschaltbar | freie Wahl; B10 (kein Vortaeuschen von Arbeit: nichts bewegt sich schneller, weil etwas geschaehe) |
| **DD-07** | Alles aus Gradienten, Inline-SVG und Systemschrift | Randbedingung B3 |
| **DD-08** | Kein `style`-Attribut, kein `url()`; Tests halten es fest | Randbedingung B3 |
| **DD-09** | Vier Ansichten, keine mehr; Lage ist der Verteiler | B11 |
| **DD-10** | Die Lage zeigt und entscheidet nicht; einziges Formular ist der Stoppschalter | B1, B2 |
| **DD-11** | Stoppschalter erstes Element im Dokument, auf jeder Ansicht, sticky | B4 |
| **DD-12** | Systemband nennt Trockenlauf, Dienste, Zugangsdaten; der unsichere Zustand ist der auffaellige | B10 |
| **DD-13** | Abweichungen (Kette, Ablage, Zugangsdaten) stehen vor allem anderen und kommen aus denselben Pruefungen wie `jarvis status` | B10, SPEC-3 12 System Status |
| **DD-14** | Kein Chat, kein Eingabefeld | B13 |
| **DD-15** | Tabellen tragen `data-kopf` und werden im schmalen Fenster zu Bloecken | freie Wahl; kein Skript noetig |
| **DD-16** | Radius 3px, Eckwinkel als einziges HUD-Zitat auf Tafeln | freie Wahl |
| **DD-17** | Zustandsnamen und Wortlaut wie im Code, deutsch, ohne Ausrufezeichen | B10 |

---

## 18. Geprueft

**Dritte Abnahme (Fassung 2.2).** Nahaufnahmen des Kerns bei doppelter
Aufloesung in den Zustaenden Betrieb, Wartet und Angehalten; vier Ansichten
bei 1440, 1100, 820 und 390 px. Geaendert: der Kern ist raeumlich
(Lichtquelle, Rand, Glanzlicht, Schichten, Aussenring, Impuls, 17rem),
Tafeln haben Weichzeichner und Reflexion, die Systemtatsachen rechts vom Kern
spiegeln die Zahlen links, Tabellen ohne Zeilenhervorhebung. Sonst nichts.

**Zweite Abnahme (Fassung 2.1).** Gegen die erste Fassung sind vier Dinge
geaendert, alle nach Ansehen im Browser: die Pfadliste rechts vom Kern ist
drei Tatsachen in Kennzahlform gewichen (sie zog den Blick vom Kern weg und
las sich wie eine Einstellungsseite); der aktive Navigationspunkt ist eine
Linie statt eines Kastens; Tafeln haben eine sichtbare Lichtkante und mehr
Luft; die Stoppzeile im Band nennt Grund, Urheber und Uhrzeit statt der
Rohzeile. Sonst nichts -- was gut war, blieb.


Chromium ueber Playwright, 2026-09-02, gegen das laufende Dashboard mit
Mock-Diensten und einer eingerichteten Probe-Ablage:

| Pruefung | Ergebnis |
|---|---|
| Vier Ansichten bei 1440, 1100, 820, 390px | kein horizontaler Ueberlauf der Seite |
| Zustaende Betrieb, Wartet, Angehalten, Abweichung (Kette gebrochen), Trockenlauf AUS, Mock | alle wie in Abschnitt 7 und 11 beschrieben |
| Leere Ablage (frisch nach `jarvis init`) | leere Zustaende in allen Ansichten |
| 15 Vorgaenge mit 40-zeiligen Entwuerfen und ueberlangen Betreffzeilen | bricht um, nichts laeuft ueber |
| Anhalten und Fortsetzen ueber das Band | Band, Kern, Grund und Knopf wechseln; Protokoll fuehrt beides |

**Nicht geprueft:** Safari auf macOS -- die Zielplattform. Die Sitzung lief
unter Linux. `backdrop-filter`, `mask` und `aspect-ratio` sind in Safari seit
Jahren vorhanden; gemessen ist es dort nicht (B10).

Das Stylesheet ist `jarvis/interfaces/web/style.py`. Wo dieses Dokument und
das Stylesheet auseinanderlaufen, gilt das Stylesheet -- und dieses Dokument
ist nachzuziehen, im selben Commit.
