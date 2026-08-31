"""Das Aussehen.

Dunkel, eine einzige Akzentfarbe, duenne Linien, Monospace fuer Zahlen und
Statuswerte. Keine Animation, keine Verlaeufe, keine Schatten -- die
Persoenlichkeit entsteht durch Wortwahl und Reaktionszeit, nicht durch Grafik.

Die Marken sind nach Rollen benannt, nicht nach Farben: `--linie`, nicht
`--grau-700`. Wer eine Farbe aendert, soll sehen, wofuer sie steht.

Drei Regeln, die nicht Geschmack sind:

  Erfolg traegt keine Farbe.   Der Normalfall ist neutral; Farbe bekommt nur,
                               was Aufmerksamkeit verdient. Eine Tafel mit
                               fuenfzehn gruenen Haken macht den einen roten
                               schwerer auffindbar, nicht leichter.
  Farbe nie allein.            Jede farbige Aussage traegt zusaetzlich ein Wort
                               und eine Form. Sonst haengt "ein Fehler darf nie
                               wie ein Erfolg aussehen" an der Farbwahrnehmung
                               des Betrachters.
  Linienart bedeutet etwas.    Durchgezogen = vom Code berechnet, gepunktet =
                               aus Fremdtext abgeleitet, gestrichelt =
                               verworfen, schraffiert = Trockenlauf.

Kein `style`-Attribut, nirgends: die Richtlinie ist `style-src 'self'`, und ein
Inline-Stil wird davon still verworfen -- ohne Fehler, ohne Warnung. Was einen
veraenderlichen Wert braucht, bekommt eine Stufenklasse (`.f-40`).

Als eigene Datei ausgeliefert, nicht in die Seite geschrieben: dann kommt die
Sicherheitsrichtlinie ohne 'unsafe-inline' aus.
"""

CSS = """\
:root {
  color-scheme: dark light;

  /* Flaechen: genau drei Tiefen, keine Schatten. */
  --grund: #0b0d0f;
  --flaeche: #101417;
  --flaeche-hoch: #151a1e;

  /* Linien: die eigentliche Struktur. */
  --linie: #1d2429;
  --linie-stark: #2b353c;

  /* Schrift: drei Stufen, mehr braucht es nicht. */
  --text: #d3d9dd;
  --text-zweit: #98a3aa;
  --text-gedaempft: #6c777e;

  /* Genau ein Akzent: Identitaet, und "hier bist du gefragt". */
  --akzent: #67b8c7;

  /* Funktionssignale, nur auf Marken -- nie als Flaeche. */
  --signal-warnung: #d9a441;
  --signal-fehler: #d9705e;

  --satz: -apple-system, BlinkMacSystemFont, system-ui, "Segoe UI", sans-serif;
  --masch: ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* Helle Fassung, ueber die Systemeinstellung. Kein Umschalter: ohne
   JavaScript braeuchte er eine Route und ein Cookie -- neue Funktion fuer eine
   reine Anzeigefrage. Auf macOS ist das Mitgehen ohnehin das Erwartete. */
@media (prefers-color-scheme: light) {
  :root {
    --grund: #f7f8f9;
    --flaeche: #ffffff;
    --flaeche-hoch: #f1f3f4;
    --linie: #dfe4e7;
    --linie-stark: #c3cbd0;
    --text: #14181b;
    --text-zweit: #4a555c;
    --text-gedaempft: #6c777e;
    --akzent: #1f6e7c;
    --signal-warnung: #8a6108;
    --signal-fehler: #a8331f;
  }
}

* { box-sizing: border-box; }

html { background: var(--grund); }

body {
  margin: 0;
  padding: 0 0 4rem;
  background: var(--grund);
  color: var(--text);
  font: 15px/1.55 var(--satz);
}

.wrap { max-width: 60rem; margin: 0 auto; padding: 0 1.5rem; }
.wrap.weit { max-width: 96rem; }

a { color: var(--akzent); }
a:focus-visible, button:focus-visible {
  outline: 2px solid var(--akzent);
  outline-offset: 2px;
}

/* Es gibt keine Bewegung. Der Eintrag steht hier, damit eine spaetere
   Ergaenzung die Zusage nicht versehentlich bricht. */
@media (prefers-reduced-motion: reduce) {
  * { animation: none !important; transition: none !important; }
}

/* --- Systemband: vier Tatsachen und der Stoppschalter -------------------- */

.systemband {
  border-bottom: 1px solid var(--linie);
  background: var(--flaeche);
}
.systemband-inhalt {
  max-width: 96rem;
  margin: 0 auto;
  padding: 0.55rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 1.1rem;
  flex-wrap: wrap;
}
.systemband form { margin: 0 0 0 auto; }
.tatsache { display: inline-flex; align-items: baseline; gap: 0.3rem; font-size: 0.8rem; }
.tatsache-name { color: var(--text-gedaempft); }
.tatsache-wert { font-family: var(--masch); color: var(--text-zweit); }
.tatsache-wert.hebt { color: var(--text); }
.tatsache-wert.gefahr { color: var(--signal-warnung); }

/* Angehalten faerbt das ganze Band. Ein System, das nicht handelt, soll man
   ohne Lesen erkennen. */
.systemband.angehalten {
  background: var(--signal-warnung);
  border-bottom-color: var(--signal-warnung);
}
.systemband.angehalten .marke,
.systemband.angehalten .tatsache-name,
.systemband.angehalten .tatsache-wert,
.systemband.angehalten button { color: var(--grund); border-color: var(--grund); }

/* --- Kopf und Navigation ------------------------------------------------- */

header { padding: 2rem 0 0.5rem; }
h1 {
  font-family: var(--masch);
  font-size: 1.05rem;
  font-weight: 500;
  letter-spacing: 0.22em;
  color: var(--akzent);
  margin: 0;
}
h2 {
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
  margin: 2.2rem 0 0.75rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--linie);
}
h3 { font-size: 0.86rem; font-weight: 600; color: var(--text-zweit); margin: 1.4rem 0 0.5rem; }

nav {
  display: flex;
  gap: 1.4rem;
  padding: 0.9rem 0 0;
  border-bottom: 1px solid var(--linie-stark);
}
nav a {
  color: var(--text-zweit);
  text-decoration: none;
  font-size: 0.9rem;
  padding-bottom: 0.6rem;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
nav a:hover { color: var(--text); }
nav a.on { color: var(--akzent); border-bottom-color: var(--akzent); }
nav .count { font-family: var(--masch); font-size: 0.78rem; color: var(--akzent); }

/* --- Zustandsmarke: Wort, Form, dann erst Farbe -------------------------- */

.marke {
  display: inline-block;
  font-family: var(--masch);
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  padding: 1px 6px;
  border: 1px solid var(--linie-stark);
  color: var(--text-zweit);
  white-space: nowrap;
}
.marke.erfolg { color: var(--text); }
.marke.offen { color: var(--akzent); border-color: var(--akzent); }
.marke.blockiert { color: var(--signal-warnung); border-color: var(--signal-warnung); }
.marke.verworfen { color: var(--text-gedaempft); border-style: dashed; }
.marke.fehler { color: var(--signal-fehler); border-color: var(--signal-fehler); }
.marke.trocken {
  color: var(--text-zweit);
  background: repeating-linear-gradient(135deg, transparent 0 3px, var(--flaeche-hoch) 3px 6px);
}

/* --- Autonomiestufe: immer beide Zahlen ---------------------------------- */

.stufe { font-family: var(--masch); font-size: 0.82rem; white-space: nowrap; }
.stufe .gewaehrt { color: var(--text); }
.stufe .verlangt { color: var(--text-gedaempft); }
.stufe.reicht-nicht .gewaehrt { color: var(--signal-warnung); }
.stufe-name { font-size: 0.82rem; color: var(--text-zweit); }

/* --- Gatterleiter: die Reihenfolge aus Abschnitt 4.2 --------------------- */

.gatter { border: 1px solid var(--linie); background: var(--flaeche); }
.gatter-sprosse {
  display: grid;
  grid-template-columns: 1.3rem 10.5rem 1fr auto;
  gap: 0.75rem;
  align-items: baseline;
  padding: 0.4rem 0.8rem;
  border-bottom: 1px solid var(--linie);
  font-size: 0.82rem;
}
.gatter-sprosse:last-child { border-bottom: 0; }
.gatter-nr { font-family: var(--masch); font-size: 0.72rem; color: var(--text-gedaempft); }
.gatter-name { color: var(--text-zweit); }
.gatter-wert { color: var(--text-gedaempft); word-break: break-word; }
.gatter-sprosse.entschieden { background: var(--flaeche-hoch); }
.gatter-sprosse.entschieden .gatter-name { color: var(--text); }
.gatter-sprosse.offen { opacity: 0.5; }

/* --- Vertrauensnaht: das Modell links, der Code rechts -------------------- */

.naht { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin: 0.8rem 0; }
.naht-halb { min-width: 0; padding-left: 0.9rem; }
.naht-halb.modell { border-left: 2px dotted var(--linie-stark); }
.naht-halb.code { border-left: 2px solid var(--linie-stark); }
.naht-kopf {
  font-size: 0.68rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
  margin-bottom: 0.5rem;
}

/* --- Fakten und Tabellen ------------------------------------------------- */

.facts { display: grid; grid-template-columns: 10rem 1fr; gap: 0.3rem 1.2rem; margin: 0; }
.facts dt { color: var(--text-gedaempft); font-size: 0.84rem; }
.facts dd { margin: 0; font-family: var(--masch); font-size: 0.84rem; word-break: break-word; }
.facts.satz dd { font-family: var(--satz); }

table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
th {
  text-align: left;
  font-weight: 600;
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
  padding: 0 1rem 0.5rem 0;
  border-bottom: 1px solid var(--linie-stark);
  white-space: nowrap;
}
td { padding: 0.45rem 1rem 0.45rem 0; border-bottom: 1px solid var(--linie); vertical-align: top; }
td.mono, .mono { font-family: var(--masch); white-space: nowrap; }
td.dim, .dim { color: var(--text-gedaempft); }

/* Eine Zahl ohne Bezug ist keine Auskunft: benutzt/Grenze mit Balken. Der
   Fuellstand kommt in Fuenferstufen, weil ein Inline-Stil nicht zulaessig ist. */
.zaehler { display: inline-flex; align-items: center; gap: 0.5rem; font-family: var(--masch); }
.balken { display: inline-block; width: 3.5rem; height: 6px; border: 1px solid var(--linie-stark); }
.balken span { display: block; height: 100%; background: var(--text-gedaempft); }
.balken.voll span { background: var(--signal-warnung); }
.f-0 { width: 0; } .f-5 { width: 5%; } .f-10 { width: 10%; } .f-15 { width: 15%; }
.f-20 { width: 20%; } .f-25 { width: 25%; } .f-30 { width: 30%; } .f-35 { width: 35%; }
.f-40 { width: 40%; } .f-45 { width: 45%; } .f-50 { width: 50%; } .f-55 { width: 55%; }
.f-60 { width: 60%; } .f-65 { width: 65%; } .f-70 { width: 70%; } .f-75 { width: 75%; }
.f-80 { width: 80%; } .f-85 { width: 85%; } .f-90 { width: 90%; } .f-95 { width: 95%; }
.f-100 { width: 100%; }

/* --- Anstehende Entscheidungen ------------------------------------------- */

.item { border: 1px solid var(--linie); background: var(--flaeche); margin-bottom: 0.9rem; }
.item-head {
  display: flex;
  gap: 0.9rem;
  align-items: baseline;
  flex-wrap: wrap;
  padding: 0.7rem 1rem;
  border-bottom: 1px solid var(--linie);
  background: var(--flaeche-hoch);
}
.item-skill {
  font-family: var(--masch);
  font-size: 0.78rem;
  color: var(--akzent);
  letter-spacing: 0.06em;
}
.item-when {
  color: var(--text-gedaempft);
  font-size: 0.76rem;
  font-family: var(--masch);
  margin-left: auto;
}
.item-body-wrap { padding: 1rem; }
.item-summary { word-break: break-word; margin: 0 0 0.9rem; font-size: 0.95rem; }

/* Fremdtext ist Anzeige, nie Aussage der Oberflaeche -- deshalb als Zitat. */
.item-body {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-zweit);
  font-size: 0.88rem;
  border-left: 2px dotted var(--linie-stark);
  padding-left: 0.9rem;
  margin: 0.6rem 0 0;
}

.actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
  padding: 0.7rem 1rem;
  border-top: 1px solid var(--linie);
  background: var(--flaeche-hoch);
}
.actions form { margin: 0; }
.actions .knapp { color: var(--text-gedaempft); font-size: 0.8rem; }

button {
  font: inherit;
  font-size: 0.84rem;
  color: var(--text);
  background: transparent;
  border: 1px solid var(--linie-stark);
  padding: 0.3rem 0.8rem;
  cursor: pointer;
}
button:hover { border-color: var(--text-gedaempft); }
button.primary { color: var(--akzent); border-color: var(--akzent); }
button.primary:hover { background: var(--akzent); color: var(--grund); }

.note {
  border-left: 2px solid var(--akzent);
  padding: 0.4rem 0 0.4rem 0.9rem;
  color: var(--text-zweit);
  font-size: 0.88rem;
  margin: 1rem 0;
}
.note.warnung { border-left-color: var(--signal-warnung); }
.briefing {
  white-space: pre-wrap;
  word-break: break-word;
  font: inherit;
  border-left: 2px solid var(--akzent);
  padding: 0.2rem 0 0.2rem 1rem;
  margin: 1.2rem 0;
}
.empty { color: var(--text-gedaempft); font-size: 0.9rem; padding: 1.5rem 0; }
footer { color: var(--text-gedaempft); font-size: 0.78rem; padding-top: 2.5rem; }

/* --- Schmales Fenster ---------------------------------------------------- */

@media (max-width: 46rem) {
  .wrap { padding: 0 1rem; }
  .naht { grid-template-columns: 1fr; gap: 0.9rem; }
  .facts { grid-template-columns: 1fr; gap: 0; }
  .facts dt { margin-top: 0.5rem; }
  .gatter-sprosse { grid-template-columns: 1.3rem 1fr auto; row-gap: 0.2rem; }
  .gatter-wert { grid-column: 2 / 4; }
  .item-when { margin-left: 0; width: 100%; }
}

/* Ein Protokollauszug soll sich als Beleg ablegen lassen. */
@media print {
  body { background: #fff; color: #000; }
  .systemband, nav, .actions { display: none; }
  .marke { border-color: #000; color: #000; }
}
"""
