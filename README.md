# JARVIS

Persoenlicher, autonom laufender Assistent. Verbindliche Vorgabe ist
`JARVIS-SPEC.md`; dieses Dokument beschreibt nur, was davon gebaut ist.

**Stand: Phase 5 abgeschlossen.** Der Kern steht, JARVIS liest und ordnet den
Posteingang ein, schreibt Antwortentwuerfe, kann sie ab Stufe 1 an Adressen auf
der Allowlist senden, liest den Kalender und meldet Terminkonflikte, fasst den
Tag in einem Morgenbriefing zusammen, und zeigt Zustand, Protokoll, Briefing
und anstehende Entscheidungen in einer Weboberflaeche auf localhost. Es gibt
noch keinen Daemon und keine Sprache.

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
keine Websuche -- was es nicht gibt, kann nicht benutzt werden. Eine echte
Prozesstrennung mit Netz-Sandbox ist damit *nicht* erreicht; siehe
[Bewusst zurueckgestellt](#bewusst-zurueckgestellt).

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

## Bewusst zurueckgestellt

Zwei Stellen weichen wissentlich von der Spezifikation ab. Sie stehen hier,
damit aus einer Ausnahme nicht stillschweigend der Normalfall wird.

### Keine echte Prozess- und Netztrennung (Abschnitt 2.2)

Die Spezifikation verlangt, dass der Teil, der fremde Inhalte verarbeitet,
weder Werkzeugzugriff noch Netzverbindung nach aussen hat.

Erreicht ist davon die *logische* Haelfte: `Provider.complete()` nimmt Text und
gibt Text zurueck, ohne Werkzeuge, Funktionsaufrufe oder Websuche -- die
Schnittstelle bietet sie gar nicht erst an. Nicht erreicht ist die technische:
alles laeuft in einem Prozess, und dieser Prozess darf ins Netz, weil er mit
Gmail, Kalender und dem Anbieter spricht. Ein Fehler im Auswertungspfad ist
damit nicht durch das Betriebssystem eingezaeunt, sondern nur dadurch, dass es
den Weg im Code nicht gibt.

Was noetig waere: der auswertende Teil als eigener Prozess ohne Netzrechte
(unter macOS `sandbox-exec` oder ein eigener Nutzer mit Paketfilterregel), der
ueber eine Pipe Text bekommt und Text zurueckgibt; die Netzaufrufe blieben im
handelnden Teil. Das ist Arbeit an der Prozessarchitektur, nicht an einer
einzelnen Datei -- und sie gehoert vor den Dauerbetrieb, nicht in eine
Fachphase.

### Zugangsdaten aus Umgebungsvariablen (Abschnitt 4)

Die Spezifikation sagt: ausschliesslich in der macOS-Keychain. Der Code kennt
zusaetzlich `JARVIS_SECRET_<NAME>`, weil sich sonst auf keinem anderen Rechner
als deinem Mac entwickeln oder testen laesst. Es wird weiterhin keine Datei
gelesen und nichts ins Repo geschrieben.

Diese Ausnahme ist sichtbar statt stillschweigend: steht `environment` in der
Kette, schreibt `jarvis status` es hin --

```
Zugangsdaten   keychain -> environment  (Abschnitt 4 verlangt nur keychain)
```

Im Dauerbetrieb auf dem Mac gehoert deshalb `JARVIS_SECRET_BACKEND=keychain`
gesetzt; dann faellt der Rueckfall weg und der Hinweis verschwindet.

### Kleinere bekannte Grenzen

- **Kalender ohne Blaettern.** `list_events` holt eine Seite, hoechstens 250
  Termine je Kalender und Fenster; ein `nextPageToken` wird nicht verfolgt.
  Fuer wenige Tage in einem persoenlichen Kalender reicht das. Wer laengere
  Fenster liest, braucht dort eine Schleife.
- **Kein Daemon.** Durchlaeufe startet die Kommandozeile.

---

## Was noch nicht existiert

Sprache (Phase 6). Es gibt noch keinen `daemon.py` und keine launchd-plist:
Durchlaeufe startet man vorerst von Hand oder ueber einen eigenen Eintrag in
der Aufgabenplanung.
