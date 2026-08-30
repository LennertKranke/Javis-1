"""Google Calendar: Anmeldung und die drei Aufrufe, die JARVIS braucht.

Gebaut wie der Gmail-Client und aus demselben Grund: eine Endpunkt-Allowlist,
die aus den Faehigkeiten folgt, die der Aufrufer mitgibt. In Phase 5 liest
JARVIS den Kalender und sonst nichts -- es gibt keinen Schreibpfad im Code,
und der Client wuerde ihn ohnehin abweisen.

Die Zustimmung laeuft ueber denselben Token wie Gmail. `calendar.readonly` ist
dabei neu hinzugekommen, ein bestehender Token traegt sie also nicht: dann
meldet `has_calendar_scope` das, statt in einen Fehler zu laufen, den niemand
zuordnen kann.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from jarvis.skills.mail.gmail import GmailAuth, GmailAuthError, GmailError

__all__ = [
    "CALENDAR_READ",
    "CALENDAR_SCOPE",
    "CalendarClient",
    "has_calendar_scope",
]

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
API_ROOT = "https://www.googleapis.com/calendar/v3"

ENDPOINTS_BY_CAPABILITY: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "read": (
        ("GET", re.compile(r"^/users/me/calendarList$")),
        ("GET", re.compile(r"^/calendars/[^/]+/events$")),
        ("GET", re.compile(r"^/calendars/[^/]+/events/[A-Za-z0-9_-]+$")),
    ),
}

CALENDAR_READ = frozenset({"read"})


def has_calendar_scope(auth: GmailAuth) -> bool:
    """Traegt der vorhandene Token bereits das Kalenderrecht?"""
    try:
        credentials = auth.credentials()
    except GmailAuthError:
        return False
    return CALENDAR_SCOPE in (getattr(credentials, "scopes", None) or [])


class CalendarClient:
    def __init__(
        self,
        auth: GmailAuth,
        *,
        capabilities: frozenset[str] | set[str] = CALENDAR_READ,
        timeout: float = 30.0,
    ) -> None:
        unbekannt = sorted(set(capabilities) - set(ENDPOINTS_BY_CAPABILITY))
        if unbekannt:
            raise ValueError(f"Unbekannte Faehigkeiten: {', '.join(unbekannt)}")
        self._auth = auth
        self._capabilities = frozenset(capabilities)
        self._timeout = timeout
        self._opener = urllib.request.build_opener()

    @property
    def capabilities(self) -> frozenset[str]:
        return self._capabilities

    def can(self, capability: str) -> bool:
        return capability in self._capabilities

    def _check_endpoint(self, method: str, path: str) -> None:
        for capability in self._capabilities:
            for erlaubte_methode, muster in ENDPOINTS_BY_CAPABILITY[capability]:
                if method == erlaubte_methode and muster.match(path):
                    return
        erlaubt = ", ".join(sorted(self._capabilities)) or "keine"
        raise GmailError(
            f"{method} {path} steht nicht auf der Liste der erlaubten Endpunkte "
            f"(freigeschaltet: {erlaubt}). In dieser Phase wird nur gelesen."
        )

    def _call(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict:
        self._check_endpoint(method, path)
        url = f"{API_ROOT}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            method=method,
            headers={
                "Authorization": f"Bearer {self._auth.token()}",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                inhalt = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise GmailAuthError(
                    f"Kalender lehnt den Zugriff ab (HTTP {exc.code}). "
                    f"Fehlt das Kalenderrecht, hilft: jarvis mail login"
                ) from exc
            if exc.code == 429:
                raise GmailError("Kalender drosselt (HTTP 429)") from exc
            raise GmailError(f"Kalender antwortet mit HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise GmailError("Kalender antwortet nicht rechtzeitig") from exc
        except urllib.error.URLError as exc:
            raise GmailError(f"Kalender nicht erreichbar ({exc.reason})") from exc

        if not inhalt:
            return {}
        try:
            return json.loads(inhalt)
        except json.JSONDecodeError as exc:
            raise GmailError("Kalender liefert unlesbares JSON") from exc

    # ---------------------------------------------------------------- #

    def list_calendars(self) -> list[dict]:
        return list(self._call("GET", "/users/me/calendarList").get("items") or [])

    def list_events(
        self, calendar_id: str, *, time_min: str, time_max: str, limit: int = 100
    ) -> list[dict]:
        """Termine in einem Zeitfenster, wiederkehrende bereits aufgeloest.

        Bewusst ohne Blaettern: es wird genau eine Seite geholt, hoechstens 250
        Termine je Kalender und Fenster. Ein `nextPageToken` in der Antwort
        wird nicht verfolgt. Fuer ein Fenster von wenigen Tagen in einem
        persoenlichen Kalender reicht das; wer laengere Fenster oder sehr volle
        Kalender liest, verliert stillschweigend den Rest -- dann gehoert hier
        eine Schleife ueber `pageToken` hin. Bis dahin ist die Grenze eine
        bekannte, keine uebersehene.
        """
        kennung = urllib.parse.quote(calendar_id, safe="")
        antwort = self._call(
            "GET",
            f"/calendars/{kennung}/events",
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": max(1, min(limit, 250)),
            },
        )
        return list(antwort.get("items") or [])
