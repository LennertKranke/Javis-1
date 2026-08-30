"""Der Modellaufruf laeuft in einem eigenen Prozess. Abschnitt 2.2.

Bisher war die Trennung logisch: `Provider.complete()` nimmt Text und gibt
Text, es gibt keinen Parameter fuer Werkzeuge. Das ist gut, aber es ist eine
Eigenschaft des Codes, nicht des Betriebssystems -- ein Fehler im
Auswertungspfad haette im selben Prozess gesteckt wie die Gmail-Zugangsdaten.

Hier wird daraus eine Trennung, die nicht am Wohlverhalten des Codes haengt:

    Elternprozess                    Kindprozess
      Gmail, Kalender, Keychain        nur der eine Modellschluessel
      Datenbank, Gatter, Protokoll     kein JARVIS_HOME, keine Datenbank
      berechnet die Ziele              sieht kein Ziel
            |                                ^
            |  Text + Schema  (stdin)        |
            +------------------------------->+
            |  JSON            (stdout)      |
            +<-------------------------------+

Drei Stufen, ueber `[llm] isolation` einstellbar:

  off         wie bisher, alles im selben Prozess. Schnell, aber 2.2 gilt
              dann nur als Zusage des Codes.
  subprocess  eigener Prozess mit gefilterter Umgebung. Der Standard.
  sandbox     zusaetzlich `sandbox-exec` unter macOS: das Betriebssystem
              verweigert dem Kind den Zugriff auf ~/.jarvis und den
              Schluesselbund.

`StaticProvider` wird nie ausgelagert. Er antwortet mit einer Konstanten,
ohne Netz und ohne den Text auch nur anzusehen -- es gibt dort nichts zu
trennen, und ein Prozessstart je Aufruf waere reine Kosten.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from jarvis.core.config import ProviderConfig
from jarvis.llm.provider import (
    Provider,
    ProviderError,
    ProviderRefused,
    ProviderTimeout,
    ProviderUnavailable,
    Request,
    Response,
)

__all__ = [
    "DURCHGEREICHT",
    "ISOLATION_MODES",
    "SubprocessProvider",
    "child_env",
    "sandbox_available",
    "sandbox_command",
    "sandbox_profile",
]

ISOLATION_MODES = ("off", "subprocess", "sandbox")

#: Umgebungsvariablen, die das Kind braucht, um ueberhaupt ins Netz zu kommen.
#: Alles andere bleibt draussen -- insbesondere alles, was mit JARVIS_ beginnt.
DURCHGEREICHT = (
    "PATH",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
)

_FEHLERARTEN: dict[str, type[ProviderError]] = {
    "unavailable": ProviderUnavailable,
    "timeout": ProviderTimeout,
    "refused": ProviderRefused,
    "error": ProviderError,
}


def child_env(*, home: str) -> dict[str, str]:
    """Die Umgebung des Kindes: eine Allowlist, kein Filter.

    Eine Sperrliste waere die falsche Richtung -- man vergisst darin immer
    etwas. Was nicht ausdruecklich genannt ist, kommt nicht mit. `HOME` zeigt
    auf ein leeres Verzeichnis: dort steht kein `.jarvis`, in das jemand
    hineinsehen koennte.
    """
    umgebung = {name: os.environ[name] for name in DURCHGEREICHT if name in os.environ}
    umgebung["HOME"] = home
    umgebung["PYTHONNOUSERSITE"] = "1"  # kein ~/.local als Einfallstor
    return umgebung


def sandbox_available() -> bool:
    return sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists()


def sandbox_profile(*, schreibbar: str) -> str:
    """Ein `sandbox-exec`-Profil: alles verboten, wenig erlaubt.

    Netz bleibt offen -- das Kind muss den Anbieter erreichen, das ist seine
    einzige Aufgabe. Verboten ist der Rest: das Basisverzeichnis von JARVIS,
    der Schluesselbund, fremde Prozesse. Selbst wenn im Kind etwas schiefgeht,
    kommt es an die Mails nicht heran.
    """
    return f"""(version 1)
(deny default)
(allow process-exec process-fork)
(allow sysctl-read)
(allow mach-lookup)
(allow network-outbound)
(allow file-read* file-write*
  (subpath "{schreibbar}")
  (subpath "/private/var/folders")
  (literal "/dev/null")
  (literal "/dev/urandom"))
(allow file-read*
  (subpath "/usr")
  (subpath "/System")
  (subpath "/Library/Frameworks")
  (subpath "/opt/homebrew")
  (subpath "/private/etc/ssl"))
(deny file-read* (subpath "{Path.home() / ".jarvis"}"))
(deny file-read* (subpath "{Path.home() / "Library" / "Keychains"}"))
(deny file-read* (subpath "/Library/Keychains"))
"""


def sandbox_command(befehl: list[str], *, schreibbar: str) -> list[str]:
    return ["/usr/bin/sandbox-exec", "-p", sandbox_profile(schreibbar=schreibbar), *befehl]


@dataclass
class _Ergebnis:
    ok: bool
    daten: dict


class SubprocessProvider(Provider):
    """Ein Anbieter, dessen Aufruf woanders stattfindet.

    Nach aussen genau ein `Provider` -- der Router merkt nichts davon, und
    die Vertraulichkeitssperre greift unveraendert, weil `local` und `name`
    aus derselben Konfiguration kommen.
    """

    def __init__(
        self,
        config: ProviderConfig,
        *,
        secret: Callable[[], str | None] | str | None = None,
        probe: Callable[[], bool] | None = None,
        mode: str = "subprocess",
        python: str | None = None,
    ) -> None:
        super().__init__(config)
        if mode not in ("subprocess", "sandbox"):
            raise ValueError(f"Unbekannte Trennung: {mode!r}")
        # Traege aufloesen: `jarvis status` baut alle Anbieter und soll dabei
        # nicht den Schluesselbund aufwecken.
        self._secret_of: Callable[[], str | None] = secret if callable(secret) else (lambda: secret)
        self._probe = probe or (lambda: True)
        self._mode = mode
        self._python = python or sys.executable

    @property
    def mode(self) -> str:
        return self._mode

    def available(self) -> bool:
        """Wird im Elternprozess beantwortet.

        Das ist eine Frage nach installierten Paketen und vorhandenen
        Zugangsdaten, kein Modellaufruf: es geht dabei kein Fremdtext durch
        die Haende, also braucht es dafuer keinen eigenen Prozess.
        """
        return self._probe()

    def command(self, *, schreibbar: str) -> list[str]:
        """Der Aufruf als Liste. Ausgelagert, damit er pruefbar ist."""
        befehl = [self._python, "-m", "jarvis.llm.isolated"]
        if self._mode == "sandbox":
            return sandbox_command(befehl, schreibbar=schreibbar)
        return befehl

    def payload(self, request: Request) -> dict:
        """Was hinuebergeht. Nur das, mehr gibt es nicht.

        Der Schluessel liegt in der Eingabe, nicht in der Umgebung und nicht
        in der Kommandozeile -- dort stuende er in `ps`.
        """
        return {
            "provider": {
                "name": self.config.name,
                "kind": self.config.kind,
                "model": self.config.model,
                "local": self.config.local,
                "max_tokens": self.config.max_tokens,
                "timeout": self.config.timeout,
                "secret": self.config.secret,
                "base_url": self.config.base_url,
                "effort": self.config.effort,
                "reply": self.config.reply,
            },
            "secret": self._secret_of(),
            "request": {
                "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                "system": request.system,
                "max_tokens": request.max_tokens,
                "effort": request.effort,
            },
        }

    def complete(self, request: Request) -> Response:
        if self._mode == "sandbox" and not sandbox_available():
            raise ProviderUnavailable(
                "sandbox-exec steht auf diesem System nicht zur Verfuegung "
                "(nur macOS). [llm] isolation auf 'subprocess' setzen."
            )

        # Ein leeres HOME je Aufruf. Danach ist es weg, samt allem, was eine
        # Bibliothek dort abgelegt haette.
        with tempfile.TemporaryDirectory(prefix="jarvis-llm-") as ordner:
            ergebnis = self._starte(request, ordner)

        if ergebnis.ok:
            daten = ergebnis.daten["response"]
            return Response(
                text=str(daten.get("text", "")),
                provider=str(daten.get("provider", self.name)),
                model=str(daten.get("model", self.model)),
                input_tokens=int(daten.get("input_tokens", 0)),
                output_tokens=int(daten.get("output_tokens", 0)),
                latency_ms=int(daten.get("latency_ms", 0)),
                stop_reason=daten.get("stop_reason"),
            )

        art = str(ergebnis.daten.get("kind", "error"))
        fehler = _FEHLERARTEN.get(art, ProviderError)
        raise fehler(str(ergebnis.daten.get("error", "ohne Angabe")))

    def _starte(self, request: Request, ordner: str) -> _Ergebnis:
        eingabe = json.dumps(self.payload(request), ensure_ascii=False)
        # Etwas Luft ueber der Anbieterzeit: der Prozessstart zaehlt mit.
        frist = float(self.config.timeout) + 30.0
        try:
            lauf = subprocess.run(
                self.command(schreibbar=ordner),
                input=eingabe,
                capture_output=True,
                text=True,
                timeout=frist,
                env=child_env(home=ordner),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderTimeout(
                f"Auswertender Prozess antwortet nicht innerhalb von {frist:.0f}s"
            ) from exc
        except OSError as exc:
            raise ProviderUnavailable(
                f"Auswertender Prozess liess sich nicht starten ({exc})"
            ) from exc

        zeile = _letzte_zeile(lauf.stdout)
        if not zeile:
            kurz = (lauf.stderr or "").strip().splitlines()
            raise ProviderError(
                f"Auswertender Prozess ohne Antwort (Code {lauf.returncode}): "
                f"{kurz[-1] if kurz else 'ohne Ausgabe'}"
            )
        try:
            daten = json.loads(zeile)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"Auswertender Prozess liefert unlesbares JSON ({exc})") from exc
        return _Ergebnis(ok=bool(daten.get("ok")), daten=daten)


def _letzte_zeile(text: str) -> str:
    """Die Antwort ist die letzte Zeile.

    Bibliotheken schreiben gelegentlich Warnungen auf die Standardausgabe.
    Das darf die Antwort nicht unlesbar machen.
    """
    for zeile in reversed((text or "").splitlines()):
        if zeile.strip():
            return zeile.strip()
    return ""


@dataclass(frozen=True)
class Sondenlauf:
    """Was die Sonde in einem Lauf erreicht hat."""

    ok: bool
    mode: str
    befunde: dict
    fehler: str | None = None


def sonde_starten(
    *,
    mode: str,
    home: Path | None = None,
    python: str | None = None,
    timeout: float = 60.0,
) -> Sondenlauf:
    """Startet `llm/probe.py` -- ohne oder mit Sandbox -- und liest den Bericht.

    Erst der Vergleich zweier Laeufe zeigt, ob die Sandbox etwas bewirkt. Ein
    einzelner Lauf beweist nichts: dass eine Datei fehlt, kann auch heissen,
    dass es sie gar nicht gibt.
    """
    lauf_python = python or sys.executable
    with tempfile.TemporaryDirectory(prefix="jarvis-probe-") as ordner:
        befehl = [lauf_python, "-m", "jarvis.llm.probe"]
        if home is not None:
            # Als Argument, nicht als Umgebungsvariable: JARVIS_* wird
            # gefiltert, und die Sonde saehe sonst am falschen Ort nach.
            befehl.append(str(home))
        if mode == "sandbox":
            if not sandbox_available():
                return Sondenlauf(
                    ok=False,
                    mode=mode,
                    befunde={},
                    fehler="sandbox-exec steht auf diesem System nicht zur Verfuegung",
                )
            befehl = sandbox_command(befehl, schreibbar=ordner)

        umgebung = child_env(home=ordner) if mode != "geerbt" else dict(os.environ)
        try:
            lauf = subprocess.run(
                befehl,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=umgebung,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return Sondenlauf(ok=False, mode=mode, befunde={}, fehler=str(exc))

        zeile = _letzte_zeile(lauf.stdout)
        if not zeile:
            kurz = (lauf.stderr or "").strip().splitlines()
            return Sondenlauf(
                ok=False,
                mode=mode,
                befunde={},
                fehler=f"kein Bericht (Code {lauf.returncode}): "
                f"{kurz[-1] if kurz else 'ohne Ausgabe'}",
            )
        try:
            return Sondenlauf(ok=True, mode=mode, befunde=json.loads(zeile))
        except json.JSONDecodeError as exc:
            return Sondenlauf(ok=False, mode=mode, befunde={}, fehler=f"unlesbarer Bericht ({exc})")
