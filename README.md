# JARVIS

Persoenlicher, autonom laufender Assistent. Verbindliche Vorgabe ist
`JARVIS-SPEC.md`; dieses Dokument beschreibt nur, was davon gebaut ist.

**Stand: Phase 1-6 abgeschlossen. Phase 7 begonnen mit den Grundlagen der
externen Anbindungen.**
Der Kern steht, JARVIS liest und ordnet den Posteingang ein, schreibt
Antwortentwuerfe, kann sie ab Stufe 1 an Adressen auf der Allowlist senden,
liest den Kalender und meldet Terminkonflikte, fasst den Tag in einem
Morgenbriefing zusammen, und zeigt Zustand, Protokoll, Briefing und
anstehende Entscheidungen in einer Weboberflaeche auf localhost. Sprache ist
die dritte Bedienweise: JARVIS liest auf Zuruf vor und laesst sich anhalten,
handeln kann er auf Zuruf nicht. Ein Daemon fuehrt die Durchlaeufe nach
Zeitplan aus. Was davon wie nachgewiesen ist, steht in
[Was wovon nachgewiesen ist](#was-wovon-nachgewiesen-ist).

---

## Einrichten

Vorausgesetzt: Python 3.12 und [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run jarvis init
uv run jarvis status
```

`init` legt `~/.jarvis/` an: Konfiguration, Datenbank, Logverzeichnis. Ein
anderes Basisverzeichnis waehlt `JARVIS_HOME` oder `--home`.

### Zugangsdaten

Ausschliesslich in der macOS-Keychain, niemals im Repo:

```sh
security add-generic-password -s jarvis -a anthropic_api_key -w
```

Zum Entwickeln auf anderen Systemen liest JARVIS ersatzweise
`JARVIS_SECRET_ANTHROPIC_API_KEY` aus der Umgebung. `JARVIS_SECRET_BACKEND`
erzwingt eine Wahl (`keychain`, `env`, `none`). Geschrieben wird ausschliesslich
in die Keychain -- die Umgebung ueberlebt keinen Prozess, und eine Datei
schliesst Abschnitt 4 aus.

### Gmail einrichten

In der Google Cloud Console ein Projekt anlegen, die Gmail-API und die
Calendar-API aktivieren und Zugangsdaten vom Typ **Desktop-App** erzeugen. Die heruntergeladene
`client_secret.json` kommt in die Keychain, nicht ins Repo:

```sh
security add-generic-password -s jarvis -a gmail_client_secret -w "$(cat ~/Downloads/client_secret.json)"
uv run jarvis mail login
```

`login` oeffnet ein Browserfenster und legt den Token danach ebenfalls in der
Keychain ab. Angefordert werden `gmail.modify`, `gmail.send` und seit Phase 5
`calendar.readonly`. Ein aelterer Token traegt das Kalenderrecht nicht -- dann
`jarvis mail login` einmal wiederholen.

---

## Befehle

| Befehl | Wirkung |
|---|---|
| `jarvis init` | Konfiguration und Datenbank anlegen |
| `jarvis status` | Stufe, Zaehler, Anbieter, Zustand |
| `jarvis stop --grund "..."` | jede ausgehende Aktion blockieren |
| `jarvis resume` | Stoppschalter loesen, mit Rueckfrage |
| `jarvis log -n 20` | letzte Protokolleintraege |
| `jarvis verify` | Hash-Kette des Protokolls pruefen |
| `jarvis mail login` | einmalige Anmeldung bei Gmail |
| `jarvis mail poll [-n N]` | einen Durchlauf ueber den Posteingang |
| `jarvis mail state` | was bisher beurteilt wurde |
| `jarvis mail labels` | fehlende Labels anlegen |
| `jarvis mail style [--refresh]` | Schreibstil zeigen oder neu ableiten |
| `jarvis mail draft [-n N]` | Antwortentwuerfe schreiben |
| `jarvis mail send [-n N]` | fertige Entwuerfe senden (verlangt Stufe 1) |
| `jarvis mail allowlist [--refresh]` | wer eine Antwort bekommen darf |
| `jarvis mail compare` | Entwuerfe gegen das Protokoll abgleichen |
| `jarvis calendar poll [--tage N]` | Termine lesen und auf Konflikte pruefen |
| `jarvis calendar state` | was im Fenster steht und was gefunden wurde |
| `jarvis briefing [--neu]` | das Briefing des Tages zeigen oder erzeugen |
| `jarvis web [--port N]` | Dashboard auf localhost starten |
| `jarvis voice check` | was fuer Sprache bereitsteht |
| `jarvis voice ask "..."` | einen getippten Satz durch dieselbe Kette |
| `jarvis voice hear <datei>` | eine fertige Aufnahme auswerten |
| `jarvis voice listen` | aufnehmen und antworten (eine Runde) |
| `jarvis daemon` | Dauerbetrieb nach `[daemon.schedule]` |
| `jarvis llm check` | nachmessen, was der auswertende Prozess noch kann |
| `jarvis services check [--live]` | Stand der externen Dienste, echter Kontakt auf Verlangen |

Der Stoppschalter ist eine Datei. Er wirkt auch ohne laufendes JARVIS:

```sh
touch ~/.jarvis/STOP
```

---

## Die vier Kernprinzipien, wie sie hier umgesetzt sind

**2.1 -- Das Modell waehlt niemals ein Ziel.** `OutputSchema` weist jedes
Schema zurueck, dessen Felder nach einem Ziel aussehen (`to`, `url`, `path`,
`iban` und weitere). Der eigentliche Schutz kommt spaeter aus `act()`, das
Ziele nur aus Originalheadern berechnet; die Namenspruefung ist die Reissleine
davor.

**2.2 -- Lesen und Handeln getrennt.** `Provider.complete()` nimmt Text und
gibt Text. Die Schnittstelle kennt keine Werkzeuge, keine Funktionsaufrufe,
keine Websuche -- was es nicht gibt, kann nicht benutzt werden. Seit
`[llm] isolation = "subprocess"` ist das nicht nur eine Zusage des Codes: der
Modellaufruf laeuft in einem eigenen Prozess ohne Gmail-Zugangsdaten und ohne
Weg zur Datenbank. Siehe [Prozesstrennung](#prozesstrennung-abschnitt-22).

**2.3 -- Fremde Inhalte sind Daten.** `sanitize()` normalisiert nach NFKC,
entfernt HTML samt Skriptinhalt, loescht unsichtbare Zeichen (Zero-Width,
Bidi-Steuerung, Unicode-Tags-Block), verdichtet Leerraum und kuerzt.
`as_untrusted_block()` rahmt das Ergebnis; die Rahmenmarker koennen im Inhalt
nicht vorkommen.

**2.4 -- Protokolliert und abschaltbar.** Jeder Eintrag in `audit_log` traegt
den Hash seines Vorgaengers; zwei SQLite-Trigger verbieten UPDATE und DELETE.
`jarvis verify` nennt die erste veraenderte Stelle. Ratenbegrenzung mit
rollenden Fenstern, Zaehlerstand in der Datenbank -- ein Neustart setzt sie
nicht zurueck.

---

## Autonomiestufen

Die Stufe steht in `config.toml` und gilt pro Faehigkeit. Alles startet auf 0.

| Stufe | Verhalten |
|---|---|
| 0 | Schattenbetrieb: entscheidet alles, sendet nichts |
| 1 | sendet an Adressen auf der Allowlist |
| 2 | sendet in freigegebenen Kategorien an bekannte Kontakte |
| 3 | sendet, ausser die Kategorie ist gesperrt |

`core/gate.py` ist die einzige Stelle, an der "darf ich nach aussen handeln"
beantwortet wird: Stoppschalter, dann Stufe, dann Ratenbegrenzung. Jeder
Aufruf hinterlaesst einen Protokolleintrag, auch der abgelehnte. Im
Trockenlauf wird die Begrenzung ausgewertet, aber nicht verbraucht -- so
zeigt der Schattenbetrieb, wann sie gegriffen haette.

---

## Modelle

`config.toml` ordnet Aufgaben Anbieterketten zu. Faellt einer aus, folgt der
naechste. Eine als `confidential` markierte Aufgabe darf nur lokale Anbieter
enthalten; das wird beim Laden der Konfiguration und noch einmal im Router
geprueft.

Gebaut sind: `anthropic` (offizielles SDK), `ollama` (lokal, Standard-
bibliothek) und `static` -- ein Anbieter, der immer dasselbe sagt und damit
Trockenlaeufe ohne Netz und ohne Schluessel moeglich macht.

---

## Entwickeln

```sh
uv sync            # installiert auch pytest und ruff
uv run pytest
uv run ruff check .
uv run ruff format .
```

---

## Phase 2: Postfach lesen

Ein Durchlauf geht immer denselben Weg:

1. **Suchen** -- der Gmail-Ausdruck aus `[skills.mail].query`, standardmaessig
   `is:unread in:inbox`, hoechstens `max_per_run` Nachrichten.
2. **Aussortieren** -- schon beurteilte Nachrichten fallen raus.
3. **Normalisieren** -- Betreff und Text zusammen durch `sanitize()`.
4. **Vorfilter** -- was aus den Kopffeldern folgt, entscheidet sich ohne
   Modell: List-Unsubscribe ist ein Newsletter, Auto-Submitted eine
   Benachrichtigung, eigene Post wird uebersprungen.
5. **Klassifizieren** -- der Rest geht ans Modell, mit erzwungenem Schema.
6. **Gatter** -- Stoppschalter, Stufe, Obergrenze.
7. **Einordnen** -- ein Label, ausschliesslich unterhalb von `JARVIS/`.

### Warum das Modell kein Ziel waehlt

Das Modell darf genau eine Kategorie aus einer geschlossenen Aufzaehlung
nennen. Welches Label daraus wird und welche Nachricht es bekommt, rechnet
danach deterministischer Code aus der Gmail-Kennung und der Zuordnung
Kategorie -> Label. Eine praeparierte Mail kann die Kategorie also
verschieben -- mehr nicht. Sie kann keinen Empfaenger, kein anderes Postfach
und keine andere Nachricht benennen, weil im Ausgabeschema kein Feld dafuer
existiert und `Decision` ein solches Feld zurueckweist.

### Warum der Client nicht senden kann

Die Zustimmung umfasst `gmail.send`, der Token koennte also senden. "Wir rufen
die Stelle einfach nicht auf" ist eine Zusage, die ein Tippfehler bricht.
`GmailClient` prueft deshalb jeden Pfad gegen eine Liste erlaubter Endpunkte;
`/messages/send`, Entwuerfe, Papierkorb und die Weiterleitungseinstellungen
stehen nicht darauf.

### Die Beobachtungswoche

Solange `dry_run = true` ist, wird beurteilt und protokolliert, aber im
Postfach veraendert sich nichts -- nicht einmal ein Label entsteht. Das ist der
Probelauf aus Phase 2:

```sh
uv run jarvis mail poll      # taeglich, oder oefter
uv run jarvis mail state     # was bisher herauskam
uv run jarvis log -n 40      # warum
```

Wenn das Protokoll plausibel aussieht, `dry_run = false` setzen. Das schaltet
das Einordnen frei -- und nur das: `mail_reply` bleibt auf Stufe 0 und
abgeschaltet, Senden gibt es in dieser Phase ohnehin nicht im Code.

---

## Phase 3: Antworten

Zwei getrennte Faehigkeiten, weil die Stufe laut Abschnitt 3 pro Faehigkeit
gilt und die beiden Schritte unterschiedlich riskant sind:

| Faehigkeit | Tut | Ausgehend | Braucht |
|---|---|---|---|
| `mail_reply` | schreibt einen Entwurf ins eigene Postfach | nein | Stufe 0 |
| `mail_send` | sendet einen bestehenden Entwurf | ja | Stufe 1 |

So laesst sich der Entwurfsteil in Ruhe beobachten, waehrend Senden weiter
unmoeglich ist. Der uebliche Ablauf:

```sh
uv run jarvis mail poll                  # einordnen
uv run jarvis mail draft                 # Entwuerfe schreiben
uv run jarvis mail compare               # Entwurf gegen Protokoll abgleichen
uv run jarvis mail allowlist --refresh   # bekannte Kontakte zaehlen
uv run jarvis mail send                  # sendet erst ab Stufe 1
```

### Die Umschaltung auf Stufe 1

In `config.toml`:

```toml
[capabilities.mail_send]
autonomy_level = 1
```

Dieser eine Wert tut zwei Dinge. Er laesst das Gatter Aktionen durch -- und er
entscheidet, mit welchen Rechten der Gmail-Client ueberhaupt gebaut wird.
Solange dort 0 steht, bekommt der Client kein Senderecht: `POST /drafts/send`
wird abgewiesen, bevor die Anfrage hinausgeht. Senden ist dann nicht bloss
unterlassen, sondern nicht erreichbar.

Gesendet wird ausserdem nur ueber `/drafts/send`, nie ueber `/messages/send`.
Es geht also genau der Entwurf hinaus, der vorher dastand und geprueft werden
konnte -- keine zweite, frisch gebaute Nachricht.

### Wohin die Antwort geht

Der Empfaenger kommt aus `Reply-To`, ersatzweise aus `From` der
Originalnachricht -- aus Kopffeldern also, nie aus dem Text. Das Modell
liefert ausschliesslich den Fliesstext und sieht `compose.py` nie.

Die gefaehrlichste Stelle ist der Betreff: er stammt vom Absender und wird in
einen Kopf zurueckgeschrieben. Ein Zeilenumbruch darin waere sonst eine
Blindkopie an den Angreifer. Jeder Wert, der in ein Kopffeld geht, wird
deshalb vorher von allem befreit, was eine Zeile beenden koennte -- CR, LF,
NUL, NEL sowie Zeilen- und Absatztrenner.

Nach dem Modell laeuft eine deterministische Nachpruefung. Ein Entwurf wird
zur Durchsicht zurueckgehalten, wenn er einen Link enthaelt (`allow_links`),
eine fremde Adresse nennt, laenger als `max_words` ist, oder das Modell selbst
`braucht_menschen` gesetzt hat. Zurueckgehaltene Entwuerfe werden nie
automatisch gesendet -- sie liegen im Postfach und warten auf dich.

### Schreibstil

`jarvis mail style --refresh` liest die gesendeten Nachrichten einmal durch und
speichert daraus **nur Kennzahlen und Bezeichner aus einem festen Katalog**:
Sprache, Du oder Sie, uebliche Begruessung, uebliche Grussformel, Satzlaenge,
Antwortlaenge. Kein Satz aus deinem Briefwechsel wird gespeichert, und keiner
geht an ein Modell -- was das Modell sieht, ist eine aus diesen Kennzahlen
zusammengesetzte Beschreibung. Die Auswertung selbst laeuft ohne Modell.

### Allowlist

Sie fuellt sich aus deinen gesendeten Nachrichten: wer oft genug von dir
gehoert hat, gilt als bekannter Kontakt. Das ist bequem, macht die Liste aber
zu einer Statistik statt zu einer Entscheidung. Drei Bremsen halten dagegen:

- **Mindestzahl** (`allowlist_threshold`, Vorgabe 3) -- ein einzelner
  Hoeflichkeitsgruss genuegt nicht.
- **Sperrliste** (`allowlist_blocked`) -- gewinnt immer, auch gegen hundert
  gesendete Nachrichten. Ganze Domains als `"@example.com"`.
- **Nur auf Befehl** -- die Liste aendert sich bei
  `jarvis mail allowlist --refresh`, nie beilaeufig waehrend eines Durchlaufs.

### Die Abnahmebedingung

*"Trockenlauf-Protokoll und tatsaechliche Entwuerfe stimmen ueberein."*

Jeder geplante Entwurf bekommt einen Fingerabdruck ueber Empfaenger, Betreff,
Referenzen und Text. `jarvis mail compare` holt die tatsaechlich im Postfach
liegenden Entwuerfe, rechnet ihren Fingerabdruck neu aus und vergleicht.
Abweichungen werden benannt; der Befehl endet mit Fehlercode, wenn es welche
gibt.

### Eine bewusste Abweichung

Die Entwuerfe schreibt das Cloud-Modell (`[llm.tasks.draft]`), nicht das
lokale. Abschnitt 5.2 verlangt fuer sensible persoenliche Daten ein lokales
Modell, und ein Antwortentwurf ist ziemlich genau das. Die Entscheidung fiel
bewusst zugunsten der Textqualitaet. Umstellen laesst sie sich in einer Zeile:

```toml
[skills.mail_reply]
task = "personal"     # vertraulich, nur Ollama
```

---

## Phase 4: Dashboard

```sh
uv run jarvis web
```

Gibt eine Adresse mit Sitzungstoken aus. Drei Ansichten -- Zustand,
Entscheidungen, Protokoll -- und genau drei Dinge, die sich ausloesen lassen:
freigeben, verwerfen, anhalten. Durchlaeufe startet weiter die Kommandozeile;
eine Oberflaeche, die Modellaufrufe ausloesen kann, ist etwas anderes als eine,
die nur bestaetigt.

### Anstehende Entscheidungen

Was nicht von selbst durchging, wandert in eine Warteschlange, sofern die
Faehigkeit das sammelt:

```toml
[capabilities.mail_reply]
collect_approvals = true
```

Eine Freigabe ersetzt die **Autonomiestufe** -- mehr nicht. Stoppschalter,
Ein-Aus-Schalter und Obergrenze gelten weiter, und der globale Trockenlauf
ebenfalls: `dry_run = true` heisst "nichts geht hinaus", auch wenn jemand
klickt. Die Seite sagt das an der Stelle, an der sonst der Knopf waere.

Greift eine dieser Sperren, bleibt der Vorgang offen und traegt den Grund als
Vermerk. Nochmal klicken kostet dann nichts, und niemand muss raten, warum
nichts geschah.

Beim Freigeben wird die urspruengliche Entscheidung aus der Datenbank wieder
aufgebaut -- ueber den regulaeren Weg, nicht per Umgehung. `Decision` prueft
dabei erneut, dass in der Modellhaelfte kein Ziel steckt. Eine von Hand
veraenderte Zeile in der Datenbank kommt damit nicht an Prinzip 2.1 vorbei.

### Absicherung

Die Oberflaeche kann E-Mails freigeben. Eine Bindung an 127.0.0.1 allein
reicht dafuer nicht: jede beliebige Webseite in deinem Browser darf ein
Formular an localhost abschicken, und der Browser tut es.

- **Sitzungstoken** in `~/.jarvis/web-token` (Rechte 0600). Ohne ihn
  antwortet der Server nichts. Beim ersten Aufruf wandert er aus der
  Adresszeile in ein Cookie, damit er nicht im Verlauf stehen bleibt.
- **Herkunftspruefung** bei jeder veraendernden Anfrage. Fehlen Origin und
  Referer, wird abgelehnt.
- **Content-Security-Policy** ohne Skripte, ohne fremde Quellen, ohne
  Einbettung in fremde Rahmen.
- **`web.host`** laesst nur Loopback zu (`127.0.0.1`, `localhost`, `::1`).
  Das gilt fuer die Konfigurationsdatei *und* fuer `--host`: beide gehen durch
  dieselbe Pruefung, sonst waere die Sperre ueber einen Schalter zu umgehen.

Das Protokoll zeigt Betreffzeilen aus fremden Mails. Jeder Wert, der auf die
Seite geht, wird maskiert -- ungefiltertes Markup waere hier kein
Schoenheits-, sondern ein Sicherheitsfehler.

---

## Zustaende, Gedaechtnis, Kontext

### Eine Nachricht hat vier Zustaende

| Zustand | Bedeutung | Kommt wieder |
|---|---|---|
| `seen` | geholt, noch nicht beurteilt | ja |
| `analysed` | beurteilt, aber nichts getan | ja |
| `acted` | tatsaechlich gehandelt | nein |
| `skipped` | endgueltig nichts zu tun | nein |

Nur `acted` und `skipped` schliessen aus. Ein Trockenlauf setzt `analysed` --
die Nachricht bleibt damit fuer den spaeteren echten Lauf offen. Frueher galt
sie nach dem Trockenlauf als verarbeitet, und die Beobachtungswoche hat den
Posteingang still verbrannt.

Der zweite Durchlauf fragt das Modell nicht erneut: eine bereits gefaellte
Beurteilung wird wiederverwendet (`decided_by = cached`). Beobachten kostet
damit einmal, nicht stuendlich.

### Speicherung und Kontext sind getrennt

Was JARVIS aufbewahrt, waechst mit der Nutzungsdauer. Was bei einer Anfrage
ans Modell geht, darf das nicht.

- **Langzeitgedaechtnis** (`memory_facts`) -- wenige, ausdruecklich abgelegte
  Tatsachen. Keine Gespraechsgeschichte.
- **Kurzzeitkontext** (`context_entries`) -- ein knapper Verlauf je Bereich,
  der sich beim Schreiben selbst beschneidet.
- **Kontextbauer** -- die einzige Stelle, die entscheidet was mitgeht, unter
  einer harten Obergrenze.

Protokoll und technische Logs sind **keine** Quelle des Kontextbauers. Ein
Test prueft das strukturell.

```sh
uv run jarvis memory                      # was dauerhaft abgelegt ist
uv run jarvis memory ton foermlich --kategorie praeferenz
uv run jarvis memory --vergessen ton
uv run jarvis context --suche "Termin"    # was bei einer Anfrage mitginge
```

`jarvis context` zeigt genau den Text, der in den Prompt ginge, samt
Obergrenze und dem, was weggelassen wurde. Ohne diesen Befehl waere die
Begrenzung eine Behauptung.

### Integritaet vor dem Versand

Vor jedem Versand wird der Entwurf aus dem Postfach geholt und sein
Fingerabdruck neu gerechnet. Weichen Empfaenger, Betreff, Thread oder Text
vom geprueften Stand ab, geht nichts hinaus -- geprueft in `decide` und noch
einmal unmittelbar vor `send_draft`, weil zwischen Freigabe und Versand Tage
liegen koennen.

### Aufbewahrte Ziele werden neu berechnet

Eine Entscheidung, die in der Warteschlange lag, ist keine vertrauenswuerdige
Quelle. `Skill.verify_targets` baut die Ziele aus der Quelle neu -- Empfaenger
aus den Originalkopffeldern, Label aus der Kategorie, Entwurf aus dem
Antwortspeicher. Die Vorgabe der Basisklasse verweigert, sobald es Ziele gibt:
eine Faehigkeit, die das vergisst, faellt auf.

### "Lokal" ist pruefbar

Ein Anbieter mit `local = true` muss auf eine Loopback-Adresse zeigen. Die
Konfiguration weist alles andere ab, und der Anbieter prueft es beim Bauen ein
zweites Mal. Damit stuetzt sich die Vertraulichkeitssperre aus Abschnitt 5.2
auf eine gepruefte Zusage statt auf eine Behauptung.

### Ein Berechtigungsmodell

`Config.permits(faehigkeit, stufe, approved=...)` ist die einzige Stelle, die
beantwortet ob gehandelt werden darf. Das Gatter fragt dort, und die Fabrik
fragt dort, wenn sie entscheidet welche Rechte ein Gmail-Client bekommt. Eine
Freigabe von Hand wirkt damit auf beide -- frueher liess das Gatter durch, was
der Client danach nicht durfte.

---

## Phase 5: Kalender und Briefing

Zwei neue Faehigkeiten, beide auf Stufe 0 und beide nicht ausgehend: `calendar`
liest den Kalender und findet Konflikte, `briefing` fasst den Tag zusammen.
Keine von beiden erreicht einen Menschen -- sie aendern nur, was JARVIS weiss
und morgens sagt.

```sh
jarvis mail login          # einmal neu: der Token traegt jetzt auch das
                           # Kalenderrecht (calendar.readonly)
jarvis calendar poll       # Termine der naechsten Tage ansehen
jarvis calendar state      # was gefunden wurde
jarvis briefing --neu      # Briefing fuer heute erzeugen
jarvis briefing            # es spaeter noch einmal lesen
```

Im Dashboard steht es unter *Briefing*. Erzeugt wird dort nichts: die
Oberflaeche liest den Zustand und gibt einzelne Entscheidungen frei, sie
startet keine Durchlaeufe.

### Konflikte sind eine Rechnung, keine Frage ans Modell

`find_conflicts` bekommt Zeiten, Status und Antwortzustaende -- keinen Text.
Ob sich zwei Termine ueberschneiden, ist Arithmetik. Ein Modell dafuer zu
fragen waere teurer, langsamer und von aussen beeinflussbar: Titel, Ort und
Beschreibung bestimmt der Einladende, nicht du. `CalendarSkill` ruft deshalb
gar keinen Anbieter; `decided_by` ist immer `rule`.

Ganztaegige, abgesagte und von dir abgelehnte Termine belegen keine Zeit --
sonst meldete JARVIS jeden Feiertag als Konflikt mit jeder Besprechung.

Titel gehen durch `sanitize`, bevor sie irgendwo landen. Ein Kalendereintrag
ist ein sehr bequemer Weg, fremden Text in ein System zu bekommen.

### Ein Befund verschwindet wieder

Konflikte sind kein Dauerzustand: wer einen Termin verschiebt, loest ihn auf.
Beim naechsten Durchlauf raeumt `clear_stale_findings` weg, was nicht mehr
gilt -- und mit dem Befund faellt auch `acted` weg. Was nicht gemeldet ist,
gilt nicht als gemeldet; kehrt der Konflikt zurueck, wird er wieder
aufgegriffen.

Verglichen wird dabei der **Befund selbst**, nicht die blosse Tatsache, dass
ein Termin noch irgendwie kollidiert. Die erste Fassung fragte nur Letzteres
und hatte damit einen Fehler, den erst die Durchsicht fand:

```
Montag:    A <-> B     Befund auf A: "A ueberschneidet sich mit B"
Dienstag:  B verschoben, C neu.  Jetzt A <-> C
           A steckt weiter in einem Konflikt -- also blieb A unangetastet
           und behielt den Satz ueber B.
```

Das Briefing warnte danach vor einem Termin, den es nicht mehr gab, *und*
nannte den echten Konflikt ein zweites Mal. Jetzt bestimmt eine einzige
Stelle -- `CalendarSkill._befunde()` -- welcher Befund fuer einen Termin gilt;
`poll`, `decide` und `verify_targets` fragen dort. Stimmt der gespeicherte
Satz nicht mehr damit ueberein, faellt er weg.

Ein konfliktfreier Termin bleibt aus demselben Grund auf `analysed` statt auf
`skipped`: morgen kann ein neuer Termin daneben liegen. Nur ein festgehaltener
Befund ist endgueltig.

### Zeit wird in UTC abgelegt und in Ortszeit gezeigt

Zwei getrennte Dinge, die leicht durcheinandergehen:

**Gespeichert wird UTC.** Google liefert Ortszeit mit Versatz
(`09:00+02:00`). Solche Texte lassen sich nicht vergleichen -- `09:00+02:00`
steht *vor* `23:00+00:00`, ist aber spaeter. Genau so vergleicht SQLite sie
aber, wenn ein Zeitfenster abgefragt wird. `as_utc_text` normalisiert deshalb
beim Schreiben, damit die Textreihenfolge wieder die zeitliche ist.

**Gerechnet und gezeigt wird in deiner Zone.** Der Tag endet um Mitternacht
auf deiner Uhr, nicht in Greenwich -- sonst faellt der Termin um halb eins
nachts in den Vortag und taucht im Morgenbriefing gar nicht auf. Die Zone
steht in der Konfiguration:

```toml
timezone = "Europe/Berlin"   # leer = die dieses Rechners
```

Leer heisst: aus `TZ` beziehungsweise `/etc/localtime` ermittelt, sonst der
aktuelle Versatz. Ein Tippfehler ist ein Fehler, kein stiller Rueckfall auf
UTC. Eine benannte Zone ist robuster als ein Versatz, weil sie ihre
Sommerzeit kennt.

**Ganztaegige Termine haben ein Datum, keinen Zeitpunkt.** Sie werden auf
oertliche Mitternacht verankert, nicht auf UTC-Mitternacht. Sonst laege der
Feiertag westlich von Greenwich vor seinem eigenen Tag und fiele aus dem
Briefing -- in Berlin faellt das nicht auf, in New York schon.

### Das Briefing haengt nicht am Anbieter

Die Tatsachen rechnet Code aus: welche Termine heute anstehen, welche
Konflikte gefunden wurden, wie viele Mails auf eine Antwort warten, welche
davon schon laenger liegen als `overdue_days`. Das Modell formuliert daraus
einen Text -- mehr nicht. Es waehlt nicht aus, was wichtig ist, und es holt
sich nichts dazu.

Faellt die ganze Anbieterkette aus, entsteht das Briefing trotzdem: dann in
der deterministischen Fassung (`decided_by = "fallback"`, `Quelle: ohne
Modell`). Ein Morgenbriefing, das an einem Ausfall haengt, ist keins.

`verify_targets` rechnet die Tatsachen aus dem Speicher neu, bevor gehandelt
wird; nur der formulierte Text bleibt stehen. Der Tag muss der heutige sein,
und ein leeres Briefing wird abgewiesen.

### Der Kalender-Client kann nicht schreiben

Wie bei Gmail: eine Endpunkt-Allowlist, die aus den mitgegebenen Faehigkeiten
folgt. `CALENDAR_READ` laesst drei GET-Aufrufe zu, sonst nichts. Es gibt
keinen Schreibpfad im Code, und der Client wuerde ihn ohnehin abweisen.

`calendar.readonly` ist neu im Token. Ein bestehender Token traegt sie nicht;
`jarvis calendar poll` sagt das dann und nennt den Weg, statt in einen Fehler
zu laufen, den niemand zuordnen kann.

---

## Phase 6: Sprache

Eine dritte Bedienweise neben Kommandozeile und Dashboard, kein Ersatz fuer
sie. Sie liegt unter `interfaces/voice/`, nicht unter `skills/` -- Sprache ist
eine Art zu bedienen, keine Faehigkeit.

```sh
jarvis voice check                       # was bereitsteht
jarvis voice ask "Jarvis, wie ist der Stand"   # ohne Mikrofon pruefen
jarvis voice hear aufnahme.wav           # eine fertige Aufnahme
jarvis voice listen                      # aufnehmen und antworten
```

### Der Satz, an dem alles haengt

> **Sprache liest vor. Sprache handelt nicht.**

Ein Mikrofon ist kein angemeldeter Eingabekanal. Was an der Tastatur getippt
wird, kommt von jemandem, der davorsitzt. Was das Mikrofon hoert, kommt aus
dem Raum: vom Fernseher, aus einer Videokonferenz, von Besuch, aus einem
Podcast. Ein Transkript ist damit genau das, was Abschnitt 2.3 meint --
fremder Text.

Deshalb gibt es sechs Absichten und sonst keine:

| Absicht | Wirkung |
|---|---|
| `status` | Zustand vorlesen |
| `briefing` | Briefing des Tages vorlesen |
| `offen` | wie viele Vorgaenge zur Freigabe stehen |
| `anhalten` | Stoppschalter setzen |
| `handeln` | erkannt und **verweigert** |
| `unbekannt` | nachfragen |

`handeln` ist die wichtigste davon. "Schick die Entwuerfe ab" wird verstanden,
im Protokoll festgehalten und abgelehnt -- mit dem Hinweis aufs Dashboard. Es
gibt im Sprachpfad keinen Code, der senden koennte; ein Test prueft
strukturell, dass die dafuer noetigen Bausteine dort gar nicht vorkommen.

### Anhalten geht, fortsetzen nicht

Die Richtung entscheidet. Ein Podcast, der JARVIS anhaelt, ist ein Aergernis:
man merkt es und gibt von Hand frei. Ein Podcast, der ihn wieder freigibt,
waere eine Luecke. `jarvis resume` bleibt deshalb Tastatur und Dashboard
vorbehalten, und "mach weiter" faellt unter `handeln`.

### Kein Gatter, mit Absicht

Sprache laeuft nicht durchs Gatter. Das Gatter blockiert bei gesetztem
Stoppschalter jede Aktion -- richtig fuer alles, was hinausgeht, falsch fuer
eine Frage nach dem Zustand: wer angehalten hat, will hoeren koennen, warum.

Der Schutz liegt nicht im Gatter, sondern darin, dass es keine ausgehende
Aktion gibt, die zu bewachen waere. Die Ratenbegrenzung wird trotzdem gefragt,
aber nur fuer den Modellrueckfall -- damit ein Dauerlauf am Mikrofon keine
Kosten treibt. Die Regeln unterliegen ihr nicht: "anhalten" muss auch dann
noch gehen, wenn die Obergrenze erreicht ist.

### Regeln zuerst, Modell nur als Rueckfall

Erkannt wird mit Wendungen, deterministisch und ohne Netz. Erst was keine
Regel trifft, geht ans Modell -- und auch dann nur als geschlossene
Aufzaehlung:

```json
{"absicht": {"enum": ["status", "briefing", "offen", "anhalten", "handeln", "unbekannt"]}}
```

Kein freier Text, keine Kennung, kein Ziel. Die Zielfeldsperre aus
`llm/schema.py` haette ein solches Feld ohnehin abgewiesen. Das Modell darf
eine von sechs Absichten benennen; die Antwort baut danach Code aus dem
tatsaechlichen Zustand.

`[llm.tasks.voice]` ist `confidential = true` und damit auf lokale Anbieter
festgelegt: was im Raum gesagt wird, verlaesst diesen Rechner nicht. Die
Konfiguration prueft das beim Laden, der Router noch einmal.

### Was vorgelesen wird, hoert jeder im Raum

Das begrenzt die Ausgabe. Vorgelesen werden der eigene Zustand und das eigene
Briefing. Bei `offen` nennt JARVIS **wie viele** Vorgaenge warten und von
welcher Faehigkeit -- nicht ihre Betreffzeilen:

```
Ein Vorgang zur Freigabe: 1 mail_reply. Ansehen im Dashboard.
```

Das Briefing ist die Ausnahme, und zwar die gewollte: es vorzulesen ist sein
Zweck. Mailinhalte werden nicht vorgelesen.

### Whisper laeuft lokal, und nur lokal

Es gibt keinen Umwandler, der Audio irgendwohin schickt -- nicht weil einer
schwer zu bauen waere, sondern weil ein Arbeitszimmermikrofon alles aufnimmt,
was im Raum gesprochen wird. Was es nicht gibt, kann nicht versehentlich
benutzt werden; dasselbe Argument wie bei den Werkzeugen in Abschnitt 2.2. Ein
Test prueft, dass in `transcribe.py` kein `urlopen` und kein HTTP-Client
vorkommt.

`whisper.cpp` wird als Programm aufgerufen, nicht als Python-Paket: schnell
auf Apple Silicon und ohne PyTorch im Projekt. Aufnahme, Umwandlung und
Ausgabe laufen ueber Argumentlisten, nie ueber eine Shell.

### Einrichten auf dem Mac

```sh
brew install whisper-cpp sox          # sox liefert "rec"
# ein Modell holen, etwa ggml-base.bin
```

```toml
[voice]
wake_word = "jarvis"
whisper_model = "/Users/du/.jarvis/ggml-base.bin"
record_command = ["rec", "-q", "-r", "16000", "-c", "1", "{datei}", "trim", "0", "6"]
```

`{datei}` wird durch den Pfad der Aufnahme ersetzt; fehlt der Platzhalter,
weist der Recorder den Befehl ab, statt ins Leere aufzunehmen. `jarvis voice
check` sagt, was noch fehlt.

Das Weckwort ist ein Filter gegen Zufall, **keine Sicherung** -- ein Podcast
kann "Jarvis" sagen. Die Sicherung ist die Absichtsliste oben.

### Was hier noch nicht ist

Eine Dauerschleife am Mikrofon. `jarvis voice listen` macht genau eine Runde:
aufnehmen, umwandeln, antworten. Dauerhaftes Zuhoeren gehoert in den Daemon,
den es noch nicht gibt -- und es ist die Art Funktion, die man nicht nebenbei
einschaltet.

---

## Prozesstrennung (Abschnitt 2.2)

Die Spezifikation verlangt, dass der Teil, der fremde Inhalte verarbeitet,
weder Werkzeugzugriff noch einen Weg zum handelnden Teil hat. Logisch war das
von Anfang an so -- `Provider.complete()` bietet gar nichts anderes an. Aber es
war eine Eigenschaft des Codes, nicht des Betriebssystems: ein Fehler im
Auswertungspfad steckte im selben Prozess wie die Gmail-Zugangsdaten.

Jetzt laeuft der Modellaufruf woanders:

```
Elternprozess                        Kindprozess
  Gmail, Kalender, Keychain            nur der eine Modellschluessel
  Datenbank, Gatter, Protokoll         keine JARVIS_-Variablen, leeres HOME
  berechnet die Ziele                  sieht kein Ziel
        |                                     ^
        |  Text + Schema  (stdin)             |
        +------------------------------------>+
        |  JSON            (stdout)           |
        +<------------------------------------+
```

### Was jede Stufe wirklich leistet

Hier stand vorher "kein Weg zur Datenbank". Das war zu stark, und die Messung
hat es widerlegt: `subprocess` nimmt dem Kind die Umgebungsvariablen und die
Code-Pfade, **nicht** den Dateizugriff. Wer im Kind einen absoluten Pfad
oeffnet, kommt an `~/.jarvis` heran. Erst `sandbox` laesst das Betriebssystem
nein sagen.

`jarvis llm check` misst das nach -- einmal ohne Trennung als Vergleichswert,
einmal mit. Auf diesem Entwicklungsrechner (Linux, kein `sandbox-exec`):

```
PRUEFUNG                GEERBT      SUBPROCESS
~/.jarvis lesen         moeglich    moeglich
state.db lesen          moeglich    moeglich
Netz nach aussen        moeglich    moeglich
JARVIS-Variablen        2 sichtbar  0 sichtbar
```

Was `subprocess` damit tatsaechlich garantiert:

* keine `JARVIS_`-Variable im Kind, also auch kein Gmail-Token aus der
  Umgebung und kein Zeiger auf das Basisverzeichnis
* ein leeres `HOME`, das nach dem Aufruf verschwindet
* der Modellschluessel ueber die Standardeingabe statt ueber `ps`
* keine Faehigkeit, kein Gatter, keine Datenbankanbindung im Kind: die
  Module werden dort nicht importiert

Was es **nicht** garantiert: dass das Kind keine Datei oeffnen kann. Dafuer
ist `sandbox` da, und die ist auf macOS nicht nachgemessen (siehe unten).

### Drei Stufen

```toml
[llm]
isolation = "subprocess"   # off | subprocess | sandbox
```

| | |
|---|---|
| `off` | alles in einem Prozess. Schnell, aber 2.2 gilt dann nur als Zusage des Codes. |
| `subprocess` | **Standard.** Eigener Prozess mit gefilterter Umgebung. |
| `sandbox` | zusaetzlich `sandbox-exec` unter macOS -- dann verweigert das Betriebssystem den Zugriff, nicht der Code. |

`jarvis status` zeigt in der Spalte TRENNUNG, was tatsaechlich gilt, und sagt
es hin, wenn die Trennung aus ist.

### Die Umgebung ist eine Allowlist, keine Sperrliste

Eine Sperrliste waere die falsche Richtung -- man vergisst darin immer etwas.
Durchgereicht wird nur, was das Kind braucht, um den Anbieter zu erreichen
(`PATH`, Proxy- und Zertifikatsvariablen). Alles andere bleibt draussen,
insbesondere alles mit `JARVIS_` im Namen. `HOME` zeigt auf ein leeres
Verzeichnis, das nach dem Aufruf wieder verschwindet.

Der Unterschied im Betrieb, mit einem echten Token im Elternprozess:

```
Kind ueber child_env()    : jarvis_vars=[]  home=/tmp/jarvis-llm-...  token sichtbar: false
Kind mit geerbter Umgebung: jarvis_vars=[JARVIS_HOME, JARVIS_SECRET_GMAIL_TOKEN]  token sichtbar: true
```

Der Modellschluessel geht ueber die **Standardeingabe**, nicht ueber Umgebung
oder Kommandozeile -- dort stuende er in `ps`.

### Was im Kind fehlt

`llm/isolated.py` importiert keine Faehigkeit, kein Gatter, keine
Datenbankanbindung und keinen Schluesselbund. Es baut genau einen Anbieter mit
genau einem Geheimnis und stellt genau eine Anfrage. Ein Test prueft das
strukturell -- das ist eine Aussage ueber die Code-Pfade, nicht ueber die
Rechte des Prozesses.

Faellt dort etwas aus, kommt es als JSON zurueck, nicht als Prozessabsturz --
und die Fehlerart (`unavailable`, `timeout`, `refused`) ueberlebt den
Prozesswechsel, damit die Rueckfallkette des Routers weiter greift.

### Der statische Anbieter bleibt drin

`StaticProvider` antwortet mit einer Konstanten, ohne Netz und ohne den Text
anzusehen. Dort gibt es nichts zu trennen, und ein Prozessstart je Aufruf
waere reine Kosten in Tests und Trockenlaeufen. `jarvis status` schreibt bei
ihm `-- (ohne Netz)`.

### Was das kostet

Ein Prozessstart je Modellaufruf, gemessen rund 100 ms. Fuer einen Assistenten,
der ein paar Dutzend Mails am Tag einordnet, ist das nicht spuerbar; wer es
anders sieht, setzt `isolation = "off"` und sieht die Folge in `jarvis status`.

---

## Dauerbetrieb

Der Daemon ist eine Uhr, kein zweites Gehirn. Er ruft dieselben Durchlaeufe
auf, die auch die Kommandozeile aufruft. Autonomiestufen, Gatter,
Ratenbegrenzung und Stoppschalter gelten unveraendert -- er darf nichts, was
`jarvis mail poll` nicht auch duerfte.

```toml
[daemon]
enabled = false        # bleibt aus, bis du es umlegst
tick_seconds = 30

[daemon.schedule]      # Faehigkeit = Abstand in Minuten
mail = 15
calendar = 60
briefing = 60
```

```sh
jarvis daemon          # im Vordergrund, Strg-C beendet
```

**Was nicht im Zeitplan steht, laeuft nicht.** `mail_reply` und `mail_send`
fehlen dort absichtlich: was Entwuerfe schreibt oder sendet, laeuft erst dann
von selbst, wenn du ihm eine Weile zugesehen hast. Ein neuer Eintrag ist eine
bewusste Zeile in der Konfiguration, kein Nebeneffekt.

### Wie er sich verhaelt

| | |
|---|---|
| **Einzelinstanz** | Sperrdatei mit `flock`. Eine zweite Instanz endet mit Code 3 und nennt die PID der ersten. Nach einem Absturz gibt das Betriebssystem die Sperre frei -- eine liegengebliebene Datei blockiert nichts. |
| **Beenden** | SIGTERM oder SIGINT setzen eine Fahne; der laufende Durchlauf endet, dann ist Schluss. Gemessen: rund 1 s, unabhaengig vom Takt. |
| **Stoppschalter** | Vor jedem Job geprueft. Ist er gesetzt, faengt der Job gar nicht erst an -- auch nicht mit dem Beurteilen. Das Gatter prueft danach noch einmal. |
| **Fehler** | Ein gescheiterter Job wird protokolliert, der Daemon laeuft weiter. Ein Fehler im Tick selbst ebenso. |
| **Neustart** | Der Zeitpunkt des letzten Laufs steht in der Datenbank, nicht im Speicher. Ein Daemon in einer Neustartschleife arbeitet den Plan nicht jedesmal von vorn ab. |
| **Fehlgeschlagene Jobs** | zaehlen als Lauf. Sonst rennt der Daemon bei jedem Tick gegen dieselbe Wand. |

### Er kostet keine zusaetzlichen Modellaufrufe

Der Daemon fragt nie selbst ein Modell. Die Faehigkeiten entscheiden weiter,
wann sie eines brauchen, und die bestehende Sparsamkeit gilt unveraendert:
eine bereits beurteilte Mail wird wiederverwendet, ein vorhandenes Briefing
nicht neu geschrieben, Terminkonflikte sind ohnehin reine Rechnung. Ein Test
prueft, dass ein Durchlauf ohne neue Arbeit **null** Modellaufrufe ausloest.

Deshalb darf `briefing` auch stuendlich im Plan stehen: liegt das Briefing des
Tages schon vor, findet der Durchlauf nichts zu tun. Nebeneffekt: das Briefing
entsteht kurz nach Mitternacht, nicht um sieben. Wen das stoert, setzt den
Abstand hoch und laesst es zur gewuenschten Zeit von Hand laufen.

### launchd

`deploy/com.jarvis.daemon.plist` ist vorbereitet; drei Pfade darin sind
anzupassen.

```sh
cp deploy/com.jarvis.daemon.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jarvis.daemon.plist
launchctl bootout   gui/$(id -u)/com.jarvis.daemon     # anhalten
```

Bewusst gesetzt: `KeepAlive.SuccessfulExit = false`, damit `launchd` nach
einem sauberen Ende nicht sofort neu startet und gegen eine bewusste
Entscheidung ankaempft; `ThrottleInterval = 60`, damit ein Absturz keine
Neustartschleife wird.

Unabhaengig davon wirkt weiterhin sofort:

```sh
touch ~/.jarvis/STOP
```

---

## Externe Dienste: Betrieb ohne Konten

JARVIS spricht mit vier externen Diensten: Anthropic, Ollama, Gmail und Google
Calendar. Alle vier haben einen Adapter, alle vier lassen sich durch ein
Laufzeit-Doppel ersetzen.

```toml
[services]
mode = "live"      # live | mock
fixtures = ""      # eigene Beispieldaten als JSON, leer = eingebaute
```

Mit `mode = "mock"` laeuft der **ganze Weg** ohne einen einzigen Account:

```sh
jarvis mail poll        # 5 Beispielnachrichten, eingeordnet
jarvis calendar poll    # 5 Termine, zwei Konfliktarten
jarvis briefing --neu   # daraus ein Briefing
```

Dieselbe Fabrik, dasselbe Gatter, dasselbe Protokoll -- nur ohne Google.

### Der Mock ist kein Trockenlauf und kein Nachweis

Zwei Verwechslungen, gegen die hier gebaut ist:

**Mock ist nicht Trockenlauf.** Beide gelten unabhaengig voneinander. Im Mock
mit `dry_run = false` entstehen echte Eintraege in der eigenen Datenbank --
Labels, Befunde, Briefings. Nur eben ohne Google.

**Ein Mock beweist nichts ueber den echten Dienst.** Deshalb ruft kein Mock je
`merke_kontakt` auf; ein Test prueft, dass der Aufruf in beiden Mock-Modulen
gar nicht vorkommt. Und der Mock ist nie nachsichtiger als der echte Client:
wer ihn ohne Senderecht baut, kann auch dort nicht senden.

Der Mock-Modus ist an zwei Stellen laut sichtbar -- in `jarvis status` und in
`jarvis services check`. Ein Mock, den man nicht sieht, ist eine Falle: alles
sieht gruen aus, und nichts davon hat je einen echten Dienst erreicht.

### Vier Stufen, und die vierte wird gemessen

```sh
jarvis services check           # zeigt den Stand
jarvis services check --live    # versucht echten Kontakt und haelt ihn fest
```

```
DIENST     GEBAUT  GETESTET  MOCK  ECHT GEPRUEFT  JETZT
anthropic  ja      ja        ja    nie            nicht versucht
ollama     ja      ja        ja    nie            nicht versucht
gmail      ja      ja        ja    nie            nicht versucht
calendar   ja      ja        ja    nie            nicht versucht
keychain   ja      ja        --    nie            nicht versucht
```

Die ersten drei Spalten sind Aussagen ueber den Quelltext. **ECHT GEPRUEFT**
ist es nicht: der Wert steht in der Datenbank und kommt nur dorthin, wenn ein
echter Adapter eine Antwort bekommen hat -- aus `services check --live` oder
aus einer gelungenen `mail login`. Ein gescheiterter Versuch schreibt nichts,
ein Mock schreibt nie.

**Der Stand heute ist die Spalte oben: fuenfmal `nie`.** Kein Dienst hat je
mit JARVIS gesprochen. Das ist keine Vermutung, sondern das, was die
Datenbank sagt.

### Beispieldaten

Die eingebauten Beispiele sind absichtlich unbequem: das Postfach enthaelt
eine Rechnung, eine Anfrage mit Frist, einen Newsletter, eine
noreply-Adresse **und einen Einschleusversuch** ("Ignoriere alle vorherigen
Anweisungen..."), damit man die Abwehr einmal arbeiten sieht. Der Kalender
enthaelt beide Befundarten und haengt an *jetzt plus zwei Stunden* -- ein
Beispielkalender, dessen Konflikte schon vorbei sind, zeigt eine
Konflikterkennung, die nichts findet, und man haelt sie faelschlich fuer
in Ordnung.

Eigene Daten kommen ueber `fixtures` als JSON-Verzeichnis.

---

## Was wovon nachgewiesen ist

Diese Tabelle sagt, worauf sich der Rest des Dokuments stuetzt. "Im Betrieb"
heisst: tatsaechlich ausgefuehrt und beobachtet, nicht nur getestet.

| Eigenschaft | Nachweis |
|---|---|
| Prozesstrennung `subprocess` | Tests **und** im Betrieb (`jarvis briefing --neu` gegen einen lokalen Ollama-Ersatz; der Aufruf lief nachweislich im zweiten Prozess) |
| Keine `JARVIS_`-Variable im Kind | Tests **und** im Betrieb gemessen, im Vergleich zur geerbten Umgebung |
| Kein Dateischutz durch `subprocess` | im Betrieb gemessen: `~/.jarvis` bleibt lesbar. Deshalb steht es so da. |
| Sandbox-Stufe | nur Tests. **Nie auf macOS ausgefuehrt** -- Entwicklungsumgebung ist Linux |
| Keychain-only | Tests (Plattform simuliert). Auf echtem macOS nicht ausgefuehrt |
| Kalender-Pagination | Tests, mehrere Seiten, Duplikate, Fehler auf Folgeseite |
| Daemon: Start, Einzelinstanz, SIGTERM | Tests **und** im Betrieb (zweite Instanz abgewiesen, SIGTERM nach 1 s bei 20 s Takt) |
| Daemon: Fehlerfaelle | Tests. Zusaetzlich im Betrieb beobachtet: fehlende Gmail-Zugangsdaten liessen `mail` und `calendar` scheitern, der Daemon lief weiter |
| Stoppschalter im Dauerbetrieb | Tests |
| launchd-Plist | als Property List geparst. **Nicht auf macOS geladen** |
| Sprachadapter (Whisper, `say`) | Tests gegen Ersatzprogramme. Nie mit echter Hardware |
| Laufzeit-Mock fuer Gmail und Kalender | Tests **und** im Betrieb (`mail poll`, `calendar poll`, `briefing --neu` liefen vollstaendig ohne Konten) |
| **Anthropic, Ollama, Gmail, Calendar -- echt** | **Nie.** Kein Adapter hat je mit dem echten Dienst gesprochen. `jarvis services check` sagt es dir jederzeit. |

---

## Bewusst zurueckgestellt

Diese Stellen weichen wissentlich von der Spezifikation ab oder sind nicht
vollstaendig geprueft. Sie stehen hier,
damit aus einer Ausnahme nicht stillschweigend der Normalfall wird.

### Die Sandbox-Stufe ist auf macOS nicht nachgemessen

Das ist die wichtigste offene Stelle, und sie ist keine Nachlaessigkeit,
sondern eine Grenze der Entwicklungsumgebung: die ist Linux, `sandbox-exec`
gibt es nur unter macOS. Profil, Aufruf und Fehlerverhalten sind getestet;
**ausgefuehrt wurde `sandbox-exec` nie**.

Nachmessen laesst sich das in einem Schritt, auf deinem Mac:

```sh
jarvis llm check
```

Erwartet wird dort eine dritte Spalte SANDBOX, in der die ersten vier Zeilen
auf `verweigert` stehen und "Netz nach aussen" auf `moeglich`. Steht dort
etwas anderes, gilt die Stufe als nicht wirksam -- dann bitte melden, statt
sie zu benutzen.

Zwei Dinge, die auch bei erfolgreicher Messung gelten:

* **Das Netz bleibt offen.** Den Anbieter zu erreichen ist die einzige
  Aufgabe des Kindes, und `sandbox-exec` filtert nicht nach Zielhost. Der
  Schutz liegt darin, dass dort keine Zugangsdaten fuer etwas anderes liegen.
* **`sandbox-exec` gilt bei Apple als veraltet.** Es funktioniert weiter, aber
  Apple weist beim Aufruf darauf hin. Der von Apple unterstuetzte Weg waere
  die App Sandbox mit Entitlements, und die setzt eine signierte, gebuendelte
  Anwendung voraus -- das waere ein anderer Zuschnitt des ganzen Projekts.
  Solange JARVIS ein Kommandozeilenwerkzeug ist, ist `sandbox-exec` das, was
  die Plattform hergibt. Diese Einschaetzung stammt aus der Dokumentationslage
  und ist hier nicht gegen ein aktuelles macOS geprueft.

### Zugangsdaten: Keychain-only auf macOS

Auf macOS ist die Keychain die einzige Quelle. Es gibt dort **keinen stillen
Rueckfall** mehr auf Umgebungsvariablen: fehlt ein Eintrag, scheitert der
Aufruf laut. Genau dieser Durchrutscher war die alte Abweichung von
Abschnitt 4 -- ein fehlender Keychain-Eintrag sah aus wie ein vorhandener.

| `JARVIS_SECRET_BACKEND` | auf macOS | sonst |
|---|---|---|
| nicht gesetzt (`auto`) | nur Keychain | nur Umgebung (Entwicklungspfad) |
| `keychain` | nur Keychain | nichts (es gibt keine) |
| `env` | nur Umgebung, **Verstoss** | nur Umgebung |
| `none` | nichts | nichts |

Der Entwicklungspfad bleibt, weil sich sonst auf keinem anderen Rechner als
deinem Mac testen laesst. Er liest Umgebungsvariablen, keine Datei -- damit
landet weiterhin nichts im Git.

`jarvis status` unterscheidet beides:

```
Zugangsdaten   environment  (auto)
  Entwicklungspfad: ... Die macOS-Keychain gibt es auf diesem System nicht.
```

```
Zugangsdaten   environment  (env)
  UNSICHER   Zugangsdaten kommen aus Klartext-Umgebungsvariablen, nicht aus
             der Keychain. Abschnitt 4 verlangt die Keychain: ...
```

Der zweite Fall setzt zusaetzlich den Rueckgabewert auf 1 -- ein Skript merkt
es also auch ohne hinzusehen. Der erste nicht: auf Linux ist die Umgebung
kein Verstoss, sondern der einzige Weg.

Es geht nie ein Wert nach draussen. `require()` nennt den Namen des Eintrags,
nicht seinen Inhalt; `describe()` nennt nur die Quellen. Getestet ist
ausserdem, dass der Modellschluessel weder in `stdout` noch in `stderr` des
auswertenden Prozesses noch im Protokoll auftaucht.

Im `launchd`-Eintrag unter `deploy/` steht `JARVIS_SECRET_BACKEND=keychain`
ausdruecklich drin -- nicht weil es noetig waere, sondern damit man es sieht.

### Kleinere bekannte Grenzen

- **Sprache ohne Dauerschleife.** `jarvis voice listen` macht eine Runde,
  nicht mehr. Dauerhaftes Zuhoeren am Mikrofon ist bewusst nicht im Daemon.
- **Sprache nur auf diesem Rechner geprueft, nicht auf Hardware.** Die
  Adapter fuer `whisper.cpp`, `say` und die Aufnahme sind gegen Ersatz-
  programme getestet, nicht gegen ein echtes Mikrofon -- die gibt es in der
  Entwicklungsumgebung nicht. `jarvis voice check` sagt auf dem Mac, was
  tatsaechlich bereitsteht.

---

## Was noch nicht existiert

Die Faehigkeiten aus Phase 7 -- Aufgabenverwaltung, Dokumentenanalyse,
Dateiablage, Hausautomation. Die Grundlage dafuer steht: jeder externe Dienst
hat einen Adapter, ein Laufzeit-Doppel und einen messbaren Nachweisstand.

Dauerhaftes Zuhoeren am Mikrofon ebenfalls nicht: der Daemon fuehrt Sprache
bewusst nicht.
