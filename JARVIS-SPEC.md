# JARVIS — Projektspezifikation

Dieses Dokument ist die verbindliche Vorgabe für dieses Projekt.
Lies es vollständig, bevor du Code schreibst.

---

## 1. Ziel

Ein persönlicher, autonom laufender Assistent auf macOS. Er liest E-Mails,
beantwortet einen wachsenden Teil davon selbständig, verwaltet Termine,
recherchiert und meldet sich proaktiv. Er läuft dauerhaft im Hintergrund
und hat eine Sprach- sowie eine Weboberfläche.

Vorbild ist J.A.R.V.I.S. aus den Iron-Man-Filmen: immer da, kennt den
Nutzer, handelt vorausschauend, meldet sich knapp und trocken. Umgesetzt
wird davon nur, was heute technisch tatsächlich geht.

### Nicht-Ziele

- Keine Alleskönner-Anwendung in einem Rutsch. Wir bauen in Phasen.
- Kein Feature ohne Test und ohne Trockenlauf-Modus.
- Keine Spracherkennung als Hauptbedienweg. Text ist der Standard,
  Sprache ist eine zusätzliche Ebene.

---

## 2. Unverhandelbare Kernprinzipien

Diese vier Regeln gelten in jeder Phase und für jede Erweiterung. Wenn
eine gewünschte Funktion gegen eine dieser Regeln verstößt, halte an und
frage nach, statt die Regel zu umgehen.

### 2.1 Das Modell wählt niemals ein Ziel

Empfängeradressen, Dateipfade, URLs für Schreibzugriffe und
Zahlungsempfänger werden ausschließlich von deterministischem Code aus
vertrauenswürdigen Quellen berechnet — bei E-Mail also aus den Headern der
Originalnachricht. Kein Feld im Ausgabeschema des Modells darf ein Ziel
enthalten.

### 2.2 Lesen und Handeln sind getrennte Prozesse

Der Teil, der fremde Inhalte verarbeitet, hat keinen Werkzeugzugriff und
keine Netzwerkverbindung nach außen. Er bekommt Text und gibt
strukturiertes JSON zurück. Der Teil, der handelt, sieht die fremden
Inhalte nie.

### 2.3 Fremde Inhalte sind Daten, keine Anweisungen

Jeder eingehende Text — E-Mails, Webseiten, Dokumente, Kalendereinladungen
— wird als unvertrauenswürdig behandelt und vor der Verarbeitung
normalisiert: HTML entfernen, Zero-Width-Zeichen entfernen, Text auf
sinnvolle Länge kürzen.

### 2.4 Jede Aktion nach außen ist protokolliert und abschaltbar

Vollständiges Protokoll in SQLite, harte Ratenbegrenzung, und eine
Stoppdatei, deren bloße Existenz jede ausgehende Aktion blockiert.

---

## 3. Autonomiestufen

"Autonom" heißt hier: läuft ohne Nachfrage durch. Das erreichen wir
schrittweise, weil ein System, das nach dem ersten Zwischenfall
abgeschaltet wird, am Ende weniger autonom ist als eines, das man laufen
lässt.

| Stufe | Verhalten | Wechsel zur nächsten Stufe |
|---|---|---|
| 0 | Schattenbetrieb: entscheidet alles, sendet nichts, protokolliert was es getan hätte | 2 Wochen ohne Einwände im Protokoll |
| 1 | Sendet automatisch an Adressen auf der Allowlist | 4 Wochen ohne Vorfall |
| 2 | Sendet automatisch in freigegebenen Kategorien an bekannte Kontakte | Manuelle Freigabe durch den Nutzer |
| 3 | Sendet automatisch, außer bei explizit gesperrten Kategorien | — |

Die Stufe steht in der Konfiguration und gilt pro Fähigkeit, nicht global.
Neue Fähigkeiten starten immer auf Stufe 0.

---

## 4. Technischer Rahmen

- macOS, Apple Silicon
- Python 3.12, Abhängigkeiten über `uv`
- SQLite für Zustand und Protokoll, ein einziges Schema, migrierbar
- `launchd` für Zeitsteuerung, plist im Repo unter `deploy/`
- Zugangsdaten ausschließlich in der macOS-Keychain, niemals im Repo,
  niemals in `.env` mit Klartext-Tokens im Git
- Strukturierte Logs als JSON Lines nach `~/.jarvis/logs/`
- `pytest` für Tests, `ruff` für Linting

---

## 5. Modulaufbau

```
jarvis/
  core/
    config.py        Konfiguration, Autonomiestufen, Stoppschalter
    db.py            SQLite-Schema, Migrationen
    audit.py         Protokoll jeder Entscheidung und Aktion
    ratelimit.py     Harte Obergrenzen pro Fähigkeit und Zeitfenster
    sanitize.py      Normalisierung unvertrauenswürdiger Texte
  llm/
    provider.py      Abstrakte Schnittstelle
    providers/       anthropic.py, openai.py, google.py, ollama.py
    router.py        Modellwahl nach Aufgabe, Kosten, Vertraulichkeit
    schema.py        Erzwungene JSON-Ausgabe, Validierung
  skills/
    base.py          Basisklasse: name, trigger, autonomiestufe, run()
    mail/
    calendar/
    research/
    briefing/
  interfaces/
    cli.py
    web/             Dashboard
    voice/           Spracheingabe und -ausgabe
  daemon.py          Hauptschleife
```

### 5.1 Fähigkeiten sind Plugins

Eine Fähigkeit ist eine Klasse mit festem Vertrag:

```python
class Skill:
    name: str
    autonomy_level: int  # ab welcher Stufe sie selbständig handeln darf
    requires_outbound: bool  # unterliegt Ratenbegrenzung und Stoppschalter

    def poll(self) -> list[Event]: ...
    def decide(self, event: Event) -> Decision: ...  # ruft das Modell, ohne Werkzeuge
    def act(self, decision: Decision) -> Result: ...  # deterministisch, ohne Modell
```

Neue Fähigkeiten kommen als neuer Ordner unter `skills/` dazu und
registrieren sich selbst. Kein Eingriff in den Kern nötig.

### 5.2 Modell-Abstraktion

Der Nutzer will mit mehreren KI-Systemen arbeiten. `provider.py` definiert
eine schmale Schnittstelle, die alle Anbieter erfüllen. Der Router wählt
pro Aufgabe:

- Klassifizierung, Sortierung → kleines, günstiges Modell
- Textentwürfe, Formulierung → starkes Modell
- alles mit sensiblen persönlichen Daten → lokales Modell über Ollama
- Recherche mit Websuche → Anbieter mit Suchwerkzeug

Die Zuordnung steht in der Konfiguration, nicht im Code. Ein Ausfall eines
Anbieters führt zu einem Rückfall auf den nächsten, nicht zum Absturz.

---

## 6. Phasen

Baue **eine Phase pro Sitzung**. Am Ende jeder Phase: Tests laufen lassen,
kurz zusammenfassen was entstanden ist, dann anhalten und auf Freigabe
warten. Beginne nicht eigenmächtig mit der nächsten Phase.

### Phase 1 — Fundament
`core/` vollständig, Konfiguration, Datenbank, Protokoll, Ratenbegrenzung,
Stoppschalter, Normalisierung. Provider-Abstraktion mit zwei Anbietern.
CLI mit `jarvis status` und `jarvis stop`. Tests für Ratenbegrenzung,
Stoppschalter und Normalisierung.
*Fertig, wenn:* `pytest` grün, `jarvis status` zeigt Stufe und Zähler.

### Phase 2 — Mail lesen
Gmail-API-Anbindung, OAuth über Desktop-Client, Scopes `gmail.modify` und
`gmail.send`. Vorfilter, Klassifizierer mit erzwungenem JSON-Schema.
Ausschließlich Stufe 0. Vergibt Labels, sendet nichts.
*Fertig, wenn:* eine Woche Postfach läuft durch, Protokoll ist plausibel.

### Phase 3 — Mail beantworten
Entwurfserzeugung mit Stilvorlagen aus alten Mails. Sendelogik nach
Prinzip 2.1. Allowlist. Umschaltung auf Stufe 1 möglich.
*Fertig, wenn:* Trockenlauf-Protokoll und tatsächliche Entwürfe stimmen überein.

### Phase 4 — Dashboard
Weboberfläche unter `localhost`, siehe Abschnitt 7. Zeigt Zustand,
Protokoll, anstehende Entscheidungen, Freigabe per Klick.
*Fertig, wenn:* eine Entscheidung lässt sich im Browser freigeben oder verwerfen.

### Phase 5 — Kalender und Briefing
Google Calendar, Morgenbriefing, proaktive Hinweise auf Konflikte und
Fristen.

### Phase 6 — Sprache
Spracheingabe über lokales Whisper, Ausgabe über macOS-Stimme oder eine
API. Weckwort optional. Sprache ist eine zusätzliche Bedienweise, kein
Ersatz für die bestehenden.

### Phase 7 und weiter
Offen für Erweiterungen: Dateiablage, Hausautomation über HomeKit oder
MQTT, Aufgabenverwaltung, Dokumentenanalyse. Jede kommt als neue Fähigkeit
nach dem Vertrag aus 5.1 und startet auf Stufe 0.

---

## 7. Oberfläche

Anlehnung an das Filmvorbild, aber zurückhaltend und ohne Kitsch:

- Dunkles Grundlayout, eine einzige Akzentfarbe, dünne Linien
- Monospace für Zahlen und Statuswerte
- Ein ruhiger Statusbereich, der Zustand und Aktivität zeigt
- Knappe, sachliche Sprache in allen Ausgaben. Keine Ausrufezeichen,
  keine Emojis, keine Beteuerungen. Trocken und kurz.
- Ein deutlich sichtbarer Stoppschalter auf jeder Ansicht
- Keine animierten Hologramme, keine Reaktoren, keine Sound-Effekte

Die Persönlichkeit entsteht durch Wortwahl und Reaktionszeit, nicht durch
Grafik.

---

## 8. Arbeitsweise für dich, Claude Code

1. Frage nach, bevor du eine Annahme triffst, die später teuer wird.
2. Schreibe den Test vor oder zusammen mit der Funktion, nie danach.
3. Kein Feature ohne Trockenlauf-Pfad.
4. Erkläre nach jeder Datei in zwei bis drei Sätzen, was sie tut und
   warum du sie so gebaut hast. Der Nutzer lernt mit.
5. Wenn du unsicher bist, ob etwas gegen Abschnitt 2 verstößt: es
   verstößt dagegen. Halte an und frage.
6. Keine neuen Abhängigkeiten ohne kurze Begründung.
