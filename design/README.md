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

1. **SPEC-3 bleibt die Source of Truth.** Wo dieses Design SPEC-3 widerspricht,
   gilt SPEC-3. `JARVIS-SPEC-3.md` wurde nicht angefasst.
2. **Nichts hier ist ein Bauauftrag.** Die Umsetzung haengt an SPEC-3 OD-4
   ("Dashboard-Gestaltung", OFFEN) und steht in der Roadmap hinter fuenf
   REQUIRED-Punkten. Blaetter, die einen PLANNED-Bereich zeigen, tragen die
   Marke im Blatt.
3. **Der Produktionsstand ist unberuehrt.** Das produktive Stylesheet liegt
   weiterhin in `jarvis/interfaces/web/style.py`. Der Ordner `jarvis/` wurde
   nicht veraendert, die Tests sind unveraendert.

## Blaetter ansehen

Kein Server, kein Build. Datei im Browser oeffnen:

```sh
open design/prototyp/index.html          # macOS
xdg-open design/prototyp/index.html      # Linux
```

Das Fenster schmaler ziehen zeigt die drei Groessenstufen. Die Systemeinstellung
auf *Hell* zeigt die helle Fassung.

**Einschraenkung:** Die Blaetter sind von Hand geschrieben und **in keinem
Browser dargestellt worden** -- die Sitzung lief unter Linux ohne Bildschirm.
Gebaut ist nicht geprueft; dieselbe Regel, die SPEC-3 fuer den Code aufstellt.
