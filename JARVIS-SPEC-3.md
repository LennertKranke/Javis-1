# JARVIS-SPEC-3

```
Document:              JARVIS-SPEC-3
Status:                CURRENT SOURCE OF TRUTH
Version:               3.0
Created:               2026-08-30
Repository state:      commit 0b7b9b7, Arbeitsbaum sauber
Test state:            1018 pytest gruen, ruff check sauber, ruff format sauber
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
15 882 Zeilen Quellcode, 12 062 Zeilen Tests, 1018 Tests gruen. Sechs
Faehigkeiten nach einem einheitlichen Vertrag. Drei Bedienwege: CLI, Dashboard,
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
Beide wurden durchgefuehrt, **beide haben eine Luecke bestaetigt**:

* **SEC-1**: Eine Freigabe umgeht die Allowlist. Bestaetigt, **OFFEN**.
* **SEC-2**: Kein atomarer Anspruch auf eine Freigabe. Doppelausfuehrung erzeugt
  doppelte Wirkung. Bestaetigt, **OFFEN**.

Beide sind dokumentiert, nicht behoben -- die Erstellung dieser Spezifikation ist
ein Dokumentationsauftrag (Blueprint §3, §65). Sie stehen als oberste
REQUIRED-Punkte in Abschnitt 21.

**Die Lehre aus dem Querschnitt**, die diese Spezifikation praegt:

> Gruene Tests je Phase beweisen nicht, dass die Phasen zusammenspielen. Alle drei
> schwersten Befunde lagen **zwischen** Bausteinen, die einzeln einwandfrei
> funktionierten.

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

SQLite mit sieben Migrationen ueber `PRAGMA user_version`, WAL,
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
Stoppschalter, **nicht** den Ein-Aus-Schalter, **nicht** die Obergrenze und
**nicht** den Trockenlauf.

**Gemessen:** Bei aktivem Trockenlauf bleibt ein freigegebener Vorgang offen,
mit Vermerk "Trockenlauf global aktiv".

### 4.3 Least Privilege bei Gmail

**CURRENT.** Die Rechte des Gmail-Clients haengen an der Autonomiestufe:

```
send_capabilities(config) -> SENDING   wenn permits("mail_send", 1)
                          -> DRAFTING  sonst
```

Auf Stufe 0 ist der Sende-Endpunkt **gar nicht freigeschaltet**. Ein Fehler in
der Sendelogik kann dort nichts senden. Vier Tests decken das ab.

### 4.4 Endpunkt-Allowlists

**CURRENT.** Je Faehigkeit eine Liste aus Methode und verankertem Muster,
geprueft mit `fullmatch`. `/messages/send` steht bewusst **nicht** darin --
Versand geht ausschliesslich ueber `/drafts/send`, damit genau der Entwurf
hinausgeht, der vorher geprueft wurde.

### 4.5 Dashboard-Absicherung

**CURRENT**, gemessen: Bindung ausschliesslich an Loopback (`--host 0.0.0.0`
scheitert mit `ConfigError`), Sitzungstoken 32 Byte in `~/.jarvis/web-token`
(0600, zeitkonstanter Vergleich), Origin-Pruefung bei jeder veraendernden
Anfrage, CSP `default-src 'none'`, `nosniff`, `no-store`, kein JavaScript.

**MUST (Blueprint §33):** Das Dashboard ist Oberflaeche, nicht
Sicherheitsinstanz. Es ruft `execute_approval` auf, das dieselbe Kette durchlaeuft
wie jeder andere Weg. Ein Knopf darf nie direkt einen externen Dienst aufrufen.

### 4.6 Zugangsdaten

**MUST.** Zugangsdaten gehoeren nicht in Git, Logs, SQLite, Konfigurationsdateien,
Prompts oder Protokolleintraege.

**CURRENT.** Auf macOS ist die Keychain die einzige Quelle, **ohne stillen
Rueckfall**. Abweichungen meldet `jarvis status` und setzt den Rueckgabewert auf
1. Das Log wurde auf fuenf Geheimnisbegriffe durchsucht: 0 Treffer.

### 4.7 Dateirechte

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

---

## 5. Execution Model

### 5.1 Zwei Wege, ein Gatter

**CURRENT.** Es gibt genau zwei Wege zu einer externen Aktion. Beide gehen durch
dasselbe Gatter, und beide fuehren Buch.

```
run_skill:           poll -> decide -> [GATTER] -> act -> after
execute_approval:            verify_targets -> [GATTER] -> act -> after_approval
```

Dass `run_skill` kein `verify_targets` braucht, ist richtig: dort sind die Ziele
gerade erst aus der Quelle berechnet worden. Auf dem Freigabeweg kommt die
Entscheidung aus der Datenbank und **MUST** gegen die Quelle geprueft werden.

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
| Freigabe | `pending`, `executed`, `rejected`, `failed` |
| Mail | `seen`, `analysed`, `acted`, `skipped` |
| Antwort | `planned`, `drafted`, `skipped`, `held`, gesendet ueber `sent_at` |

**Bekannte Luecke:** Es gibt **keinen** zentralen, atomaren Anspruch auf eine
Aktion (`CLAIMED` / `EXECUTING`). Siehe SEC-2.

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
    autonomy_level: int       # ab welcher gewaehrten Stufe sie handeln darf
    requires_outbound: bool   # erreicht sie Dritte? (Anzeige + Pflicht zur Obergrenze)

    def poll(self) -> list[Event]: ...
    def decide(self, event: Event) -> Decision: ...
    def act(self, decision: Decision) -> Result: ...

    def verify_targets(self, decision: Decision) -> Decision: ...
    def after(self, event, decision, disposition, result) -> None: ...
    def after_approval(self, decision, result) -> None: ...
```

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
| Temporary | Prozessweise `TemporaryDirectory` | leeres `HOME` je Modellaufruf |

**Datensparsamkeit, CURRENT:** `mail_messages` speichert nur Kennung, Thread und
Kategorie -- **keine** Inhalte. Absender und Betreff stehen im Protokoll und in
Freigaben (das Dashboard zeigt sie), der Nachrichtentext nirgends.

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

**Was fehlt (PLANNED):** ein ausdruecklicher Vertrauensgrad je Eintrag, und eine
Unterscheidung zwischen vom Nutzer gesagten und aus Fremdtext abgeleiteten
Tatsachen. Siehe OD-2.

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

**CURRENT.** Lokale Instrumententafel: Zustand, Briefing, anstehende
Entscheidungen, Protokoll. Freigabe und Verwerfen per Klick, Stoppschalter auf
jeder Ansicht. Serverseitiges HTML, kein JavaScript, ein handgeschriebenes
Stylesheet.

Im Trockenlauf zeigt es die Vorgaenge, blendet die Freigabe-Schaltflaeche aus und
sagt warum: "Trockenlauf ist an. Verwerfen geht, Freigeben bewirkt nichts."

**Abweichung von SPEC-2 (HISTORICAL).** SPEC-2 §7 gibt Farbwerte, IBM-Plex-Schriften,
SSE und ein zweigeteiltes Stromelement vor. Umgesetzt sind andere Farbwerte,
Systemschriften und `meta refresh`. Das ist **bewusst offen** und keine Schuld:
SPEC-2 ist nicht mehr verbindlich. Ob angeglichen wird, ist eine offene
Entscheidung (OD-4).

**MUST:** Das Dashboard ist niemals die Sicherheitsinstanz (§4.5).

---

## 13. Testing

**CURRENT:** 1018 Tests, Laufzeit rund 16 s. Verhaeltnis Testcode zu Quellcode
0,76 : 1.

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
| SQLite, Migrationen | CURRENT | ja | -- | -- | NO | 7 Migrationen, WAL, `BEGIN IMMEDIATE` |
| Protokoll mit Hash-Kette | CURRENT | ja | -- | -- | NO | UPDATE/DELETE gemessen abgewiesen |
| Ratenbegrenzung | CURRENT | ja | -- | -- | NO | nebenlaeufig geprueft; Trockenlauf verbraucht nichts |
| Stoppschalter | CURRENT | ja | -- | -- | NO | wirkt ohne Datenbank, faellt geschlossen aus |
| Normalisierung | CURRENT | ja | -- | -- | NO | Rahmenfaelschung gemessen blockiert |
| Gatter | CURRENT | ja | -- | -- | NO | einzige Stelle, gilt fuer alle Faehigkeiten |
| Freigabewarteschlange | CURRENT | ja | -- | -- | NO | **SEC-1, SEC-2 offen** |
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
| Dashboard | CURRENT | ja | -- | -- | NO | Token, Origin, CSP, kein JS |
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
| **Approval** | Ersetzt die Stufe, nicht Stoppschalter/Trockenlauf/Obergrenze | **ja** fuer diese Eigenschaft | **hoch** | **SEC-1 und SEC-2 schliessen** |
| **Allowlist** | Nur in `decide()` ausgewertet. Der Freigabeweg umgeht `decide()` | **Luecke bestaetigt** | **hoch** | **SEC-1**: in `verify_targets` und unmittelbar vor dem Versand pruefen |
| **Prompt Injection** | Normalisierung + P1 + P2; Modell hat keine Werkzeuge, Ausgabe wird nie ausgefuehrt | **ja**, Fassung des Rahmens blockiert; Ziel aus Kopffeldern gemessen | niedrig | Bei Dokumenten und Web dieselbe Grenze |
| **Isolation** | Eigener Prozess, gefilterte Umgebung, leeres HOME, Schluessel ueber stdin | **teilweise**: Dateizugriff und Netz offen | mittel | `sandbox` auf macOS messen; Zielhost-Allowlist pruefen |
| **Secret Storage** | Keychain-only auf macOS, kein stiller Rueckfall, Abweichung gemeldet | **teilweise**: nur simulierte Plattform | mittel | Auf echtem macOS verifizieren |
| **File Permissions** | 0700/0600, reparierend, vollstaendig inkl. WAL, Rotation, Sperrdatei, Token | **ja**, gemessen | niedrig | Bei neuen Dateiarten `core/files.py` benutzen |
| **Audit** | Hash-Kette + SQLite-Trigger, auch abgelehnte Aktionen | **ja**, Manipulation gemessen abgewiesen | niedrig | Bei komplexeren Aktionen Kette erhalten |
| **Idempotency** | **Kein** zentraler atomarer Anspruch. Nur `mail_send` schuetzt sich selbst ueber `sent_at` | **Luecke bestaetigt**: doppelte Freigabe erzeugt zwei Entwuerfe | **hoch** | **SEC-2**: zentraler Anspruch im Ausfuehrungsweg |
| **Exception Handling** | `decide` und `act` auf beiden Wegen abgesichert, Daemon je Tick | **ja**, gemessen | niedrig | Bei neuen Wegen mitziehen |

---

## 17. Known Issues

### Bestaetigte Sicherheitsluecken -- OFFEN

#### SEC-1 — Eine Freigabe umgeht die Allowlist

```
Status:      BESTAETIGT, OFFEN
Schwere:     hoch  (eine E-Mail geht an eine gesperrte Adresse)
Gefunden:    bei der Erstellung von SPEC-3, Blueprint §44
Betroffen:   jarvis/skills/runner.py (execute_approval)
             jarvis/skills/mail/reply.py (MailSendSkill.verify_targets, act)
```

**Ursache.** Die Allowlist wird ausschliesslich in `MailSendSkill.decide()`
ausgewertet. Der Freigabeweg ruft `decide()` nie auf -- er baut die Entscheidung
aus der Datenbank wieder auf und geht direkt zu `verify_targets`. Dort werden
Antwortdatensatz, Versandzustand, Durchsicht und Entwurfsintegritaet geprueft,
**nicht** die Allowlist. Die harte Sperre in `act()` prueft Entwurfsidentitaet und
Fingerabdruck -- ebenfalls nicht die Allowlist.

**Fehlerszenario, gemessen:**

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

**Gewuenschtes Verhalten.** Eine Freigabe **MUST** ausschliesslich die
Autonomiestufe ersetzen. Sie darf die Allowlist nicht ersetzen -- so wie sie
Stoppschalter, Trockenlauf und Obergrenze nicht ersetzt. Die Allowlist gehoert in
`verify_targets` **und** in die harte Sperre unmittelbar vor dem Versand, weil
zwischen Freigabe und Ausfuehrung Tage liegen koennen.

**Regressionstest (zu schreiben).** Vorgang bei erlaubter Adresse einstellen,
Adresse sperren, freigeben -- es darf nichts hinausgehen, und der Vorgang muss den
Grund tragen. Gegenprobe: bei weiterhin erlaubter Adresse geht er hinaus.

**Status des Fixes:** nicht behoben. Diese Runde ist ein Dokumentationsauftrag
(Blueprint §3, §65). Oberster REQUIRED-Punkt, Abschnitt 21.

#### SEC-2 — Kein atomarer Anspruch auf eine Freigabe

```
Status:      BESTAETIGT, OFFEN
Schwere:     hoch  (doppelte externe Wirkung)
Gefunden:    bei der Erstellung von SPEC-3, Blueprint §45
Betroffen:   jarvis/skills/runner.py (execute_approval)
             jarvis/core/approvals.py
```

**Ursache.** `execute_approval` prueft `approval.pending` auf dem **uebergebenen
Abbild**, nicht gegen die Datenbank, und es gibt keinen Zustand zwischen
`pending` und `executed`. Zwei Aufrufe mit demselben Abbild -- Doppelklick, zwei
Arbeiter, Daemon und Dashboard gleichzeitig -- laufen beide durch.

**Fehlerszenario, gemessen:**

```
mail_reply, derselbe Vorgang zweimal freigegeben:
  1. Aufruf: performed = True
  2. Aufruf: performed = True
  Entwuerfe: ['Draft_1', 'Draft_2']

ERGEBNIS: doppelter Entwurf im Postfach
```

Bei `mail_send` haelt es -- aber **zufaellig**: `verify_targets` prueft dort
`sent_at`, und das ist gesetzt. Der Schutz liegt in der Faehigkeit, nicht im
Rahmenwerk. Eine kuenftige Faehigkeit erbt ihn nicht.

**Gewuenschtes Verhalten.** Der Ausfuehrungsweg **MUST** einen Vorgang atomar
beanspruchen, bevor gehandelt wird -- ein Zustandsuebergang
`pending -> claimed`, der nur einmal gelingen kann. Konzeptionell:
`PENDING -> CLAIMED -> EXECUTING -> SUCCEEDED | FAILED | CANCELLED`. Die genaue
Zustandsmaschine wird nach Analyse des bestehenden Codes festgelegt (OD-1).

**Regressionstest (zu schreiben).** Derselbe Vorgang zweimal ausgefuehrt -- genau
eine Wirkung. Zusaetzlich nebenlaeufig mit getrennten Verbindungen.

**Status des Fixes:** nicht behoben. Zweiter REQUIRED-Punkt.

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
Freigabeweg (Q-1) und der fehlende atomare Anspruch (SEC-2) sind Symptome
desselben Musters. Ein zentraler Ausfuehrungsweg wuerde beides an einer Stelle
loesen:

```
Skill Decision
      -> Execution Request
      -> Target Verification
      -> Authorization       (Stufe, Allowlist, Policy)
      -> Approval Check
      -> Stop Switch
      -> Atomic Claim        (loest SEC-2)
      -> External Action
      -> Result
      -> Audit
```

**Was die heutige Architektur dafuer schon mitbringt:** ein einziges Gatter,
`verify_targets` als Vertragsbestandteil, die Hash-Kette, und seit dem Audit zwei
symmetrische Wege. **Was fehlt:** der atomare Anspruch und die Allowlist als
Teil der Autorisierung statt der Entscheidung.

**Explizit nicht jetzt umgesetzt:** keine neue Klasse, kein Interface, kein
Umbau. Die Beschreibung dient dazu, SEC-1 und SEC-2 nicht als Einzelpflaster zu
loesen, sondern in die richtige Richtung.

### 19.3 Feature-Steckbriefe

#### Tasks — PLANNED

```
Feature:       Aufgabenverwaltung
Status:        PLANNED
Purpose:       Aufgaben erkennen, verwalten, priorisieren, an Fristen erinnern
Architectural role:  Neue Faehigkeit nach dem Vertrag aus Abschnitt 6
Inputs:        Mail, Kalender, direkte Eingabe
Outputs:       strukturierte Aufgaben mit Faelligkeit und Zustand
Security:      Aufgabentexte aus Mail sind untrusted. Das Modell darf eine
               Aufgabe vorschlagen, aber kein Ziel und keine Frist erzwingen,
               die eine Aktion ausloest
Integration boundary:  eigener Speicher, eigene Faehigkeit, Stufe 0
Dependencies:  keine externen Dienste
What today's architecture must support:
               Skill-Vertrag traegt sie unveraendert; Gatter, Protokoll und
               Ratenbegrenzung erbt sie ueber run_skill
Explicitly NOT implemented now:
               keine Task-Klasse, keine Tabelle, kein Scheduler, keine
               Erinnerung, kein Dashboard-Element, kein CLI-Befehl
```

#### Documents — PLANNED

```
Feature:       Dokumentenanalyse
Status:        PLANNED
Purpose:       PDFs, Rechnungen, Vertraege verstehen
Architectural role:  Leseweg mit besonders strenger Untrusted-Grenze
Security:      Dokumente sind untrusted, ausnahmslos. Ein Dokument darf keine
               Anweisung an JARVIS ausloesen. Der Analyseprozess bekommt keine
               Werkzeuge -- genau wie heute der Modellaufruf
What today's architecture must support:
               sanitize() und die Prozesstrennung sind der vorgesehene Weg;
               beide sind vorhanden und muessen es bleiben
Explicitly NOT implemented now:
               kein Parser, kein OCR, keine Dokumententabelle, kein Skill
```

#### Files — PLANNED

```
Feature:       Dateiablage
Status:        PLANNED
Purpose:       Dateien finden, klassifizieren, kontrolliert ablegen
Security:      Dateipfade sind Ziele im Sinne von P1. Sie muessen
               deterministisch berechnet werden -- nie aus der Modellantwort
What today's architecture must support:
               Die Zielfeldsperre deckt path, filepath, filename und
               destination bereits ab. Jede schreibende Aktion muss durch
               denselben Ausfuehrungsweg wie eine E-Mail
Explicitly NOT implemented now:
               kein Dateiskill, keine Pfad-Allowlist, kein Index
```

#### Research (Netzquelle) — REQUIRED, nicht PLANNED

Die Faehigkeit **existiert** (CURRENT), ihr fehlt nur die Quelle. Siehe
Abschnitt 21.

#### Voice (Komfort) — PLANNED

```
Feature:       Weckwort, Dauerschleife, komfortablere Sprachbedienung
Status:        PLANNED  (die Sprachschicht selbst ist CURRENT)
Security:      Ein Sprachbefehl darf nie mehr Rechte haben als derselbe Befehl
               als Text. Die heutige Asymmetrie -- anhalten per Sprache moeglich,
               fortsetzen nie -- MUST erhalten bleiben
What today's architecture must support:
               Sprache ist Bedienweise, keine Faehigkeit, und hat keinen
               act-Pfad. Das MUST so bleiben
Explicitly NOT implemented now:
               kein Weckwort, keine Dauerschleife, keine Sprachfaehigkeit
```

#### Home Automation — PLANNED

```
Feature:       HomeKit oder MQTT
Status:        PLANNED
Security:      Sicherheitskritischer als alles Bisherige. Das Modell darf nie
               eine Geraeteadresse oder ein Kommando erzeugen und ausfuehren.
               Modell entscheidet WAS grundsaetzlich gewuenscht ist ->
               deterministischer Code waehlt erlaubtes Geraet und Befehl ->
               Sicherheitsgatter -> Audit -> Aktion
What today's architecture must support:
               Der Action-/Permission-Layer darf nicht so eng an Gmail gekoppelt
               werden, dass externe Aktoren sich nicht sauber einfuegen. Heute
               ist er es nicht: das Gatter kennt nur Faehigkeitsnamen und Stufen
Explicitly NOT implemented now:
               keine HomeKit-Anbindung, kein MQTT, kein Geraeteskill,
               keine Geraete-Allowlist
```

#### Proactive Agent — PLANNED

```
Feature:       Proaktivitaet
Status:        PLANNED
Purpose:       Wichtige Mail, bevorstehende Frist, Kalenderkonflikt, offene
               Entscheidung von sich aus melden
Security:      Proactive Observation ist nicht Proactive Action. Beobachten
               darf JARVIS; jede daraus entstehende Aktion MUST weiterhin durch
               Policy, Permission, Autonomy, Approval, Gate, Execution, Audit
What today's architecture must support:
               Kalenderkonflikte und Fristen werden bereits erkannt. Es fehlt
               nur der Weg, sich von selbst zu melden -- und der darf kein
               zweiter Aktionspfad werden
Explicitly NOT implemented now:
               keine Benachrichtigung, kein Push, keine Regel-Engine
```

---

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
[erledigt]  SPEC-3  <- hier stehen wir

  1. SEC-1 und SEC-2 schliessen                          REQUIRED
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

### Die fuenf REQUIRED-Punkte

| # | Was | Warum jetzt | Braucht |
|---|---|---|---|
| **1** | **SEC-1 und SEC-2 schliessen** | Zwei bestaetigte Sicherheitsluecken im Freigabeweg. Beide sind Voraussetzung dafuer, dass eine echte Verbindung ueberhaupt verantwortbar ist | nichts ausser Freigabe |
| **2** | Erste echte Verbindung, lesend, Stufe 0, Trockenlauf an | Der groesste offene Punkt ueberhaupt. Alles ist gebaut, nichts ist je gelaufen. OAuth, Fehlerformate, Token-Erneuerung sind ungepruefte Annahmen | Google-Cloud-Projekt, Desktop-OAuth |
| **3** | macOS-Verifikation | Zielplattform. `jarvis llm check` mit Sandbox, `services check --live`, Plist laden, Keychain, Whisper, `say` | den Mac; keine neue Zeile Code |
| **4** | Execution Layer konsolidieren | SEC-2, TD-3 und KI-1 haben dieselbe Wurzel. Einzeln geflickt bleiben sie wiederkehrend | Entscheidung OD-1 |
| **5** | Netzquelle fuer Recherche | Die Faehigkeit steht, findet aber nur den Beispielbestand | Anbieter-Key oder eigene Quelle |

**Reihenfolge-Begruendung.** 1 vor 2, weil eine bestaetigte Luecke im
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
          C ist der Ist-Zustand und die Ursache von SEC-2.
Status:   OFFEN
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
Empfehlung: Erst entscheiden, wenn das Dashboard zur Control Plane ausgebaut
          wird. Eine Angleichung jetzt waere Aufwand ohne Funktionsgewinn.
Status:   OFFEN
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

* Die Designfassung des Dashboards aus SPEC-2 §7. Sie bleibt eine gute Vorlage
  fuer die kuenftige Control Plane, ist aber kein Abnahmekriterium (OD-4).
* Der Entscheidungsstrom als Signaturelement (§7.5) -- die Zweiteilung "was das
  Modell entschied / was der Code tat" macht die Vertrauensgrenze sichtbar und
  bleibt eine starke Idee.

---

## 26. Acceptance Criteria

Woran sich die naechsten Schritte messen lassen.

### Fuer SEC-1 (Allowlist)

* [ ] Ein Vorgang, dessen Adresse nach dem Einstellen gesperrt wurde, geht bei
      Freigabe **nicht** hinaus.
* [ ] Der Grund steht im Vorgang und im Protokoll.
* [ ] Gegenprobe: eine weiterhin erlaubte Adresse geht hinaus.
* [ ] Die Pruefung greift in `verify_targets` **und** unmittelbar vor dem Versand.
* [ ] Mutationsprobe: Pruefung entfernt -> Test schlaegt fehl.

### Fuer SEC-2 (atomarer Anspruch)

* [ ] Derselbe Vorgang zweimal ausgefuehrt erzeugt genau **eine** Wirkung.
* [ ] Nebenlaeufig mit getrennten Verbindungen ebenso.
* [ ] Der zweite Aufruf meldet einen verstaendlichen Grund, keinen Fehler.
* [ ] Gilt fuer **alle** Faehigkeiten, nicht nur `mail_send`.

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

---

## 28. Handoff Instructions

Fuer eine neue Sitzung ohne bisherigen Verlauf.

### In fuenf Saetzen

JARVIS ist ein persoenlicher Assistent fuer macOS, der Mail und Kalender liest,
einordnet, Antworten entwirft und ein Briefing erzeugt. Der Kern ist fertig und
getestet (1018 Tests), sechs Faehigkeiten laufen nach einem einheitlichen
Vertrag. **Kein externer Dienst wurde je erreicht, und nichts lief je auf
macOS.** Zwei bestaetigte Sicherheitsluecken im Freigabeweg sind offen (SEC-1,
SEC-2) und stehen ganz oben auf der Roadmap. Alles unter PLANNED und IDEA ist
ausdruecklich **nicht** zu bauen.

### Schnellstart

```sh
uv sync
uv run pytest -q                              # 1018 Tests
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
| Was kommt als Naechstes? | Abschnitt 21, die fuenf REQUIRED-Punkte |
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

## Anhang — Self-Audit dieser Spezifikation

| Pruefung | Ergebnis |
|---|---|
| Ist der aktuelle Code korrekt dargestellt? | ja -- jede CURRENT-Aussage am Code oder an ausgefuehrten Tests geprueft |
| Sind alle Audit-Befunde beruecksichtigt? | ja -- 12 behobene in Abschnitt 17, 6 offene Unstimmigkeiten, 2 neue Sicherheitsluecken |
| Sind offene Probleme sichtbar? | ja -- SEC-1 und SEC-2 in Executive Summary, Security Matrix, Known Issues und Roadmap |
| Sind Security-Findings korrekt klassifiziert? | ja -- SEC-1 und SEC-2 als SECURITY ISSUE, nicht als technische Schuld (Blueprint §44) |
| Sind Mock und Live getrennt? | ja -- Abschnitt 11, alle fuenf LIVE VERIFIED = NO |
| Ist macOS-Verifikation korrekt angegeben? | ja -- Abschnitt 14, ausnahmslos NO |
| Ist SPEC-2 als historisch gekennzeichnet? | ja -- Abschnitt 25 |
| Sind aktuelle Anforderungen von Zukunftsplaenen getrennt? | ja -- Abschnitte 1-16 vs. 19-21 |
| Sind PLANNED-Features nicht zur Implementierung freigegeben? | ja -- Abschnitt 20, Spalte "Implement Now?" durchgehend NO |
| Ist die zukuenftige Architektur ausreichend beschrieben? | ja -- Abschnitt 19 mit Steckbriefen |
| Voice, Tasks, Files, Documents, Research, Home Automation, Proaktivitaet? | ja -- alle in Abschnitt 19/20; Research als REQUIRED, weil die Faehigkeit existiert |
| Gibt es Phantom-Implementierungen? | nein -- diese Runde hat **keinen** Code geaendert |
| Ist das Execution-/Authorization-Modell klar? | ja -- Abschnitt 5 |
| Ist die Approval-Architektur klar? | ja -- Abschnitt 5.1, mit beiden offenen Luecken |
| Ist der Stop Switch geschuetzt? | ja -- Abschnitt 4.2, gemessen |
| Ist Untrusted Content korrekt behandelt? | ja -- P3, gemessen |
| Ist Idempotenz/Race Condition beruecksichtigt? | ja -- SEC-2, gemessen und bestaetigt |
| Sind Memory und Privacy beruecksichtigt? | ja -- Abschnitte 9 und 10 |
| Ist die Roadmap nachvollziehbar? | ja -- Abschnitt 21 mit Begruendung der Reihenfolge |
| Kann ein neuer Claude allein mit Repository + SPEC-3 arbeiten? | Abschnitt 28 ist darauf ausgelegt |

**Nicht geprueft und ausdruecklich offen:** alles unter Abschnitt 14 (macOS) und
Abschnitt 11 (Live-Verbindungen). Diese Luecken lassen sich nicht durch Lesen
schliessen.
