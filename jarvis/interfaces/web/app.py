"""Das Dashboard.

Drei Ansichten -- Zustand, Entscheidungen, Protokoll -- und genau drei Dinge,
die man ausloesen kann: freigeben, verwerfen, anhalten. Durchlaeufe startet
weiter die Kommandozeile. Jede Schaltflaeche ist eine Angriffsflaeche, und eine
Oberflaeche, die Modellaufrufe ausloesen kann, ist etwas anderes als eine, die
nur bestaetigt.

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
from datetime import UTC, datetime
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
from jarvis.core.ratelimit import RateLimiter
from jarvis.interfaces.web.render import esc, fakten, hinweis, leer, seite, tabelle, vorgang
from jarvis.interfaces.web.security import (
    COOKIE_NAME,
    SECURITY_HEADERS,
    load_or_create_token,
    origin_is_own,
    token_matches,
)
from jarvis.interfaces.web.style import CSS
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
    "fortgesetzt": "Freigegeben. Ausgehende Aktionen sind wieder moeglich.",
    "nicht-erreichbar": "Gmail war nicht erreichbar. Der Vorgang bleibt offen.",
}


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

    def rahmen(request: Request, titel: str, inhalt: str, aktiv: str) -> HTMLResponse:
        config = konfiguration()
        schalter = config.stop_switch
        conn = verbindung()
        try:
            offen = ApprovalStore(conn).count_pending()
        finally:
            conn.close()

        meldung = MELDUNGEN.get(request.query_params.get("m", ""))
        koerper = (hinweis(meldung) if meldung else "") + inhalt
        return HTMLResponse(
            seite(
                titel,
                inhalt_html=koerper,
                aktiv=aktiv,
                angehalten=schalter.engaged(),
                stopp_grund=schalter.reason(),
                offen=offen,
                refresh=config.web.refresh_seconds,
            )
        )

    # ---------------------------------------------------------------- #

    @geschuetzt
    def zustand(request: Request) -> Response:
        config = konfiguration()
        conn = verbindung()
        try:
            audit = AuditLog(conn)
            kette = audit.verify()
            begrenzer = RateLimiter(conn, config.capabilities)
            offen = ApprovalStore(conn).count_pending()

            kopf = fakten(
                [
                    ("Trockenlauf", "an" if config.dry_run else "AUS"),
                    ("Protokoll", f"{audit.count()} Eintraege"),
                    ("Kette", "intakt" if kette.ok else f"GEBROCHEN bei {kette.broken_at}"),
                    ("Offen", offen),
                ]
            )

            zeilen = []
            for name in sorted(config.capabilities):
                cap = config.capabilities[name]
                zaehler = (
                    "  ".join(f"{w.window} {w.used}/{w.limit}" for w in begrenzer.usage(name))
                    or "--"
                )
                zeilen.append(
                    [
                        name,
                        f"{int(cap.autonomy_level)}  {cap.autonomy_level.label}",
                        "ja" if cap.requires_outbound else "nein",
                        "ja" if cap.enabled else "nein",
                        zaehler,
                    ]
                )
            inhalt = (
                "<h2>Zustand</h2>"
                + kopf
                + "<h2>Faehigkeiten</h2>"
                + tabelle(
                    ["Faehigkeit", "Stufe", "Ausgehend", "Aktiv", "Zaehler"],
                    zeilen,
                    mono=(0, 4),
                )
            )
        finally:
            conn.close()
        return rahmen(request, "Zustand", inhalt, "/")

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
            heute = datetime.now(UTC).date().isoformat()

            if not eintraege:
                inhalt = "<h2>Briefing</h2>" + leer(
                    "Noch kein Briefing abgelegt. Erzeugen: jarvis briefing --neu"
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
                inhalt = (
                    "<h2>Briefing</h2>" + kopf + f'<pre class="briefing">{esc(neuestes.text)}</pre>'
                )
                if len(eintraege) > 1:
                    inhalt += "<h2>Frueher</h2>" + tabelle(
                        ["Tag", "Quelle", "Anfang"],
                        [
                            [b.day, b.model or "ohne Modell", b.text.split(chr(10))[0][:60]]
                            for b in eintraege[1:]
                        ],
                        mono=(0,),
                    )
        finally:
            conn.close()
        return rahmen(request, "Briefing", inhalt, "/briefing")

    @geschuetzt
    def entscheidungen(request: Request) -> Response:
        config = konfiguration()
        conn = verbindung()
        try:
            eintraege = ApprovalStore(conn).pending(limit=50)
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
                        "dry_run in der Konfiguration auf false setzen."
                    )
                )
            teile += [vorgang(e, ausfuehrbar=ausfuehrbar) for e in eintraege]
            inhalt = "".join(teile)
        return rahmen(request, "Entscheidungen", inhalt, "/entscheidungen")

    @geschuetzt
    def protokoll(request: Request) -> Response:
        conn = verbindung()
        try:
            eintraege = AuditLog(conn).recent(60)
        finally:
            conn.close()
        zeilen = [
            [
                e.id,
                e.ts[:19].replace("T", " "),
                "T" if e.dry_run else "",
                e.capability,
                e.kind,
                e.outcome,
                str(e.detail.get("reason", "") or e.detail.get("summary", ""))[:90],
            ]
            for e in eintraege
        ]
        inhalt = "<h2>Protokoll</h2>" + tabelle(
            ["Nr", "Zeit (UTC)", "T", "Faehigkeit", "Art", "Ergebnis", "Grund"],
            zeilen,
            mono=(0, 1, 2),
        )
        return rahmen(request, "Protokoll", inhalt, "/protokoll")

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
            from jarvis.core.gate import Gate

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
        Route("/", zustand),
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
