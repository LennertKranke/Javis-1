"""Das Aussehen, nach Abschnitt 7.

Dunkel, eine einzige Akzentfarbe, duenne Linien, Monospace fuer Zahlen und
Statuswerte. Keine Animation, keine Verlaeufe, keine Schatten -- die
Persoenlichkeit entsteht durch Wortwahl und Reaktionszeit, nicht durch Grafik.

Als eigene Datei ausgeliefert, nicht in die Seite geschrieben: dann kommt die
Sicherheitsrichtlinie ohne 'unsafe-inline' aus.
"""

CSS = """\
:root {
  --bg: #0c0e10;
  --panel: #111417;
  --line: #1d2429;
  --text: #ccd2d6;
  --dim: #6d787e;
  --accent: #67b8c7;
}

* { box-sizing: border-box; }

html { background: var(--bg); }

body {
  margin: 0;
  padding: 0 0 4rem;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
}

.wrap { max-width: 60rem; margin: 0 auto; padding: 0 1.5rem; }

/* --- Stoppschalter: auf jeder Ansicht, oben, nicht zu uebersehen --------- */

.stop {
  border-bottom: 1px solid var(--line);
  background: var(--panel);
}
.stop-inner {
  max-width: 60rem;
  margin: 0 auto;
  padding: 0.7rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
}
.stop-state {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  letter-spacing: 0.12em;
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--line);
  color: var(--dim);
}
.stop.engaged { background: var(--accent); border-bottom-color: var(--accent); }
.stop.engaged .stop-state { background: var(--bg); color: var(--accent); border-color: var(--bg); }
.stop.engaged .stop-reason { color: var(--bg); }
.stop-reason { color: var(--dim); font-size: 0.9rem; flex: 1; }

/* --- Kopf und Navigation ------------------------------------------------- */

header { padding: 2rem 0 0.5rem; }
h1 {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 1.1rem;
  font-weight: 500;
  letter-spacing: 0.22em;
  color: var(--accent);
  margin: 0;
}
h2 {
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--dim);
  margin: 2.2rem 0 0.7rem;
}
nav { display: flex; gap: 1.4rem; padding: 0.9rem 0 0; border-bottom: 1px solid var(--line); }
nav a {
  color: var(--dim);
  text-decoration: none;
  font-size: 0.9rem;
  padding-bottom: 0.6rem;
  border-bottom: 1px solid transparent;
}
nav a:hover { color: var(--text); }
nav a.on { color: var(--accent); border-bottom-color: var(--accent); }
nav .count {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  color: var(--accent);
}

/* --- Statusbereich: ruhig, in Spalten ------------------------------------ */

.facts { display: grid; grid-template-columns: 10rem 1fr; gap: 0.35rem 1.5rem; }
.facts dt { color: var(--dim); font-size: 0.86rem; }
.facts dd {
  margin: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.86rem;
}

table { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
th {
  text-align: left;
  font-weight: 500;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--dim);
  padding: 0 1rem 0.5rem 0;
  border-bottom: 1px solid var(--line);
}
td {
  padding: 0.45rem 1rem 0.45rem 0;
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}
td.num, td.mono, .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: nowrap;
}
td.dim, .dim { color: var(--dim); }

/* --- Anstehende Entscheidungen ------------------------------------------- */

.item { border: 1px solid var(--line); padding: 1rem 1.2rem; margin-bottom: 0.8rem; }
.item-head { display: flex; gap: 1rem; align-items: baseline; margin-bottom: 0.5rem; }
.item-skill {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  color: var(--accent);
  letter-spacing: 0.06em;
}
.item-when { color: var(--dim); font-size: 0.78rem; margin-left: auto; }
.item-summary { word-break: break-word; margin-bottom: 0.5rem; }
.item-body {
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--dim);
  font-size: 0.88rem;
  border-left: 1px solid var(--line);
  padding-left: 0.9rem;
  margin: 0.6rem 0;
}
.actions { display: flex; gap: 0.6rem; margin-top: 0.9rem; }

button {
  font: inherit;
  font-size: 0.86rem;
  color: var(--text);
  background: transparent;
  border: 1px solid var(--line);
  padding: 0.35rem 0.9rem;
  cursor: pointer;
}
button:hover { border-color: var(--dim); }
button.primary { color: var(--accent); border-color: var(--accent); }
button.primary:hover { background: var(--accent); color: var(--bg); }

.note {
  border-left: 1px solid var(--accent);
  padding: 0.5rem 0 0.5rem 0.9rem;
  color: var(--dim);
  font-size: 0.88rem;
  margin: 1rem 0;
}
.empty { color: var(--dim); font-size: 0.9rem; padding: 1.5rem 0; }
footer { color: var(--dim); font-size: 0.78rem; padding-top: 2.5rem; }
"""
