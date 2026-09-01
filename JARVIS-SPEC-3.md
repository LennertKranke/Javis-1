# JARVIS-SPEC-3

```
Document:              JARVIS-SPEC-3
Status:                CURRENT SOURCE OF TRUTH
Version:               3.2
Created:               2026-08-30  (Fassung 3.0, Stand commit 0b7b9b7)
Updated:               2026-08-31  (Fassung 3.1) -- SEC-1 und SEC-2 behoben,
                       mit Regressionstests
Changed:               2026-09-01  (Fassung 3.2) -- OD-4 entschieden und
                       umgesetzt. Inhaltlich betroffen: 4.2, 12, 15, 23,
                       25, Anhang B. Nur Zahlen: 1, 3.4, 13, 28. Keine
                       Prinzipien, keine Roadmap, kein offener Befund
                       beruehrt
Repository state:      Nachfolger von 9cc40fb (main), Arbeitsbaum sauber
Test state:            1063 pytest gruen (in diesem Lauf alle), ruff check und
                       format sauber. Ein Test ist zeitabhaengig und faellt
                       taeglich fuer rund zwei Stunden aus -- siehe KI-8.
                       Kein Codefehler
Based on:              aktueller Repository-Code und tatsaechlich ausgefuehrte Tests
                       Phase-1-7-Audit (zwei Runden, abgeschlossen)
                       historische JARVIS-SPEC.md (SPEC-1)
                       historische SPEC-2  --  HISTORICAL, nicht verbindlich
                       SPEC-3-Blueprint (Struktur- und Regelbasis)
Implementation status: siehe Abschnitt 15, Current Capability Matrix
```

> **Wie dieses Dokument zu lesen ist.** Abschnitte 1-16 beschreiben, **was ist** --
> jede Aussage darin ist am Code gemessen oder in einem ausgefuehrten Test belegt.
> Abschnitte 17-23 beschreiben **was fehlt und was kommen soll**. Kein Absatz tut
> beides. Wo eine Aussage nicht gemessen werden konnte, steht das ausdruecklich da.

---

## Statusstufen

Diese fuenf Stufen werden im ganzen Dokument konsequent verwendet.

| Stufe | Bedeutung |
|---|---|
| **CURRENT** | Im Repository vorhanden, getestet, in diesem Audit ausgefuehrt oder am Code eindeutig belegt |
| **REQUIRED** | Beschlossenes naechstes Ziel. Implementierung **nur** nach separatem Auftrag |
| **PLANNED** | Langfristige Architektur oder Faehigkeit. **Keine** Implementierung, auch keine vorbereitende |
| **IDEA** | Moegliche spaetere Idee. Unverbindlich |
| **HISTORICAL** | Aus SPEC-1/SPEC-2, ueberholt oder ersetzt |

Verbindlichkeitsgrade: **MUST** (harte Pflicht), **SHOULD** (starke Empfehlung),
**MAY** (zulaessig).

### Die goldene Regel

**PLANNED heisst nicht "jetzt vorbereiten durch Implementierung".** Aus einer
PLANNED-Beschreibung darf ohne separaten Auftrag nichts entstehen: keine Klasse,
kein Interface, kein Stub, kein Mock, kein Skill, keine Tabelle, kein Endpunkt,
kein CLI-Befehl, kein Dashboard-Element, keine Capability, kein Feature-Flag,
kein Test.

Zukunftsfunktionen stehen hier aus einem einzigen Grund: damit die **heutige**
Architektur nicht versehentlich in eine Sackgasse laeuft.

### Nachweisstufen

Fuer externe Dienste gilt zusaetzlich eine eigene Leiter. Sie ist im Code
verankert (`jarvis/core/integrations.py`) und darf nicht vermischt werden.

| Stufe | Bedeutung |
|---|---|
| BUILT | Der Adapter existiert |
| TESTED | Tests decken ihn ab, ohne Netz |
| MOCKED | Der ganze Weg laeuft gegen ein Laufzeit-Doppel |
| LIVE VERIFIED | Mindestens ein erfolgreicher Aufruf gegen den echten Dienst |
| PLATFORM VERIFIED | Auf macOS ausgefuehrt |

**Der wichtigste Satz dieses Dokuments:**

> **Kein externer Dienst hat je mit JARVIS gesprochen, und keine Zeile ist je auf
> macOS gelaufen.** LIVE VERIFIED = NO fuer alle fuenf Dienste.
> PLATFORM VERIFIED = NO fuer alles.

---

## 1. Executive Summary

JARVIS ist ein persoenlicher, lokal laufender Assistent fuer macOS. Er liest das
Postfach, ordnet Nachrichten ein, schreibt Antwortentwuerfe, liest den Kalender,
erkennt Terminkonflikte, erzeugt ein Morgenbriefing und zeigt alles in einem
lokalen Dashboard, in dem sich Entscheidungen freigeben lassen.

**Was tatsaechlich steht.** Der Kern (Konfiguration, Datenbank, Protokoll mit
Hash-Kette, Ratenbegrenzung, Stoppschalter, Normalisierung, Gatter, Freigaben)
ist vollstaendig und in den sicherheitskritischen Teilen belastbar getestet:
16 620 Zeilen Quellcode, 12 668 Zeilen Tests, 1063 Tests -- davon 1062 zu jeder
Tageszeit gruen, einer zeitabhaengig (KI-8). Sechs Faehigkeiten nach einem
einheitlichen Vertrag. Drei Bedienwege: CLI, Dashboard,
Sprache.

**Was fehlt.** Nicht Qualitaet, sondern Kontakt mit der Wirklichkeit. Jeder
Adapter fuer Gmail, Kalender, Anthropic, Ollama und die Keychain ist eine
ungepruefte Annahme. Das Zielsystem macOS ist nie beruehrt worden.

**Was der Audit gefunden hat.** Zwei Runden. Die erste schloss sieben Befunde
(Dateirechte, Ausnahmeschutz, Endpunktmuster, Anzeigefehler, Dokumentation). Die
zweite -- ein Querschnitt statt Phase fuer Phase -- fand vier weitere, darunter
den schwersten des Projekts: **ein im Dashboard freigegebener Entwurf konnte nie
versendet werden**, weil der Freigabeweg keine Nachbereitung hatte. Beide
Faehigkeiten funktionierten fuer sich, ihre Tests waren gruen, und trotzdem
ergaben sie zusammen eine Sackgasse.

**Was bei der Erstellung dieser Spezifikation dazukam.** Der Blueprint verlangt
zwei gezielte Pruefungen (§44 Approval-vs-Allowlist, §45 Doppelausfuehrung).
Beide wurden durchgefuehrt, beide haben eine Luecke bestaetigt -- und beide sind
seit Version 3.1 **behoben, mit Regressionstests**:

* **SEC-1**: Eine Freigabe umging die Allowlist. **BEHOBEN**: die Allowlist wird
  auf dem Freigabeweg in `verify_targets` **und** unmittelbar vor dem Versand in
  `act()` geprueft. Abschnitt 17.
* **SEC-2**: Kein atomarer Anspruch auf eine Freigabe; Doppelausfuehrung erzeugte
  doppelte Wirkung. **BEHOBEN**: der Freigabeweg beansprucht einen Vorgang atomar
  (`pending -> claimed`) auf Datenbankebene, bevor gehandelt wird. Abschnitt 17.

**Die Lehre aus dem Querschnitt**, die diese Spezifikation praegt:

> Gruene Tests je Phase beweisen nicht, dass die Phasen zusammenspielen. Alle drei
> schwersten Befunde lagen **zwischen** Bausteinen, die einzeln einwandfrei
> funktionierten.

### Der Leitsatz

> **JARVIS soll heute so gebaut werden, dass er morgen sehr viel mehr koennen
> kann -- aber wir bauen morgen nicht schon heute.**

Daraus folgen zwei Anforderungen, die einander begrenzen. Der heutige Code
**MUST** stabil, sicher, modular und zukunftsfaehig sein. Die beschriebene
Zukunftsarchitektur **MUST** konkret genug sein, um heutige Fehlentscheidungen
zu verhindern -- und **MUST** abstrakt genug bleiben, damit spaetere
Technologien und Implementierungen frei waehlbar sind. Wo dieses Dokument
konkreter wird als noetig, ist das ein Fehler; wo es so vage bleibt, dass eine
falsche Abzweigung nicht auffaellt, ebenfalls.

---

## 2. Current System

Alles in diesem Abschnitt ist **CURRENT**.

### 2.1 Was JARVIS heute tut

| Faehigkeit | Was sie tut | Verlangte Stufe | Erreicht Dritte |
|---|---|---|---|
| `mail` | Postfach lesen, vorfiltern, mit erzwungenem JSON-Schema einordnen, Label vergeben | 0 | nein |
| `mail_reply` | Antwortentwuerfe erzeugen und im Postfach ablegen | 0 | nein |
| `mail_send` | Abgelegte Entwuerfe versenden | **1** | **ja** |
| `calendar` | Termine lesen, Konflikte und enge Uebergaenge erkennen | 0 | nein |
| `briefing` | Tagesbriefing aus Kalender, Mail und Antwortstand | 0 | nein |
| `research` | Frage in Suchbegriffe uebersetzen, Quellen einer Freigabeliste befragen | **1** | **ja** |

`voice` ist **keine** Faehigkeit, sondern eine Bedienweise. `build_skill("voice")`
scheitert absichtlich mit `ConfigError` -- eine Faehigkeit haette einen
`act`-Pfad, und genau den soll Sprache nicht haben. Gebaut wird sie ueber
`build_session`.

### 2.2 Modulaufbau

```
jarvis/
  core/         config, db, audit, ratelimit, sanitize, gate, approvals,
                memory, context, secrets, integrations, log, files
  llm/          provider, router, schema, isolation, isolated, probe
    providers/  anthropic, ollama, static
  skills/       base (Vertrag), factory, runner
    mail/       skill, reply, gmail, mock, message, compose, prefilter,
                classify, labels, allowlist, style, store
    calendar/   skill, google, mock, event, conflicts, store
    briefing/   skill, store
    research/   skill, source, store
  interfaces/   cli, web/, voice/
  daemon.py
deploy/         com.jarvis.daemon.plist
```

### 2.3 Technischer Rahmen

Python >= 3.12 (Entwicklung auf 3.12.3), Abhaengigkeiten ueber `uv`. Laufzeit
bewusst schmal: `anthropic`, `google-auth`, `google-auth-oauthlib`, `starlette`,
`uvicorn`. Kein Frontend-Framework, kein ORM, kein `jsonschema` -- der
Schemapruefer ist eine eigene kleine Teilmenge.

SQLite mit acht Migrationen ueber `PRAGMA user_version`, WAL,
`BEGIN IMMEDIATE` fuer Protokoll und Ratenbegrenzung. Logs als JSON Lines.

**Kein Typpruefer konfiguriert** (siehe TD-2).

### 2.4 Bedienwege

17 CLI-Befehle: `init`, `status`, `stop`, `resume`, `log`, `verify`, `memory`,
`context`, `web`, `research`, `services`, `daemon`, `llm`, `voice`, `calendar`,
`briefing`, `mail`.

Dashboard auf `127.0.0.1`, serverseitig gerendertes HTML, kein JavaScript.
Sprachschicht mit Whisper und macOS `say` -- beide nur gegen Ersatzprogramme
getestet.

---

## 3. Architecture

### 3.1 Das Grundmuster

```
  EINGANG            Postfach, Kalender, CLI, Sprache, Dashboard
     |
     v
  NORMALISIERUNG     sanitize() -- alles von aussen, ausnahmslos
     |
     v
  MODELL             decide(): sieht Fremdtext, hat keine Werkzeuge
     |               laeuft in einem eigenen Prozess
     v
  STRUKTURIERTE      Decision.fields  (vom Modell, schemageprueft)
  ENTSCHEIDUNG       Decision.targets (von deterministischem Code)
     |
     v
  ZIELPRUEFUNG       verify_targets(): Ziele aus der Quelle neu gerechnet
     |
     v
  GATTER             Ein-Aus-Schalter -> Stoppschalter -> Stufe -> Obergrenze
     |
     v
  AUSFUEHRUNG        act(): sieht keinen Fremdtext, nur berechnete Ziele
     |
     v
  PROTOKOLL          Hash-Kette, unveraenderlich
```

Diese Struktur ist **CURRENT** und in `jarvis/skills/runner.py` umgesetzt.

### 3.2 Die vier unverhandelbaren Prinzipien

Sie stammen aus SPEC-1 und bleiben in Kraft. Prinzip 2.2 ist neu formuliert;
die Begruendung steht in Abschnitt 25.

#### P1 -- Das Modell waehlt niemals ein Ziel

**MUST.** Empfaengeradressen, Dateipfade, URLs fuer Schreibzugriffe, Geraeteziele
und Zahlungsempfaenger werden ausschliesslich von deterministischem Code aus
vertrauenswuerdigen Quellen berechnet. Kein Feld im Ausgabeschema des Modells
darf ein Ziel enthalten.

**CURRENT, vierfach abgesichert:**

1. `OutputSchema.__post_init__` verweigert schon das *Anlegen* eines Schemas mit
   Zielfeld (`llm/schema.py`, 24 Zielwoerter).
2. `Decision.__post_init__` verweigert Zielnamen in der Modellhaelfte.
3. `verify_targets()` rechnet jedes Ziel aus der Quelle neu.
4. Der Freigabeweg baut die Entscheidung ueber `Decision` wieder auf -- eine von
   Hand veraenderte Datenbankzeile kommt nicht vorbei.

**Gemessen im Querschnitt:** Die Einschleusungsnachricht des Mocks verlangt
Versand an `sammler@fremd.example`. In der Warteschlange steht als Ziel
`fremder@unbekannt.example` -- der Absender aus den Kopffeldern. Das
Angreiferziel taucht im ganzen Vorgang nicht auf.

#### P2 -- Lesen und Handeln sind getrennte Prozesse

**MUST.** Der Teil, der fremde Inhalte verarbeitet:

* **MUST** keinen Werkzeugzugriff haben -- das Modell bekommt keine Werkzeuge,
  seine Ausgabe wird nie ausgefuehrt
* **MUST** keinen Zugang zu Zugangsdaten, Datenbank oder JARVIS-Zustand haben
* **MUST** nur Text hineinbekommen und strukturiertes JSON zurueckgeben
* **SHOULD** ausgehende Netzverbindungen ausschliesslich zum Modellanbieter
  aufbauen koennen

Der Teil, der handelt, sieht die fremden Inhalte nie.

**CURRENT-Stand, gemessen:**

```
Kindprozess unter child_env(), Modus "subprocess":
  JARVIS_*-Variablen sichtbar ......... 0        erfuellt
  Werkzeuge fuer das Modell ........... keine    erfuellt
  Zugangsdaten ausser dem Modellschluessel  keine    erfuellt
  ~/.jarvis lesbar .................... JA       NICHT erfuellt
  state.db lesbar ..................... JA       NICHT erfuellt
  Netz nach aussen unbeschraenkt ...... JA       NICHT erfuellt
```

Der letzte Punkt ist mit einem entfernten Anbieter nicht vollstaendig loesbar:
das Kind *muss* den Anbieter erreichen, und `sandbox-exec` filtert nicht nach
Zielhost. Deshalb steht dort **SHOULD**, nicht MUST. Vollstaendig erfuellbar
waere er nur mit ausschliesslich lokalem Ollama.

Die Dateizugriffs-Punkte **koennen** erfuellt werden -- durch
`[llm] isolation = "sandbox"`. Diese Stufe ist gebaut, aber **nie ausgefuehrt**
(kein macOS). Siehe KI-2.

> **Wichtig fuer die Einordnung:** Die Dateirechte 0700/0600 aus dem Audit
> verbessern P2 **nicht**. Der Kindprozess laeuft unter derselben
> Benutzerkennung und ist von Dateirechten nicht betroffen.

#### P3 -- Fremde Inhalte sind Daten, keine Anweisungen

**MUST.** Jeder eingehende Text wird als unvertrauenswuerdig behandelt und vor
der Verarbeitung normalisiert.

**CURRENT** (`core/sanitize.py`), Reihenfolge ist nicht beliebig:
NFKC -> Rahmenmarker aufbrechen -> HTML entfernen -> unsichtbare Zeichen
entfernen -> Leerraum verdichten -> kuerzen.

**Gemessen:** Ein Faelschungsversuch des `<<<UNTRUSTED-CONTENT>>>`-Rahmens mit
Zero-Width-Space wurde von zwei unabhaengigen Mechanismen blockiert.

Ein sprachlich als Anweisung formulierter Fremdtext wird dadurch **nicht**
vertrauenswuerdig. Der eigentliche Schutz sind P1 und P2; die Normalisierung
nimmt der Einschleusung nur die Tarnung.

#### P4 -- Jede Aktion nach aussen ist protokolliert und abschaltbar

**MUST.** Vollstaendiges Protokoll, harte Ratenbegrenzung, und eine Stoppdatei,
deren blosse Existenz jede ausgehende Aktion blockiert.

**CURRENT.** Hash-Kette ueber kanonisches JSON plus SQLite-Trigger gegen UPDATE
und DELETE. **Gemessen:** beide Manipulationsversuche mit `IntegrityError`
abgewiesen. Auch abgelehnte Aktionen werden protokolliert.

### 3.3 Read / Decide / Act

**MUST.** Die drei Ebenen duerfen nicht verschmelzen.

| Ebene | Was | Wer sieht Fremdtext | Wer waehlt Ziele |
|---|---|---|---|
| READ (`poll`) | Daten holen | -- | -- |
| DECIDE (`decide`) | Analysieren, strukturierte Absicht erzeugen | **ja** | **nein** |
| ACT (`act`) | Externe Zustandsaenderung | **nein** | Code, deterministisch |

### 3.4 Nicht-funktionale Anforderungen

Qualitaetseigenschaften, an denen sich jede Aenderung messen lassen muss. Sie
stehen hier und nicht in einem eigenen Abschnitt, weil es Architektur-, keine
Funktionsanforderungen sind.

| Eigenschaft | Anforderung | Heutiger Stand |
|---|---|---|
| **Security** | Jede Aktion nach aussen **MUST** deterministisch autorisiert sein | erfuellt fuer die vorhandenen Wege; SEC-1 und SEC-2 seit 3.1 behoben |
| **Reliability** | Ein Fehler **MUST NOT** zu einer unkontrollierten Aktion fuehren, und **MUST NOT** wie ein Erfolg aussehen | erfuellt: `decide` und `act` auf beiden Wegen abgesichert, Daemon je Tick, alles faellt geschlossen aus |
| **Observability** | Jede Aktion **MUST** nachvollziehbar sein -- siehe 4.9 | erfuellt fuer Entscheidung, Gatterurteil und Ergebnis |
| **Modularity** | Skills und Anbieter **MUST** austauschbar sein, ohne den Kern anzufassen | erfuellt: `@register_skill`, `Provider`-Schnittstelle, Zuordnung in der Konfiguration |
| **Maintainability** | Eine neue Faehigkeit **SHOULD** ohne Eingriff in den Kern integrierbar sein | erfuellt; Einschraenkung: `core/config.py` waechst mit jeder Faehigkeit (TD-4) |
| **Privacy** | Daten **MUST** nur dort verarbeitet und gespeichert werden, wo es noetig ist | erfuellt: keine Mailinhalte in der Ablage, Vertraulichkeitssperre, 0700/0600 |
| **Portability** | macOS ist Zielplattform und **MUST** beruecksichtigt werden | Plattformweichen vorhanden, **nichts davon auf macOS gemessen** (Abschnitt 14) |
| **Testability** | Sicherheitskritische Funktionen **MUST** automatisiert pruefbar sein | erfuellt: 1063 Tests, Sicherheitseigenschaften einzeln getestet und gegen Mutation geprueft |

Diese Liste ist kein Wunschzettel: wo eine Eigenschaft heute nicht erfuellt ist,
steht der Verweis auf den Befund, der sie offen haelt.

---

## 4. Security Architecture

### 4.1 Vertrauensgrenzen

```
  VERTRAUENSWUERDIG                    UNVERTRAUENSWUERDIG
  ------------------                   -------------------
  Konfiguration                        Mailinhalte
  Originalkopffelder                   Betreffzeilen
  Datenbankzustand                     Kalendertexte
  Berechnete Ziele                     Rechercheergebnisse
  Allowlist                            Modellausgabe (schemageprueft)
```

**MUST:** Nichts aus der rechten Spalte darf ohne deterministische Pruefung in
die linke wandern.

### 4.2 Das Gatter

`core/gate.py` ist die **einzige** Stelle, an der "darf gehandelt werden"
beantwortet wird. Reihenfolge ist Absicht:

```
Faehigkeit abgeschaltet?   -> BLOCKED
Stoppschalter gesetzt?     -> BLOCKED   (vor der Obergrenze: ein angehaltenes
                                          System soll kein Kontingent aufbrauchen)
Stufe reicht / freigegeben? -> sonst DRY_RUN
Obergrenze erreicht?       -> BLOCKED
                           -> ACT
```

**MUST:** Eine Freigabe von Hand ersetzt die Autonomiestufe -- **nicht** den
Stoppschalter, **nicht** den Ein-Aus-Schalter, **nicht** die Obergrenze,
**nicht** den Trockenlauf und **nicht** die Allowlist (SEC-1, gemessen).

**Gemessen:** Bei aktivem Trockenlauf bleibt ein freigegebener Vorgang offen,
mit Vermerk "Trockenlauf global aktiv".

**Zwei Eingaenge, eine Entscheidung.** `evaluate()` beantwortet "darf
gehandelt werden" und schreibt dabei ins Protokoll und verbraucht Kontingent.
`preview()` beantwortet ausschliesslich "woran haengt es gerade" -- fuer die
Anzeige (Abschnitt 12). Es schreibt nichts, verbraucht nichts und erlaubt
nichts.

**MUST:** Die Vorschau darf nie etwas anderes sagen als die Auswertung. Weil
sie die Reihenfolge ein zweites Mal abbildet, haelt ein Test beide ueber alle
Lagen gegeneinander -- abgeschaltet, Stoppschalter, Stufe, Freigabe,
Trockenlauf, Obergrenze. Ohne diesen Test waere die zweite Fassung eine
Einladung zum Auseinanderdriften.

### 4.3 Autonomiestufen

**CURRENT.** Vier Stufen, im Code als `AutonomyLevel` festgelegt. Sie gelten
**je Faehigkeit**, nicht global, und stehen in `[capabilities]`.

| Stufe | Bezeichnung im Code | Verhalten | Wechsel zur naechsten Stufe |
|---|---|---|---|
| **0** | `Schattenbetrieb` | Entscheidet alles, handelt nichts nach aussen, protokolliert was es getan haette | 2 Wochen ohne Einwand im Protokoll |
| **1** | `Allowlist` | Handelt automatisch gegenueber Zielen auf der Freigabeliste | 4 Wochen ohne Vorfall |
| **2** | `Freigegebene Kategorien` | Handelt automatisch in freigegebenen Kategorien gegenueber bekannten Kontakten | manuelle Freigabe durch den Nutzer |
| **3** | `Alles ausser Gesperrtes` | Handelt automatisch, ausser bei ausdruecklich gesperrten Kategorien | -- |

Die Blueprint-Vorlage nennt beispielhaft fuenf Stufen (Observe, Prepare,
Approval, Limited, Full). Diese Nummerierung wird **nicht** uebernommen: der
Code hat bereits ein vierstufiges System, und eine Umnummerierung waere ein
Eingriff ohne Gewinn. Was die Vorlage als "Prepare / Draft" fuehrt, ist hier
kein eigener Rang, sondern eine Eigenschaft der Faehigkeit -- `mail_reply`
entwirft auf Stufe 0, weil ein Entwurf niemanden erreicht.

**MUST:** Autonomie darf niemals implizit entstehen. Eine neue Faehigkeit
startet auf Stufe 0, und die verlangte Stufe steht am Skill, nicht in der
Konfiguration. Wer eine Faehigkeit baut, die hinausgreift, setzt
`autonomy_level = 1` -- sonst laesst das Gatter sie schon auf Stufe 0 durch
(siehe 6.1).

**MAY:** Eine Stufe darf jederzeit gesenkt werden, auch mitten im Betrieb. Ein
Herabstufen ist keine Konfigurationsaenderung mit Vorlauf, sondern ein zulaessiger
Eingriff -- die naechste Auswertung des Gatters liest den neuen Wert.

### 4.4 Least Privilege bei Gmail

**CURRENT.** Die Rechte des Gmail-Clients haengen an der Autonomiestufe:

```
send_capabilities(config) -> SENDING   wenn permits("mail_send", 1)
                          -> DRAFTING  sonst
```

Auf Stufe 0 ist der Sende-Endpunkt **gar nicht freigeschaltet**. Ein Fehler in
der Sendelogik kann dort nichts senden. Vier Tests decken das ab.

### 4.5 Endpunkt-Allowlists

**CURRENT.** Je Faehigkeit eine Liste aus Methode und verankertem Muster,
geprueft mit `fullmatch`. `/messages/send` steht bewusst **nicht** darin --
Versand geht ausschliesslich ueber `/drafts/send`, damit genau der Entwurf
hinausgeht, der vorher geprueft wurde.

### 4.6 Dashboard-Absicherung

**CURRENT**, gemessen: Bindung ausschliesslich an Loopback (`--host 0.0.0.0`
scheitert mit `ConfigError`), Sitzungstoken 32 Byte in `~/.jarvis/web-token`
(0600, zeitkonstanter Vergleich), Origin-Pruefung bei jeder veraendernden
Anfrage, CSP `default-src 'none'`, `nosniff`, `no-store`, kein JavaScript.

**MUST (Blueprint §33):** Das Dashboard ist Oberflaeche, nicht
Sicherheitsinstanz. Es ruft `execute_approval` auf, das dieselbe Kette durchlaeuft
wie jeder andere Weg. Ein Knopf darf nie direkt einen externen Dienst aufrufen.

### 4.7 Zugangsdaten

**MUST.** Zugangsdaten gehoeren nicht in Git, Logs, SQLite, Konfigurationsdateien,
Prompts oder Protokolleintraege.

**CURRENT.** Auf macOS ist die Keychain die einzige Quelle, **ohne stillen
Rueckfall**. Abweichungen meldet `jarvis status` und setzt den Rueckgabewert auf
1. Das Log wurde auf fuenf Geheimnisbegriffe durchsucht: 0 Treffer.

### 4.8 Dateirechte

**CURRENT**, seit dem Audit. 0700 auf Verzeichnissen, 0600 auf Dateien, in
`core/files.py` an einer Stelle gekapselt. Zwei Eigenschaften sind wesentlich:

* **Reparierend, nicht nur anlegend.** Die Rechte werden bei jedem Laden der
  Konfiguration und jedem Verbindungsaufbau nachgezogen -- ein Fix nur beim
  Anlegen haette genau die Installationen offen gelassen, die schon Daten
  enthalten.
* **Vollstaendig.** WAL-Begleitdateien, rotierte Logdateien, Sperrdatei,
  Sitzungstoken und Zwischenverzeichnisse eingeschlossen.

`offene_pfade()` laeuft das Verzeichnis ab, statt bekannte Pfade aufzuzaehlen;
`jarvis status` meldet, was danach noch offen ist.

### 4.9 Observability

Ein System, das im Namen des Nutzers handelt, **MUST** hinterher erklaeren
koennen, was es getan hat. Acht Fragen muessen aus dem Protokoll beantwortbar
sein:

| Frage | Woher, CURRENT |
|---|---|
| Was ist passiert? | `audit_log.kind` und `outcome` |
| Warum ist es passiert? | `detail.reason` -- bei Modellentscheidungen die Begruendung, bei Vorfilter und Allowlist der Regelgrund |
| Welche Komponente war beteiligt? | `capability` plus `detail.decided_by` (`model`, `prefilter`, `cached`, `allowlist`, `integritaet`) |
| Welche Aktion wurde vorgeschlagen? | `outcome` des `decision`-Eintrags |
| Welche Regel hat gegriffen? | `detail.reason` des `action`-Eintrags, mit `granted_level` und `required_level` |
| War eine Freigabe noetig? | `dry_run`-Kennzeichen plus `approval_id`, wenn der Vorgang ueber den Freigabeweg lief |
| Wurde die Aktion blockiert? | `outcome = blocked`, mit dem Grund -- **auch abgelehnte Aktionen stehen im Protokoll** |
| Welches Ergebnis kam heraus? | `performed` oder `failed`, mit `detail` |

**MUST:** Protokolleintraege enthalten **keine** Geheimnisse. Geprueft: das Log
wurde auf fuenf Geheimnisbegriffe durchsucht, 0 Treffer. Der Modellschluessel
taucht weder in `stdout` noch `stderr` des auswertenden Prozesses noch im
Protokoll auf -- dafuer gibt es einen eigenen Test.

**SHOULD:** Der Fremdtext selbst gehoert nicht ins Protokoll. `audit_detail`
nimmt Kategorie, Begruendung und berechnete Ziele auf, nicht den
Nachrichtentext. Absender und Betreff stehen darin, weil das Dashboard sie zum
Einordnen braucht.

**Bekannte Grenze.** Die Kette deckt heute `decision` und `action` ab. Eine
laengere Kette -- Eingang, Entscheidung, Intent, Validierung, Freigabe,
Ausfuehrung, Ergebnis -- waere bei komplexeren Aktionen nachvollziehbarer.
**PLANNED**, siehe 19.2. Eine solche Erweiterung **MUST NOT** dazu fuehren, dass
mehr Inhalte geloggt werden als heute.

---

## 5. Execution Model

### 5.1 Zwei Wege, ein Gatter

**CURRENT.** Es gibt genau zwei Wege zu einer externen Aktion. Beide gehen durch
dasselbe Gatter, und beide fuehren Buch.

```
run_skill:           poll -> decide -> [GATTER] -> act -> after
execute_approval:    claim -> verify_targets -> [GATTER] -> act -> after_approval
```

Dass `run_skill` kein `verify_targets` braucht, ist richtig: dort sind die Ziele
gerade erst aus der Quelle berechnet worden. Auf dem Freigabeweg kommt die
Entscheidung aus der Datenbank und **MUST** gegen die Quelle geprueft werden.

`claim` ist der atomare Anspruch (SEC-2): der Uebergang `pending -> claimed` ist
ein einzelnes UPDATE mit Zustandsbedingung unter `BEGIN IMMEDIATE` und gelingt
genau einem Aufrufer, auch ueber Prozessgrenzen. Der Verlierer tut nichts und
bekommt den Grund ins Protokoll. Lehnt das Gatter nach dem Anspruch ab, gibt
`release` den Vorgang zurueck auf `pending`, mit dem Grund als Vermerk.

`after_approval` ist die Gegenstelle zu `after` und stammt aus dem Audit: auf dem
Freigabeweg gibt es kein Ereignis mehr, weil die Entscheidung gespeichert war und
manche Faehigkeiten aus `event.payload` lesen. Ohne diesen Haken war der
Freigabeweg eine Sackgasse (siehe Abschnitt 17, Q-1).

### 5.2 Ausfuehrungszustaende

**CURRENT.** Verwendete Zustaende:

| Ebene | Zustaende |
|---|---|
| Gatter | `act`, `dry_run`, `blocked` |
| Ergebnis | `performed`, `failed` |
| Freigabe | `pending`, `claimed`, `executed`, `rejected`, `failed` |
| Mail | `seen`, `analysed`, `acted`, `skipped` |
| Antwort | `planned`, `drafted`, `skipped`, `held`, gesendet ueber `sent_at` |

Zuordnung zu den neun konzeptionell geforderten Zustaenden -- damit sichtbar
wird, welche das System heute wirklich unterscheidet und welche nicht:

| Konzeptioneller Zustand | Heute abgebildet durch | Vorhanden |
|---|---|---|
| `SUCCESS` | `Result.performed = True`, Protokoll `performed` | ja |
| `PENDING` | `approvals.state = pending` | ja |
| `BLOCKED` | `Disposition.BLOCKED` -- Stoppschalter, Obergrenze, abgeschaltete Faehigkeit | ja |
| `REJECTED` | `approvals.state = rejected` (im Dashboard verworfen) | ja |
| `FAILED` | `Result.performed = False` mit `error`, Protokoll `failed` | ja |
| `DRY_RUN` | `Disposition.DRY_RUN`, im Protokoll als `T` gekennzeichnet | ja |
| `UNVERIFIED` | -- kein Zustand. Der Nachweisstand externer Dienste (`nie`) traegt diese Bedeutung, aber nicht als Aktionszustand | **nein** |
| `OFFLINE` | -- kein eigener Zustand. Ein nicht erreichbarer Anbieter endet als `failed` mit Fehlertext | **nein** |
| `CANCELLED` | -- kein Zustand. Verwerfen im Dashboard fuehrt zu `rejected` | **nein** |

**MUST:** Ein Fehler darf nie wie ein Erfolg aussehen. Erfuellt: `failed` und
`performed` sind getrennt, und eine Ausnahme wird als `failed` protokolliert,
nicht verschluckt.

**Bekannte Luecken.**

1. Der atomare Anspruch (`claimed`) existiert seit SEC-2 **auf dem
   Freigabeweg**. Fuer `run_skill` gibt es weiterhin keinen zentralen Anspruch --
   dort entstehen die Entscheidungen frisch aus `poll()`, zwei parallel
   laufende Durchlaeufe derselben Faehigkeit sind aber nicht zentral
   ausgeschlossen (der Daemon schuetzt sich mit `flock`, die CLI nicht).
   Gehoert in den Execution Layer, siehe 19.2 und OD-1.
2. Ein **teilweise ausgefuehrter** externer Vorgang hat keinen eigenen Zustand.
   Bricht `act()` nach dem Aufruf des Dienstes ab -- der Entwurf ist gesendet,
   das Nachtragen scheitert --, steht im Protokoll `failed`, obwohl aussen etwas
   geschehen ist. Heute ist das entschaerft, weil das Nachtragen nach dem
   Versand gegen einen Fehler abgesichert ist und die Aktion trotzdem als
   ausgefuehrt gilt. Als allgemeine Eigenschaft fehlt es. Gehoert in den
   Execution Layer, siehe 19.2 und OD-1.

### 5.3 Fehlerbehandlung

**CURRENT.** `decide()` und `act()` sind beide gegen unerwartete Ausnahmen
abgesichert, auf beiden Wegen. Ein Vorgang, der wirft, gilt als fehlgeschlagen,
steht im Protokoll, und der naechste ist an der Reihe. Der Daemon faengt
zusaetzlich auf Tick-Ebene.

**MUST:** Ein Fehler darf nie wie ein Erfolg behandelt werden. Ein
fehlgeschlagenes Nachtragen darf eine bereits ausgefuehrte Aktion nicht als
gescheitert erscheinen lassen -- und tut es nicht.

---

## 6. Skill Model

### 6.1 Der Vertrag

**MUST.** Jede Faehigkeit erfuellt diesen Vertrag vollstaendig. Er ist gegenueber
SPEC-1 **erweitert**: dort standen nur `poll`, `decide`, `act`. Genau daran ist
die Sackgasse aus dem Audit entstanden -- der Vertrag beschrieb den Freigabeweg
nicht.

```python
class Skill:
    name: str
    autonomy_level: int  # ab welcher gewaehrten Stufe sie handeln darf
    requires_outbound: bool  # erreicht sie Dritte? (Anzeige + Pflicht zur Obergrenze)

    def poll(self) -> list[Event]: ...
    def decide(self, event: Event) -> Decision: ...
    def act(self, decision: Decision) -> Result: ...

    def verify_targets(self, decision: Decision) -> Decision: ...
    def after(self, event, decision, disposition, result) -> None: ...
    def after_approval(self, decision, result) -> None: ...
```

Der Vertrag ist die technische Form. Fachlich **MUST** jede Faehigkeit
ausserdem diese sieben Eigenschaften besitzen -- sie sind die Pruefliste, an der
sich eine neue Faehigkeit messen laesst:

| Eigenschaft | Wo sie im Vertrag steckt | Beispiel `mail_send` |
|---|---|---|
| **Klar definierte Inputs** | `poll()` liefert `Event`; nur `Event.content` ist Fremdtext | wartende Entwuerfe aus dem Antwortspeicher |
| **Klare Outputs** | `Decision` mit getrennten `fields` und `targets`, `Result` mit `performed` und `detail` | gesendet ja/nein plus Entwurfskennung |
| **Definierte Permissions** | `requires_outbound` plus die Rechte, die die Fabrik dem Client gibt | `SENDING` erst ab Stufe 1, sonst `DRAFTING` |
| **Definierte Autonomie** | `autonomy_level` am Skill (verlangt) gegen `[capabilities]` (gewaehrt) | verlangt 1 |
| **Definierte Targets** | ausschliesslich `Decision.targets`, aus vertrauenswuerdiger Quelle | Empfaenger aus dem Antwortdatensatz, nie aus der Modellantwort |
| **Deterministische Validierung** | `verify_targets()` baut die Ziele neu und vergleicht | Entwurf, Versandzustand, Durchsicht, Fingerabdruck |
| **Audit-Faehigkeit** | `Decision.audit_detail` plus die Eintraege, die `run_skill` und `execute_approval` schreiben | Entscheidung, Gatterurteil und Ergebnis je Vorgang |

**MUST:** Eine Faehigkeit wird nie direkt mit dem Modell verheiratet. Sie
bekommt einen `Router`, keinen Anbieter -- welches Modell antwortet, entscheidet
die Konfiguration. `mail_send` und `calendar` rufen ueberhaupt kein Modell auf;
dort entscheidet Code.

**Fallstricke, die Geld oder Sicherheit gekostet haben:**

* `autonomy_level` am Skill ist die **verlangte** Stufe, in `[capabilities]` steht
  die **gewaehrte**. `0 >= 0` ist wahr -- eine Faehigkeit mit
  `autonomy_level = 0` handelt also auch auf Stufe 0. Alles, was hinausgreift,
  gehoert auf **1**. (Genau dieser Fehler wurde bei `research` gefunden.)
* Wer `verify_targets` nicht implementiert, dessen Freigaben werden **verweigert**
  -- nicht durchgelassen. Fail-closed.
* Wer `after_approval` nicht implementiert, verliert auf dem Freigabeweg seine
  Buchfuehrung. Standard ist absichtlich ein No-op, aber das ist eine bewusste
  Entscheidung, keine Empfehlung.

### 6.2 Eine neue Faehigkeit hinzufuegen

1. Neuer Ordner unter `skills/`, Klasse mit `@register_skill`.
2. **`autonomy_level = 0`** wenn sie niemanden erreicht, **`1`** sonst.
3. `requires_outbound = true` erzwingt beim Laden mindestens eine Obergrenze.
4. Ausgabeschema ueber `OutputSchema` -- die Zielfeldsperre greift beim Anlegen.
5. Ziele **ausschliesslich** in `Decision.targets`, aus vertrauenswuerdiger Quelle.
6. `verify_targets` implementieren: Ziele aus der Quelle neu bauen und vergleichen.
7. `after` **und** `after_approval` implementieren, wenn Zustand nachzutragen ist.
8. In `factory.BUILDABLE` eintragen, Abschnitt in `[capabilities]` mit Stufe 0.
9. Tests: mindestens Trockenlauf, Zielpruefung, Freigabeweg, Einschleusversuch.

**MUST:** Neue Faehigkeiten starten immer auf Stufe 0. Autonomie darf niemals
implizit entstehen.

---

## 7. LLM Architecture

**CURRENT.** `Provider` ist eine schmale Schnittstelle **ohne Werkzeugparameter**
-- P2 als Bauform, nicht als Zusage. Drei Anbieter: Anthropic, Ollama, und ein
statischer fuer Trockenlaeufe.

Der Router waehlt je Aufgabe aus einer Kette; faellt einer aus, kommt der
naechste. Die Zuordnung steht in der Konfiguration, nicht im Code.

**Vertraulichkeitssperre:** `confidential = true` laesst ausschliesslich lokale
Anbieter zu. Geprueft beim Laden **und** beim Routen -- eine im Betrieb
zusammengesetzte Kette soll nicht an einer Pruefung vorbeikommen, die nur beim
Start stattfand.

**MUST:** Die Sicherheitsarchitektur darf nicht davon abhaengen, dass ein
bestimmtes Modell sich gutartig verhaelt. Der Sicherheitslayer ist modellagnostisch:
Ziele berechnet Code, das Gatter kennt kein Modell, und die Modellausgabe wird nie
ausgefuehrt.

**Prozesstrennung.** `[llm] isolation` kennt drei Stufen: `off`, `subprocess`
(Standard), `sandbox`. Der Schluessel geht ueber die Standardeingabe, nicht ueber
Umgebung oder Kommandozeile -- dort stuende er in `ps`. Der statische Anbieter
wird nie ausgelagert (reine Kosten).

---

## 8. Data Architecture

**MUST:** Diese Kategorien werden nicht unnoetig vermischt.

| Kategorie | Wo | Anmerkung |
|---|---|---|
| Configuration | `~/.jarvis/config.toml` | 0600, enthaelt **keine** Geheimnisse |
| Secrets | macOS-Keychain | nie in Git, Logs, DB, Prompts |
| Application State | `state.db` | Mail-, Antwort-, Kalender-, Recherchezustand |
| Audit Records | `state.db`, `audit_log` | Hash-Kette, Trigger gegen UPDATE/DELETE |
| Memory | `state.db`, `memory_facts` | hoechstens 500 Tatsachen |
| Short-term Context | `state.db`, `context_entries` | begrenzte Fenstergroesse |
| Logs | `~/.jarvis/logs/*.jsonl` | 0600, taegliche Rotation, kein Fremdtext |
| External Data | `state.db` -- `research_findings`, sowie Fremdtext waehrend eines Durchlaufs | **nie roh gespeichert**: von Mail bleiben nur Kennung, Thread und Kategorie |
| User Data | `state.db` -- `mail_allowlist`, `style_profile`, `briefings` | vom Nutzer stammend oder aus seinem Verhalten abgeleitet |
| Tasks | -- | **existiert nicht.** PLANNED, Abschnitt 19.5 |
| Events | -- | **existiert nicht** als eigene Kategorie. `Event` ist ein Laufzeitobjekt, es wird nirgends abgelegt |
| Temporary | Prozessweise `TemporaryDirectory` | leeres `HOME` je Modellaufruf |

**Datensparsamkeit, CURRENT:** `mail_messages` speichert nur Kennung, Thread und
Kategorie -- **keine** Inhalte. Absender und Betreff stehen im Protokoll und in
Freigaben (das Dashboard zeigt sie), der Nachrichtentext nirgends.

**MUST:** Diese Kategorien werden nicht vermischt. Die beiden Faelle, in denen
das heute besonders zaehlt: Zugangsdaten liegen **ausserhalb** der Datenbank
(Keychain), und externe Inhalte werden nicht zu Anwendungszustand, sondern
erzeugen ihn allenfalls in abgeleiteter Form (eine Kategorie, kein Text).

**MUST NOT:** Eine kuenftige Kategorie -- Tasks, Events -- darf nicht in eine
bestehende Tabelle hineinwachsen, nur weil dort schon eine Spalte frei ist.

---

## 9. Memory

**CURRENT.** Zwei getrennte Speicher:

* **Langzeit** (`core/memory.py`): benannte Tatsachen mit Kategorie, Quelle,
  Gewicht, Zeitstempel. Obergrenze 500 -- verdraengt wird die unwichtigste, bei
  gleichem Gewicht die aelteste.
* **Kurzzeit** (`core/context.py`): begrenztes Fenster plus Kontextbauer mit
  Obergrenzen (4000 Zeichen, 12 Tatsachen, 8 Eintraege).

**MUST:** Memory heisst nicht "alles dauerhaft speichern". Jede Tatsache traegt
Quelle und Zeitpunkt und ist ueber `jarvis memory` einsehbar und loeschbar.

### 9.1 Informationsarten

**MUST:** Memory heisst nicht "alles dauerhaft speichern". Diese Arten werden
unterschieden -- und drei davon existieren heute ausdruecklich **nicht**:

| Art | Heute | Wo |
|---|---|---|
| Conversation Context | CURRENT | `context_entries`, begrenztes Fenster je Bereich |
| User Facts | CURRENT | `memory_facts`, Kategorie `person`, `zugang`, `sonstiges` |
| Preferences | CURRENT | `memory_facts`, Kategorie `praeferenz` |
| Task State | **existiert nicht** | PLANNED, Abschnitt 19.5 |
| External Information | teilweise | `research_findings` -- an eine Frage gebunden, kein Gedaechtnis |
| Derived Knowledge | **existiert nicht** | JARVIS leitet heute nichts selbst ab, das es dauerhaft behaelt |
| Audit Data | CURRENT | `audit_log`, getrennt vom Gedaechtnis und unveraenderlich |

### 9.2 Was ueber eine gespeicherte Tatsache bekannt ist

| Attribut | CURRENT | Anmerkung |
|---|---|---|
| Quelle | ja | `source`-Spalte |
| Zeitpunkt | ja | `created_at` und `updated_at` |
| Status | teilweise | nur ueber `weight` und die Verdraengung, kein eigenes Feld |
| **Vertrauensgrad** | **nein** | eine vom Nutzer gesagte und eine aus Fremdtext abgeleitete Tatsache sind nicht unterscheidbar |
| Aenderbarkeit | ja | erneutes Ablegen desselben Schluessels ueberschreibt |
| Loeschbarkeit | ja | `jarvis memory --vergessen <schluessel>` |

**REQUIRED, sobald etwas anderes als der Nutzer schreibt.** Heute schreibt nur
der Nutzer ins Langzeitgedaechtnis -- deshalb ist der fehlende Vertrauensgrad
noch folgenlos. Sobald Dokumente, Recherche oder Mailinhalte Tatsachen erzeugen
duerfen, **MUST** jede Tatsache ihre Herkunftsklasse tragen, sonst wird
Fremdtext ununterscheidbar von einer Nutzeraussage. Siehe OD-2.

### 9.3 User Context

**PLANNED.** JARVIS soll langfristig einen dauerhaften Benutzerkontext besitzen
-- wer der Nutzer ist, was er bevorzugt, woran er gerade arbeitet.

Der Kern **MUST NOT** davon ausgehen, dass alles, was irgendwann gesagt wurde,
dauerhaft gespeichert werden darf. Heute ist das strukturell abgesichert, nicht
durch Vorsatz: ins Langzeitgedaechtnis kommt ausschliesslich, was der Nutzer
ausdruecklich mit `jarvis memory <schluessel> <wert>` ablegt. Es gibt **keinen**
Pfad, auf dem ein Gespraech oder eine Mail von selbst zu einer dauerhaften
Tatsache wird -- und das ist eine Eigenschaft, die erhalten bleiben **MUST**.

**MUST:** Privacy und Memory werden gemeinsam entworfen, nicht nacheinander.
Konkret heisst das fuer jede kuenftige Erweiterung des Gedaechtnisses: bevor
eine neue Quelle schreiben darf, sind Herkunftsklasse (9.2), Loeschweg und die
Frage geklaert, ob der Inhalt ueberhaupt an ein externes Modell gehen darf
(Abschnitt 10).

**Explizit nicht jetzt umgesetzt:** kein Nutzerprofil, keine automatische
Extraktion von Tatsachen aus Gespraechen oder Mails, keine Ableitung.

---

## 10. Privacy

**MUST**, CURRENT umgesetzt:

* Minimale Speicherung -- Mailinhalte werden nicht abgelegt.
* Die Ablage gehoert nur dem Eigentuemer (0700/0600).
* Kein Geheimnis in Logs, Protokoll oder Prompts.
* Vertrauliche Aufgaben (`confidential = true`) verlassen den Rechner nicht.
* Loeschbarkeit des Langzeitgedaechtnisses: `jarvis memory --vergessen <schluessel>`.
  Der Kurzzeitkontext hat `ShortTermContext.clear()` im Code, aber **keinen
  CLI-Weg** -- siehe KI-7.

**MUST**, noch nicht umgesetzt: Bei Cloud-Modellen soll nicht jede Information
automatisch an externe Anbieter gehen. Heute entscheidet das die
Aufgabenzuordnung in der Konfiguration -- grob, aber wirksam. Feiner waere eine
Klassifikation je Inhalt. **PLANNED**, siehe OD-3.

---

## 11. External Integrations

**Alle fuenf: LIVE VERIFIED = NO.** Aus der Datenbank gelesen, nicht behauptet --
den Nachweis schreibt nur ein echter Adapter nach einer echten Antwort, ein Mock
nie.

| Dienst | BUILT | TESTED | MOCKED | LIVE VERIFIED | Anmerkung |
|---|---|---|---|---|---|
| Anthropic | ja | ja | statisch | **NO** | Schluessel aus der Keychain |
| Ollama | ja | ja | statisch | **NO** | Lokalitaet beim Bauen geprueft |
| Gmail | ja | ja | ja | **NO** | OAuth Desktop, `gmail.modify` + `gmail.send` |
| Google Calendar | ja | ja | ja | **NO** | dasselbe Token, `calendar.readonly` |
| macOS Keychain | ja | ja | -- | **NO** | nur mit simulierter Plattform |

`jarvis services check` zeigt diesen Stand; `--live` versucht echten Kontakt und
haelt ihn fest. **Im Mock-Modus schreibt auch `--live` keinen Nachweis**, sondern
meldet "Mock -- zaehlt nicht als Nachweis".

**Grenze des Mocks:** Der Gmail-Mock haelt Entwuerfe nur im Arbeitsspeicher. Ueber
mehrere CLI-Aufrufe hinweg laesst sich der Versandweg deshalb nicht durchspielen;
innerhalb eines Prozesses laeuft die Kette vollstaendig.

---

## 12. Dashboard

**CURRENT.** Lokale Instrumententafel: Lage, Briefing, anstehende
Entscheidungen, Protokoll. Freigabe und Verwerfen per Klick, Stoppschalter auf
jeder Ansicht. Serverseitiges HTML, kein JavaScript, ein handgeschriebenes
Stylesheet.

Im Trockenlauf zeigt es die Vorgaenge, blendet die Freigabe-Schaltflaeche aus und
sagt warum: "Trockenlauf ist an. Verwerfen geht, Freigeben bewirkt nichts."

**Vier Anzeigen tragen mehr als Gestaltung** -- CURRENT seit der Umsetzung
von OD-4:

| Anzeige | Was sie sichtbar macht |
|---|---|
| **Stufe gewaehrt / verlangt** | Die Faehigkeitstabelle zeigt beide Zahlen. Nur die gewaehrte zu zeigen konnte den Fehlertyp aus 6.1 nicht anzeigen: `0 >= 0` ist wahr |
| **Zustandsmarke** | Ein Protokollergebnis erscheint als Wort mit Form, nicht als Farbe allein. Nur bekannte Ergebnisse bekommen eine Marke; die vom Modell vorgeschlagene Aktion eines `decision`-Eintrags ist kein Zustand und bleibt Text |
| **Gatterleiter** | Die fuenf Sprossen aus 4.2 in ihrer Reihenfolge, mit der haltenden markiert. Sie zeigt am Vorgang, dass eine Freigabe nur Sprosse 3 ersetzt -- Stoppschalter, Obergrenze und Trockenlauf gelten weiter |
| **Vertrauensnaht** | `Decision.fields` links, `Decision.targets` rechts, getrennt ueber Linienart und Schriftart statt ueber Farbe. Macht P1 (3.2) am Vorgang pruefbar: ein Ziel links waere sofort zu sehen |

**MUST:** Die Gatterleiter ist eine **Erklaerung, keine Entscheidung**. Sie
kommt aus `Gate.preview()`, das die Reihenfolge lesend abbildet: kein
Protokolleintrag, kein verbrauchtes Kontingent (4.2).

**Abweichung von SPEC-2 (HISTORICAL).** SPEC-2 §7 gibt Farbwerte, IBM-Plex-Schriften,
SSE und ein zweigeteiltes Stromelement vor. Angeglichen wurde **nicht** an
SPEC-2, sondern an ein eigenes Designsystem (`design/JARVIS-DESIGN-SYSTEM.md`):
Systemschriften, eigene Farbrollen, `meta refresh`. Das zweigeteilte
Stromelement ist als Vertrauensnaht uebernommen, weil es die Vertrauensgrenze
sichtbar macht -- es ist die einzige Gestaltungsidee aus SPEC-2 §7, die
uebernommen wurde (Abschnitt 25). Damit ist OD-4 entschieden.

**MUST:** Das Dashboard ist niemals die Sicherheitsinstanz (§4.6).

### Was es heute zeigt, und was eine Control Plane zeigen muesste

**PLANNED.** Die folgende Liste ist ein Zielbild, **kein Arbeitsauftrag**. Sie
steht hier, damit sichtbar bleibt, wie weit die heutige Oberflaeche davon
entfernt ist.

| Bereich | Heute |
|---|---|
| System Status | CURRENT -- Zustand, Trockenlauf, Zugangsdatenquelle, Dateirechte |
| Stop Switch | CURRENT -- auf jeder Ansicht |
| Skills | CURRENT -- Name, Stufe, erreicht Dritte, aktiv, Zaehler |
| Autonomy | CURRENT -- als Spalte in der Faehigkeitstabelle |
| Approvals | CURRENT -- eigene Ansicht mit Freigeben und Verwerfen |
| Pending Actions | CURRENT -- dieselbe Ansicht |
| Audit | CURRENT -- Protokollansicht |
| Integrations | **fehlt** -- der Nachweisstand steht nur in `jarvis services check` |
| Model Status | **fehlt** -- Anbieterzustand nur in `jarvis status` |
| Provider Status | **fehlt** -- dito, inkl. Rueckfallkette und Trennung |
| Errors | **fehlt** -- Fehler stehen im Protokoll, aber ohne eigene Sicht |
| Events | **fehlt** |
| Memory | **fehlt** -- nur ueber `jarvis memory` |
| Tasks | **fehlt**, weil es keine Tasks gibt (PLANNED) |
| Automations | **fehlt**, weil es keine Automationen gibt (PLANNED) |

Sieben von fuenfzehn -- **unveraendert nach OD-4**. Die Entscheidung hat
vorhandene Bereiche mehr sagen lassen, aber keinen hinzugefuegt. Die
fehlenden acht sind kein Versaeumnis: ob das Dashboard zur Control Plane
ausgebaut wird, ist weiterhin offen und steht als Roadmap-Punkt 6 auf
PLANNED. Vier der acht setzen ausserdem Faehigkeiten voraus, die es nicht
gibt.

**MUST NOT:** Ein Ausbau darf keinen zweiten Aktionsweg schaffen. Jede
Schaltflaeche, die etwas ausloest, geht durch `execute_approval` und damit durch
dasselbe Gatter -- nicht direkt an einen Dienst.

---

## 13. Testing

**CURRENT:** 1063 Tests, Laufzeit rund 19 s. Verhaeltnis Testcode zu Quellcode
0,76 : 1. **1062 davon laufen zu jeder Tageszeit gruen**; einer ist zeitabhaengig
und faellt taeglich in einem Zwei-Stunden-Fenster aus (KI-8). Das ist ein Fehler
im Test, nicht im Code -- aber er entwertet jede pauschale "alle gruen"-Aussage.

| Art | Vorhanden | Beispiel |
|---|---|---|
| Unit | ja | `test_sanitize.py`, `test_schema.py` |
| Integration | ja | `test_integration.py`, `test_reply_runner.py` |
| Security | ja | `test_hardening.py` (32), Einschleusung in fuenf Dateien |
| Regression | ja | jeder Auditbefund hat einen |
| End-to-End | teilweise | innerhalb eines Prozesses vollstaendig |
| Platform (macOS) | **nein** | nicht moeglich, Umgebung ist Linux |
| Live Integration | **nein** | keine Zugangsdaten |

**Was die Tests wirklich pruefen.** Stichprobenartig gelesen, nicht nur gezaehlt.
Der aussagekraeftigste Einzeltest ist `test_briefing.py:352`: er prueft, dass
Einschleusungstext im *Nutzer*teil des Prompts ankommt, aber **nicht** im
*System*teil -- genau die Grenze, um die es bei P3 geht.

**Mutationspruefung.** Jede Korrektur des Audits wurde gegen eine Mutation des
eigenen Codes geprueft: Absicherung entfernt, Test muss fehlschlagen. Ein Test,
der auch ohne den Fix besteht, ist wertlos. **SHOULD** fuer alle kuenftigen
Sicherheitskorrekturen.

**Bekannte Testluecken:** kein Test, dass jede neue Web-Route geschuetzt ist
(TD-1); `test_isolation.py` prueft das Sandbox-*Profil*, nicht seine Wirkung; ein
Test bestaetigt ausdruecklich, dass das Netz offen bleibt (ehrlich, aber ein Test
fuer eine Einschraenkung).

---

## 14. macOS

**PLATFORM VERIFIED = NO, ausnahmslos.** Entwicklungs- und Testumgebung ist
Linux.

| Baustein | Zustand |
|---|---|
| Keychain | nur mit simulierter Plattform getestet |
| `sandbox-exec` | Profil geprueft, **nie ausgefuehrt** |
| launchd-Plist | als Property List geparst, **nie geladen** |
| Whisper | nur gegen Ersatzprogramme |
| `say` | nur gegen Ersatzprogramme |
| Dateirechte | auf Linux gemessen; umask 022 gilt auf macOS gleich, der echte Benutzerkontext ist ungeprueft |
| Ollama | nie erreicht |
| SQLite, Dashboard | plattformunabhaengig, auf Linux gemessen |

Die Plattformweichen im Code sind sauber (`sys.platform == "darwin"`), aber
ungeprueft.

**MUST:** Keine Linux-Verifikation darf als macOS-Verifikation ausgegeben werden.

---

## 15. Current Capability Matrix

Ausschliesslich anhand des Repository- und Auditstandes gefuellt.

| Capability | Status | Tested | Mock | Live | macOS | Notes |
|---|---|---|---|---|---|---|
| Konfiguration, Autonomiestufen | CURRENT | ja | -- | -- | NO | 7 Faehigkeiten, alle Stufe 0, `dry_run = true` |
| SQLite, Migrationen | CURRENT | ja | -- | -- | NO | 8 Migrationen, WAL, `BEGIN IMMEDIATE` |
| Protokoll mit Hash-Kette | CURRENT | ja | -- | -- | NO | UPDATE/DELETE gemessen abgewiesen |
| Ratenbegrenzung | CURRENT | ja | -- | -- | NO | nebenlaeufig geprueft; Trockenlauf verbraucht nichts |
| Stoppschalter | CURRENT | ja | -- | -- | NO | wirkt ohne Datenbank, faellt geschlossen aus |
| Normalisierung | CURRENT | ja | -- | -- | NO | Rahmenfaelschung gemessen blockiert |
| Gatter | CURRENT | ja | -- | -- | NO | einzige Stelle, gilt fuer alle Faehigkeiten |
| Freigabewarteschlange | CURRENT | ja | -- | -- | NO | SEC-1, SEC-2 behoben; atomarer Anspruch `claimed` |
| Dateirechte | CURRENT | ja | -- | -- | NO | 0700/0600, reparierend, gemessen |
| Zielfeldsperre | CURRENT | ja | -- | -- | NO | 9 Zielnamen gemessen abgewiesen |
| Prozesstrennung | CURRENT | ja | -- | -- | NO | `subprocess` wirksam, `sandbox` nie ausgefuehrt |
| Modellabstraktion | CURRENT | ja | statisch | **NO** | NO | 3 Anbieter, Rueckfallkette, Vertraulichkeitssperre |
| Mail lesen, einordnen | CURRENT | ja | ja | **NO** | NO | Stufe 0, nur Labels |
| Mail-Entwuerfe | CURRENT | ja | ja | **NO** | NO | Stufe 0, Stilprofil, Fingerabdruck |
| Mail senden | CURRENT | ja | ja | **NO** | NO | Stufe 1, Allowlist, Integritaetspruefung |
| Kalender, Konflikte | CURRENT | ja | ja | **NO** | NO | Stufe 0 |
| Briefing | CURRENT | ja | ja | -- | NO | Stufe 0, Fassung ohne Modell als Rueckfall |
| Recherche | CURRENT | ja | ja | **NO** | NO | Stufe 1, **keine Netzquelle** |
| CLI | CURRENT | ja | -- | -- | NO | 17 Befehle |
| Dashboard | CURRENT | ja | -- | -- | NO | Token, Origin, CSP, kein JS; Gatterleiter und Naht seit OD-4 |
| Sprache | CURRENT | ja | Ersatz | **NO** | NO | Bedienweise, keine Faehigkeit, kein `act`-Pfad |
| Daemon | CURRENT | ja | -- | -- | NO | `flock`, Fehlertoleranz je Tick; Plist nie geladen |
| Gedaechtnis, Kontext | CURRENT | ja | -- | -- | NO | 500 Tatsachen, begrenzter Kontext |
| Nachweisstand extern | CURRENT | ja | -- | -- | NO | 5 Dienste, alle "nie" |

---

## 16. Security Matrix

| Security Property | Current State | Verified | Risk | Required Direction |
|---|---|---|---|---|
| **Stop Switch** | Datei, wirkt ohne DB, vor der Obergrenze ausgewertet, unabhaengig von Modell, UI, Sprache | **ja**, ausgefuehrt | niedrig | Bei jeder neuen Faehigkeit erhalten; kein Umgehungspfad |
| **Target Validation** | Vierfach: Schemasperre, `Decision`-Sperre, `verify_targets`, Freigabeweg ueber `Decision` | **ja**, gemessen durch die ganze Kette | niedrig | Bei neuen Zielarten (Pfad, Geraet) dieselbe Strenge |
| **Approval** | Ersetzt die Stufe, nicht Stoppschalter/Trockenlauf/Obergrenze/Allowlist; atomarer Anspruch vor der Ausfuehrung | **ja**, gemessen (SEC-1- und SEC-2-Regressionstests) | niedrig | Bei jedem neuen Ausfuehrungsweg: Anspruch zuerst, Freigabe ersetzt nur die Stufe |
| **Allowlist** | In `decide()`, in `verify_targets` **und** in der harten Sperre in `act()` unmittelbar vor dem Versand | **ja**, gemessen je Schicht | niedrig | Bei neuen ausgehenden Faehigkeiten dieselbe Doppelung: Pruefung im Urteil und unmittelbar vor der Wirkung |
| **Prompt Injection** | Normalisierung + P1 + P2; Modell hat keine Werkzeuge, Ausgabe wird nie ausgefuehrt | **ja**, Fassung des Rahmens blockiert; Ziel aus Kopffeldern gemessen | niedrig | Bei Dokumenten und Web dieselbe Grenze |
| **Isolation** | Eigener Prozess, gefilterte Umgebung, leeres HOME, Schluessel ueber stdin | **teilweise**: Dateizugriff und Netz offen | mittel | `sandbox` auf macOS messen; Zielhost-Allowlist pruefen |
| **Secret Storage** | Keychain-only auf macOS, kein stiller Rueckfall, Abweichung gemeldet | **teilweise**: nur simulierte Plattform | mittel | Auf echtem macOS verifizieren |
| **File Permissions** | 0700/0600, reparierend, vollstaendig inkl. WAL, Rotation, Sperrdatei, Token | **ja**, gemessen | niedrig | Bei neuen Dateiarten `core/files.py` benutzen |
| **Audit** | Hash-Kette + SQLite-Trigger, auch abgelehnte Aktionen | **ja**, Manipulation gemessen abgewiesen | niedrig | Bei komplexeren Aktionen Kette erhalten |
| **Idempotency** | Zentraler atomarer Anspruch (`pending -> claimed`) im Freigabeweg, fuer alle Faehigkeiten; `mail_send` schuetzt sich zusaetzlich ueber `sent_at` | **ja**, gemessen: doppelte und nebenlaeufige Freigabe erzeugen genau eine Wirkung | niedrig | Beim Execution Layer (19.2) den Anspruch auf alle Ausfuehrungswege ausdehnen |
| **Exception Handling** | `decide` und `act` auf beiden Wegen abgesichert, Daemon je Tick | **ja**, gemessen | niedrig | Bei neuen Wegen mitziehen |

---

## 17. Known Issues

### Bestaetigte Sicherheitsluecken -- BEHOBEN in 3.1

#### SEC-1 — Eine Freigabe umging die Allowlist

```
Status:      BEHOBEN (2026-08-31), mit Regressionstests und Mutationsprobe
Schwere:     hoch  (eine E-Mail ging an eine gesperrte Adresse)
Gefunden:    bei der Erstellung von SPEC-3, Blueprint §44
Betroffen:   jarvis/skills/runner.py (execute_approval)
             jarvis/skills/mail/reply.py (MailSendSkill.verify_targets, act)
```

**Ursache.** Die Allowlist wurde ausschliesslich in `MailSendSkill.decide()`
ausgewertet. Der Freigabeweg ruft `decide()` nie auf -- er baut die Entscheidung
aus der Datenbank wieder auf und geht direkt zu `verify_targets`. Dort wurden
Antwortdatensatz, Versandzustand, Durchsicht und Entwurfsintegritaet geprueft,
**nicht** die Allowlist. Die harte Sperre in `act()` pruefte Entwurfsidentitaet
und Fingerabdruck -- ebenfalls nicht die Allowlist.

**Fehlerszenario, gemessen (vor dem Fix):**

```
1. Adresse anna@example.com steht auf der Allowlist
2. Lauf auf Stufe 0 -> Vorgang wandert in die Freigabewarteschlange
3. Adresse wird gesperrt (allowlist_blocked)
   Allowlist.permits("anna@example.com").allowed == False
4. Vorgang im Dashboard freigegeben
   -> execute_approval: performed = True
   -> client.sent_drafts == ['Draft_a']

ERGEBNIS: an eine gesperrte Adresse gesendet
```

**Fix.** Eine Freigabe ersetzt ausschliesslich die Autonomiestufe -- so wie sie
Stoppschalter, Trockenlauf und Obergrenze nicht ersetzt, ersetzt sie jetzt auch
die Allowlist nicht. Die Pruefung steht doppelt, weil zwischen Freigabe und
Ausfuehrung Tage liegen koennen, und beide Male gegen den Empfaenger aus dem
eigenen Antwortspeicher, nie aus der aufbewahrten Entscheidung:

* `MailSendSkill.verify_targets`: `Allowlist.permits` -- nicht erlaubt heisst
  `TargetMismatch`, der Vorgang wird mit dem Grund als `failed` geschlossen und
  der Grund steht im Protokoll (`refused`).
* `MailSendSkill.act`: dieselbe Pruefung in der harten Sperre unmittelbar vor
  `send_draft`, unabhaengig vom Weg hierher -- wer `decide` und `verify_targets`
  umgeht, scheitert hier.

Das Modell bestimmt auch hier zu keinem Zeitpunkt das Ziel (Prinzip 2.1 gilt
unveraendert; `Decision` prueft das beim Wiederaufbau erneut).

**Regressionstests** (`tests/test_reply_runner.py`, alle vor dem Fix gemessen
rot, danach gruen):

* `test_eine_freigabe_umgeht_die_allowlist_nicht` -- das Szenario oben: nichts
  geht hinaus, der Grund steht am Vorgang und im Protokoll.
* `test_gegenprobe_eine_weiterhin_erlaubte_adresse_geht_hinaus`.
* `test_verify_targets_prueft_die_allowlist` -- Mutationsprobe erste Schicht.
* `test_die_harte_sperre_prueft_die_allowlist_unmittelbar_vor_dem_versand` --
  Mutationsprobe zweite Schicht, ruft `act()` direkt.

#### SEC-2 — Kein atomarer Anspruch auf eine Freigabe

```
Status:      BEHOBEN (2026-08-31), mit Regressionstests, auch nebenlaeufig
Schwere:     hoch  (doppelte externe Wirkung)
Gefunden:    bei der Erstellung von SPEC-3, Blueprint §45
Betroffen:   jarvis/skills/runner.py (execute_approval)
             jarvis/core/approvals.py
             jarvis/core/db.py (Migration 8)
```

**Ursache.** `execute_approval` pruefte `approval.pending` auf dem **uebergebenen
Abbild**, nicht gegen die Datenbank, und es gab keinen Zustand zwischen
`pending` und `executed`. Zwei Aufrufe mit demselben Abbild -- Doppelklick, zwei
Arbeiter, Daemon und Dashboard gleichzeitig -- liefen beide durch.

**Fehlerszenario, gemessen (vor dem Fix):**

```
mail_reply, derselbe Vorgang zweimal freigegeben:
  1. Aufruf: performed = True
  2. Aufruf: performed = True
  Entwuerfe: ['Draft_1', 'Draft_2']

ERGEBNIS: doppelter Entwurf im Postfach
```

Bei `mail_send` hielt es -- aber **zufaellig**: `verify_targets` prueft dort
`sent_at`. Der Schutz lag in der Faehigkeit, nicht im Rahmenwerk.

**Fix.** `execute_approval` beansprucht den Vorgang atomar, bevor irgendetwas
geschieht: `ApprovalStore.claim` ist der Uebergang `pending -> claimed` als
einzelnes UPDATE mit Zustandsbedingung unter `BEGIN IMMEDIATE` -- auf
Datenbankebene, nicht als Python-Zustand, und damit korrekt ueber getrennte
Verbindungen und Prozesse. Genau ein Aufrufer gewinnt; der Verlierer tut nichts
und traegt den Grund ins Protokoll (`refused`, "kein Anspruch"). Der Schutz
liegt im Rahmenwerk und gilt fuer **alle** Faehigkeiten. Im Einzelnen:

* Zustandsmodell: `pending -> claimed -> executed | failed`; `rejected` nur aus
  `pending` (was gerade ausgefuehrt wird, laesst sich nicht mehr verwerfen).
* Lehnt das Gatter nach dem Anspruch ab (Stoppschalter, Obergrenze,
  Trockenlauf), gibt `release` den Vorgang zurueck auf `pending`, mit Grund.
* Die Entscheidung wird aus der **beanspruchten Zeile** wieder aufgebaut, nicht
  aus dem Abbild des Aufrufers.
* `claimed` zaehlt als offen: der Teilindex `ux_approvals_offen` (Migration 8)
  und der Einstell-Check verhindern, dass waehrend einer laufenden Ausfuehrung
  eine zweite Kopie desselben Vorgangs entsteht.
* Stirbt der Prozess zwischen Anspruch und Abschluss, bleibt der Vorgang als
  `claimed` stehen und wird **nie von selbst erneut ausgefuehrt** -- das System
  faellt geschlossen aus, nicht offen. Ein solcher Vorgang ist unter den
  letzten Vorgaengen und in der Zustandszaehlung sichtbar, aber nicht mehr
  freigebbar; einen Bedienweg zum Aufraeumen gibt es bewusst noch nicht
  (gehoert zu OD-1). Das ist die eine offen dokumentierte Einschraenkung.

Die volle konzeptionelle Zustandsmaschine
(`PENDING -> CLAIMED -> EXECUTING -> SUCCEEDED | FAILED | CANCELLED`) bleibt
OD-1 und dem Execution Layer (19.2) vorbehalten -- hier steht das Minimum, das
die Doppelwirkung ausschliesst.

**Regressionstests** (vor dem Fix gemessen rot bzw. den Befund reproduzierend,
danach gruen):

* `tests/test_reply_runner.py::test_eine_doppelte_freigabe_erzeugt_nur_einen_entwurf`
  -- das gemessene Szenario: genau ein Entwurf.
* `tests/test_approvals.py::test_dieselbe_freigabe_zweimal_wirkt_nur_einmal`,
  `test_der_verlierer_bekommt_einen_grund_ins_protokoll`,
  `test_der_anspruch_ist_atomar`,
  `test_der_anspruch_haelt_nebenlaeufig_ueber_getrennte_verbindungen` (zwei
  Faeden, zwei eigene Datenbankverbindungen, genau ein Gewinner),
  `test_freigeben_am_stoppschalter_gibt_den_anspruch_zurueck`,
  `test_beanspruchtes_laesst_sich_nicht_verwerfen`,
  `test_solange_beansprucht_wird_nichts_neues_eingestellt`.

### Behobene Befunde aus dem Phase-1-7-Audit

Alle mit Regressionstest, alle gegen Mutation geprueft.

| # | Befund | Status |
|---|---|---|
| Q-1 | **Der Freigabeweg war eine Sackgasse.** `execute_approval` rief `skill.after()` nie. Ein im Dashboard freigegebener Entwurf landete im Postfach, aber der Antwortspeicher blieb auf "geplant, kein Entwurf" -- und `pending_for_send` verlangt das Gegenteil. Der Entwurf war dauerhaft unsichtbar fuer den Versand | behoben, `after_approval` |
| A | `act()` war nicht gegen Ausnahmen abgesichert; eine unerwartete Ausnahme beendete den ganzen Durchlauf | behoben |
| B | Endpunkt-Allowlist nutzte `match` statt `fullmatch`; Pythons `$` laesst einen abschliessenden Umbruch durch | behoben |
| C | `~/.jarvis` 0755, `state.db`/Logs/`config.toml` 0644 -- darin Entwurfstexte, Empfaenger, Betreffzeilen, Gedaechtnis | behoben |
| N-1 | Web-Token legte das Basisverzeichnis mit 0755 an | behoben |
| N-2 | Sperrdatei des Daemons entstand mit 0644 | behoben |
| N-3 | Rechtepruefung zaehlte Pfade auf und uebersah genau die zwei offenen | behoben, `offene_pfade()` |
| +1 | `secure_dir` liess Zwischenstufen offen (`mkdir(parents=True, mode=...)` setzt den Modus nur auf die letzte Stufe) | behoben |
| G | Ganztagestermine standen als `00:00`; die Zeitzonenumrechnung schob sie in westlichen Zonen auf den **Vortag** | behoben |
| Q-2 | Briefing-Hinweis fuehrte im Kreis: nach `--neu` stand da "Erzeugen: jarvis briefing --neu" | behoben |
| Q-3 | Das Gatter versprach, der Schattenbetrieb zeige, *wann* die Grenze gegriffen haette -- tut er nicht | behoben (Zusage gestrichen, Verhalten unveraendert) |
| D, E, F | Plist-Kommentar widersprach `RunAtLoad`; Mock-Ueberbehauptung; Spalte "Ausgehend" irrefuehrend | behoben |

### Offene Unstimmigkeiten (keine Sicherheitsluecken)

| # | Punkt | Bewertung |
|---|---|---|
| KI-1 | `mail` und `calendar` haben kein `after_approval`. Nach einer Freigabe bleibt ihr Zustand nicht-final | folgenarm, selbstheilend: `cached_analysis` verhindert einen zweiten Modellaufruf, das Label ist idempotent, der naechste normale Lauf setzt den Zustand. Aber es ist dieselbe Asymmetrie, die bei `mail_reply` eine Sackgasse war |
| KI-2 | `sandbox`-Isolation nie ausgefuehrt | blockiert P2 vollstaendig zu erfuellen |
| KI-3 | `briefing` speichert nur in `act()`; mit `dry_run = true` entsteht deshalb nie eines | folgerichtig, aber inkonsistent zu `mail`/`calendar`, die in `poll`/`after` speichern |
| KI-4 | `jarvis briefing --neu` gibt im Trockenlauf 1 zurueck | vertretbar in beide Richtungen; eine Entscheidung, keine Korrektur |
| KI-5 | Recherche hat keine Netzquelle | Faehigkeit vollstaendig, aber sie findet nur den Beispielbestand |
| KI-6 | Gmail-Mock haelt Entwuerfe nur im Arbeitsspeicher | begrenzt End-to-End-Tests ueber Prozessgrenzen |
| KI-8 | **Zeitabhaengiger Test.** `test_das_briefing_entsteht_aus_mock_daten` nutzt `Europe/Berlin`, der Kalender-Mock verankert Termine an *jetzt + 2 h*, und das Briefing gilt fuer *heute*. Ab 22:00 Ortszeit rollt der Mock auf den Folgetag, das Briefing findet keine Termine, der Test faellt aus | **Fehler im Test, nicht im Code.** Beim Erstellen dieser Matrix aufgefallen, weil der Lauf zufaellig um 22:02 Berliner Zeit stattfand. Rund zwei von 24 Stunden taeglich. Er entwertet jede pauschale "alle Tests gruen"-Aussage und gehoert deshalb behoben, bevor eine solche Aussage wieder getroffen wird. Empfohlene Richtung: die Uhr im Test festnageln, statt `datetime.now()` zu benutzen -- der Mock kann das bereits (`beispiel_kalender(jetzt=...)`) |
| KI-7 | Kurzzeitkontext laesst sich nicht ueber die CLI leeren. `ShortTermContext.clear()` existiert, `jarvis context` bietet keinen Weg dorthin | klein, aber ein Privacy-Versprechen ohne Bedienweg. Beim Erstellen von SPEC-3 gefunden |

---

## 18. Technical Debt

Je Punkt: Problem, aktuelle Auswirkung, Sicherheitsauswirkung, Grund, empfohlene
Richtung, Prioritaet.

### TD-1 — Dashboard-Schutz ist ein Dekorator, keine Middleware

* **Problem:** Jede Route traegt `@geschuetzt` einzeln.
* **Aktuelle Auswirkung:** keine. Alle acht Datenrouten tragen ihn; nur
  `/jarvis.css` nicht, und das ist richtig.
* **Sicherheitsauswirkung:** latent. Die naechste Route ohne Dekorator ist ohne
  Warnung offen -- also genau dann, wenn niemand daran denkt.
* **Warum es so ist:** organisch gewachsen, Routen wurden einzeln hinzugefuegt.
* **Empfohlene Richtung:** ablehnende Middleware (deny by default), Ausnahmen
  ausdruecklich aufgezaehlt. Plus ein Test, der jede registrierte Route prueft.
* **Prioritaet:** mittel.

### TD-2 — Kein Typpruefer konfiguriert

* **Problem:** Weder mypy noch pyright in `pyproject.toml`.
* **Aktuelle Auswirkung:** durchgehende Typannotationen werden nicht geprueft.
* **Sicherheitsauswirkung:** indirekt -- Typfehler in Sicherheitspfaden fallen
  erst zur Laufzeit auf.
* **Warum es so ist:** nie eingerichtet.
* **Empfohlene Richtung:** mypy im strict-Modus fuer `core/` und `llm/`, danach
  schrittweise ausweiten.
* **Prioritaet:** mittel.

### TD-3 — Nachbereitung ist je Faehigkeit, nicht zentral

* **Problem:** `after` und `after_approval` sind zwei Haken mit
  unterschiedlichen Signaturen; `mail` und `calendar` bedienen nur einen.
* **Aktuelle Auswirkung:** KI-1.
* **Sicherheitsauswirkung:** keine direkte. Aber genau diese Asymmetrie war die
  Ursache von Q-1, dem schwersten Befund des Audits.
* **Warum es so ist:** `after` verlangt ein `Event`, das auf dem Freigabeweg nicht
  mehr existiert; `mail` und `calendar` lesen aus `event.payload`.
* **Empfohlene Richtung:** im Rahmen des Execution Layer (Abschnitt 19) eine
  Nachbereitung, die aus der Entscheidung allein arbeitet.
* **Prioritaet:** mittel.

### TD-4 — Groesse von `core/config.py`

* **Problem:** ueber 1300 Zeilen.
* **Aktuelle Auswirkung:** eine Datei fuer alle Validierung.
* **Sicherheitsauswirkung:** keine; die Buendelung ist eher ein Vorteil.
* **Warum es so ist:** bewusst -- eine Stelle fuer alle Konfigurationspruefung.
* **Empfohlene Richtung:** erst aufteilen, wenn neue Faehigkeiten es erzwingen;
  dann je Faehigkeit ein Optionsmodul, Kern bleibt zentral.
* **Prioritaet:** niedrig.

### TD-5 — Zwei Faehigkeiten in `mail/reply.py`

* **Problem:** 747 Zeilen, `MailDraftSkill` und `MailSendSkill`.
* **Aktuelle Auswirkung:** Lesbarkeit.
* **Sicherheitsauswirkung:** keine.
* **Empfohlene Richtung:** trennen, wenn die Datei erneut waechst.
* **Prioritaet:** niedrig.

---

## 19. Future Architecture

Alles hier ist **PLANNED**. Nichts davon wird jetzt gebaut.

### 19.1 Zielbild

JARVIS soll ein modulares persoenliches Assistenz- und Agentensystem werden:
Informationen aufnehmen, analysieren, Kontext verstehen, Relevantes speichern,
Aufgaben verwalten, externe Dienste nutzen, Aktionen vorbereiten und ausfuehren,
proaktiv auf Relevantes hinweisen.

**MUST, dauerhaft:** Autonomie darf niemals bedeuten, dass das Modell beliebige
externe Aktionen direkt kontrolliert.

### 19.2 Action Execution Layer — PLANNED

Heute traegt jede Faehigkeit ein Stueck Verantwortung fuer den Ablauf. Der
Freigabeweg (Q-1) und der lange fehlende atomare Anspruch (SEC-2) waren
Symptome desselben Musters. Ein zentraler Ausfuehrungsweg buendelt das an einer
Stelle:

```
Skill Decision
      -> Execution Request
      -> Target Verification
      -> Authorization       (Stufe, Allowlist, Policy)
      -> Approval Check
      -> Stop Switch
      -> Atomic Claim        (SEC-2: fuer den Freigabeweg umgesetzt)
      -> External Action
      -> Result
      -> Audit
```

**Was die heutige Architektur dafuer schon mitbringt:** ein einziges Gatter,
`verify_targets` als Vertragsbestandteil, die Hash-Kette, zwei symmetrische
Wege -- und seit den SEC-Fixes den atomaren Anspruch auf dem Freigabeweg sowie
die Allowlist in Zielpruefung und harter Sperre, nicht nur in der Entscheidung.
**Was fehlt:** die gemeinsame Schnittstelle beider Wege, der Anspruch auch fuer
`run_skill`, und die volle Zustandsmaschine (OD-1).

**Explizit nicht jetzt umgesetzt:** keine neue Klasse, kein Interface, kein
Umbau. Die SEC-Fixes wurden bewusst so geschnitten, dass sie in diese Richtung
zeigen, statt ihr im Weg zu stehen.

### 19.3 Extension Points

Die heutige Architektur **MAY** Erweiterungspunkte besitzen -- aber nur dort, wo
sie sich aus dem vorhandenen Design ergeben, nicht dort, wo eine Zukunftsfunktion
sie spaeter braeuchte.

| Erweiterungspunkt | CURRENT | Was daran erweiterbar ist |
|---|---|---|
| **Provider Interface** | ja, `llm/provider.py` | ein neuer Anbieter braucht keine Aenderung am Router. Bewusst **ohne** Werkzeugparameter |
| **Skill Interface** | ja, `skills/base.py` | `@register_skill`, kein Eingriff in den Kern |
| **Storage Abstraction** | teilweise | jede Faehigkeit bringt ihren eigenen Speicher mit (`MailStore`, `CalendarStore`, ...). Gemeinsam ist nur die Datenbank, keine Abstraktion darueber |
| **Execution Interface** | **nein** | es gibt zwei Wege (`run_skill`, `execute_approval`), aber keine gemeinsame Schnittstelle. Genau das waere 19.2 |
| **Input Abstraction** | teilweise | `Event` vereinheitlicht, was eine Faehigkeit findet. Die Bedienwege (CLI, Web, Sprache) haben dagegen keine gemeinsame Grenze |

**MUST NOT:** Ein Erweiterungspunkt ist keine Erlaubnis fuer halbfertigen Code.
Es gibt in diesem Repository **keinen** `HomeKitSkill`, `VoiceSkill`,
`TaskSkill` oder `DocumentSkill` -- auch nicht leer, auch nicht als Stub, auch
nicht registriert. Wer einen anlegt, ohne dass ein Auftrag ihn verlangt,
verstoesst gegen die goldene Regel.

### 19.4 Future Compatibility

**MUST:** Bei jeder wichtigen Architekturentscheidung wird gefragt: *Blockiert
sie eine bereits geplante Faehigkeit?* Wenn ja, wird das Problem dokumentiert
und eine bessere Architektur empfohlen -- die Faehigkeit selbst wird deshalb
**nicht** gebaut.

Der Stand dieser Pruefung heute:

| Geplante Faehigkeit | Blockiert? | Begruendung |
|---|---|---|
| Tasks | nein | Der Skill-Vertrag traegt sie unveraendert |
| Documents | nein | `sanitize()` und die Prozesstrennung sind der vorgesehene Weg und vorhanden |
| Files | nein | Die Zielfeldsperre deckt `path`, `filename`, `destination` bereits ab |
| Voice-Komfort | nein | Sprache ist bereits Bedienweise ohne `act`-Pfad |
| Home Automation | **teilweise** | Das Gatter kennt nur Faehigkeitsnamen und Stufen, ist also nicht Gmail-spezifisch. Aber es gibt kein Modell fuer *Zielarten* -- eine Geraeteadresse ist etwas anderes als eine E-Mail-Adresse, und die Zielpruefung liegt heute je Faehigkeit statt zentral. Empfehlung: mit 19.2 loesen, nicht mit einem Geraeteskill |
| Proactive Agent | **teilweise** | Es gibt keinen Weg, von sich aus zu melden. Der Daemon kann pollen, aber nichts zustellen. Empfehlung: ein Benachrichtigungsweg, der durch dasselbe Gatter geht -- nicht daneben |

Zwei Befunde, kein Auftrag. Beide sind in der Roadmap verortet (Abschnitt 21),
und beide **MUST NOT** durch vorgezogene Implementierung geloest werden.

### 19.5 Feature-Steckbriefe

Alle nach demselben Schema. Die beiden letzten Felder sind die wichtigsten: sie
trennen "woran die heutige Architektur nicht scheitern darf" von "was jetzt
ausdruecklich nicht gebaut wird".

#### Tasks

```
Feature:            Aufgabenverwaltung
Status:             PLANNED
Purpose:            Aufgaben erkennen, verwalten, priorisieren, an Faelligkeiten
                    erinnern
Future UX:          Aufgaben tauchen im Briefing und im Dashboard auf; JARVIS
                    fragt nach, statt selbst zu entscheiden, was dringend ist
Architectural role: Neue Faehigkeit nach dem Vertrag aus Abschnitt 6
Inputs:             Mail, Kalender, direkte Eingabe
Outputs:            Strukturierte Aufgabe mit Faelligkeit, Kategorie, Zustand
Security:           Aufgabentexte aus Mail sind untrusted. Das Modell darf eine
                    Aufgabe vorschlagen, aber weder Faelligkeit noch Ziel so
                    setzen, dass daraus eine Aktion entsteht
Integration:        Eigener Speicher, eigene Faehigkeit, Stufe 0
Dependencies:       keine externen Dienste
Heute noetig:       Skill-Vertrag traegt sie unveraendert; Gatter, Protokoll und
                    Ratenbegrenzung erbt sie ueber run_skill. Datenkategorie
                    "Tasks" ist in Abschnitt 8 benannt, aber leer
NICHT jetzt:        keine Task-Klasse, keine Tabelle, kein Scheduler, keine
                    Erinnerung, kein Dashboard-Element, kein CLI-Befehl
```

#### Documents

```
Feature:            Dokumentenanalyse
Status:             PLANNED
Purpose:            PDFs, Rechnungen, Vertraege verstehen
Future UX:          Ein Dokument wird abgelegt, JARVIS sagt was drinsteht und
                    ordnet es einem Vorgang zu
Architectural role: Leseweg mit besonders strenger Untrusted-Grenze
Inputs:             PDF, Text, Tabellen, spaeter OCR
Outputs:            Strukturiertes Ergebnis -- Klassifikation, Extraktion,
                    Zusammenfassung
Security:           Dokumente sind untrusted, ausnahmslos. Ein Dokument darf
                    keine Anweisung an JARVIS ausloesen. Der Analyseprozess
                    bekommt keine Werkzeuge, genau wie heute der Modellaufruf.
                    OCR-Ergebnisse sind ebenfalls untrusted
Integration:        Parser -> Normalisierung -> Untrusted-Grenze -> Analyse ->
                    strukturiertes Ergebnis -> optional Memory
Dependencies:       ein Parser; fuer OCR zusaetzlich eine lokale Engine
Heute noetig:       sanitize() und die Prozesstrennung sind der vorgesehene Weg
                    und vorhanden. Wenn Dokumente ins Gedaechtnis schreiben
                    duerfen, wird der Vertrauensgrad aus 9.2 zur Pflicht
NICHT jetzt:        kein Parser, kein OCR, keine Dokumententabelle, kein Skill
```

#### Files

```
Feature:            Dateiablage
Status:             PLANNED
Purpose:            Dateien finden, klassifizieren, kontrolliert ablegen
Future UX:          "Wo liegt der Vertrag von Maerz" -- und spaeter: kontrolliert
                    einsortieren
Architectural role: Erste Faehigkeit mit schreibendem Zugriff ausserhalb von Mail
Inputs:             Dateipfade aus einem freigegebenen Bereich, Dateiinhalte
Outputs:            Fundstellen, Klassifikation, vorgeschlagene Ablage
Security:           Dateipfade sind Ziele im Sinne von P1 und MUST
                    deterministisch berechnet werden -- nie aus der
                    Modellantwort. Jede schreibende Aktion durchlaeuft denselben
                    Weg wie ein Mailversand
Integration:        Faehigkeit mit Pfad-Freigabeliste, analog zur Allowlist
Dependencies:       keine externen Dienste
Heute noetig:       Die Zielfeldsperre deckt path, filepath, filename und
                    destination bereits ab -- ein Schema mit solchen Feldern
                    laesst sich nicht anlegen
NICHT jetzt:        kein Dateiskill, keine Pfad-Allowlist, kein Index, kein
                    Verschieben
```

#### Research -- Netzquelle

```
Feature:            Recherche mit echter Quelle
Status:             REQUIRED, nicht PLANNED
Purpose:            Die Faehigkeit existiert (CURRENT) und findet nur den
                    Beispielbestand
Future UX:          unveraendert -- jarvis research ask, nur mit echten Funden
Architectural role: Neue Source hinter der vorhandenen Freigabeliste
Inputs:             Suchbegriffe vom Modell, Quelle vom Code gewaehlt
Outputs:            Belege mit Quelle und Fundstelle
Security:           Webseiten sind untrusted. JARVIS darf sie analysieren, ihre
                    Inhalte duerfen seine Systemregeln nicht veraendern. Der
                    Rueckweg laeuft durch dieselbe Normalisierung wie Mail
Integration:        Source-Protokoll in research/source.py, waehle_quellen()
Dependencies:       Anbieter-Key oder eine eigene Quelle
Heute noetig:       Rollentrennung steht: Modell macht Begriffe, Code waehlt die
                    Quelle. Stufe 1 ist gesetzt, Ratenbegrenzung greift
NICHT jetzt:        keine Recherche-Engine, kein Crawler, kein Index. Nur eine
                    Source hinter der bestehenden Naht -- nach separatem Auftrag
```

#### Voice -- Komfort

```
Feature:            Weckwort, Dauerschleife, komfortablere Sprachbedienung
Status:             PLANNED  (die Sprachschicht selbst ist CURRENT)
Purpose:            Sprache als beilaeufige Bedienweise statt einzelner Aufrufe
Future UX:          Ansprechen ohne Tastatur, kurze Antwort, kein Bildschirm
Architectural role: Zusaetzliche Ein-/Ausgabeschicht, keine Faehigkeit
Inputs:             Mikrofon -> Whisper -> Text
Outputs:            Text -> macOS say
Security:           Ein Sprachbefehl MUST NOT mehr Rechte haben als derselbe
                    Befehl als Text. Die heutige Asymmetrie -- anhalten per
                    Sprache moeglich, fortsetzen nie -- MUST erhalten bleiben.
                    Sprache MUST NOT einen act-Pfad bekommen
Integration:        interfaces/voice/, gebaut ueber build_session
Dependencies:       whisper.cpp, ein Modell, ein Mikrofon
Heute noetig:       Die Eingabemodalitaet ist nicht fest auf CLI verdrahtet:
                    build_skill("voice") scheitert absichtlich, Sprache laeuft
                    ueber sechs feste Absichten. Das MUST so bleiben
NICHT jetzt:        kein Weckwort, keine Dauerschleife, keine Sprachfaehigkeit,
                    keine Sprachrechte, keine Sprach-UI
```

#### Home Automation

```
Feature:            HomeKit oder MQTT
Status:             PLANNED
Purpose:            Geraete steuern
Future UX:          "Licht im Buero aus" -- und JARVIS weiss, welches Geraet
                    gemeint ist, ohne dass das Modell die Adresse waehlt
Architectural role: Erste Faehigkeit mit physischer Wirkung
Inputs:             Absicht des Nutzers, Geraeteliste aus vertrauenswuerdiger
                    Quelle
Outputs:            Ein erlaubtes Kommando an ein erlaubtes Geraet
Security:           Sicherheitskritischer als alles Bisherige. Das Modell MUST
                    NOT eine Geraeteadresse oder ein Kommando erzeugen und
                    ausfuehren. Ablauf: Modell entscheidet WAS grundsaetzlich
                    gewuenscht ist -> deterministischer Code waehlt erlaubtes
                    Geraet und erlaubten Befehl -> Sicherheitsgatter -> Audit ->
                    Aktion. Neue Geraetefaehigkeiten starten auf Stufe 0
Integration:        Eigene Faehigkeit mit Geraete-Freigabeliste
Dependencies:       HomeKit braucht macOS und eine Zentrale; MQTT einen Broker
Heute noetig:       Der Aktionsweg ist nicht Gmail-spezifisch -- das Gatter kennt
                    nur Faehigkeitsnamen und Stufen. Was fehlt: ein Modell fuer
                    Zielarten, siehe 19.4
NICHT jetzt:        keine HomeKit-Anbindung, kein MQTT, kein Geraeteskill, keine
                    Geraete-Allowlist, keine Geraetetabelle
```

#### Proactive Agent

```
Feature:            Proaktivitaet
Status:             PLANNED
Purpose:            Wichtige Mail, bevorstehende Frist, Kalenderkonflikt, offene
                    Entscheidung von sich aus melden
Future UX:          JARVIS meldet sich knapp, wenn etwas ansteht -- nicht, wenn
                    nichts ansteht
Architectural role: Beobachtungsschicht ueber vorhandenen Faehigkeiten
Inputs:             Bestehende Befunde: Kalenderkonflikte, Fristen, wartende
                    Freigaben
Outputs:            Eine Meldung, keine Aktion
Security:           Proactive Observation ist nicht Proactive Action. Beobachten
                    darf JARVIS, sofern erlaubt. Jede daraus entstehende Aktion
                    MUST weiterhin durch Policy, Permission, Autonomy, Approval,
                    Gate, Execution, Audit. Der Meldeweg selbst MUST NOT ein
                    zweiter Aktionspfad werden
Integration:        Zustellweg, der durch dasselbe Gatter geht
Dependencies:       ein Zustellweg (Push, Mail an sich selbst, Dashboard)
Heute noetig:       Konflikte und Fristen werden bereits erkannt -- es fehlt nur
                    das Melden. Der Daemon kann pollen, aber nichts zustellen,
                    siehe 19.4
NICHT jetzt:        keine Benachrichtigung, kein Push, keine Regel-Engine, kein
                    Schwellenwertsystem
```

#### Always-On / Daemon

```
Feature:            Dauerbetrieb als macOS-Hintergrunddienst
Status:             PLANNED  (der Daemon selbst ist CURRENT, ungeprueft auf macOS)
Purpose:            JARVIS laeuft dauerhaft, ueberlebt Neustarts und Fehler
Future UX:          Man merkt ihn nicht, ausser wenn er sich meldet
Architectural role: Zeitsteuerung ueber launchd
Inputs:             Zeitplan aus [daemon.schedule]
Outputs:            Regelmaessige Durchlaeufe der eingeplanten Faehigkeiten
Security:           Ein dauerhaft laufender Prozess MUST NOT eine
                    Sicherheitsregel umgehen. Er ruft dieselben Faehigkeiten
                    ueber dasselbe Gatter auf. Der Stoppschalter wirkt sofort
                    und unabhaengig vom Daemon
Integration:        deploy/com.jarvis.daemon.plist
Dependencies:       macOS, launchd
Heute noetig:       Sechs geforderte Eigenschaften, gemessen am Ist-Stand:
                      restartfaehig    -- KeepAlive und ThrottleInterval gesetzt,
                                          nie geladen
                      ueberwacht       -- fehlt. Kein Gesundheitszustand, keine
                                          Meldung bei wiederholtem Scheitern
                      ressourcenschonend -- ProcessType=Background gesetzt, nie
                                          gemessen
                      sicher           -- erfuellt: dasselbe Gatter, Einzelinstanz
                                          per flock
                      stoppbar         -- erfuellt: Stoppschalter und
                                          launchctl bootout
                      auditierbar      -- erfuellt: jeder Durchlauf protokolliert
NICHT jetzt:        keine Ueberwachung, kein Gesundheitsendpunkt, keine
                    Ressourcenmessung, keine Always-On-Architektur
```

## 20. Future Capability Matrix

Diese Tabelle existiert ausdruecklich, damit Zukunftsfunktionen nicht
versehentlich als aktuelle Arbeitspakete gelesen werden.

| Future Capability | Status | Purpose | Architectural Requirement | Implement Now? |
|---|---|---|---|---|
| Tasks | PLANNED | Aufgaben erkennen und verwalten | Skill-Vertrag traegt sie unveraendert | **NO** |
| Documents | PLANNED | PDFs und Dokumente verstehen | Untrusted-Grenze und Prozesstrennung muessen bleiben | **NO** |
| Files | PLANNED | Dateien kontrolliert ablegen | Pfade sind Ziele nach P1; Zielfeldsperre deckt sie ab | **NO** |
| Voice-Komfort | PLANNED | Weckwort, Dauerschleife | Sprache bleibt Bedienweise ohne `act`-Pfad | **NO** |
| Home Automation | PLANNED | Geraete steuern | Aktionsweg darf nicht Gmail-spezifisch werden | **NO** |
| Proactive Agent | PLANNED | Von sich aus melden | Kein zweiter Aktionspfad am Gatter vorbei | **NO** |
| Always-On / Daemon | PLANNED | Dauerbetrieb, ueberwacht und ressourcenschonend | Daemon existiert; Ueberwachung fehlt, siehe 19.5 | **NO** |
| Weitere Anbieter | PLANNED | OpenAI, Google, lokale Modelle | Provider-Schnittstelle ist bereits schmal genug | **NO** |
| Kostenbasiertes Routing | PLANNED | Modellwahl nach Kosten, Tempo, Kontextgroesse | Router existiert; Kriterien fehlen | **NO** |
| Smartphone-Steuerung | IDEA | -- | -- | **NO** |
| Telefonzugriff | IDEA | -- | -- | **NO** |
| Social Media | IDEA | -- | -- | **NO** |
| Autonomes Trading | IDEA | ausdruecklich Zukunftsmusik | -- | **NO** |

---

## 21. Roadmap

Abgeleitet aus dem tatsaechlichen Zustand, nicht aus alten Phasennummern.

**Leitregel (Blueprint §52): Security before Autonomy.** Je autonomer JARVIS
wird, desto wichtiger werden deterministische Sicherheitsmechanismen. Komplexe
proaktive Autonomie darf nicht vor einem stabilen Permission-, Execution-,
Audit-, State- und Stop-System gebaut werden.

```
[erledigt]  Phase-1-7-Audit, zwei Runden
[erledigt]  Sicherheits- und Zuverlaessigkeitskorrekturen (A-G, N-1..N-3, Q-1..Q-3)
[erledigt]  SPEC-3
[erledigt]  SEC-1 und SEC-2 schliessen  <- hier stehen wir

  2. Erste echte Verbindung (Gmail + Kalender, lesend)   REQUIRED
  3. macOS-Verifikation                                  REQUIRED
  4. Execution Layer konsolidieren                       REQUIRED
  5. Netzquelle fuer Recherche                           REQUIRED
  6. Dashboard als Control Plane                         PLANNED
  7. Tasks                                               PLANNED
  8. Documents, Files                                    PLANNED
  9. Voice-Komfort                                       PLANNED
 10. Proaktivitaet                                       PLANNED
 11. Home Automation                                     PLANNED
 12. Dauerbetrieb haerten und optimieren                 PLANNED
```

### Die REQUIRED-Punkte

| # | Was | Warum jetzt | Braucht |
|---|---|---|---|
| **1** | **SEC-1 und SEC-2 schliessen** -- **erledigt (2026-08-31)**, siehe Abschnitt 17 | Zwei bestaetigte Sicherheitsluecken im Freigabeweg. Beide waren Voraussetzung dafuer, dass eine echte Verbindung ueberhaupt verantwortbar ist | -- |
| **2** | Erste echte Verbindung, lesend, Stufe 0, Trockenlauf an | Der groesste offene Punkt ueberhaupt. Alles ist gebaut, nichts ist je gelaufen. OAuth, Fehlerformate, Token-Erneuerung sind ungepruefte Annahmen | Google-Cloud-Projekt, Desktop-OAuth |
| **3** | macOS-Verifikation | Zielplattform. `jarvis llm check` mit Sandbox, `services check --live`, Plist laden, Keychain, Whisper, `say` | den Mac; keine neue Zeile Code |
| **4** | Execution Layer konsolidieren | SEC-2, TD-3 und KI-1 haben dieselbe Wurzel. Einzeln geflickt bleiben sie wiederkehrend | Entscheidung OD-1 |
| **5** | Netzquelle fuer Recherche | Die Faehigkeit steht, findet aber nur den Beispielbestand | Anbieter-Key oder eigene Quelle |

**Reihenfolge-Begruendung.** 1 stand vor 2, weil eine bestaetigte Luecke im
Freigabeweg nicht mit echten Zugangsdaten kombiniert werden sollte. 2 vor 4,
weil der Execution Layer aus den Erfahrungen der ersten echten Verbindung lernen
sollte statt sie vorwegzunehmen. 3 kann parallel laufen, es braucht nur den Mac.

---

## 22. Implementation Phases

Was in einer Sitzung passiert, und was nicht.

**MUST:** Ein klar abgegrenzter Arbeitsschritt pro Sitzung. Am Ende Tests
ausfuehren, Ergebnis nennen, anhalten, auf Freigabe warten.

**MUST:** Tests vor oder zusammen mit der Funktion, nie danach.

**MUST:** Kein Feature ohne Trockenlaufpfad.

**SHOULD:** Jede Sicherheitskorrektur gegen eine Mutation des eigenen Codes
pruefen -- Absicherung entfernen, Test muss fehlschlagen.

**MUST:** Keine neue Abhaengigkeit ohne kurze Begruendung.

**MUST:** Wenn etwas gegen Abschnitt 3.2 verstoesst -- anhalten und fragen. Wer
unsicher ist, ob etwas dagegen verstoesst: es verstoesst dagegen.

---

## 23. Open Decisions

### OD-1 — Zustandsmaschine fuer Aktionen

```
Frage:    Welche Zustaende braucht eine externe Aktion, und wo wird der
          atomare Anspruch gehalten?
Optionen: A  Zustandsspalte in `approvals`, Uebergang per BEGIN IMMEDIATE
          B  eigene Tabelle `action_claims` mit Ablauf
          C  Anspruch je Faehigkeit (heutiger Zustand, implizit)
Empfehlung: A fuer den naechsten Schritt -- kleinste Aenderung, nutzt die
          vorhandene Schreibsperre. B, wenn spaeter mehrere Arbeiter dazukommen.
          C war der Ist-Zustand und die Ursache von SEC-2.
Stand:    Der SEC-2-Fix hat Option A umgesetzt (Zustand `claimed` in
          `approvals`, Uebergang per BEGIN IMMEDIATE) -- fuer den Freigabeweg.
          Offen bleibt die volle Zustandsmaschine (EXECUTING, CANCELLED,
          Aufraeumen liegengebliebener `claimed`-Vorgaenge) und ihre
          Ausdehnung auf alle Ausfuehrungswege im Execution Layer (19.2).
Status:   TEILWEISE ENTSCHIEDEN (A), Rest OFFEN
```

### OD-2 — Vertrauensgrad im Gedaechtnis

```
Frage:    Soll eine gespeicherte Tatsache ihren Vertrauensgrad tragen --
          vom Nutzer gesagt vs. aus Fremdtext abgeleitet?
Empfehlung: Ja, sobald Dokumente oder Recherche ins Gedaechtnis schreiben.
          Heute schreibt nur der Nutzer, deshalb noch nicht dringend.
Status:   OFFEN
```

### OD-3 — Feinere Vertraulichkeitssteuerung

```
Frage:    Reicht die Zuordnung je Aufgabe, oder braucht es eine
          Klassifikation je Inhalt?
Empfehlung: Aufgabenzuordnung beibehalten, bis Dokumente dazukommen.
Status:   OFFEN
```

### OD-4 — Dashboard-Gestaltung

```
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

### OD-5 — Zielhost-Allowlist fuer den Modellprozess

```
Frage:    Laesst sich der ausgehende Netzzugriff des Kindprozesses auf die
          Anbieter-Endpunkte begrenzen?
Optionen: A  lokaler Weiterleitungsproxy mit Allowlist
          B  Paketfilter je Prozess (macOS: Network Extension, aufwaendig)
          C  ausschliesslich lokales Ollama
Empfehlung: Erst auf macOS messen (REQUIRED 3), dann entscheiden. C erfuellt P2
          vollstaendig, kostet aber die starken Modelle.
Status:   OFFEN
```

---

## 24. Non-Goals

JARVIS soll ausdruecklich **nicht** sein:

* **Kein unkontrollierter autonomer Agent.** Autonomie waechst in Stufen, je
  Faehigkeit, nie global und nie implizit.
* **Kein System, in dem das Modell direkte Systemrechte besitzt.** Das Modell
  bekommt keine Werkzeuge, waehlt kein Ziel, und seine Ausgabe wird nie
  ausgefuehrt.
* **Keine versteckte automatische Aktion.** Jede Aktion nach aussen steht im
  Protokoll, auch die abgelehnte.
* **Keine Vermischung von untrusted data und system instructions.**
* **Keine Speicherung ohne Zweck.** Mailinhalte werden nicht abgelegt.
* **Keine Fake-Features, die nur eine Roadmap abbilden.** Kein Stub, kein
  Dummy-Skill, keine leere Tabelle fuer eine PLANNED-Funktion.
* **Keine Alleskoenner-Anwendung in einem Rutsch.**
* **Spracherkennung ist nicht der Hauptbedienweg.** Text ist der Standard.

---

## 25. SPEC-2 → SPEC-3 Migration

SPEC-2 ist **HISTORICAL**. Sie liegt dem Repository nicht bei; die dort
vorhandene `JARVIS-SPEC.md` ist SPEC-1 und ebenfalls historisch.

### Retained — unveraendert uebernommen

* Die vier Kernprinzipien als Rahmen (P1, P3, P4 wortgleich in der Sache).
* Autonomiestufen 0-3, je Faehigkeit, neue Faehigkeiten starten auf 0.
* Der Skill-Vertrag als Grundmuster `poll` / `decide` / `act`.
* Provider-Abstraktion mit Router und Rueckfallkette.
* Trockenlauf als Pflicht fuer jede Faehigkeit.
* Keychain als einzige Quelle fuer Zugangsdaten auf macOS.
* Dashboard lokal, ohne Anmeldung, ohne Nutzerverwaltung, kein Build-Schritt.

### Modified — veraendert uebernommen

| Was | SPEC-2 | SPEC-3 | Grund |
|---|---|---|---|
| **Prinzip 2.2** | "keine Netzwerkverbindung nach aussen" (MUST) | Werkzeuge, Zugangsdaten und Zustand als MUST; Netz nur zum Anbieter als SHOULD | Mit einem entfernten Anbieter unerfuellbar. Ein MUST, das dauerhaft verletzt ist, entwertet alle anderen |
| **Skill-Vertrag** | drei Methoden | sechs: zusaetzlich `verify_targets`, `after`, `after_approval` | Der unvollstaendige Vertrag war die Ursache der Sackgasse Q-1 |
| **`requires_outbound`** | "unterliegt Ratenbegrenzung und Stoppschalter" | Anzeige plus Pflicht zur Obergrenze; das Gatter gilt fuer **alle** Faehigkeiten | Strenger als SPEC-2 verlangt. Bleibt so |
| **Phasenmodell** | Phase 1-7 als Bauplan | Roadmap aus dem Ist-Zustand abgeleitet | Phase 1-7 sind abgeschlossen und auditiert |

### Superseded — durch neue Architektur ersetzt

* **Der Ausfuehrungsweg.** SPEC-2 kennt nur `run_skill`. Der Freigabeweg ist
  gleichberechtigt und im Vertrag beschrieben (Abschnitt 5.1).
* **Nachweisstufen.** SPEC-2 unterscheidet nicht zwischen gebaut, getestet,
  gemockt und live. SPEC-3 macht die Leiter zum Dokumentprinzip.

### Removed — bewusst entfernt

* **Nichts inhaltlich.** SPEC-2 §7.2-7.8 (Farbwerte, IBM Plex, SSE,
  Signaturelement, Bewegung) sind nicht mehr verbindlich, aber als
  Gestaltungsmaterial erhalten -- siehe Future-only.

### Future-only — weiterhin interessant, jetzt nur Bauplan

* Die Designfassung des Dashboards aus SPEC-2 §7. Sie war eine Vorlage und
  ist kein Abnahmekriterium geworden: OD-4 hat sich fuer ein eigenes
  Designsystem entschieden (`design/JARVIS-DESIGN-SYSTEM.md`), nicht fuer
  eine Angleichung.
* Der Entscheidungsstrom als Signaturelement (SPEC-2 §7.5) -- die Zweiteilung
  "was das Modell entschied / was der Code tat" macht die Vertrauensgrenze
  sichtbar. Das war die einzige gestalterische Idee, die aus SPEC-2
  uebernommen wurde: sie steht seit OD-4 als Vertrauensnaht am Vorgang
  (Abschnitt 12) und ist damit nicht mehr Future-only, sondern **CURRENT**.

---

## 26. Acceptance Criteria

Woran sich die naechsten Schritte messen lassen.

### Fuer SEC-1 (Allowlist) — alle erfuellt, 2026-08-31

* [x] Ein Vorgang, dessen Adresse nach dem Einstellen gesperrt wurde, geht bei
      Freigabe **nicht** hinaus.
* [x] Der Grund steht im Vorgang und im Protokoll.
* [x] Gegenprobe: eine weiterhin erlaubte Adresse geht hinaus.
* [x] Die Pruefung greift in `verify_targets` **und** unmittelbar vor dem Versand.
* [x] Mutationsprobe: die Regressionstests wurden gegen den Code vor dem Fix
      ausgefuehrt und schlagen dort fehl; je eine Schicht wird einzeln geprueft.

### Fuer SEC-2 (atomarer Anspruch) — alle erfuellt, 2026-08-31

* [x] Derselbe Vorgang zweimal ausgefuehrt erzeugt genau **eine** Wirkung.
* [x] Nebenlaeufig mit getrennten Verbindungen ebenso (zwei Faeden, je eigene
      Datenbankverbindung).
* [x] Der zweite Aufruf meldet einen verstaendlichen Grund ins Protokoll,
      keinen Fehler.
* [x] Gilt fuer **alle** Faehigkeiten: der Anspruch liegt in
      `execute_approval`/`ApprovalStore`, nicht in einer Faehigkeit.

### Fuer die erste echte Verbindung

* [ ] `jarvis services check` zeigt fuer Gmail und Kalender ein Datum statt "nie".
* [ ] Trockenlauf bleibt an, Stufe bleibt 0.
* [ ] Ein Protokolldurchgang ist plausibel: Kategorien passen zu den Nachrichten.
* [ ] Kein Geheimnis in Log oder Protokoll.

### Fuer macOS

* [ ] `jarvis llm check` zeigt eine dritte Spalte SANDBOX, in der Dateizugriffe
      auf `verweigert` stehen und "Netz nach aussen" auf `moeglich`.
* [ ] `jarvis status` meldet Keychain ohne Abweichung.
* [ ] Die Plist laedt, der Daemon ueberlebt einen Neustart.
* [ ] Alle Dateien unter `~/.jarvis` stehen auf 0700/0600.

---

## 27. Change Management

Damit SPEC-3 nicht wieder veraltet.

| Ausloeser | Pflicht |
|---|---|
| Codeaenderung | Betroffenen SPEC-Abschnitt mitziehen, im selben Commit |
| Architekturaenderung | SPEC-Aenderung **vor** der Implementierung |
| Neue Faehigkeit | Statusstufe festlegen, in die Capability Matrix eintragen |
| Sicherheitsaenderung | Security Matrix und Abschnitt 4 aktualisieren |
| Neuer Befund | Known Issues ergaenzen, mit Schwere und Status |
| Behobener Befund | Status aendern, Regressionstest nennen |
| Roadmap-Aenderung | Abschnitt 21 aktualisieren, Reihenfolge begruenden |
| Live-Verbindung | Nachweisstand in Abschnitt 11 **und** `integrations.py` |
| macOS-Verifikation | Abschnitt 14, keine Vorwegnahme |

**MUST:** Keine Erfolgsmeldung darf staerker formuliert sein als der
tatsaechliche Nachweis.

### Wie konkret dieses Dokument werden darf

**MUST:** Bei Sicherheit konkret werden. Nicht "JARVIS soll sicher sein",
sondern: "Jede Aktion nach aussen durchlaeuft vor der Ausfuehrung eine
deterministische Zielpruefung und Autorisierung." Nicht "Fremdtext wird
behandelt", sondern: "Unvertrauenswuerdiger externer Inhalt wird vom Modelllayer
niemals zu einer vertrauenswuerdigen Anweisung erhoben."

**MUST NOT:** Technische Details festschreiben, die keine Architekturentscheidung
sind. Eine Bibliothek und ihre Version gehoeren in `pyproject.toml`, nicht in
eine Spezifikation -- sonst veraltet sie beim naechsten Update.

Die Grenze verlaeuft an der Frage: *Wuerde eine andere Wahl hier die
Sicherheitsarchitektur oder eine geplante Faehigkeit beruehren?* Wenn ja, ist es
eine Architekturentscheidung und gehoert hierher. Wenn nein, gehoert es in den
Code.

Beispiele aus diesem Dokument. Festgeschrieben, weil Architektur: dass das
Dashboard ausschliesslich an Loopback bindet; dass der Modellschluessel ueber
die Standardeingabe geht; dass Ziele aus vertrauenswuerdiger Quelle neu
berechnet werden. Bewusst nicht festgeschrieben: welcher Webserver, welches
Schriftbild, welche SQLite-Version, welches Modell -- alles austauschbar, ohne
eine Zusage dieses Dokuments zu brechen.

---

## 28. Handoff Instructions

Fuer eine neue Sitzung ohne bisherigen Verlauf.

### In fuenf Saetzen

JARVIS ist ein persoenlicher Assistent fuer macOS, der Mail und Kalender liest,
einordnet, Antworten entwirft und ein Briefing erzeugt. Der Kern ist fertig und
getestet (1063 Tests), sechs Faehigkeiten laufen nach einem einheitlichen
Vertrag. **Kein externer Dienst wurde je erreicht, und nichts lief je auf
macOS.** Die zwei bestaetigten Sicherheitsluecken im Freigabeweg (SEC-1, SEC-2)
sind seit 3.1 behoben und mit Regressionstests belegt; naechster
REQUIRED-Punkt ist die erste echte Verbindung. Alles unter PLANNED und IDEA ist
ausdruecklich **nicht** zu bauen.

### Schnellstart

```sh
uv sync
uv run pytest -q                              # 1063 Tests, siehe KI-8
uv run ruff check . && uv run ruff format --check .

export JARVIS_HOME=/tmp/jarvis-probe
uv run python -m jarvis init
# In der Konfiguration: [services] mode = "mock"
uv run python -m jarvis mail poll
uv run python -m jarvis services check        # zeigt den Nachweisstand
```

`mail poll` braucht zusaetzlich einen erreichbaren Modellanbieter -- der Mock
ersetzt Gmail, **nicht** das Modell. Wer den ganzen Weg ohne Netz sehen will,
haengt `trocken` in `[llm.tasks.classify]` und setzt dessen `reply` auf eine
Antwort, die zum Schema passt.

### Die Fragen, die eine neue Sitzung beantwortet haben muss

| Frage | Antwort |
|---|---|
| Was existiert? | Abschnitt 15, Current Capability Matrix |
| Was ist nur Mock? | Abschnitt 11 -- alle fuenf Dienste LIVE VERIFIED = NO |
| Was ist verifiziert? | Was in Abschnitt 15/16 als "gemessen" steht |
| Was ist sicherheitskritisch? | Abschnitt 3.2 (vier Prinzipien) und 16 |
| Was funktioniert nicht? | Abschnitt 17, Known Issues |
| Was kommt als Naechstes? | Abschnitt 21, die REQUIRED-Punkte |
| Was darf **nicht** gebaut werden? | Alles unter PLANNED und IDEA, Abschnitt 20 |
| Wie fuege ich eine Faehigkeit hinzu? | Abschnitt 6.2, neun Schritte |
| Wie loest ein Modell eine Aktion aus? | Gar nicht direkt -- Abschnitt 3.1 und 5.1 |
| Welche Gatter gibt es? | Abschnitt 4.2 |
| Was muss vor einer externen Aktion passieren? | Zielpruefung, Gatter, Protokoll -- Abschnitt 5.1 |

### Architekturentscheidungen, die nicht gebrochen werden duerfen

1. Das Modell waehlt nie ein Ziel.
2. Das Gatter ist die einzige Stelle, die Handeln erlaubt.
3. Der Stoppschalter wirkt ohne Datenbank und faellt geschlossen aus.
4. Eine Freigabe ersetzt die Autonomiestufe -- sonst nichts.
5. Fremdtext erreicht nie `act()`.
6. Das Protokoll ist unveraenderlich.
7. Neue Faehigkeiten starten auf Stufe 0.
8. Sprache hat keinen `act`-Pfad.
9. Zugangsdaten nur in der Keychain.
10. Kein PLANNED-Feature wird vorgezogen.

### Arbeitsweise

1. Frage nach, bevor du eine Annahme triffst, die spaeter teuer wird.
2. Test vor oder zusammen mit der Funktion, nie danach.
3. Kein Feature ohne Trockenlaufpfad.
4. Erklaere nach jeder Datei kurz, was sie tut und warum so.
5. Unsicher, ob etwas gegen Abschnitt 3.2 verstoesst? Dann verstoesst es dagegen.
   Anhalten und fragen.
6. Keine neue Abhaengigkeit ohne Begruendung.
7. Ein abgegrenzter Arbeitsschritt pro Sitzung, danach Tests, Zusammenfassung,
   anhalten.

---

## Anhang A — Abdeckung der 70 Blueprint-Anforderungen

Der SPEC-3-Blueprint enthaelt **70 nummerierte Anforderungen** (§1-§70) und
verlangt in §69 zusaetzlich **28 Ausgabe-Abschnitte**. Beides ist zweierlei: die
28 Abschnitte sind die Gliederung, die 70 Anforderungen sind der Inhalt. Diese
Matrix fuehrt die 70 einzeln nach.

Status: **erfuellt** = im Dokument vorhanden und belegt. Der Beleg nennt die
SPEC-3-Stelle.

| § | Anforderung | Status | Beleg in SPEC-3 |
|---|---|---|---|
| 1 | Nichts blind uebernehmen, Quellenhierarchie | erfuellt | Kopf ("Repository state", "Based on"); Lesehinweis; Abschnitt 2 durchgehend am Code belegt |
| 2 | Vier Statusstufen | erfuellt | Abschnitt *Statusstufen*, fuenf Stufen inkl. HISTORICAL |
| 3 | Goldene Regel fuer Zukunftsfunktionen | erfuellt | *Statusstufen* → "Die goldene Regel", 15 verbotene Artefakte |
| 4 | Warum die Zukunft beschrieben wird | erfuellt | 19.1; 19.4 mit der konkreten Sackgassen-Pruefung |
| 5 | Zielbild von JARVIS | erfuellt | 19.1 |
| 6 | Grundarchitektur | erfuellt | 3.1 Diagramm |
| 7 | Das Modell ist nicht die Autoritaet | erfuellt | 3.2 P1, vierfach abgesichert; 5.1 |
| 8 | Read / Decide / Act | erfuellt | 3.3 Tabelle |
| 9 | Untrusted Content | erfuellt | 3.2 P3; 4.1 Vertrauensgrenzen |
| 10 | Prompt-Injection als Architekturprinzip | erfuellt | 3.2 P1+P2+P3 zusammen; gemessenes Beispiel in 3.2 P1 |
| 11 | Action Execution Layer | erfuellt | 19.2 |
| 12 | Atomische Aktion, Race Conditions | erfuellt | 5.2 bekannte Luecken; SEC-2; OD-1 |
| 13 | Approval System | erfuellt | 4.2; 5.1; SEC-1 als bestaetigter Verstoss gegen genau diese Regel |
| 14 | Stop Switch | erfuellt | 4.2 Reihenfolge; Security Matrix |
| 15 | Autonomie explizit modelliert | erfuellt | **4.3**, vier Stufen tabelliert; Begruendung gegen die 5-Stufen-Vorlage |
| 16 | Skill-System, sieben Eigenschaften | erfuellt | **6.1**, Tabelle mit Beispiel `mail_send` |
| 17 | LLM Layer, Provider-Abstraktion | erfuellt | Abschnitt 7; Routing-Kriterien als PLANNED in Abschnitt 20 |
| 18 | Lokale und Cloud-Modelle, modellagnostisch | erfuellt | Abschnitt 7, MUST-Satz |
| 19 | Isolation, Model vs JARVIS capability | erfuellt | 3.2 P2 mit Messung; OD-5 Zielhost-Allowlist |
| 20 | Secrets | erfuellt | 4.7; Abschnitt 8 Kategorie Secrets |
| 21 | Datenarchitektur, zehn Kategorien | erfuellt | **Abschnitt 8**, alle zehn, drei davon ausdruecklich leer |
| 22 | Memory, Arten und Attribute | erfuellt | **9.1** sieben Arten, **9.2** sechs Attribute |
| 23 | User Context | erfuellt | **9.3** |
| 24 | Task System | erfuellt | 19.5 Steckbrief Tasks |
| 25 | Document System | erfuellt | 19.5 Steckbrief Documents |
| 26 | File System | erfuellt | 19.5 Steckbrief Files |
| 27 | Research / Web | erfuellt | 19.5 Steckbrief Research (als REQUIRED gefuehrt, weil die Faehigkeit existiert) |
| 28 | Voice | erfuellt | 19.5 Steckbrief Voice |
| 29 | Home Automation | erfuellt | 19.5 Steckbrief Home Automation |
| 30 | Proaktivitaet | erfuellt | 19.5 Steckbrief Proactive Agent |
| 31 | Daemon / Always-On | erfuellt | **19.5 Steckbrief Always-On**, sechs Eigenschaften einzeln bewertet |
| 32 | Dashboard als Control Plane | erfuellt | **Abschnitt 12**, alle 15 Bereiche mit Ist-Stand (7 vorhanden) |
| 33 | Dashboard ist nicht die Sicherheitsinstanz | erfuellt | 4.6; Abschnitt 12 MUST |
| 34 | Observability | erfuellt | **4.9**, acht Fragen mit Herkunft |
| 35 | Audit-Integritaet | erfuellt | 3.2 P4; 4.9 bekannte Grenze |
| 36 | Privacy | erfuellt | Abschnitt 10; 9.3 |
| 37 | Fehlerzustaende | erfuellt | **5.2**, neun Zustaende zugeordnet, drei fehlen nachweislich |
| 38 | Idempotenz | erfuellt | SEC-2 mit Messung; Security Matrix; OD-1 |
| 39 | Teststrategie, sieben Arten | erfuellt | Abschnitt 13, Tabelle |
| 40 | Mock ist nicht Live | erfuellt | *Statusstufen* → Nachweisstufen; Abschnitt 11 |
| 41 | macOS | erfuellt | Abschnitt 14, PLATFORM VERIFIED = NO ausnahmslos |
| 42 | Technische Schulden, sechs Felder | erfuellt | Abschnitt 18, TD-1 bis TD-5 |
| 43 | Security Findings aus dem Audit | erfuellt | Abschnitt 17, 12 behobene und 7 offene |
| 44 | **Approval + Allowlist pruefen** | erfuellt | **SEC-1** -- geprueft, bestaetigt, als SECURITY ISSUE gefuehrt |
| 45 | **Doppelte Ausfuehrung pruefen** | erfuellt | **SEC-2** -- geprueft, bestaetigt, mit Messung |
| 46 | SPEC-2 Vergleich | erfuellt | Abschnitt 25, alle fuenf Kategorien |
| 47 | Zwoelf-Felder-Schema je PLANNED-Feature | erfuellt | **19.5**, acht Steckbriefe, alle zwoelf Felder |
| 48 | Keine Phantom-Implementierungen | erfuellt | 19.3 MUST NOT; Abschnitt 24; kein Code geaendert |
| 49 | Architectural Playground / Extension Points | erfuellt | **19.3**, fuenf Punkte mit Ist-Stand |
| 50 | Future Compatibility | erfuellt | **19.4**, sechs Faehigkeiten geprueft, zwei Befunde |
| 51 | Roadmap aus dem Ist-Zustand | erfuellt | Abschnitt 21 mit Reihenfolgebegruendung |
| 52 | Security before Autonomy | erfuellt | Abschnitt 21 Leitregel |
| 53 | Nicht-funktionale Anforderungen | erfuellt | **3.4**, alle acht mit Ist-Stand |
| 54 | Current Capability Matrix | erfuellt | Abschnitt 15, sieben Spalten |
| 55 | Security Matrix | erfuellt | Abschnitt 16, alle elf geforderten Eigenschaften |
| 56 | Future Capability Matrix | erfuellt | Abschnitt 20, "Implement Now?" durchgehend NO |
| 57 | Open Architectural Decisions | erfuellt | Abschnitt 23, OD-1 bis OD-5 |
| 58 | Non-Goals | erfuellt | Abschnitt 24 |
| 59 | Change Management | erfuellt | Abschnitt 27 |
| 60 | Versionierung | erfuellt | Kopfblock |
| 61 | Handoff-Anforderung | erfuellt | Abschnitt 28, alle 15 Fragen beantwortet |
| 62 | MUST / SHOULD / MAY / PLANNED / IDEA | erfuellt | *Statusstufen*; **MAY tatsaechlich verwendet** in 4.3 und 19.3 |
| 63 | Technische Details nur wo stabil | erfuellt | **Abschnitt 27** → "Wie konkret dieses Dokument werden darf" |
| 64 | Sicherheit muss konkret sein | erfuellt | Abschnitt 27 mit Gegenbeispielen; 3.2 durchgehend |
| 65 | Keine Code-Aenderungen waehrend der Spec | erfuellt | Abschnitt 17 SEC-1/SEC-2 als Finding statt Fix; Anhang B |
| 66 | Validierung der fertigen Spec | erfuellt | Anhang B |
| 67 | Finaler Self-Audit | erfuellt | Anhang B |
| 68 | Abschliessender Grundsatz | erfuellt | **Abschnitt 1** → "Der Leitsatz" |
| 69 | Erwartetes Ergebnis, 28 Abschnitte | erfuellt | Abschnitte 1-28 vollstaendig vorhanden |
| 70 | Letzte Anweisung, nichts vorziehen | erfuellt | goldene Regel; Abschnitt 20; Abschnitt 24; kein Code geaendert |

**70 von 70 erfuellt.** Die fett gesetzten Belege sind in der Nachtragsrunde
entstanden -- acht Anforderungen fehlten ganz, acht waren nur teilweise
abgedeckt. Gefunden wurden sie nicht durch den Self-Audit unten, sondern durch
eine Auszaehlung der Blueprint-Anforderungen: der Self-Audit prueft gegen die
**Gliederung**, und eine vollstaendige Gliederung kann fehlenden Inhalt
verdecken. Beide Pruefungen sind noetig, und sie pruefen Verschiedenes.

---

## Anhang B — Self-Audit dieser Spezifikation

| Pruefung | Ergebnis |
|---|---|
| Ist der aktuelle Code korrekt dargestellt? | ja -- jede CURRENT-Aussage am Code oder an ausgefuehrten Tests geprueft |
| Sind alle Audit-Befunde beruecksichtigt? | ja -- 12 behobene in Abschnitt 17, 7 offene Unstimmigkeiten, 2 Sicherheitsluecken |
| Sind offene Probleme sichtbar? | ja -- SEC-1 und SEC-2 in Executive Summary, Security Matrix, Known Issues und Roadmap |
| Sind Security-Findings korrekt klassifiziert? | ja -- SEC-1 und SEC-2 als SECURITY ISSUE, nicht als technische Schuld (Blueprint §44) |
| Sind Mock und Live getrennt? | ja -- Abschnitt 11, alle fuenf LIVE VERIFIED = NO |
| Ist macOS-Verifikation korrekt angegeben? | ja -- Abschnitt 14, ausnahmslos NO |
| Ist SPEC-2 als historisch gekennzeichnet? | ja -- Abschnitt 25 |
| Sind aktuelle Anforderungen von Zukunftsplaenen getrennt? | ja -- Abschnitte 1-16 vs. 19-21 |
| Sind PLANNED-Features nicht zur Implementierung freigegeben? | ja -- Abschnitt 20, Spalte "Implement Now?" durchgehend NO |
| Ist die zukuenftige Architektur ausreichend beschrieben? | ja -- Abschnitt 19 mit acht Steckbriefen nach vollem Schema |
| Voice, Tasks, Files, Documents, Research, Home Automation, Proaktivitaet? | ja -- alle in 19.5; Research als REQUIRED, weil die Faehigkeit existiert |
| Gibt es Phantom-Implementierungen? | nein -- die Spec-Erstellung und die Nachtragsrunde haben keinen Code geaendert. Fassung 3.2 begleitet eine Codeaenderung (OD-4), die ausschliesslich vorhandene Anzeigen betrifft: keine neue Faehigkeit, kein Stub, keine Tabelle, kein vorgezogenes PLANNED-Feature |
| Ist das Execution-/Authorization-Modell klar? | ja -- Abschnitt 5, beide Wege symmetrisch |
| Ist die Approval-Architektur klar? | ja -- 5.1, mit beiden offenen Luecken |
| Ist der Stop Switch geschuetzt? | ja -- 4.2, gemessen |
| Ist Untrusted Content korrekt behandelt? | ja -- 3.2 P3, gemessen |
| Ist Idempotenz/Race Condition beruecksichtigt? | ja -- SEC-2, gemessen und bestaetigt; 5.2 nennt zusaetzlich den Teilausfuehrungsfall |
| Sind Memory und Privacy beruecksichtigt? | ja -- Abschnitte 9 und 10, gemeinsam entworfen (9.3) |
| Ist die Roadmap nachvollziehbar? | ja -- Abschnitt 21 mit Begruendung der Reihenfolge |
| Kann ein neuer Claude allein mit Repository + SPEC-3 arbeiten? | Abschnitt 28 ist darauf ausgelegt |
| Sind alle 70 Blueprint-Anforderungen abgedeckt? | ja -- Anhang A, einzeln mit Beleg |

**Nicht geprueft und ausdruecklich offen:** alles unter Abschnitt 14 (macOS) und
Abschnitt 11 (Live-Verbindungen). Diese Luecken lassen sich nicht durch Lesen
schliessen.
