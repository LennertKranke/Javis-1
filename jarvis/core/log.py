"""Strukturierte Logs als JSON Lines (Abschnitt 4).

Eine Zeile ist ein JSON-Objekt. Das laesst sich mit `jq` durchsuchen, ohne
Logzeilen zu zerlegen, und es bleibt maschinenlesbar, wenn spaeter das Dashboard
dieselben Daten anzeigen soll.

Das Log ist die Betriebssicht: was lief, wie lange, was schlug fehl. Es ist
nicht das Protokoll aus `audit.py` -- das ist der Nachweis, liegt in SQLite und
laesst sich nicht ueberschreiben. Beides getrennt zu halten ist Absicht.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

__all__ = ["configure", "get_logger"]

_STANDARD = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


class JsonlFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD or key.startswith("_"):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = str(value)
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure(log_dir: Path, *, level: str = "INFO", stderr: bool = False) -> logging.Logger:
    """Richtet den Wurzel-Logger von JARVIS ein.

    Mehrfach aufrufbar. Zeigt ein vorhandener Handler schon auf dieselbe Datei,
    bleibt alles wie es ist; zeigt er woanders hin, wird er ersetzt. Ein
    Modulschalter waere hier falsch: er wuerde beim zweiten Aufruf mit einem
    anderen Verzeichnis stillschweigend beim ersten bleiben.
    """
    logger = logging.getLogger("jarvis")
    log_dir.mkdir(parents=True, exist_ok=True)
    target = str((log_dir / "jarvis.jsonl").resolve())

    for handler in list(logger.handlers):
        if getattr(handler, "_jarvis_target", None) == target:
            logger.setLevel(level)
            return logger
        logger.removeHandler(handler)
        handler.close()

    file_handler = TimedRotatingFileHandler(
        target, when="midnight", backupCount=30, encoding="utf-8", utc=True
    )
    file_handler.setFormatter(JsonlFormatter())
    file_handler._jarvis_target = target  # type: ignore[attr-defined]
    logger.addHandler(file_handler)

    if stderr:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        logger.addHandler(stream)

    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger(name: str = "jarvis") -> logging.Logger:
    return logging.getLogger(name if name.startswith("jarvis") else f"jarvis.{name}")
