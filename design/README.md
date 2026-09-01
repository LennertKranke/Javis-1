# design/ -- Gestaltung, kein Produktionscode

Dieser Ordner enthaelt den **Designvorschlag** fuer JARVIS. Er aendert nichts am
laufenden System.

```
design/
  JARVIS-DESIGN-SYSTEM.md    Das Hauptdokument. Begruendung jeder Entscheidung
                             mit ihrer SPEC-3-Grundlage
  prototyp/
    jarvis-prototyp.css      Marken und Bausteine als lauffaehige Referenz
    index.html               Verzeichnis der Entwurfsblaetter
    01..09-*.html            Entwurfsblaetter, ohne Server im Browser zu oeffnen
```

## Die drei Saetze, die zaehlen

1. **SPEC-3 bleibt die Source of Truth.** Wo dieses Design SPEC-3
   widerspricht, gilt SPEC-3. `JARVIS-SPEC-3.md` ist unveraendert.
2. **Ein Teil ist umgesetzt, der groessere nicht.** Umgesetzt wurde, was neue
   Information bringt: verlangte Stufe, Zustandsmarken, Gatterleiter,
   Vertrauensnaht, Systemband. Was dazu gehoert und was bewusst draussen
   blieb, steht in Abschnitt 48 des Hauptdokuments.
3. **Alles Uebrige ist kein Bauauftrag.** Neue Bereiche -- Dienste, Modelle,
   Gedaechtnis, Fehler -- bleiben PLANNED und haengen hinter fuenf
   REQUIRED-Punkten. Blaetter, die einen solchen Bereich zeigen, tragen die
   Marke im Blatt.
4. **SPEC-3 ist an dieser Stelle veraltet, und das ist offen.** OD-4 steht
   dort als OFFEN, ist aber entschieden; Abschnitt 12 beschreibt eine
   Oberflaeche, die inzwischen mehr zeigt. Abschnitt 27 verlangt, dass eine
   Codeaenderung den betroffenen SPEC-Abschnitt mitzieht. Der fertige Wortlaut
   dafuer liegt in `SPEC-3-NACHTRAG.md` und wartet auf eine Entscheidung --
   SPEC-3 wird nicht ohne ausdrueckliche Freigabe geaendert.

## Blaetter ansehen

Kein Server, kein Build. Datei im Browser oeffnen:

```sh
open design/prototyp/index.html          # macOS
xdg-open design/prototyp/index.html      # Linux
```

Das Fenster schmaler ziehen zeigt die drei Groessenstufen. Die Systemeinstellung
auf *Hell* zeigt die helle Fassung.

**Einschraenkung:** Die Blaetter sind von Hand geschrieben. Bei der
Konsolidierung (2026-09-01) wurden drei davon (01, 02, 08) erstmals in einem
Browser gerendert -- helle Fassung, 1280 px, headless Chromium -- und stellen
korrekt dar. Die uebrigen sechs Blaetter, die dunkle Fassung und die
Groessenstufen sind weiterhin ungeprueft. Gebaut ist nicht geprueft; dieselbe
Regel, die SPEC-3 fuer den Code aufstellt.
