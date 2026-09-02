# design/ -- das Designsystem des Dashboards

Zwei Dateien, klar getrennt:

```
design/
  JARVIS-DESIGN-SYSTEM.md    Fassung 2.0. Die eine Quelle fuer die Gestaltung:
                             Farben, Schrift, Abstaende, Tafeln, Kern,
                             Zustaende, Bausteine, Groessenstufen, Bewegung,
                             Zugaenglichkeit. Beschreibt, was
                             jarvis/interfaces/web/style.py tut
  SPEC-3-NACHTRAG.md         Nachweis: der Vorschlag, der am 2026-09-01 als
                             SPEC-3 Fassung 3.2 eingetragen wurde. Historisch,
                             mit Hinweis auf das, was sich seither geaendert hat
```

## Die drei Saetze, die zaehlen

1. **SPEC-3 bleibt die Source of Truth.** Wo das Design SPEC-3 widerspricht,
   gilt SPEC-3. Das Design aendert SPEC-3 nicht.
2. **Das Design beschreibt die Implementierung, nicht umgekehrt.** Es gibt
   keine Entwurfsblaetter und keine Mockups mehr: die Referenz ist das laufende
   Dashboard (`uv run jarvis web`). Wer das Design sehen will, startet es.
3. **Kein Bereich ohne Funktion.** Die Navigation zeigt genau die vier
   Ansichten, die es gibt. Was SPEC-3 unter PLANNED fuehrt (Dienste, Modelle,
   Gedaechtnis, Fehler, Aufgaben, Chat), hat weder Seite noch Platzhalter.

## Was entfernt wurde, und warum

Am 2026-09-02 wurden `design/designsystem.html` (das "Blaetterwerk", 25 Tafeln
der Fassung 1.0) und `design/prototyp/` (zehn handgeschriebene Entwurfsblaetter
plus Stylesheet) entfernt. Sie beschrieben ein anderes Design -- hell/dunkel,
Tuerkis, ohne Bewegung -- und zeigten Bereiche, die es nicht gibt. Zwei
Designsysteme nebeneinander sind keins. Beides liegt in der Git-Geschichte
(letzter Stand: Commit `71a68d9`).
