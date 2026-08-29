"""Gmail: Anmeldung und die fuenf Aufrufe, die JARVIS braucht.

Der Zustimmungsablauf laeuft ueber Googles eigene Bibliothek -- OAuth mit
Token-Erneuerung selbst zu bauen ist eine der Stellen, an denen man still und
falsch liegt. Die API-Aufrufe dagegen macht `urllib`: es sind fuenf Endpunkte,
sie stehen sichtbar im Code, und genau deshalb lassen sie sich einschraenken.

Das ist der Punkt der Allowlist unten. Die Zustimmung umfasst laut Vorgabe auch
`gmail.send`, der Token koennte also senden. In Phase 2 soll er das nicht, und
"wir rufen die Stelle einfach nicht auf" ist eine Zusage, die ein Tippfehler
brechen kann. `_call` prueft jeden Pfad gegen die Liste; `/messages/send` steht
nicht darauf und ist damit nicht erreichbar, auch nicht versehentlich.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from jarvis.core.secrets import SecretsError, SecretStore

__all__ = ["GMAIL_SCOPES", "GmailAuth", "GmailAuthError", "GmailClient", "GmailError"]

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]

API_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"

# Was JARVIS in dieser Phase aufrufen darf. Alles andere -- allen voran
# /messages/send -- ist nicht vorgesehen und wird abgewiesen.
ALLOWED_ENDPOINTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GET", re.compile(r"^/profile$")),
    ("GET", re.compile(r"^/messages$")),
    ("GET", re.compile(r"^/messages/[A-Za-z0-9_-]+$")),
    ("POST", re.compile(r"^/messages/[A-Za-z0-9_-]+/modify$")),
    ("GET", re.compile(r"^/labels$")),
    ("POST", re.compile(r"^/labels$")),
)


class GmailError(RuntimeError):
    """Gmail hat nicht wie erwartet geantwortet."""


class GmailAuthError(GmailError):
    """Nicht angemeldet, oder die Anmeldung ist abgelaufen."""


class GmailAuth:
    """Haelt die Zugangsdaten. Schreibt nie eine Datei."""

    def __init__(
        self,
        secrets: SecretStore,
        *,
        client_secret_name: str = "gmail_client_secret",
        token_name: str = "gmail_token",
    ) -> None:
        self._secrets = secrets
        self._client_secret_name = client_secret_name
        self._token_name = token_name
        self._cached: Any = None

    def configured(self) -> bool:
        return self._secrets.has(self._token_name)

    def login(self, *, port: int = 0) -> None:
        """Fuehrt den Zustimmungsablauf durch und legt den Token ab.

        Braucht einen Browser und einen beschreibbaren Speicher, laeuft also
        nur auf dem Zielrechner.
        """
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:  # pragma: no cover
            raise GmailAuthError("Paket 'google-auth-oauthlib' fehlt (uv sync)") from exc

        try:
            roh = self._secrets.require(self._client_secret_name)
        except SecretsError as exc:
            raise GmailAuthError(
                f"Die Zugangsdaten des Desktop-Clients fehlen. Lade client_secret.json "
                f"in der Google Cloud Console herunter und lege sie ab mit:\n"
                f"  security add-generic-password -s jarvis -a {self._client_secret_name} -w"
            ) from exc

        try:
            config = json.loads(roh)
        except json.JSONDecodeError as exc:
            raise GmailAuthError(
                f"{self._client_secret_name}: kein gueltiges JSON aus der Cloud Console"
            ) from exc

        flow = InstalledAppFlow.from_client_config(config, GMAIL_SCOPES)
        credentials = flow.run_local_server(port=port)
        self._secrets.store(self._token_name, credentials.to_json())
        self._cached = credentials

    def credentials(self) -> Any:
        """Laedt den Token und erneuert ihn bei Bedarf."""
        if self._cached is not None and getattr(self._cached, "valid", False):
            return self._cached

        try:
            from google.auth.transport.requests import Request as GoogleRequest
            from google.oauth2.credentials import Credentials
        except ImportError as exc:  # pragma: no cover
            raise GmailAuthError("Paket 'google-auth' fehlt (uv sync)") from exc

        roh = self._secrets.get(self._token_name)
        if not roh:
            raise GmailAuthError("Nicht angemeldet. Erst: jarvis mail login")

        credentials = Credentials.from_authorized_user_info(json.loads(roh), GMAIL_SCOPES)
        if not credentials.valid:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(GoogleRequest())
                self._secrets.store(self._token_name, credentials.to_json())
            else:
                raise GmailAuthError("Anmeldung abgelaufen. Erneut: jarvis mail login")
        self._cached = credentials
        return credentials

    def token(self) -> str:
        return str(self.credentials().token)


class GmailClient:
    def __init__(self, auth: GmailAuth, *, timeout: float = 30.0) -> None:
        self._auth = auth
        self._timeout = timeout
        self._opener = urllib.request.build_opener()

    # ---------------------------------------------------------------- #

    @staticmethod
    def _check_endpoint(method: str, path: str) -> None:
        for erlaubte_methode, muster in ALLOWED_ENDPOINTS:
            if method == erlaubte_methode and muster.match(path):
                return
        raise GmailError(
            f"{method} {path} steht nicht auf der Liste der erlaubten Endpunkte. "
            f"In dieser Phase liest und beschriftet JARVIS nur."
        )

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict:
        self._check_endpoint(method, path)

        url = f"{API_ROOT}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self._auth.token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                inhalt = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise GmailAuthError(f"Gmail lehnt den Zugriff ab (HTTP {exc.code})") from exc
            if exc.code == 429:
                raise GmailError("Gmail drosselt (HTTP 429)") from exc
            raise GmailError(f"Gmail antwortet mit HTTP {exc.code}") from exc
        except TimeoutError as exc:
            raise GmailError("Gmail antwortet nicht rechtzeitig") from exc
        except urllib.error.URLError as exc:
            raise GmailError(f"Gmail nicht erreichbar ({exc.reason})") from exc

        if not inhalt:
            return {}
        try:
            return json.loads(inhalt)
        except json.JSONDecodeError as exc:
            raise GmailError("Gmail liefert unlesbares JSON") from exc

    # ---------------------------------------------------------------- #

    def address(self) -> str:
        """Die eigene Adresse. Der Vorfilter braucht sie, um sich selbst zu erkennen."""
        return str(self._call("GET", "/profile").get("emailAddress", "")).lower()

    def list_message_ids(self, query: str, limit: int) -> list[str]:
        antwort = self._call(
            "GET",
            "/messages",
            params={"q": query, "maxResults": max(1, min(limit, 500))},
        )
        return [str(eintrag["id"]) for eintrag in antwort.get("messages") or []]

    def get_message(self, message_id: str) -> dict:
        return self._call("GET", f"/messages/{message_id}", params={"format": "full"})

    def modify_labels(
        self, message_id: str, *, add: list[str] | None = None, remove: list[str] | None = None
    ) -> dict:
        return self._call(
            "POST",
            f"/messages/{message_id}/modify",
            body={"addLabelIds": add or [], "removeLabelIds": remove or []},
        )

    def list_labels(self) -> list[dict]:
        return list(self._call("GET", "/labels").get("labels") or [])

    def create_label(self, name: str) -> dict:
        return self._call(
            "POST",
            "/labels",
            body={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
