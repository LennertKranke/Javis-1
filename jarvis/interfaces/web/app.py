"""Das Dashboard.

Vier Ansichten -- Lage, Entscheidungen, Briefing, Protokoll -- und genau vier
Dinge, die man ausloesen kann: freigeben, verwerfen, anhalten, fortsetzen.
Durchlaeufe startet weiter die Kommandozeile. Jede Schaltflaeche ist eine
Angriffsflaeche, und eine Oberflaeche, die Modellaufrufe ausloesen kann, ist
etwas anderes als eine, die nur bestaetigt.

Die Lage ist die Leitstelle: in der Mitte der Kern mit dem Systemzustand,
daneben die Zahlen, die zaehlen, darunter was wartet, was zuletzt geschah und
was die Faehigkeiten duerfen. Alles darauf ist gelesen, nichts davon ist
entschieden -- gehandelt wird nur in der Ansicht Entscheidungen, und auch dort
nur ueber `execute_approval`.

Die Endpunkte sind bewusst gewoehnliche Funktionen, nicht `async`. Starlette
fuehrt sie dann in einem Threadpool aus, und SQLite bekommt pro Anfrage eine
eigene Verbindung -- das ist einfacher und verlaesslicher, als eine Verbindung
ueber Threads zu teilen.

Nach jeder veraendernden Anfrage wird umgeleitet. Ein Neuladen der Seite
wiederholt sonst die Freigabe, und das darf es hier auf keinen Fall.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Route

from jarvis.core.approvals import ApprovalStore
from jarvis.core.audit import KIND_SYSTEM, AuditLog
from jarvis.core.config import Config, ConfigError, Paths, StopSwitch
from jarvis.core.db import open_database
from jarvis.core.files import offene_pfade
from jarvis.core.gate import Gate, GatePreview
from jarvis.core.ratelimit import RateLimiter
from jarvis.core.secrets import default_store
from jarvis.daemon import letzter_lauf
from jarvis.interfaces.web.render import (
    esc,
    fakten,
    hinweis,
    kennzahl,
    kern,
    leer,
    seite,
    stufe,
    tabelle,
    tafel,
    vorgang,
    vorgang_kurz,
    zaehler,
    zustand_ermitteln,
    zustandsmarke,
)
from jarvis.interfaces.web.security import (
    COOKIE_NAME,
    SECURITY_HEADERS,
    load_or_create_token,
    origin_is_own,
    token_matches,
)
from jarvis.interfaces.web.style import CSS
from jarvis.skills.base import available_skills
from jarvis.skills.briefing.store import BriefingStore
from jarvis.skills.factory import build_skill
from jarvis.skills.runner import execute_approval, reject_approval

__all__ = ["create_app"]

# Rueckmeldungen als Code, nicht als Text in der Adresszeile -- sonst laesst
# sich ueber einen Link beliebiger Text auf der eigenen Seite anzeigen.
MELDUNGEN = {
    "freigegeben": "Freigegeben und ausgefuehrt.",
    "nicht-ausgefuehrt": "Freigegeben, aber nicht ausgefuehrt. Der Grund steht am Vorgang.",
    "verworfen": "Verworfen. Es ist nichts geschehen.",
    "fehlgeschlagen": "Die Ausfuehrung ist fehlgeschlagen. Der Grund steht am Vorgang.",
    "unbekannt": "Diesen Vorgang gibt es nicht mehr.",
    "angehalten": "Angehalten. Jede ausgehende Aktion ist blockiert.",
    "fortgesetzt": "Fortgesetzt. Ausgehende Aktionen sind wieder moeglich.",
    "nicht-erreichbar": "Gmail war nicht erreichbar. Der Vorgang bleibt offen.",
}

#: Wie die Trennung des Modellprozesses heisst, wenn man sie liest.
TRENNUNG = {
    "subprocess": "eigener Prozess",
    "sandbox": "eigener Prozess, Sandbox",
    "off": "AUS -- im selben Prozess",
}


def _stoppgrund(schalter: StopSwitch) -> str | None:
    """Der Grund lesbar: "<grund> (<urheber>, seit hh:mm UTC)" statt der Rohzeile.

    Die Stoppdatei traegt "<zeit> <urheber>: <grund>". Im Band zaehlt der
    Grund; Urheber und Uhrzeit stehen dahinter, weil sie sagen, wer und seit
    wann. Passt die Zeile nicht auf die Form -- von Hand geschrieben --, wird
    sie unveraendert gezeigt.
    """
    roh = schalter.reason()
    if not roh:
        return None
    kopf, trenner, rest = roh.partition(": ")
    teile = kopf.split()
    if trenner and len(teile) == 2 and rest.strip():
        zeit, urheber = teile
        return f"{rest.strip()} ({urheber}, seit {zeit[11:16]} UTC)"
    return roh


class SecurityHeaders:
    """Setzt die Schutzkopfzeilen auf jede Antwort, ohne Ausnahme."""

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def gesendet(nachricht: Any) -> None:
            if nachricht["type"] == "http.response.start":
                kopf = MutableHeaders(scope=nachricht)
                for name, wert in SECURITY_HEADERS.items():
                    kopf.setdefault(name, wert)
            await send(nachricht)

        await self._app(scope, receive, gesendet)


def create_app(
    *,
    home: Path | None = None,
    token: str | None = None,
    port: int | None = None,
) -> Starlette:
    """`port` ist der Port, auf dem tatsaechlich gelauscht wird.

    Nicht der aus der Konfiguration: mit `--port` weichen die beiden ab, und
    die Herkunftspruefung wuerde dann die eigenen Formulare abweisen. Ein
    Fehler, der sich als "die Knoepfe tun nichts" zeigt.
    """
    paths = Paths(home=home) if home is not None else Paths.default()
    sitzungstoken = token or load_or_create_token(paths.home)
    eigener_port = port

    def verbindung() -> sqlite3.Connection:
        return open_database(paths.db_file)

    def konfiguration() -> Config:
        return Config.load(home=paths.home)

    def eigene_quellen(config: Config) -> set[str]:
        gelauscht = eigener_port or config.web.port
        return {f"http://{host}:{gelauscht}" for host in ("127.0.0.1", "localhost", "[::1]")}

    # ---------------------------------------------------------------- #

    def geschuetzt(funktion: Callable[..., Response]) -> Callable[..., Response]:
        @wraps(funktion)
        def gepruefte(request: Request) -> Response:
            aus_abfrage = request.query_params.get("token")
            aus_cookie = request.cookies.get(COOKIE_NAME)

            if token_matches(sitzungstoken, aus_abfrage):
                # Token aus der Adresszeile in ein Cookie umwandeln und die
                # Adresse saeubern -- sonst steht er im Verlauf jeder Seite.
                ziel = request.url.path or "/"
                antwort = RedirectResponse(ziel, status_code=303)
                antwort.set_cookie(
                    COOKIE_NAME,
                    sitzungstoken,
                    httponly=True,
                    samesite="strict",
                    path="/",
                )
                return antwort

            if not token_matches(sitzungstoken, aus_cookie):
                return PlainTextResponse(
                    "Kein gueltiger Zugang.\n\n"
                    "Das Dashboard verlangt den Sitzungstoken aus ~/.jarvis/web-token.\n"
                    "Die vollstaendige Adresse steht in der Ausgabe von: jarvis web\n",
                    status_code=403,
                )

            if request.method not in ("GET", "HEAD"):
                config = konfiguration()
                if not origin_is_own(
                    request.headers.get("origin"),
                    request.headers.get("referer"),
                    eigene_quellen(config),
                ):
                    return PlainTextResponse(
                        "Herkunft der Anfrage passt nicht zu dieser Oberflaeche.\n",
                        status_code=403,
                    )
            return funktion(request)

        return gepruefte

    def rahmen(
        request: Request, titel: str, inhalt: str, aktiv: str, *, weit: bool = False
    ) -> HTMLResponse:
        config = konfiguration()
        schalter = config.stop_switch
        conn = verbindung()
        try:
            offen = ApprovalStore(conn).count_pending()
        finally:
            conn.close()

        # Die Zugangsdatenquelle steht im Band, weil Abschnitt 12 sie zum
        # Systemzustand zaehlt. `describe()` liest nur, was beim Start gewaehlt
        # wurde -- es fragt keinen Speicher und holt kein Geheimnis.
        speicher = default_store()
        zugangsdaten = speicher.describe()
        if speicher.violates_spec:
            zugangsdaten = f"{zugangsdaten} -- Abweichung"

        meldung = MELDUNGEN.get(request.query_params.get("m", ""))
        return HTMLResponse(
            seite(
                titel,
                inhalt_html=inhalt,
                meldung_html=hinweis(meldung, art="meldung") if meldung else "",
                aktiv=aktiv,
                angehalten=schalter.engaged(),
                stopp_grund=_stoppgrund(schalter),
                offen=offen,
                refresh=config.web.refresh_seconds,
                trockenlauf=config.dry_run,
                dienste_mock=config.services.is_mock,
                zugangsdaten=zugangsdaten,
                weit=weit,
            )
        )

    # ---------------------------------------------------------------- #

    def _abweichungen(config: Config, kette_ok: bool, kette_bei: int | None) -> list[str]:
        """Was nicht stimmt -- aus denselben Pruefungen wie `jarvis status`.

        Drei Quellen, alle gemessen: die Hash-Kette, die Dateirechte der
        Ablage, die Quelle der Zugangsdaten. Nichts davon ist ein Zustand, den
        sich die Oberflaeche ausdenkt; jede Zeile hier laesst `jarvis status`
        ebenfalls mit 1 enden.
        """
        befunde: list[str] = []
        if not kette_ok:
            befunde.append(f"Protokollkette gebrochen bei Eintrag {kette_bei}")

        # Nur bei eingerichteter Ablage, wie in der CLI: ein leeres
        # Verzeichnis hat nichts, was auslaufen koennte.
        eingerichtet = paths.db_file.exists() or paths.config_file.exists()
        offen = [p.name or str(p) for p in offene_pfade(paths.home)] if eingerichtet else []
        if offen:
            sichtbar = ", ".join(offen[:4]) + (
                f" und {len(offen) - 4} weitere" if len(offen) > 4 else ""
            )
            befunde.append(f"Ablage offen fuer andere Benutzer: {sichtbar}")

        speicher = default_store()
        grund = speicher.insecure_reason()
        if grund and speicher.violates_spec:
            befunde.append(f"Zugangsdaten: {grund}")
        return befunde

    @geschuetzt
    def lage(request: Request) -> Response:
        config = konfiguration()
        schalter = config.stop_switch
        conn = verbindung()
        try:
            audit = AuditLog(conn)
            kette = audit.verify()
            begrenzer = RateLimiter(conn, config.capabilities)
            freigaben = ApprovalStore(conn)
            offen = freigaben.count_pending()
            anstehend = freigaben.pending(limit=4)
            letzte = audit.recent(8)
            protokoll_anzahl = audit.count()
            # Der letzte Lauf je Faehigkeit stammt vom Daemon; die CLI
            # verzeichnet ihren Lauf nicht. Die Spalte heisst deshalb so.
            laeufe = {name: letzter_lauf(conn, name) for name in config.capabilities}
            # Vor dem Schliessen lesen: der Begrenzer haengt an der Verbindung.
            kontingente = {
                name: [(w.window, w.used, w.limit) for w in begrenzer.usage(name)]
                for name in config.capabilities
            }
        finally:
            conn.close()

        abweichungen = _abweichungen(config, kette.ok, kette.broken_at)
        # Im Satz unter dem Kern nur der Grund; Zeitstempel und Urheber
        # stehen weiterhin im Band.
        zustand = zustand_ermitteln(
            angehalten=schalter.engaged(),
            stopp_grund=schalter.spoken_reason(),
            offen=offen,
            abweichungen=abweichungen,
            trockenlauf=config.dry_run,
        )

        # --- Kern, Zahlen, System ------------------------------------------ #
        kette_text = "intakt" if kette.ok else f"gebrochen bei {kette.broken_at}"
        zahlen = (
            kennzahl("Offene Entscheidungen", offen, art="hebt" if offen else "")
            + kennzahl(
                "Protokoll",
                protokoll_anzahl,
                art="" if kette.ok else "gefahr",
                zusatz=f"Eintraege, Kette {kette_text}",
            )
            + (
                kennzahl("Letzter Eintrag", letzte[0].ts[11:19], zusatz=f"{letzte[0].ts[:10]}, UTC")
                if letzte
                else kennzahl("Letzter Eintrag", "--")
            )
        )

        speicher = default_store()
        eingerichtet = paths.db_file.exists() or paths.config_file.exists()
        offene = offene_pfade(paths.home) if eingerichtet else []
        # Rechts vom Kern die drei Tatsachen, die sagen, wie sicher das
        # System gerade steht -- in derselben Form wie die Zahlen links.
        # Pfade stehen hier nicht: `jarvis status` nennt sie, die Lage nicht.
        system = (
            kennzahl("Zugangsdaten", f"{speicher.describe()} ({speicher.mode})", art="klein")
            + kennzahl(
                "Ablage",
                "geschlossen, 0700/0600" if not offene else f"{len(offene)} Pfade offen",
                art="klein" if not offene else "klein gefahr",
            )
            + kennzahl(
                "Modellprozess",
                TRENNUNG.get(config.llm.isolation, config.llm.isolation),
                art="klein" if config.llm.isolation != "off" else "klein gefahr",
            )
        )
        mitte = (
            kern(zustand)
            + f'<span class="lage-zustandsmarke {esc(zustand.art)}">{esc(zustand.titel)}</span>'
            + f'<p class="lage-satz">{esc(zustand.satz)}</p>'
        )
        kopf = (
            '<section class="lage">'
            f'<div class="lage-kennzahlen"><div class="kennzahlen">{zahlen}</div></div>'
            f'<div class="lage-mitte">{mitte}</div>'
            f'<div class="lage-system"><div class="kennzahlen">{system}</div></div>'
            "</section>"
        )
        if abweichungen:
            punkte = "".join(f"<li>{esc(a)}</li>" for a in abweichungen)
            kopf += (
                '<div class="abweichungen">Abweichungen, die vor jeder Arbeit geklaert '
                f"gehoeren:<ul>{punkte}</ul></div>"
            )

        # --- Was wartet, was zuletzt geschah ------------------------------- #
        if anstehend:
            wartend = '<ul class="anstehend">' + "".join(map(vorgang_kurz, anstehend)) + "</ul>"
            weg = f'<a href="/entscheidungen">Alle {offen} ansehen und entscheiden</a>'
        else:
            wartend = leer("Nichts anstehend. Was von selbst durchging, steht im Protokoll.")
            weg = ""
        zuletzt = tabelle(
            ["Zeit (UTC)", "Faehigkeit", "Ergebnis", "Grund"],
            [
                [
                    e.ts[11:19],
                    e.capability,
                    zustandsmarke(e.outcome, dry_run=e.dry_run),
                    str(e.detail.get("reason", "") or e.detail.get("summary", ""))[:70],
                ]
                for e in letzte
            ],
            mono=(0, 1),
            roh=(2,),
            umbruch=(3,),
        )
        tafeln = (
            '<div class="tafeln">'
            + tafel("Anstehend", wartend, fuss_html=weg)
            + tafel(
                "Zuletzt im Protokoll",
                zuletzt,
                fuss_html='<a href="/protokoll">Vollstaendiges Protokoll</a>',
            )
            + "</div>"
        )

        # --- Faehigkeiten --------------------------------------------------- #
        # Die verlangte Stufe steht am Skill, die gewaehrte in der
        # Konfiguration. Nur eine von beiden zu zeigen war die alte Fassung --
        # und genau diese Verwechslung hat im Audit eine Faehigkeit auf Stufe 0
        # handeln lassen: `0 >= 0` ist wahr.
        faehigkeiten = available_skills()
        zeilen = []
        for name in sorted(config.capabilities):
            cap = config.capabilities[name]
            klasse = faehigkeiten.get(name)
            verlangt = None if klasse is None else int(klasse.autonomy_level)
            lauf = laeufe.get(name)
            zuletzt_gelaufen = (
                datetime.fromtimestamp(lauf, tz=config.timezone).strftime("%Y-%m-%d %H:%M")
                if lauf
                else "--"
            )
            zeilen.append(
                [
                    name,
                    stufe(int(cap.autonomy_level), verlangt, cap.autonomy_level.label),
                    "ja" if cap.requires_outbound else "nein",
                    "ja" if cap.enabled else "nein",
                    zaehler(kontingente[name]),
                    zuletzt_gelaufen,
                ]
            )
        faehigkeitstafel = tafel(
            "Faehigkeiten",
            tabelle(
                # Siehe cli.py: "Ausgehend" war irrefuehrend. Labels und
                # Entwuerfe gehen zu Google, erreichen aber niemanden.
                # "Stufe" traegt beide Zahlen: gewaehrt / verlangt.
                [
                    "Faehigkeit",
                    "Stufe gewaehrt / verlangt",
                    "Erreicht Dritte",
                    "Aktiv",
                    "Kontingent",
                    "Letzter Lauf (Daemon)",
                ],
                zeilen,
                mono=(0, 2, 3, 5),
                roh=(1, 4),
            ),
            klasse="breit",
        )
        return rahmen(request, "Lage", kopf + tafeln + faehigkeitstafel, "/", weit=True)

    @geschuetzt
    def briefing(request: Request) -> Response:
        """Zeigt, was abgelegt ist. Erzeugt wird hier nichts.

        Ein Durchlauf gehoert an die Kommandozeile: die Oberflaeche liest den
        Zustand und gibt einzelne Entscheidungen frei, sie startet keine.
        """
        conn = verbindung()
        try:
            store = BriefingStore(conn)
            eintraege = store.recent(limit=7)
            heute = datetime.now(konfiguration().timezone).date().isoformat()

            if not eintraege:
                inhalt = tafel(
                    "Briefing",
                    leer("Noch kein Briefing abgelegt. Erzeugen: jarvis briefing --neu"),
                )
            else:
                neuestes = eintraege[0]
                kopf = fakten(
                    [
                        ("Tag", neuestes.day),
                        ("Stand", "heute" if neuestes.day == heute else "aelter"),
                        ("Quelle", neuestes.model or "ohne Modell"),
                        ("Erstellt", neuestes.created_at[:19].replace("T", " ")),
                    ]
                )
                inhalt = tafel(
                    "Briefing", kopf + f'<pre class="briefing">{esc(neuestes.text)}</pre>'
                )
                if len(eintraege) > 1:
                    inhalt += tafel(
                        "Frueher",
                        tabelle(
                            ["Tag", "Quelle", "Anfang"],
                            [
                                [b.day, b.model or "ohne Modell", b.text.split(chr(10))[0][:60]]
                                for b in eintraege[1:]
                            ],
                            mono=(0,),
                            umbruch=(2,),
                        ),
                        klasse="breit",
                    )
        finally:
            conn.close()
        return rahmen(request, "Briefing", inhalt, "/briefing")

    def _vorschau(gate: Gate, skill: str) -> GatePreview | None:
        """Woran haengt dieser Vorgang, wenn jetzt freigegeben wird?

        `approved=True`, weil das die Frage ist, die vor dem Klick zaehlt. Die
        Leiter zeigt dann, dass eine Freigabe nur auf Sprosse 3 wirkt --
        Stoppschalter, Obergrenze und Trockenlauf gelten weiter.

        Sie entscheidet nichts: `preview` schreibt kein Protokoll und
        verbraucht kein Kontingent. Wer wirklich handelt, ist `execute_approval`
        ueber `evaluate`.
        """
        klasse = available_skills().get(skill)
        if klasse is None:
            return None
        try:
            return gate.preview(skill, required_level=int(klasse.autonomy_level), approved=True)
        except ConfigError:
            # Ein Vorgang zu einer Faehigkeit, die es in der Konfiguration
            # nicht mehr gibt. Kein Grund, die ganze Ansicht zu verlieren.
            return None

    @geschuetzt
    def entscheidungen(request: Request) -> Response:
        config = konfiguration()
        conn = verbindung()
        try:
            eintraege = ApprovalStore(conn).pending(limit=50)
            gate = Gate(config, AuditLog(conn), RateLimiter(conn, config.capabilities))
            vorschauen = {e.id: _vorschau(gate, e.skill) for e in eintraege}
        finally:
            conn.close()

        if not eintraege:
            inhalt = "<h2>Anstehende Entscheidungen</h2>" + leer(
                "Nichts anstehend. Was von selbst durchging, steht im Protokoll."
            )
        else:
            ausfuehrbar = not config.dry_run
            teile = ["<h2>Anstehende Entscheidungen</h2>"]
            if not ausfuehrbar:
                teile.append(
                    hinweis(
                        "Trockenlauf ist an. Verwerfen geht, Freigeben bewirkt nichts -- "
                        "dry_run in der Konfiguration auf false setzen.",
                        art="warnung",
                    )
                )
            teile += [
                vorgang(e, ausfuehrbar=ausfuehrbar, vorschau=vorschauen[e.id]) for e in eintraege
            ]
            inhalt = "".join(teile)
        return rahmen(request, "Entscheidungen", inhalt, "/entscheidungen")

    @geschuetzt
    def protokoll(request: Request) -> Response:
        conn = verbindung()
        try:
            audit = AuditLog(conn)
            eintraege = audit.recent(60)
            anzahl = audit.count()
            kette = audit.verify()
        finally:
            conn.close()
        # Statt einer T-Spalte mit Legende steht der Zustand als Marke da.
        # Was kein Zustand ist -- die vom Modell vorgeschlagene Aktion eines
        # `decision`-Eintrags -- bekommt keine Marke, sondern bleibt Text.
        zeilen = [
            [
                e.id,
                e.ts[:19].replace("T", " "),
                e.capability,
                e.kind,
                zustandsmarke(e.outcome, dry_run=e.dry_run),
                str(e.detail.get("reason", "") or e.detail.get("summary", ""))[:90],
            ]
            for e in eintraege
        ]
        kette_text = "intakt" if kette.ok else f"gebrochen bei {kette.broken_at}"
        stand = f"{anzahl} Eintraege, Kette {kette_text}; die letzten {len(zeilen)} stehen hier"
        inhalt = tafel(
            "Protokoll",
            tabelle(
                ["Nr", "Zeit (UTC)", "Faehigkeit", "Art", "Ergebnis", "Grund"],
                zeilen,
                mono=(0, 1, 2),
                roh=(4,),
                umbruch=(5,),
            ),
            fuss_html=esc(stand),
        )
        return rahmen(request, "Protokoll", inhalt, "/protokoll", weit=True)

    # ---------------------------------------------------------------- #

    @geschuetzt
    def freigeben(request: Request) -> Response:
        vorgangs_id = int(request.path_params["vorgang_id"])
        config = konfiguration()
        conn = verbindung()
        try:
            speicher = ApprovalStore(conn)
            eintrag = speicher.get(vorgangs_id)
            if eintrag is None or not eintrag.pending:
                return _zurueck("unbekannt")

            audit = AuditLog(conn)
            gate = Gate(config, audit, RateLimiter(conn, config.capabilities))
            try:
                # Die Freigabe wirkt auf das Gatter und auf die Rechte des
                # Clients gleichermassen. Sonst laesst das Gatter durch, was
                # der Client anschliessend nicht darf.
                skill = build_skill(eintrag.skill, config=config, conn=conn, approved=True)
            except ConfigError:
                speicher.note(vorgangs_id, "Faehigkeit laesst sich nicht bauen")
                return _zurueck("fehlgeschlagen")

            try:
                ergebnis = execute_approval(
                    eintrag, skill=skill, gate=gate, audit=audit, approvals=speicher
                )
            except Exception as exc:  # Gmail weg, Modell weg -- Vorgang bleibt offen
                speicher.note(vorgangs_id, str(exc)[:200])
                return _zurueck("nicht-erreichbar")

            if ergebnis is None:
                return _zurueck("nicht-ausgefuehrt")
            return _zurueck("freigegeben" if ergebnis.performed else "fehlgeschlagen")
        finally:
            conn.close()

    @geschuetzt
    def verwerfen(request: Request) -> Response:
        vorgangs_id = int(request.path_params["vorgang_id"])
        conn = verbindung()
        try:
            speicher = ApprovalStore(conn)
            eintrag = speicher.get(vorgangs_id)
            if eintrag is None or not eintrag.pending:
                return _zurueck("unbekannt")
            reject_approval(eintrag, audit=AuditLog(conn), approvals=speicher)
            return _zurueck("verworfen")
        finally:
            conn.close()

    @geschuetzt
    def anhalten(request: Request) -> Response:
        config = konfiguration()
        StopSwitch(config.paths.stop_file).engage("ueber das Dashboard", actor="web")
        _system_notiz(config, "stop_engaged", {"actor": "web"})
        return _zurueck("angehalten", ziel="/")

    @geschuetzt
    def fortsetzen(request: Request) -> Response:
        config = konfiguration()
        StopSwitch(config.paths.stop_file).release()
        _system_notiz(config, "stop_released", {"actor": "web"})
        return _zurueck("fortgesetzt", ziel="/")

    def _system_notiz(config: Config, ergebnis: str, detail: dict[str, Any]) -> None:
        if not config.paths.db_file.exists():
            return
        conn = verbindung()
        try:
            AuditLog(conn).record(
                capability="core", kind=KIND_SYSTEM, outcome=ergebnis, detail=detail
            )
        finally:
            conn.close()

    def _zurueck(code: str, *, ziel: str = "/entscheidungen") -> Response:
        return RedirectResponse(f"{ziel}?m={code}", status_code=303)

    def stylesheet(request: Request) -> Response:
        return Response(CSS, media_type="text/css")

    routen = [
        Route("/", lage),
        Route("/briefing", briefing),
        Route("/entscheidungen", entscheidungen),
        Route("/entscheidungen/{vorgang_id:int}/freigeben", freigeben, methods=["POST"]),
        Route("/entscheidungen/{vorgang_id:int}/verwerfen", verwerfen, methods=["POST"]),
        Route("/protokoll", protokoll),
        Route("/stop", anhalten, methods=["POST"]),
        Route("/weiter", fortsetzen, methods=["POST"]),
        Route("/jarvis.css", stylesheet),
    ]
    app = Starlette(routes=routen)
    app.add_middleware(SecurityHeaders)
    return app
