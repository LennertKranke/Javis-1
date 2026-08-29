# JARVIS

Persoenlicher, autonom laufender Assistent. Verbindliche Vorgabe ist
`JARVIS-SPEC.md`; dieses Dokument beschreibt nur, was davon gebaut ist.

**Stand: Phase 1 abgeschlossen.** Der Kern steht. Es gibt noch keine
Faehigkeit, keinen Daemon und keine Anbindung an ein Postfach. JARVIS kann
derzeit sagen, was er duerfte -- nicht etwas tun.

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
erzwingt eine Wahl (`keychain`, `env`, `none`).

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

## Was noch nicht existiert

`skills/`, `daemon.py`, `interfaces/web/`, `interfaces/voice/` und die
launchd-plist unter `deploy/`. Alles ab Phase 2.
