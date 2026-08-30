"""Prueft von innen, was der auswertende Prozess tatsaechlich noch kann.

Der Sinn: eine Sandbox, die man nicht nachmisst, ist eine Behauptung. Dieses
Modul laeuft unter demselben Aufruf wie `llm/isolated.py` -- einmal ohne und
einmal mit Sandbox -- und berichtet, was jeweils gelingt. Erst der Vergleich
beider Laeufe zeigt, ob die Sandbox etwas bewirkt.

Es wird nichts geschrieben und nichts veraendert; jeder Versuch ist lesend
oder ein Verbindungsaufbau. Gefundene Inhalte werden nicht ausgegeben, nur ob
der Zugriff gelang -- ein Pruefwerkzeug, das Geheimnisse ausdruckt, waere
selbst das Leck.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

__all__ = ["befunde", "main"]


def _lesen(pfad: Path) -> dict[str, Any]:
    """Gelingt ein Lesezugriff? Der Inhalt wird nie zurueckgegeben."""
    try:
        if pfad.is_dir():
            eintraege = list(pfad.iterdir())
            return {"ok": True, "detail": f"{len(eintraege)} Eintraege sichtbar"}
        with pfad.open("rb") as fh:
            fh.read(1)
        return {"ok": True, "detail": "lesbar"}
    except OSError as exc:
        return {"ok": False, "detail": type(exc).__name__}


def _netz(host: str, port: int, timeout: float = 3.0) -> dict[str, Any]:
    """Darf dieser Prozess ueberhaupt eine Verbindung aufbauen?

    Der Unterschied, auf den es ankommt: ein *abgelehnter* Verbindungsversuch
    beweist, dass der Aufruf erlaubt war -- da hat jemand geantwortet. Eine
    Sandbox verweigert dagegen schon den Systemaufruf. Beides als "geht nicht"
    zu zaehlen waere die Pruefung wertlos.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"ok": True, "detail": "verbunden"}
    except ConnectionRefusedError:
        return {"ok": True, "detail": "erreichbar (Gegenstelle lehnt ab)"}
    except (PermissionError, BlockingIOError) as exc:
        return {"ok": False, "detail": type(exc).__name__}
    except TimeoutError:
        return {"ok": False, "detail": "TimeoutError"}
    except OSError as exc:
        # EPERM/EACCES kommen unter macOS als OSError mit errno durch.
        verweigert = exc.errno in (1, 13, 65)  # EPERM, EACCES, EHOSTUNREACH
        return {
            "ok": not verweigert,
            "detail": f"{type(exc).__name__} errno={exc.errno}",
        }


def _keychain() -> dict[str, Any]:
    """Laesst sich das `security`-Kommando ueberhaupt aufrufen?"""
    programm = "/usr/bin/security"
    if not Path(programm).exists():
        return {"ok": False, "detail": "security nicht vorhanden (kein macOS)"}
    try:
        lauf = subprocess.run(
            [programm, "list-keychains"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except OSError as exc:
        return {"ok": False, "detail": type(exc).__name__}
    return {"ok": lauf.returncode == 0, "detail": f"Rueckgabewert {lauf.returncode}"}


def befunde(*, home: Path | None = None) -> dict[str, Any]:
    """Was dieser Prozess erreicht. `home` nur zum Pruefen ueberschreibbar."""
    basis = home if home is not None else Path.home() / ".jarvis"
    return {
        "platform": sys.platform,
        "pid": os.getpid(),
        "jarvis_env": sorted(k for k in os.environ if k.startswith("JARVIS")),
        "home": os.environ.get("HOME", ""),
        "checks": {
            "jarvis_verzeichnis": _lesen(basis),
            "jarvis_datenbank": _lesen(basis / "state.db"),
            "keychain_verzeichnis": _lesen(Path.home() / "Library" / "Keychains"),
            "keychain_kommando": _keychain(),
            "netz_ausgehend": _netz("127.0.0.1", 1),
            "eigenes_paket": _lesen(Path(__file__)),
        },
    }


def main(argv: list[str] | None = None) -> int:
    """Der zu pruefende Pfad kommt als Argument, nicht aus der Umgebung.

    Unter Trennung zeigt `HOME` auf ein leeres Verzeichnis. Wuerde die Sonde
    von dort aus suchen, faende sie nichts -- und meldete "verweigert", wo in
    Wahrheit nur nichts lag. Die Pruefung haette sich selbst bestaetigt. Ein
    Pfad ist kein Geheimnis und darf in der Kommandozeile stehen.
    """
    argumente = sys.argv[1:] if argv is None else argv
    ziel = Path(argumente[0]) if argumente else None
    print(json.dumps(befunde(home=ziel), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
