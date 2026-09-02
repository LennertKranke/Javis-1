# JARVIS — Projektstand und Uebergabe

Stand: Neugestaltung des Dashboards 2026-09-02, Branch `claude/plugin-082094`
(Pull Request gegen `main`).
1076 Tests gruen, zu jeder Tageszeit (KI-8 im Test behoben), `ruff check`
und `ruff format --check` sauber.

Dieses Dokument beschreibt den **tatsaechlichen** Stand, nicht die Absicht.
Verbindliche Vorgabe ist `JARVIS-SPEC-3.md` (Source of Truth); die
historische `JARVIS-SPEC.md` bleibt als Ursprung liegen und gilt nur, wo
SPEC-3 nichts sagt. Ausfuehrliche Begruendungen stehen in `README.md`; hier
steht, was eine neue Sitzung wissen muss, um ohne den bisherigen Verlauf
weiterzuarbeiten.

---

## 0. Die vier Zustaende

Ueberall in diesem Dokument gilt:

| Zustand | Bedeutung |
|---|---|
| **implementiert** | Code da, Tests da, im Betrieb ausgefuehrt |
| **nicht produktiv verbunden** | Code da, Tests da, **nie mit dem echten Dienst gesprochen** |
| **geplant** | Entwurf steht, Code fehlt |
| **fehlt** | nichts davon |

Der wichtigste Satz des ganzen Dokuments:

> **Kein externer Dienst hat je mit JARVIS gesprochen.**
> `jarvis services check` zeigt fuenfmal `nie`. Das ist gemessen, nicht
> geschaetzt: die Spalte fuellt nur ein echter Adapter nach einer Antwort.

---

## 1. Was vollstaendig implementiert und getestet ist

### Kern (`jarvis/core/`)

| Modul | Was es tut |
|---|---|
| `config.py` | TOML, Autonomiestufen, Stoppschalter, alle Abschnitte. 1371 Zeilen -- die groesste Datei, weil jede Einstellung dort geprueft wird |
| `db.py` | SQLite, 7 Migrationen, `BEGIN IMMEDIATE`, WAL |
| `audit.py` | Hash-Kette (SHA-256 ueber kanonisches JSON + Vorgaenger), Trigger gegen UPDATE/DELETE |
| `ratelimit.py` | Rollende Fenster, in der Datenbank. Haelt unter Nebenlaeufigkeit (gemessen) |
| `sanitize.py` | NFKC, HTML weg, unsichtbare Zeichen weg, `<<<UNTRUSTED-CONTENT>>>`-Rahmen |
| `gate.py` | Die einzige Stelle, die "darf gehandelt werden" beantwortet |
| `approvals.py` | Warteschlange fuer Freigaben von Hand |
| `memory.py` | Langzeitgedaechtnis, hoechstens 500 Tatsachen |
| `context.py` | Kurzzeitkontext + Kontextbauer mit Obergrenze |
| `secrets.py` | macOS-Keychain. Auf macOS **ohne** stillen Rueckfall |
| `integrations.py` | Der Nachweisstand je externem Dienst |
| `log.py` | JSON Lines nach `~/.jarvis/logs/` |

### Modelle (`jarvis/llm/`)

Provider-Schnittstelle ohne Werkzeugparameter (Prinzip 2.2 als Bauform),
Router mit Rueckfallkette und Vertraulichkeitssperre, erzwungenes JSON-Schema
mit **Zielfeldsperre** (ein Schema mit `to`/`url`/`path`/`iban` laesst sich
nicht anlegen).

Prozesstrennung: `[llm] isolation = "subprocess"` (Standard) fuehrt jeden
Modellaufruf in einem eigenen Interpreter aus, mit gefilterter Umgebung.

### Faehigkeiten (`jarvis/skills/`)

| Skill | Verlangte Stufe | Ausgehend | Stand |
|---|---|---|---|
| `mail` | 0 | nein | implementiert, nicht produktiv verbunden |
| `mail_reply` | 0 | nein | implementiert, nicht produktiv verbunden |
| `mail_send` | **1** | ja | implementiert, nicht produktiv verbunden |
| `calendar` | 0 | nein | implementiert, nicht produktiv verbunden |
| `briefing` | 0 | nein | **implementiert** (braucht keinen externen Dienst) |
| `research` | **1** | ja | implementiert, **ohne Netzquelle** |

### Bedienweisen (`jarvis/interfaces/`)

- `cli.py` -- 17 Befehle, siehe unten
- `web/` -- Dashboard auf localhost, Token, Origin-Pruefung, CSP, kein JS.
  Seit 2026-09-02 eine Leitstelle: Kern (Orb) mit Systemzustand, vier
  Ansichten, Gestaltung in `design/JARVIS-DESIGN-SYSTEM.md` (Fassung 2.0)
- `voice/` -- Sprache. **Bedienweise, keine Faehigkeit** (siehe §4)

### Dauerbetrieb

`daemon.py` mit `flock`-Einzelinstanz, unterbrechbarem Schlaf, letztem Lauf in
der Datenbank. `deploy/com.jarvis.daemon.plist` vorbereitet.

---

## 2. Was seit dem letzten Review geaendert wurde (`fb36f1c` bis `d0a010a`)

1. **Research-Skill gebaut.** SPEC Abschnitt 5 nennt `skills/research/`; es
   fehlte. Rollentrennung: Modell formuliert Begriffe, Code waehlt die Quelle
   aus einer Freigabeliste.
2. **Eigener Fehler gefunden und behoben:** Research stand auf
   `autonomy_level = 0`. Das Gatter vergleicht gewaehrte gegen verlangte
   Stufe -- beide 0, also lief sie auf Stufe 0 durch. Jetzt Stufe 1.
3. **Daemon-Zeitplan** prueft gegen baubare Faehigkeiten. Vorher liess sich
   `voice` einplanen; der Daemon waere bei jedem Tick stumm gescheitert.
4. **Whisper-Modellpfad** muss absolut sein. Ein relativer haengt am
   Arbeitsverzeichnis, und unter `launchd` ist das ein anderes.
5. **Gedaechtnis begrenzt** auf 500 Tatsachen. Verdraengt wird die
   unwichtigste, bei gleichem Gewicht die aelteste.
6. **Nebenlaeufigkeitstest** fuer die Ratenbegrenzung. Der behauptete
   Race-Condition-Befund war **keiner** -- 8 Faeden, 20 Versuche, Obergrenze
   10, es kamen genau 10 durch. Gefehlt hat nur der Test.
7. **Voice end-to-end** und **Dry-Run von aussen** getestet (zaehlender
   Client statt "nichts gespeichert", mit Gegenprobe).

Davor, in `fb36f1c`: Laufzeit-Mock fuer Gmail und Kalender, `integrations.py`,
`jarvis services check`.

---

## 2a. Audit Phase 1-7 und was daraus folgte

Ein unabhaengiger Durchgang durch Phase 1-7, ohne die Angaben der vorigen
Sitzung zu uebernehmen. Nachgemessen statt nachgelesen: Stoppschalter,
Hash-Kette, Schemapruefung, Rahmenfaelschung, Kopfeinschleusung, XSS,
Endpunktmuster und die Prozesstrennung wurden einzeln angegriffen.

**Ergebnis:** Phase 1-3, 5, 6 tragen. Die vier Kernprinzipien halten, mit der
bekannten und dokumentierten Einschraenkung bei 2.2 (das Netz bleibt offen,
siehe README). Die Dokumentation war an keiner Stelle gruener als der
Nachweis -- ausser bei der Mock-Aussage weiter oben, die jetzt korrigiert ist.

**Behoben, jeweils mit Regressionstest:**

| Befund | Was war | Wo |
|---|---|---|
| Dateirechte | `~/.jarvis` 0755, `state.db`/Logs/`config.toml` 0644. Darin: Entwurfstexte, Empfaenger, Betreffzeilen, Gedaechtnis | `core/files.py` (neu) |
| `act()` ohne Ausnahmeschutz | eine unerwartete Ausnahme beendete den ganzen Durchlauf, die restlichen Vorgaenge fielen aus | `skills/runner.py` |
| Endpunkt-Allowlist | `muster.match` statt `fullmatch` -- Pythons `$` laesst einen abschliessenden Umbruch durch | `mail/gmail.py`, `calendar/google.py` |
| Ganztagestermine | standen als `00:00` da, und die Zeitzonenumrechnung schob sie in westlichen Zonen auf den **Vortag** | `interfaces/cli.py` |
| Spalte "Ausgehend" | `mail` stand auf "nein", schreibt aber Labels zu Google. Der Wert war richtig, die Ueberschrift falsch | CLI + Dashboard |
| plist-Kommentar | behauptete das Gegenteil von `RunAtLoad` | `deploy/` |
| Mock-Aussage | siehe Abschnitt 5 | dieses Dokument |

**Neu dazugekommen:** `jarvis status` meldet offene Dateirechte und gibt dann
1 zurueck. JARVIS zieht die Rechte bei jedem Laden und jedem
Verbindungsaufbau selbst nach -- auch bei einer Ablage, die vor dieser
Aenderung entstanden ist. Die Meldung ist fuer den Fall, dass das `chmod`
scheitert.

**Beim Beheben zusaetzlich gefunden:** die Rechtepruefung im Statusbericht
schlug zuerst auf einer noch leeren Ablage an -- ein Fehlalarm, der einen
bestehenden Test brach. Beides steht jetzt als Test da.

**Nicht angefasst:** das Dashboard weicht in Farbwerten, Schrift und
Nachladeweise von der Designfassung der Spezifikation ab (Meta-Refresh statt
SSE, keine IBM-Plex-Schriften). Das ist bekannt und bewusst offen gelassen --
es gehoert in die konsolidierte Spezifikation, nicht in eine Korrekturrunde.

---

## 2b. End-to-End-Review Phase 1-7

Nach A-G ein zweiter, unabhaengiger Durchgang -- diesmal nicht Phase fuer Phase,
sondern quer: greifen sie ineinander? Der Postfachlauf wurde vollstaendig
durchgespielt (einordnen, entwerfen, freigeben, versenden) und dabei gemessen,
was in der Datenbank landet.

### Was der Durchgang belegt hat

* **Prinzip 2.1 haelt durch die ganze Kette.** Die Einschleusungsnachricht des
  Mocks verlangt Versand an `sammler@fremd.example`. In der Warteschlange steht
  als Ziel `fremder@unbekannt.example` -- der Absender aus den Kopffeldern. Das
  Angreiferziel kommt im ganzen Vorgang nicht vor.
* **Eine Freigabe hebt den Trockenlauf nicht auf.** Gemessen: der Vorgang bleibt
  offen, mit dem Vermerk "Trockenlauf global aktiv".
* **Der Versand faellt geschlossen aus.** Ein Entwurf, der sich nicht mehr
  verifizieren laesst, geht nicht hinaus -- auch nicht nach einer Freigabe.
* **Ratenbegrenzung**: Trockenlauf verbraucht nichts, echte Laeufe schon.

### Behobene Befunde

| Befund | Was war | Wo |
|---|---|---|
| **Freigabeweg war eine Sackgasse** | `execute_approval` rief `skill.after()` nie. Der Entwurf entstand im Postfach, aber der Antwortspeicher blieb auf "geplant, kein Entwurf" -- und `pending_for_send` verlangt das Gegenteil. Ein im Dashboard freigegebener Entwurf konnte **nie versendet werden** | `skills/base.py`, `skills/runner.py`, `mail/reply.py` |
| `secure_dir` liess Zwischenstufen offen | `mkdir(parents=True, mode=...)` setzt den Modus nur auf die letzte Stufe. Bei `JARVIS_HOME=/a/b/c` blieben `/a` und `/a/b` offen | `core/files.py` |
| Web-Token legte das Basisverzeichnis mit 0755 an | N-1 aus dem Audit | `web/security.py` |
| Sperrdatei des Daemons entstand mit 0644 | N-2 aus dem Audit | `daemon.py` |
| Rechtepruefung zaehlte Pfade auf | N-3. Sie uebersah genau die zwei, die offen waren. Jetzt laeuft sie das Verzeichnis ab | `core/files.py`, `cli.py` |
| Briefing-Hinweis fuehrte im Kreis | Nach `briefing --neu` im Trockenlauf stand da "Erzeugen: jarvis briefing --neu" -- genau der Befehl, der gerade lief | `cli.py` |
| Gatter versprach zu viel | Der Kommentar sagte, der Schattenbetrieb zeige, *wann* die Grenze gegriffen haette. Tut er nicht: was nichts verbraucht, laesst den Zaehler stehen | `core/gate.py` |

Der neue Haken **`after_approval`** ist die Gegenstelle zu `after`: auf dem
Freigabeweg gibt es kein Ereignis mehr, weil die Entscheidung aus der Datenbank
kommt. Standard ist absichtlich nichts; verdrahtet sind `mail_reply` und
`mail_send`, deren Buchfuehrung das Ereignis ohnehin nie brauchte.

### Bewusst nicht geaendert

* **`mail` und `calendar` haben kein `after_approval`.** Nach einer Freigabe
  bleibt ihr Zustand nicht-final, die Nachricht wird also erneut aufgegriffen.
  Folgenarm: `cached_analysis` verhindert einen zweiten Modellaufruf, das Label
  ist idempotent, und der naechste normale Durchlauf setzt den Zustand richtig.
  Ihre `after`-Rumpfe lesen aus `event.payload` Dinge, die sich aus der
  aufbewahrten Entscheidung nicht rekonstruieren lassen -- das waere ein Umbau,
  keine Korrektur.
* **`briefing` speichert nur in `act()`.** `mail` und `calendar` speichern in
  `poll`/`after` und ueberleben damit den Trockenlauf; das Briefing nicht. Mit
  dem voreingestellten `dry_run = true` entsteht deshalb nie eines. Das ist
  folgerichtig (Trockenlauf heisst: nichts geschieht), aber es ist eine
  Unstimmigkeit zwischen den Phasen. Der Hinweistext sagt es jetzt; die
  Semantik zu aendern waere eine Entscheidung, keine Korrektur.
* **`jarvis briefing --neu` gibt im Trockenlauf 1 zurueck.** Vertretbar in beide
  Richtungen -- nichts ist schiefgegangen, aber es liegt auch kein Briefing vor.

### Grenze des Mocks

Der Gmail-Mock haelt Entwuerfe nur im Arbeitsspeicher. Ueber mehrere
CLI-Aufrufe hinweg laesst sich der Versandweg deshalb nicht durchspielen: der
Entwurf ist im naechsten Prozess weg, und die Integritaetspruefung haelt ihn --
zu Recht -- zurueck. Innerhalb eines Prozesses laeuft die Kette vollstaendig.

---

## 2c. Konsolidierung (2026-09-01)

Vor dieser Sitzung lag die Arbeit in vier unverbundenen Branches; der
Default-Branch war der aelteste Stand, und es gab weder `main` noch CI noch
je einen Pull Request. Der juengste Arbeitsstand (Designsystem) enthielt die
SEC-Fixe **nicht** -- sie lagen auf einem Geschwister-Branch.

Was diese Sitzung getan hat:

1. **Zusammengefuehrt:** `claude/jarvis-design-system-us1y4r` (Designsystem,
   Entwurfsblaetter, Dashboard-Umbau mit `gate.preview`) und
   `claude/javis-1-read-only-audit-e2lawf` (SEC-1 und SEC-2 behoben,
   SPEC-3 Fassung 3.1). Der Merge war konfliktfrei; alle Tests gruen.
2. **Naht geprueft und getestet:** Das Dashboard ruft `execute_approval`,
   damit greifen atomarer Anspruch (SEC-2) und Allowlist auf dem Freigabeweg
   (SEC-1) auch vom Browser aus. Zwei neue Tests in `test_web.py` halten das
   fest: Doppelklick fuehrt genau einmal aus; ein bereits beanspruchter
   Vorgang wird ueber die Route weder ausgefuehrt noch geschlossen.
3. **SPEC-Versionierung bereinigt:** 3.1 gehoert den SEC-Fixen. Der
   Dashboard-Nachtrag (`design/SPEC-3-NACHTRAG.md`, OD-4) ist auf **3.2**
   umnummeriert und wurde nach Freigabe des Nutzers am 2026-09-01 in
   `JARVIS-SPEC-3.md` eingetragen (OD-4: ENTSCHIEDEN; Zahlen am aktuellen
   Stand neu gemessen).
4. **CI eingerichtet:** `.github/workflows/ci.yml` -- `uv sync`, `ruff check`,
   `ruff format --check`, `pytest` bei jedem Push und Pull Request.
5. **`CLAUDE.md` angelegt:** Befehle, Dokumenten-Rangfolge, Arbeitsregeln --
   wird von jeder Claude-Code-Sitzung automatisch geladen.
6. **Drei Entwurfsblaetter erstmals im Browser gerendert** (01, 02, 08;
   helle Fassung, 1280 px, headless Chromium): sie stellen korrekt dar.
   Dunkle Fassung und Groessenstufen bleiben ungeprueft.

Die alten Branches (`claude/jarvis-spec-phase-1-e3hopg`,
`claude/jarvis-audit-phase-1-7-w73he0`, `claude/jarvis-design-system-us1y4r`,
`claude/javis-1-read-only-audit-e2lawf`) sind vollstaendig in `main`
enthalten und koennen geloescht werden, sobald `main` der Default-Branch ist.

Arbeitsweise ab jetzt: **jede Sitzung endet mit einem Pull Request gegen
`main`**, nicht mit einem frei stehenden Branch. Die CI muss gruen sein,
bevor gemerged wird.

---

## 2d. Neugestaltung des Dashboards (2026-09-02)

Auftrag: das Webinterface zu einer konsistenten, tatsaechlich nutzbaren
Leitstelle machen -- dunkel, Orange, ruhig, mit einem Kern als visuellem
Zentrum -- und `design/` auf eine einzige Quelle bringen. Architektur,
Routen, Sicherheitskopfzeilen und Aktionswege sind unveraendert; geaendert
ist ausschliesslich `jarvis/interfaces/web/` samt Tests und Dokumentation.

1. **Stylesheet neu** (`style.py`): warmes Schwarz, ein Akzent Orange, Glas
   statt Flaeche, Systemschriften, Bewegung nur am Kern und am Puls im Band,
   `prefers-reduced-motion` schaltet alles ab. Keine helle Fassung mehr.
   Kein `url()`, kein `style`-Attribut -- beides wuerde die CSP still
   verwerfen; zwei Tests halten das fest.
2. **Lage als Leitstelle** (`app.py`, `render.py`): in der Mitte der Kern,
   dessen Zustand aus Tatsachen abgeleitet ist (`render.zustand_ermitteln`:
   angehalten > Abweichung > wartet > Betrieb; Abweichung heisst Kette
   gebrochen, Ablage offen oder Zugangsdaten abweichend -- dieselben
   Pruefungen wie `jarvis status`). Daneben Kennzahlen und System, darunter
   Anstehend (Vorschau ohne Knopf), Zuletzt im Protokoll, Faehigkeiten mit
   der Spalte "Letzter Lauf (Daemon)" aus `daemon.letzter_lauf`. Die Lage
   hat kein Formular ausser dem Stoppschalter.
3. **Rahmen**: Systemband zuerst im Dokument (klebt oben), Stoppschalter als
   `Anhalten` / `Fortsetzen` mit Inline-SVG; Kopf mit Wortmarke und
   Navigation; Tafeln mit Eckwinkeln; Tabellen tragen `data-kopf` und werden
   im schmalen Fenster zu Bloecken; breite Tabellen rollen im Rahmen.
4. **Nicht gebaut, mit Absicht**: Chat oder Eingabefeld (zweiter Aktionsweg,
   SPEC-3 12 MUST NOT, `web/app.py`), Seiten fuer Dienste, Modelle,
   Gedaechtnis, Fehler, Tasks (PLANNED, Roadmap 6), Zustaende Laeuft, Denkt,
   Offline (SPEC-3 5.2 kennt sie nicht). Keine Mock-Daten in der
   Oberflaeche: alles kommt aus Konfiguration, Datenbank und Stoppdatei.
5. **`design/` bereinigt**: `designsystem.html` (Blaetterwerk) und
   `prototyp/` (zehn Entwurfsblaetter plus CSS) entfernt -- altes Design,
   Vorschlag 1.0, zeigte PLANNED-Bereiche. `JARVIS-DESIGN-SYSTEM.md` ist in
   Fassung 2.0 neu geschrieben und beschreibt die Implementierung, nicht
   umgekehrt. `SPEC-3-NACHTRAG.md` bleibt als Nachweis, mit Hinweis.
   README.md (Phase 4) und CLAUDE.md nachgezogen.
6. **Tests**: 13 neue in `test_web.py` (jetzt 67): jede registrierte Route
   ausser `/jarvis.css` verlangt den Token (TD-1 als Test ueber
   `app.routes`), kein Inline-Stil, kein `url()`, der Kern folgt
   Stoppschalter, offenen Vorgaengen und Kette, die Navigation zeigt genau
   vier Ansichten, die Lage entscheidet nichts (zehnmal Laden aendert weder
   Protokoll noch Kontingent) und hat kein Formular ausser `/stop`, Tabellen
   tragen ihren Kopf, der Stoppschalter steht vor allem anderen. Alle 54
   bestehenden Tests sind unveraendert gruen.
7. **Im Browser geprueft** (Chromium ueber Playwright, gegen das laufende
   Dashboard mit Mock-Diensten): vier Ansichten bei 1440, 1100, 820 und 390
   px ohne horizontalen Ueberlauf; Zustaende Betrieb, Wartet, Angehalten,
   Abweichung (Kette gebrochen), Trockenlauf AUS, Mock; leere Ablage; 15
   Vorgaenge mit 40-zeiligen Entwuerfen und ueberlangen Betreffzeilen.
   Safari auf macOS: nicht geprueft (Sitzung unter Linux).

**Zweite Runde, visuelle Abnahme (Fassung 2.1 des Designsystems).** Nach
Ansehen aller Ansichten bei 1440, 1100, 820 und 390 px vier gezielte
Aenderungen, sonst nichts: rechts vom Kern stehen drei Tatsachen
(Zugangsdaten, Ablage, Modellprozess) in derselben Form wie die Zahlen links
statt einer Pfadliste; der aktive Navigationspunkt ist eine Akzentlinie statt
eines Kastens; Tafeln haben eine sichtbare Lichtkante und mehr Luft; das
Band nennt beim Stopp Grund, Urheber und Uhrzeit statt der Rohzeile
(`app._stoppgrund`). Eine ungenutzte Marke (`--kalt-flaeche`) entfernt.
Tests unveraendert gruen.

**Dritte Runde, Feinschliff am Kern (Fassung 2.2).** Der Kern ist eine
Kugel mit Lichtquelle oben links, dunklem Rand, Glanzlicht und feinen
Schichten, ein blasser Aussenring und ein Impuls alle neun Sekunden dazu,
17rem statt 15rem; Tafeln mit Weichzeichner und diagonaler Reflexion; die
Systemtatsachen rechts vom Kern spiegeln die Zahlen links; Tabellen ohne
Zeilenhervorhebung, Werte in Maschinenschrift. Nichts an Aufbau, Routen
oder Zustaenden. Im Browser geprueft in allen Zustaenden und Breiten.

**Vierte Runde, letzte Politur (Fassung 2.3).** Nur `style.py`: Systemzone
um den Kern (weiter Kreis, Horizontlinie, Hauch Licht), Doppelring und
zwoelf Naehte am Kern, ruhigeres Atmen und Glanzlicht; Kennzahlen als
Telemetrie mit zum Kern auslaufenden Lichtlinien; Akzentstrich an
Tafeltiteln, blassere Tabellenlinien, auslaufende Linie unter dem Band.
`--kern-groesse` haengt jetzt an `.lage-mitte`. Kein Aufbau, keine Route,
kein Zustand geaendert; im Browser bei 1440, 820, 390 px und im Stopp
geprueft.

**Ein Befund fuer den Nutzer -- SPEC-3 aendert nur er.** SPEC-3 Abschnitt 12
fuehrt die *Vertrauensnaht* als CURRENT (auch in Abschnitt 15 und 25). Sie
war am 2026-08-31 zurueckgebaut worden (Commit 397c3dd, Weg A-teil); der
Nachtrag wurde am 2026-09-01 trotzdem mit dieser Zeile eingetragen. Der Code
hat seit dem Rueckbau `render.vorgangsfakten()` -- eine gemeinsame Liste --
und ein Test prueft, dass keine Naht erscheint. Empfehlung: Zeile in 12
streichen, Bemerkung in 15 und 25 anpassen (Fassung 3.3). Der Hinweis steht
auch am Kopf von `design/SPEC-3-NACHTRAG.md`.

---

## 3. Tests

**1076, alle gruen -- zu jeder Tageszeit.** `uv run pytest` — Laufzeit
rund 20 s. KI-8 (`test_das_briefing_entsteht_aus_mock_daten`, fiel taeglich
von 22 bis 24 Uhr Berliner Zeit aus) ist am 2026-09-02 im Test behoben: die
Uhr ist auf acht Uhr des heutigen Ortstags festgenagelt, fuer Kalender-Mock
und Kalenderfaehigkeit gleichermassen; nachgemessen um 23:41 Ortszeit. Der
Code war nie betroffen. Die Tests laufen seit der Konsolidierung auch in der
CI (`.github/workflows/ci.yml`) bei jedem Push und Pull Request.

Groesste Gruppen: `test_voice.py` (99), `test_cli.py` (84), `test_web.py`
(67), `test_calendar.py` (64), `test_approvals.py` (51), `test_schema.py` (42),
`test_isolation.py` (41), `test_briefing.py` (39), `test_daemon.py` (38),
`test_research.py` (37).

Keine Typechecks im Projekt konfiguriert (kein mypy, kein pyright).

**Struktur-Tests** -- sie pruefen Architektur, nicht Verhalten, und schlagen
Alarm, wenn jemand etwas verdrahtet, das nicht verdrahtet sein darf:
- `interfaces/voice/session.py` enthaelt kein `build_skill`, kein `GmailClient`
- `llm/isolated.py` importiert keine Faehigkeit, kein Gatter, keine Datenbank
- `llm/transcribe.py` enthaelt keinen HTTP-Client
- `skills/research/` enthaelt keinen HTTP-Client
- die beiden Mock-Module rufen nie `merke_kontakt`

---

## 4. Bekannte Fehler, Schulden und offene Punkte

### Echte Fehler
Keine offenen. Die aus dem Audit sind behoben, siehe Abschnitt 2a.

### Dokumentation
- **SPEC-3 Abschnitt 12 nennt die Vertrauensnaht als CURRENT; sie ist seit
  2026-08-31 zurueckgebaut.** Siehe Abschnitt 2d. Korrektur nur durch den
  Nutzer (SPEC-3 Abschnitt 27).
- **KI-8 ist behoben** (Test auf feste Uhr gestellt, siehe Abschnitt 3).
  SPEC-3 Abschnitt 17 und der Kopfblock fuehren ihn noch als offen; das
  Nachziehen gehoert dem Nutzer (Abschnitt 27).

### Nie auf echter Hardware ausgefuehrt
- **macOS-Sandbox** (`isolation = "sandbox"`): Profil und Aufruf getestet,
  `sandbox-exec` **nie ausgefuehrt** -- Entwicklungsumgebung ist Linux.
  Nachmessen auf dem Mac: `jarvis llm check`, erwartet eine dritte Spalte.
- **Keychain-only**: nur mit simulierter Plattform getestet.
- **launchd-Plist**: als Property List geparst, nie geladen.
- **Whisper und `say`**: nur gegen Ersatzprogramme.

### Bewusste Grenzen
- `isolation = "subprocess"` nimmt dem Kindprozess die Umgebungsvariablen und
  die Code-Pfade, **nicht** den Dateizugriff. `~/.jarvis` bleibt ueber einen
  absoluten Pfad lesbar. Das ist gemessen und steht so im README.
- Das Netz bleibt auch in der Sandbox offen -- `sandbox-exec` filtert nicht
  nach Zielhost.
- Sprache hat keine Dauerschleife; `voice listen` macht eine Runde.

### Fallen fuer die naechste Sitzung
- **`voice` ist kein Skill.** SPEC Abschnitt 5 fuehrt `voice/` unter
  `interfaces/`. `build_skill("voice")` soll scheitern. Sie zur Faehigkeit zu
  machen hiesse, ihr einen `act`-Pfad zu geben -- genau den, der ihr fehlen
  soll. Gebaut wird sie ueber `build_session`.
- **`autonomy_level` am Skill ist die *verlangte* Stufe**, in
  `[capabilities]` steht die *gewaehrte*. `0 >= 0` ist wahr -- eine Faehigkeit
  mit `autonomy_level = 0` handelt also auch auf Stufe 0. Fuer alles, was
  hinausgreift, gehoert dort **1**.
- **Mock ist nicht Trockenlauf.** Beide gelten unabhaengig.
- **`ruff check --fix` auf einer halb geschriebenen Testdatei** entfernt
  Importe, die erst weiter unten gebraucht werden. Erst fertig schreiben.
- **`StaticProvider` wird nie ausgelagert** (Kosten). Wer den
  Subprozess-Weg testen will, baut `SubprocessProvider` direkt.
- **Das Dashboard hat `style-src 'self'` und `img-src 'none'`.** Ein
  `style`-Attribut oder ein `url()` im Stylesheet wird still verworfen --
  im Browser sieht man nur, dass etwas fehlt. Tests pruefen beides. Der Kern
  ist deshalb aus Gradienten gebaut, Symbole sind Inline-SVG.
- **Der Kern zeigt nur Zustaende, die das System fuehrt.** Wer einen neuen
  will, braucht erst die Tatsache (`zustand_ermitteln`), dann die Klasse,
  dann den Test -- nicht umgekehrt.

---

## 5. Was Mock/Stub ist und was wirklich funktioniert

### Funktioniert wirklich, ohne jeden externen Dienst
`init`, `status`, `stop`/`resume`, `log`, `verify`, `memory`, `context`,
`web` (Dashboard), `daemon`, `llm check`, `services check`, `voice ask`,
`research ask/poll/list`, `briefing` (Fassung ohne Modell).

### Laufzeit-Mock vorhanden (`[services] mode = "mock"`)
- **Gmail** (`skills/mail/mock.py`) -- 5 Beispielnachrichten, darunter ein
  Einschleusversuch. Dieselbe Faehigkeitspruefung wie der echte Client.
- **Kalender** (`skills/calendar/mock.py`) -- 5 Termine, beide Befundarten,
  verankert an *jetzt + 2 h*.
- Damit laufen `calendar poll` und `briefing --neu` vollstaendig -- beide
  brauchen kein Modell.
- **`mail poll` nicht.** Der Mock ersetzt Gmail, nicht das Modell: ohne
  erreichbaren Anbieter enden alle Nachrichten in `Fehler`. Nachgemessen im
  Audit. Wer den ganzen Weg ohne Netz sehen will, haengt `trocken` in
  `[llm.tasks.classify]` und setzt dessen `reply` auf eine Antwort, die zum
  Schema passt -- ein `{}` weist der Validierer korrekt ab.

### Stub mit klarer Naht, aber ohne Inhalt
- **Research-Quelle**: `MockSource` mit vier festen Dokumenten. Das
  Quellenprotokoll und die Freigabeliste stehen; **eine Netzquelle fehlt.**

### Nur Adapter, nie erreicht
Anthropic, Ollama, Gmail, Google Calendar, Keychain.

---

## 6. Was aus der Zielarchitektur fehlt

| Baustein | Zustand |
|---|---|
| Mail lesen/beantworten | implementiert, nicht produktiv verbunden |
| Kalender | implementiert, nicht produktiv verbunden |
| Lagebild / Briefing | **implementiert** |
| Internet / Research | Faehigkeit implementiert, **Netzquelle fehlt** |
| Voice (Eingabe/Ausgabe) | implementiert, nur gegen Ersatzprogramme |
| Memory | **implementiert** (Langzeit + Kurzzeit + Kontextbauer) |
| Kontrollierte Aktionen mit Freigabe | **implementiert** (Warteschlange + Dashboard) |
| Autonomer Dauerbetrieb | **implementiert** (Daemon + Plist, Plist nie geladen) |
| Smartphone-Steuerung | **fehlt** |
| Telefonzugriff | **fehlt** |
| Social Media | **fehlt** |
| Haus-/Geraetesteuerung | **fehlt** |
| Dateiablage | **fehlt** |
| Dokumentenanalyse | **fehlt** |
| Aufgabenverwaltung | **fehlt** |
| Autonomes Trading | ausdruecklich Zukunftsmusik, blockiert nichts |

---

## 7. Was spaeter echte Zugangsdaten braucht

Alles davon **nur nach ausdruecklicher Freigabe des Nutzers**. Keine
Zugangsdaten im Repo, in Argumenten, in der Prozessumgebung oder in Logs.

| Integration | Was noetig ist |
|---|---|
| Gmail | Google-Cloud-Projekt, Desktop-OAuth, `gmail.modify` + `gmail.send` |
| Google Calendar | dasselbe Token, zusaetzlich `calendar.readonly` |
| Anthropic | API-Key in der Keychain |
| Ollama | kein Schluessel, aber ein laufender lokaler Dienst |
| Websuche (Research) | Anbieter-Key oder eine eigene Quelle |
| Smartphone / Telefon | geraeteseitige Freigabe, vermutlich Shortcuts/Push |
| Social Media | je Plattform ein eigener OAuth-Weg |
| HomeKit / MQTT | HomeKit braucht macOS + Zentrale; MQTT einen Broker |

---

## 8. Was sich ohne Zugangsdaten vollstaendig vorbereiten laesst

- **Adapter + Laufzeit-Mock + Freigabeliste** fuer jede neue Integration,
  nach dem Muster von `skills/mail/mock.py` und `research/source.py`.
- **Skills** nach dem Vertrag aus 5.1 -- Aufgabenverwaltung, Dokumentenanalyse
  und Dateiablage brauchen ueberhaupt keinen externen Dienst.
- **Der Nachweisstand**: jede neue Integration bekommt einen Eintrag in
  `core/integrations.py` und faengt bei `nie` an.
- **Zeitplan, Gatter, Ratenbegrenzung, Protokoll** -- alles vorhanden, eine
  neue Faehigkeit erbt es durch `run_skill`.

---

## 9. Vorhandene Sicherheitsmechanismen

| Mechanismus | Wo |
|---|---|
| Modell waehlt nie ein Ziel | `llm/schema.py` Zielfeldsperre + `verify_targets` je Skill |
| Fremdtext ist Daten | `core/sanitize.py` + `<<<UNTRUSTED-CONTENT>>>`-Rahmen |
| Lesen/Handeln getrennt | `llm/isolation.py`, eigener Prozess ohne `JARVIS_*` |
| Protokoll unveraenderlich | Hash-Kette + SQLite-Trigger, `jarvis verify` |
| Ratenbegrenzung | `core/ratelimit.py`, `BEGIN IMMEDIATE`, nebenlaeufig geprueft |
| Stoppschalter | Datei; wirkt ohne Datenbank, faellt geschlossen aus |
| Autonomiestufen je Faehigkeit | `Config.permits()` -- eine Stelle fuer Gatter und Fabrik |
| Trockenlauf | global; eine Freigabe von Hand hebt ihn nicht auf |
| Freigabe von Hand | `core/approvals.py` + Dashboard, Ziele werden neu berechnet |
| Entwurfsintegritaet | Pruefung unmittelbar vor dem Versand |
| Sprache handelt nie | sechs feste Absichten, kein `act`-Pfad im Sprachmodul |
| Anhalten per Sprache, Fortsetzen nie | Asymmetrie in `voice/intents.py` |
| Keychain-only auf macOS | `core/secrets.py`, `status` meldet Abweichung |
| Endpunkt-Allowlists | Gmail und Kalender, abgeleitet aus den Faehigkeiten, `fullmatch` |
| Ablage nur fuer den Eigentuemer | `core/files.py`, 0700/0600, reparierend, samt Zwischenstufen |
| Rechtepruefung | `offene_pfade()` laeuft das Verzeichnis ab; `status` meldet und gibt 1 zurueck |
| Freigabeweg vollstaendig | `verify_targets` -> Gatter -> `act` -> `after_approval`, symmetrisch zu `run_skill` |

**Diese Mechanismen duerfen nicht abgeschwaecht werden.** SPEC Abschnitt 8.5:
Wer unsicher ist, ob etwas gegen Abschnitt 2 verstoesst -- es verstoesst
dagegen. Anhalten und fragen.

---

## 10. Vorschlag fuer die Reihenfolge

Die Konsolidierung (Abschnitt 2c) ist erledigt. Die Punkte 1 und 2 brauchen
beide den Nutzer an seinem Mac und lassen sich als **ein** Termin erledigen.

1. **Erste echte Verbindung** (Gmail + Kalender lesend, Stufe 0, Trockenlauf
   an). Der groesste offene Punkt ueberhaupt: alles ist gebaut, nichts ist je
   gelaufen. Braucht Zugangsdaten vom Nutzer.
2. **macOS-Verifikation** (`jarvis llm check`, `services check --live`,
   Plist laden). Braucht nur den Mac, keine neue Zeile Code.
3. **Aufgabenverwaltung** -- der naechste Skill, der ohne externen Dienst
   auskommt und Mail, Kalender und Briefing zusammenbindet.
4. **Research-Netzquelle** hinter der bestehenden Freigabeliste.
5. **Dokumentenanalyse**, dann **Dateiablage**.
6. Danach erst Geraete-, Telefon- und Social-Media-Anbindungen.

---

## Schnellstart fuer eine neue Sitzung

```sh
uv sync
uv run pytest -q                 # 1076 Tests
uv run ruff check . && uv run ruff format --check .

export JARVIS_HOME=/tmp/jarvis-probe
uv run python -m jarvis init
# In der Konfiguration: [services] mode = "mock"
uv run python -m jarvis mail poll
uv run python -m jarvis services check     # zeigt den Nachweisstand
```

Arbeitsweise: **eine Phase pro Sitzung**, danach Tests, Zusammenfassung,
anhalten und auf Freigabe warten (SPEC Abschnitt 6).
