# JARVIS

Persoenlicher, autonom laufender Assistent. Verbindliche Vorgabe ist
`JARVIS-SPEC.md`; dieses Dokument beschreibt nur, was davon gebaut ist.

**Stand: Phase 2 abgeschlossen.** Der Kern steht, und die erste Faehigkeit
liest Gmail und ordnet es ein. Sie sendet nichts. Es gibt noch keinen Daemon,
kein Dashboard und keine Sprache.

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

In der Google Cloud Console ein Projekt anlegen, die Gmail-API aktivieren und
Zugangsdaten vom Typ **Desktop-App** erzeugen. Die heruntergeladene
`client_secret.json` kommt in die Keychain, nicht ins Repo:

```sh
security add-generic-password -s jarvis -a gmail_client_secret -w "$(cat ~/Downloads/client_secret.json)"
uv run jarvis mail login
```

`login` oeffnet ein Browserfenster und legt den Token danach ebenfalls in der
Keychain ab. Angefordert werden `gmail.modify` und `gmail.send`.

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
Prozesstrennung mit Netz-Sandbox ist damit *nicht* erreicht; das bleibt eine
spaetere Verschaerfung.

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

## Was noch nicht existiert

Antworten (Phase 3), Dashboard (Phase 4), Kalender und Briefing (Phase 5),
Sprache (Phase 6). Es gibt noch keinen `daemon.py` und keine launchd-plist:
Durchlaeufe startet man vorerst von Hand mit `jarvis mail poll`.
