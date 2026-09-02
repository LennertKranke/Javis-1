"""Das Aussehen.

Dunkel, fast schwarz, eine warme Akzentfarbe: Orange. Halbtransparente
Tafeln auf einem ruhigen Grund, duenne Linien, Maschinenschrift fuer Zahlen,
Kennungen und Zustaende. In der Mitte der Lage-Ansicht der Kern -- ein
leuchtender Orb, der den Systemzustand traegt und aus nichts als Gradienten
besteht.

Die Marken sind nach Rollen benannt, nicht nach Farben: `--linie`, nicht
`--orange-700`. Wer eine Farbe aendert, soll sehen, wofuer sie steht.

Vier Regeln, die nicht Geschmack sind:

  Erfolg traegt keine Farbe.   Der Normalfall ist neutral; Farbe bekommt nur,
                               was Aufmerksamkeit verdient. Eine Tafel voller
                               gruener Haken macht den einen roten schwerer
                               auffindbar, nicht leichter.
  Farbe nie allein.            Jede farbige Aussage traegt zusaetzlich ein Wort
                               und eine Form. Sonst haengt "ein Fehler darf nie
                               wie ein Erfolg aussehen" an der Farbwahrnehmung
                               des Betrachters.
  Warm heisst lebendig,        Orange ist der Betrieb. Angehalten und blockiert
  kalt heisst angehalten.      sind kalt und ohne Glut -- ein stehendes System
                               erkennt man, bevor man liest. Rot ist allein dem
                               Fehlgeschlagenen vorbehalten.
  Linienart bedeutet etwas.    Durchgezogen = vom Code berechnet, gepunktet =
                               aus Fremdtext abgeleitet, gestrichelt =
                               verworfen, schraffiert = Trockenlauf.

Bewegung gibt es, aber wenig: der Kern atmet, seine Ringe drehen sich langsam.
Ein angehaltenes System steht auch optisch still. `prefers-reduced-motion`
schaltet alles ab. Nichts blinkt, nichts springt.

Zwei Randbedingungen der Sicherheitsrichtlinie formen das Stylesheet:

  `style-src 'self'`   Kein `style`-Attribut, nirgends -- ein Inline-Stil wird
                       still verworfen. Veraenderliche Werte bekommen eine
                       Stufenklasse (`.f-40`).
  `img-src 'none'`     Kein `url()`, auch nicht als Daten-URI, auch nicht in
                       `mask`. Der Kern und alle Muster sind Gradienten; die
                       sind kein Abruf und bleiben erlaubt.

Als eigene Datei ausgeliefert, nicht in die Seite geschrieben: dann kommt die
Sicherheitsrichtlinie ohne 'unsafe-inline' aus.
"""

CSS = """\
:root {
  color-scheme: dark;

  /* Grund: warmes Schwarz. Tafeln sind Glas darauf, keine eigene Flaeche. */
  --grund: #0a0806;
  --glas: rgba(255, 150, 70, 0.045);
  --glas-hoch: rgba(255, 150, 70, 0.075);
  --schatten: rgba(0, 0, 0, 0.28);

  /* Linien: die eigentliche Struktur. */
  --linie: rgba(255, 165, 90, 0.14);
  --linie-stark: rgba(255, 165, 90, 0.32);

  /* Schrift: drei Stufen, mehr braucht es nicht. */
  --text: #f1e8da;
  --text-zweit: #c4b29c;
  --text-gedaempft: #8e7e6a;

  /* Genau ein Akzent: Identitaet, Fokus und "hier bist du gefragt". */
  --akzent: #ff9a3d;
  --akzent-hell: #ffc37c;
  --akzent-tief: #d9671c;
  --glut: rgba(255, 150, 60, 0.45);
  --glut-weit: rgba(255, 120, 30, 0.22);

  /* Kalt: angehalten, blockiert. Rot: fehlgeschlagen. Nur auf Marken. */
  --kalt: #a4b8cc;
  --kalt-tief: #52677c;
  --kalt-glut: rgba(120, 150, 185, 0.22);
  --signal-fehler: #ff5f5f;
  --fehler-glut: rgba(255, 95, 95, 0.35);

  --satz: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", sans-serif;
  --masch: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
}

* { box-sizing: border-box; }

html { background: var(--grund); }

body {
  margin: 0;
  padding: 0 0 4rem;
  min-height: 100vh;
  color: var(--text);
  font: 15px/1.55 var(--satz);
  font-variant-numeric: tabular-nums;
  background:
    radial-gradient(ellipse 70% 42% at 50% -4%, rgba(255, 140, 50, 0.12), transparent 70%),
    var(--grund);
}

/* Ein sehr feines Raster, fixiert im Hintergrund. Technische Praezision,
   kaum sichtbar -- es soll gespuert werden, nicht gesehen. */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  background:
    repeating-linear-gradient(0deg, transparent 0 55px, rgba(255, 165, 90, 0.028) 55px 56px),
    repeating-linear-gradient(90deg, transparent 0 55px, rgba(255, 165, 90, 0.028) 55px 56px);
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 30%, #000 30%, transparent 100%);
  mask-image: radial-gradient(ellipse 80% 70% at 50% 30%, #000 30%, transparent 100%);
}

/* Angehalten: der ganze Grund wird kalt. */
body.angehalten {
  background:
    radial-gradient(ellipse 70% 42% at 50% -4%, rgba(120, 150, 185, 0.14), transparent 70%),
    var(--grund);
}
body.angehalten::before {
  background:
    repeating-linear-gradient(0deg, transparent 0 55px, rgba(160, 180, 200, 0.03) 55px 56px),
    repeating-linear-gradient(90deg, transparent 0 55px, rgba(160, 180, 200, 0.03) 55px 56px);
}

a { color: var(--akzent-hell); }
a:hover { color: var(--text); }
:focus-visible {
  outline: 2px solid var(--akzent);
  outline-offset: 2px;
  border-radius: 2px;
}

::selection { background: var(--akzent); color: var(--grund); }

/* --- Bewegung: wenig, langsam, abschaltbar ------------------------------ */

@keyframes atmen {
  0%, 100% { transform: scale(1); opacity: 0.94; }
  50%      { transform: scale(1.02); opacity: 1; }
}
@keyframes drehen { to { transform: rotate(360deg); } }
@keyframes gegendrehen { to { transform: rotate(-360deg); } }
@keyframes puls {
  0%, 100% { opacity: 0.35; transform: scale(1); }
  50%      { opacity: 0.95; transform: scale(1.025); }
}
@keyframes impuls {
  0%   { opacity: 0.55; transform: scale(1); }
  70%  { opacity: 0; transform: scale(1.9); }
  100% { opacity: 0; transform: scale(1.9); }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}

/* --- Systemband: Zustand, drei Tatsachen, Stoppschalter ------------------ */

.systemband {
  position: sticky;
  top: 0;
  z-index: 3;
  background:
    linear-gradient(90deg, transparent, var(--linie-stark) 15%, var(--linie-stark) 85%, transparent)
      bottom / 100% 1px no-repeat,
    rgba(10, 8, 6, 0.82);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}
.systemband-inhalt {
  max-width: 96rem;
  margin: 0 auto;
  padding: 0.6rem 1.5rem;
  display: flex;
  align-items: center;
  gap: 1.3rem;
  flex-wrap: wrap;
}
.zustand { display: inline-flex; align-items: center; gap: 0.6rem; }
.puls {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--akzent);
  box-shadow: 0 0 10px var(--glut), 0 0 22px var(--glut-weit);
  animation: atmen 4s ease-in-out infinite;
}
.systemband form { margin: 0 0 0 auto; }

.tatsache { display: inline-flex; align-items: baseline; gap: 0.4rem; font-size: 0.78rem; }
.tatsache-name {
  font-family: var(--masch);
  font-size: 0.64rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
}
.tatsache-wert { font-family: var(--masch); color: var(--text-zweit); }
.tatsache-wert.hebt { color: var(--text); }
.tatsache-wert.gefahr { color: var(--akzent-hell); text-shadow: 0 0 12px var(--glut-weit); }

/* Angehalten faerbt das Band kalt und nimmt ihm die Glut. Ein System, das
   nicht handelt, soll man ohne Lesen erkennen. */
.systemband.angehalten {
  background: rgba(20, 28, 38, 0.92);
  border-bottom: 1px solid var(--kalt-tief);
  box-shadow: 0 1px 0 rgba(164, 184, 204, 0.15), 0 0 30px var(--kalt-glut);
}
.systemband.angehalten .puls {
  background: var(--kalt);
  box-shadow: 0 0 0 3px rgba(164, 184, 204, 0.15);
  animation: none;
}
.systemband.angehalten .marke { color: var(--kalt); border-color: var(--kalt); }
.systemband.angehalten .tatsache-wert { color: var(--kalt); }
.systemband.angehalten .tatsache-wert.hebt { color: #e2ebf3; }

/* --- Stoppschalter: immer da, immer gleich ------------------------------- */

button.stopp {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--akzent-hell);
  border-color: var(--akzent);
  background: rgba(255, 154, 61, 0.06);
}
button.stopp:hover {
  background: rgba(255, 154, 61, 0.16);
  box-shadow: 0 0 18px var(--glut-weit);
}
button.stopp svg { width: 13px; height: 13px; flex: none; }
.angehalten button.stopp {
  color: var(--text);
  border-color: var(--kalt);
  background: rgba(164, 184, 204, 0.08);
}
.angehalten button.stopp:hover { background: rgba(164, 184, 204, 0.18); box-shadow: none; }

/* --- Kopf und Navigation ------------------------------------------------- */

.kopf {
  max-width: 96rem;
  margin: 0 auto;
  padding: 1.5rem 1.5rem 0.25rem;
  display: flex;
  align-items: center;
  gap: 2rem;
  flex-wrap: wrap;
}
h1 {
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  font: 500 0.95rem var(--masch);
  letter-spacing: 0.34em;
  color: var(--akzent-hell);
  text-shadow: 0 0 18px var(--glut-weit);
}
h1 a {
  color: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
}
.wortmarke-kern {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: radial-gradient(
    circle at 45% 40%, #fff1d8 0, var(--akzent) 45%, var(--akzent-tief) 78%
  );
  box-shadow: 0 0 12px var(--glut), 0 0 0 1px rgba(255, 195, 124, 0.25);
}
.angehalten .wortmarke-kern {
  background: radial-gradient(circle at 45% 40%, #e6edf3 0, var(--kalt) 45%, var(--kalt-tief) 78%);
  box-shadow: 0 0 0 1px rgba(164, 184, 204, 0.3);
}
.angehalten h1 { color: var(--kalt); text-shadow: none; }

nav { display: flex; gap: 0.2rem; margin-left: auto; flex-wrap: wrap; }
nav a {
  font: 500 0.7rem/1 var(--masch);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-zweit);
  text-decoration: none;
  padding: 0.6rem 0.9rem;
  border: 1px solid transparent;
  border-radius: 3px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
}
nav a:hover { color: var(--text); border-color: var(--linie); }
nav a.on {
  color: var(--akzent-hell);
  text-shadow: 0 0 12px var(--glut-weit);
  box-shadow: inset 0 -1px 0 var(--akzent), 0 8px 16px -12px var(--glut);
}
nav .count {
  display: inline-block;
  min-width: 1.5em;
  margin-left: 0.55em;
  padding: 0.05em 0.4em;
  border-radius: 2px;
  background: var(--akzent);
  color: var(--grund);
  font-weight: 600;
  text-align: center;
  box-shadow: 0 0 10px var(--glut-weit);
}

/* --- Spur ---------------------------------------------------------------- */

.wrap { max-width: 60rem; margin: 0 auto; padding: 0 1.5rem; }
.wrap.weit { max-width: 96rem; }

h2 {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin: 2.2rem 0 0.9rem;
  font: 600 0.68rem var(--masch);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
}
h2::after {
  content: "";
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--linie-stark), transparent);
}
h3 {
  margin: 1.4rem 0 0.55rem;
  font: 600 0.66rem var(--masch);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-zweit);
}

/* --- Tafel: Glas mit Kante ----------------------------------------------- */

.tafel {
  position: relative;
  padding: 1.3rem 1.5rem 1.5rem;
  border: 1px solid var(--linie);
  border-radius: 3px;
  background:
    linear-gradient(135deg, rgba(255, 190, 120, 0.05), transparent 28%),
    linear-gradient(180deg, rgba(255, 165, 90, 0.05), transparent 38%),
    var(--glas);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  box-shadow: inset 0 1px 0 rgba(255, 195, 130, 0.14), 0 14px 44px -22px var(--schatten);
}
.tafel::before, .tafel::after {
  content: "";
  position: absolute;
  width: 11px;
  height: 11px;
  border: 1px solid var(--linie-stark);
  pointer-events: none;
}
.tafel::before { top: -1px; left: -1px; border-right: 0; border-bottom: 0; }
.tafel::after { right: -1px; bottom: -1px; border-left: 0; border-top: 0; }
.tafel > h2 { margin-top: 0; }
.tafel > h2::before {
  content: "";
  width: 10px;
  height: 1px;
  background: var(--akzent);
  opacity: 0.85;
}
.tafel-fuss { margin: 1rem 0 0; font-size: 0.8rem; color: var(--text-gedaempft); }
.tafel-fuss a { font-family: var(--masch); font-size: 0.72rem; letter-spacing: 0.08em; }

.tafeln {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 1.4rem;
  margin-top: 2.2rem;
}
.tafel.breit { margin-top: 1.4rem; }

/* --- Der Kern ------------------------------------------------------------ */
/*
   Ein Orb aus Gradienten: eine Kugel mit Lichtquelle oben links, dunklem
   Rand und feiner innerer Struktur; darum vier Ringe, ein Bogen, der langsam
   umlaeuft, und alle neun Sekunden ein Impuls, der nach aussen verklingt.
   Kein Bild, keine Datei -- `img-src 'none'` laesst keines zu, und es
   braucht auch keines.

   Der Zustand kommt als Klasse und ist kein Schmuck. Er wird serverseitig aus
   Tatsachen abgeleitet, die das System wirklich fuehrt:

     betrieb      Stoppschalter nicht gesetzt, nichts wartet, nichts weicht ab
     wartet       offene Entscheidungen -- der aeussere Ring pulsiert
     abweichung   Kette gebrochen, Ablage offen oder Zugangsdaten abweichend
     angehalten   Stoppschalter gesetzt -- die Glut ist aus, nichts dreht sich

   Zustaende, die das System nicht kennt (laeuft, denkt, offline), gibt es
   hier nicht. Eine Anzeige ohne Deckung waere keine Anzeige.
*/

.kern {
  position: relative;
  width: var(--kern-groesse);
  aspect-ratio: 1;
  margin: 0 auto;
  border-radius: 50%;
}
/* Weiter Lichthof, leicht nach unten versetzt: der Kern steht im Raum. */
.kern::before {
  content: "";
  position: absolute;
  inset: -40%;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 56%, var(--glut-weit) 0, transparent 60%);
  pointer-events: none;
}
/* Der Impuls: ein Ring, der von der Kugel ausgeht und nach aussen verklingt. */
.kern::after {
  content: "";
  position: absolute;
  inset: 26%;
  border-radius: 50%;
  border: 1px solid rgba(255, 190, 120, 0.6);
  animation: impuls 9s ease-out infinite;
  pointer-events: none;
}
/* Die Kugel: Licht von oben links, dunkler Rand unten rechts. */
.kern-glut {
  position: absolute;
  inset: 26%;
  border-radius: 50%;
  background: radial-gradient(
    circle at 40% 34%,
    #fff3dd 0,
    #ffd39a 5%,
    #ffab55 22%,
    var(--akzent) 40%,
    #d4561a 62%,
    #7a2a06 86%,
    #3a1203 100%
  );
  box-shadow:
    0 0 30px var(--glut),
    0 0 80px var(--glut-weit),
    0 34px 60px -18px rgba(255, 120, 30, 0.3),
    inset -14px -18px 36px rgba(60, 15, 0, 0.55),
    inset 8px 10px 24px rgba(255, 235, 205, 0.25);
  animation: atmen 7s ease-in-out infinite;
}
/* Glanzlicht: die Lichtquelle, an der Kugel gespiegelt. */
.kern-glut::before {
  content: "";
  position: absolute;
  left: 22%;
  top: 14%;
  width: 32%;
  height: 22%;
  border-radius: 50%;
  background: radial-gradient(ellipse, rgba(255, 250, 240, 0.38), rgba(255, 250, 240, 0) 70%);
  transform: rotate(-24deg);
}
/* Innere Struktur: feine Schichten und zwoelf kaum sichtbare Naehte --
   ein technischer Kern, keine Spielkugel. */
.kern-glut::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    repeating-conic-gradient(
      from 15deg, rgba(255, 240, 220, 0.05) 0 0.5deg, transparent 0.5deg 30deg
    ),
    repeating-radial-gradient(
      circle at 40% 34%, transparent 0 8px, rgba(255, 228, 195, 0.035) 8px 9px
    );
}
.kern-ring {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
.kern-ring.r0 { inset: -8%; border: 1px solid rgba(255, 175, 100, 0.13); }
/* r1 ist ein Doppelring: die Linie und, drei Pixel aussen, ihr Echo. */
.kern-ring.r1 {
  inset: 9%;
  border: 1px solid rgba(255, 175, 100, 0.6);
  outline: 1px solid rgba(255, 175, 100, 0.12);
  outline-offset: 3px;
}
.kern-ring.r2 {
  inset: 0;
  border: 1px dashed rgba(255, 175, 100, 0.32);
  animation: drehen 110s linear infinite;
}
.kern-ring.r3 {
  inset: 15.5%;
  background: repeating-conic-gradient(
    from 0deg,
    rgba(255, 185, 110, 0.8) 0 0.8deg,
    transparent 0.8deg 7.5deg
  );
  -webkit-mask: radial-gradient(
    circle, transparent 0 calc(50% - 7px), #000 calc(50% - 6px) 50%, transparent 50%
  );
  mask: radial-gradient(
    circle, transparent 0 calc(50% - 7px), #000 calc(50% - 6px) 50%, transparent 50%
  );
  animation: gegendrehen 140s linear infinite;
}
.kern-bogen {
  position: absolute;
  inset: 3.2%;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg, transparent 0 74%, rgba(255, 200, 140, 0.85) 93%, transparent 100%
  );
  -webkit-mask: radial-gradient(
    circle, transparent 0 calc(50% - 2.5px), #000 calc(50% - 2px) 50%, transparent 50%
  );
  mask: radial-gradient(
    circle, transparent 0 calc(50% - 2.5px), #000 calc(50% - 2px) 50%, transparent 50%
  );
  animation: drehen 26s linear infinite;
  pointer-events: none;
}

.kern.wartet .kern-ring.r1 {
  border-color: rgba(255, 195, 124, 0.7);
  box-shadow: 0 0 18px var(--glut-weit);
  animation: puls 3.2s ease-in-out infinite;
}

.kern.abweichung .kern-ring.r1 {
  border-color: var(--signal-fehler);
  box-shadow: 0 0 22px var(--fehler-glut);
}
.kern.abweichung .kern-ring.r2 { border-color: rgba(255, 95, 95, 0.4); }
.kern.abweichung::after { border-color: rgba(255, 95, 95, 0.55); }
.kern.abweichung .kern-glut { box-shadow: 0 0 40px var(--fehler-glut), 0 0 110px var(--glut-weit); }

/* Angehalten: kalt, ohne Glut, ohne Bewegung. */
.kern.angehalten::before {
  background: radial-gradient(circle, var(--kalt-glut) 0, transparent 60%);
}
.kern.angehalten::after { display: none; }
.kern.angehalten .kern-glut {
  background: radial-gradient(
    circle at 40% 34%,
    #eef3f7 0,
    #c9d6e2 8%,
    var(--kalt) 28%,
    var(--kalt-tief) 58%,
    #22303f 86%,
    #121a23 100%
  );
  box-shadow:
    0 0 24px var(--kalt-glut),
    inset -14px -18px 36px rgba(10, 18, 28, 0.6),
    inset 8px 10px 24px rgba(235, 242, 250, 0.2);
  animation: none;
}
.kern.angehalten .kern-glut::after {
  background: repeating-radial-gradient(
    circle at 40% 34%, transparent 0 8px, rgba(220, 232, 244, 0.035) 8px 9px
  );
}
.kern.angehalten .kern-ring.r0 { border-color: rgba(164, 184, 204, 0.12); }
.kern.angehalten .kern-ring.r1 { border-color: rgba(164, 184, 204, 0.45); }
.kern.angehalten .kern-ring.r2 { border-color: rgba(164, 184, 204, 0.3); animation: none; }
.kern.angehalten .kern-ring.r3 {
  background: repeating-conic-gradient(
    from 0deg, rgba(164, 184, 204, 0.5) 0 0.7deg, transparent 0.7deg 7.5deg
  );
  animation: none;
}
.kern.angehalten .kern-bogen { display: none; }

/* --- Lage: der Kern in der Mitte, Zahlen links, System rechts ------------ */

.lage {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 3rem;
  padding: 2rem 0 1.2rem;
}
.lage-mitte { --kern-groesse: 17rem; position: relative; text-align: center; padding: 1.2rem 0; }

/* Die Systemzone um den Kern: ein weiter, blasser Kreis, eine Horizontlinie
   durch die Mitte, ein Hauch Licht. Orientierung, kein Ornament. */
.lage-mitte::before {
  content: "";
  position: absolute;
  left: 50%;
  top: calc(1.2rem + var(--kern-groesse) / 2);
  width: calc(var(--kern-groesse) * 1.6);
  height: calc(var(--kern-groesse) * 1.6);
  transform: translate(-50%, -50%);
  border-radius: 50%;
  pointer-events: none;
  background:
    linear-gradient(
      90deg,
      transparent 0,
      rgba(255, 165, 90, 0.16) 18%,
      transparent 40%,
      transparent 60%,
      rgba(255, 165, 90, 0.16) 82%,
      transparent 100%
    ) center / 100% 1px no-repeat,
    radial-gradient(
      circle, transparent 0 calc(50% - 1px), rgba(255, 165, 90, 0.08) calc(50% - 1px) 50%,
      transparent 50%
    ),
    radial-gradient(circle, rgba(255, 140, 50, 0.05), transparent 62%);
}
.angehalten .lage-mitte::before {
  background:
    linear-gradient(
      90deg,
      transparent 0,
      rgba(164, 184, 204, 0.14) 18%,
      transparent 40%,
      transparent 60%,
      rgba(164, 184, 204, 0.14) 82%,
      transparent 100%
    ) center / 100% 1px no-repeat,
    radial-gradient(
      circle, transparent 0 calc(50% - 1px), rgba(164, 184, 204, 0.08) calc(50% - 1px) 50%,
      transparent 50%
    );
}
.lage-zustandsmarke {
  display: block;
  margin-top: 1.4rem;
  font: 500 0.84rem var(--masch);
  letter-spacing: 0.36em;
  text-transform: uppercase;
  color: var(--akzent-hell);
  text-shadow: 0 0 20px var(--glut);
}
.lage-zustandsmarke.kalt { color: var(--kalt); text-shadow: none; }
.lage-zustandsmarke.fehler {
  color: var(--signal-fehler);
  text-shadow: 0 0 20px var(--fehler-glut);
}
.lage-satz {
  max-width: 34ch;
  margin: 0.55rem auto 0;
  color: var(--text-zweit);
  font-size: 0.92rem;
}
.lage-satz .mono { font-size: 0.86em; }

.kennzahlen { display: flex; flex-direction: column; margin: 0; }
/* Telemetrie: Beschriftung klein und still, Wert gross; darunter eine
   Lichtlinie, die zum Kern hin auslaeuft -- links nach rechts, rechts nach
   links. Die Spalten zeigen auf die Mitte. */
.kennzahl {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.85rem 0 0.95rem;
}
.kennzahl::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background: linear-gradient(90deg, var(--linie-stark), transparent);
}
.lage-system .kennzahl::after {
  background: linear-gradient(270deg, var(--linie-stark), transparent);
}
.kennzahl-name {
  font: 500 0.62rem var(--masch);
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
}
.kennzahl-wert {
  font: 400 1.55rem/1.2 var(--masch);
  letter-spacing: 0.01em;
  color: var(--text);
  word-break: break-word;
}
.kennzahl-wert.hebt { color: var(--akzent-hell); text-shadow: 0 0 16px var(--glut-weit); }
.kennzahl-wert.gefahr { color: var(--signal-fehler); }
.kennzahl-wert.kalt { color: var(--kalt); }
.kennzahl-wert.klein { font-size: 0.95rem; line-height: 1.5; }
.lage-system .kennzahl { align-items: flex-end; text-align: right; }
.kennzahl-zusatz { font-size: 0.78rem; color: var(--text-zweit); }


/* Abweichungen stehen vor allem anderen, als Liste mit Grund. */
.abweichungen {
  margin: 0.8rem 0 0;
  padding: 0.8rem 1rem;
  border: 1px solid var(--signal-fehler);
  border-radius: 3px;
  background: rgba(255, 95, 95, 0.06);
  font-size: 0.86rem;
}
.abweichungen ul { margin: 0.4rem 0 0; padding-left: 1.1rem; }
.abweichungen li { margin: 0.2rem 0; word-break: break-word; }

/* --- Zustandsmarke: Wort, Form, dann erst Farbe -------------------------- */

.marke {
  display: inline-block;
  font: 500 0.64rem/1.65 var(--masch);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  padding: 0 7px;
  border: 1px solid var(--linie-stark);
  border-radius: 2px;
  color: var(--text-zweit);
  background: rgba(0, 0, 0, 0.28);
  white-space: nowrap;
  vertical-align: middle;
}
.marke.erfolg { color: var(--text); }
.marke.offen {
  color: var(--akzent-hell);
  border-color: var(--akzent);
  box-shadow: 0 0 10px var(--glut-weit);
}
.marke.blockiert { color: var(--kalt); border-color: var(--kalt-tief); }
.marke.verworfen { color: var(--text-gedaempft); border-style: dashed; }
.marke.fehler { color: var(--signal-fehler); border-color: var(--signal-fehler); }
.marke.trocken {
  color: var(--text-zweit);
  background: repeating-linear-gradient(
    135deg, transparent 0 3px, rgba(255, 165, 90, 0.13) 3px 6px
  );
}

/* --- Autonomiestufe: immer beide Zahlen ---------------------------------- */

.stufe { font-family: var(--masch); font-size: 0.84rem; white-space: nowrap; }
.stufe .gewaehrt { color: var(--text); }
.stufe .verlangt { color: var(--text-gedaempft); }
.stufe.reicht-nicht .gewaehrt { color: var(--akzent-hell); text-shadow: 0 0 10px var(--glut-weit); }
.stufe-name { font-size: 0.8rem; color: var(--text-zweit); }

/* --- Gatterleiter: die Reihenfolge aus Abschnitt 4.2 --------------------- */

.gatter { border: 1px solid var(--linie); border-radius: 3px; background: rgba(0, 0, 0, 0.26); }
.gatter-sprosse {
  display: grid;
  grid-template-columns: 1.6rem 10.5rem minmax(0, 1fr) auto;
  gap: 0.8rem;
  align-items: baseline;
  padding: 0.45rem 0.9rem;
  border-bottom: 1px solid var(--linie);
  font-size: 0.82rem;
}
.gatter-sprosse:last-child { border-bottom: 0; }
.gatter-nr { font: 500 0.66rem var(--masch); color: var(--text-gedaempft); }
.gatter-name { color: var(--text-zweit); }
.gatter-wert {
  color: var(--text-gedaempft);
  font-family: var(--masch);
  font-size: 0.78rem;
  word-break: break-word;
}
.gatter-sprosse.entschieden {
  background: var(--glas-hoch);
  box-shadow: inset 2px 0 0 var(--akzent);
}
.gatter-sprosse.entschieden .gatter-name { color: var(--text); }
.gatter-sprosse.entschieden.blockiert { box-shadow: inset 2px 0 0 var(--kalt); }
.gatter-sprosse.offen { opacity: 0.45; }

/* --- Fakten und Tabellen ------------------------------------------------- */

.facts {
  display: grid;
  grid-template-columns: minmax(8rem, 11rem) minmax(0, 1fr);
  gap: 0.35rem 1.2rem;
  margin: 0;
  font-size: 0.84rem;
}
.facts dt { color: var(--text-gedaempft); }
.facts dd {
  margin: 0;
  font-family: var(--masch);
  color: var(--text);
  overflow-wrap: anywhere;
}

/* Breite Tabellen rollen in ihrem Rahmen, nie die Seite. */
.tabelle { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
th {
  text-align: left;
  font: 600 0.64rem var(--masch);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-gedaempft);
  padding: 0 1rem 0.6rem 0;
  border-bottom: 1px solid var(--linie-stark);
  white-space: nowrap;
}
td {
  padding: 0.55rem 1rem 0.55rem 0;
  border-bottom: 1px solid rgba(255, 165, 90, 0.09);
  vertical-align: top;
}
td.mono, .mono { font-family: var(--masch); white-space: nowrap; }
td.dim, .dim { color: var(--text-gedaempft); }
td.umbruch { word-break: break-word; }

/* Eine Zahl ohne Bezug ist keine Auskunft: benutzt/Grenze mit Balken. Der
   Fuellstand kommt in Fuenferstufen, weil ein Inline-Stil nicht zulaessig ist. */
.zaehler { display: inline-flex; align-items: center; gap: 0.5rem; font-family: var(--masch); }
.balken {
  display: inline-block;
  width: 3.5rem;
  height: 5px;
  border: 1px solid var(--linie-stark);
  border-radius: 1px;
  background: rgba(0, 0, 0, 0.3);
}
.balken span { display: block; height: 100%; background: var(--akzent-tief); }
.balken.voll span { background: var(--kalt); }
.f-0 { width: 0; } .f-5 { width: 5%; } .f-10 { width: 10%; } .f-15 { width: 15%; }
.f-20 { width: 20%; } .f-25 { width: 25%; } .f-30 { width: 30%; } .f-35 { width: 35%; }
.f-40 { width: 40%; } .f-45 { width: 45%; } .f-50 { width: 50%; } .f-55 { width: 55%; }
.f-60 { width: 60%; } .f-65 { width: 65%; } .f-70 { width: 70%; } .f-75 { width: 75%; }
.f-80 { width: 80%; } .f-85 { width: 85%; } .f-90 { width: 90%; } .f-95 { width: 95%; }
.f-100 { width: 100%; }

/* --- Anstehende Entscheidungen ------------------------------------------- */

.item {
  position: relative;
  margin-bottom: 1.1rem;
  border: 1px solid var(--linie);
  border-radius: 3px;
  background:
    linear-gradient(135deg, rgba(255, 190, 120, 0.05), transparent 28%),
    linear-gradient(180deg, rgba(255, 165, 90, 0.05), transparent 38%),
    var(--glas);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  box-shadow: inset 0 1px 0 rgba(255, 195, 130, 0.14), 0 14px 44px -22px var(--schatten);
}
.item::before {
  content: "";
  position: absolute;
  top: -1px;
  left: -1px;
  width: 11px;
  height: 11px;
  border: 1px solid var(--akzent);
  border-right: 0;
  border-bottom: 0;
  pointer-events: none;
}
.item-head {
  display: flex;
  gap: 0.9rem;
  align-items: baseline;
  flex-wrap: wrap;
  padding: 0.75rem 1.15rem;
  border-bottom: 1px solid var(--linie);
  background: var(--glas-hoch);
}
.item-skill {
  font: 500 0.76rem var(--masch);
  letter-spacing: 0.1em;
  color: var(--akzent-hell);
}
.item-when {
  margin-left: auto;
  font: 400 0.74rem var(--masch);
  color: var(--text-gedaempft);
}
.item-body-wrap { padding: 1.15rem; }
.item-summary { margin: 0 0 1rem; font-size: 1rem; word-break: break-word; }

/* Fremdtext ist Anzeige, nie Aussage der Oberflaeche -- deshalb als Zitat. */
.item-body {
  margin: 0.6rem 0 0;
  padding-left: 1rem;
  border-left: 2px dotted var(--linie-stark);
  color: var(--text-zweit);
  font-size: 0.88rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
  padding: 0.75rem 1.15rem;
  border-top: 1px solid var(--linie);
  background: rgba(0, 0, 0, 0.22);
}
.actions form { margin: 0; }
.actions .knapp { color: var(--text-gedaempft); font-size: 0.8rem; }

/* Kurzfassung eines Vorgangs auf der Lage: eine Zeile, ein Weg in die Tiefe. */
.anstehend { list-style: none; margin: 0; padding: 0; }
.anstehend li {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.25rem 0.9rem;
  padding: 0.65rem 0;
  border-bottom: 1px solid var(--linie);
  font-size: 0.86rem;
}
.anstehend li:first-child { border-top: 1px solid var(--linie); }
.anstehend .item-skill { font-size: 0.72rem; }
.anstehend .anstehend-satz { grid-column: 2; word-break: break-word; }
.anstehend .anstehend-zeit {
  grid-column: 2;
  font: 400 0.72rem var(--masch);
  color: var(--text-gedaempft);
}

/* --- Schaltflaechen ------------------------------------------------------ */

button {
  font: 500 0.72rem/1 var(--masch);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text);
  background: transparent;
  border: 1px solid var(--linie-stark);
  border-radius: 3px;
  padding: 0.55rem 1rem;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
button:hover { border-color: var(--text-zweit); background: var(--glas-hoch); }
button.primary {
  color: var(--grund);
  background: var(--akzent);
  border-color: var(--akzent);
  box-shadow: 0 0 16px var(--glut-weit);
}
button.primary:hover { background: var(--akzent-hell); border-color: var(--akzent-hell); }

/* --- Meldungen und Hinweise ---------------------------------------------- */

.note {
  margin: 1.2rem 0;
  padding: 0.7rem 1rem;
  border: 1px solid var(--linie);
  border-left: 3px solid var(--akzent);
  border-radius: 3px;
  background: var(--glas);
  color: var(--text-zweit);
  font-size: 0.88rem;
}
.note.warnung { border-left-color: var(--akzent-hell); }
.meldung { margin-top: 1.4rem; }

.briefing {
  margin: 1.2rem 0 0;
  padding: 0.2rem 0 0.2rem 1.1rem;
  border-left: 2px solid var(--akzent);
  font: inherit;
  font-size: 0.95rem;
  white-space: pre-wrap;
  word-break: break-word;
}
.empty {
  margin: 0;
  padding: 2rem 1rem;
  border: 1px dashed var(--linie-stark);
  border-radius: 3px;
  color: var(--text-gedaempft);
  font-size: 0.9rem;
  text-align: center;
}
footer {
  max-width: 96rem;
  margin: 0 auto;
  padding: 3rem 1.5rem 0;
  color: var(--text-gedaempft);
  font: 400 0.7rem var(--masch);
  letter-spacing: 0.06em;
}

/* --- Groessenstufen ------------------------------------------------------ */

@media (max-width: 70rem) {
  .lage { grid-template-columns: 1fr; gap: 1.6rem; }
  .lage-mitte { order: -1; }
  .kennzahlen { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 1.5rem; }
  .kennzahl:first-child { border-top: 0; }
  .kennzahl { border-top: 1px solid var(--linie); }
  .tafeln { grid-template-columns: 1fr; }
  .lage-mitte { --kern-groesse: 13rem; }
  .lage-system .kennzahl { align-items: flex-start; text-align: left; }
  .lage-system .kennzahl::after {
    background: linear-gradient(90deg, var(--linie-stark), transparent);
  }
  th { white-space: normal; }
}

@media (max-width: 46rem) {
  .systemband { position: static; }
  .systemband-inhalt { gap: 0.6rem 1rem; padding: 0.6rem 1rem; }
  .systemband form { margin-left: 0; width: 100%; }
  .systemband button.stopp { width: 100%; justify-content: center; }
  .kopf { padding: 1.2rem 1rem 0; gap: 1rem; }
  nav { margin-left: 0; width: 100%; }
  nav a { padding: 0.55rem 0.7rem; }
  .wrap { padding: 0 1rem; }
  footer { padding: 2.5rem 1rem 0; }
  .lage-mitte { --kern-groesse: 11rem; }
  .kennzahlen { grid-template-columns: 1fr; }
  .kennzahl { border-top: 0; }
  .facts { grid-template-columns: 1fr; gap: 0; }
  .facts dt { margin-top: 0.55rem; }
  .gatter-sprosse { grid-template-columns: 1.6rem minmax(0, 1fr) auto; row-gap: 0.2rem; }
  .gatter-wert { grid-column: 2 / 4; }
  .item-when { margin-left: 0; width: 100%; }
  .tafel { padding: 1rem; }

  /* Tabellen werden zu Bloecken: jede Zelle traegt ihren Kopf als Beschriftung. */
  table, thead, tbody, tr, td { display: block; }
  thead { display: none; }
  tr { padding: 0.6rem 0; border-bottom: 1px solid var(--linie); }
  td { padding: 0.15rem 0; border: 0; }
  td.mono, .mono { white-space: normal; }
  td::before {
    content: attr(data-kopf);
    display: block;
    font: 500 0.6rem var(--masch);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-gedaempft);
  }
}

/* Ein Protokollauszug soll sich als Beleg ablegen lassen. */
@media print {
  body, html { background: #fff; color: #000; }
  body::before, .systemband, nav, .actions, .kern, .puls { display: none; }
  .tafel, .item, .gatter { border-color: #000; background: none; box-shadow: none; }
  .marke, .kennzahl-wert, h1, h2, a { color: #000; text-shadow: none; }
}
"""
