"""SQLite-Schema und Migrationen.

Ein einziges Schema, versioniert ueber `PRAGMA user_version`, migriert durch
eine geordnete Liste von Schritten. Kein Alembic: die Migrationen sind hier
wenige, sie sind reines SQL, und eine Abhaengigkeit fuer drei Tabellen waere
nicht zu rechtfertigen.

Zwei Entscheidungen, die spaeter nur schwer nachzuholen waeren: `audit_log`
traegt eine Hash-Kette, und zwei Trigger verbieten UPDATE und DELETE auf dieser
Tabelle. Das Protokoll ist damit auf Datenbankebene anhaengend, nicht nur per
Konvention -- auch ein Fehler im eigenen Code kann es nicht mehr umschreiben.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

__all__ = ["SCHEMA_VERSION", "connect", "migrate", "open_database", "transaction"]

MIGRATIONS: list[tuple[int, tuple[str, ...]]] = [
    (
        1,
        (
            """
            CREATE TABLE audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT    NOT NULL,
                ts_epoch    REAL    NOT NULL,
                capability  TEXT    NOT NULL,
                kind        TEXT    NOT NULL,
                outcome     TEXT    NOT NULL,
                dry_run     INTEGER NOT NULL CHECK (dry_run IN (0, 1)),
                subject     TEXT,
                detail      TEXT    NOT NULL,
                prev_hash   TEXT    NOT NULL,
                entry_hash  TEXT    NOT NULL UNIQUE
            )
            """,
            "CREATE INDEX ix_audit_capability ON audit_log (capability, ts_epoch)",
            "CREATE INDEX ix_audit_kind ON audit_log (kind, ts_epoch)",
            # Das Protokoll ist anhaengend. Wer korrigieren will, schreibt einen
            # neuen Eintrag; alte Zeilen bleiben stehen.
            """
            CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log ist anhaengend: UPDATE nicht erlaubt');
            END
            """,
            """
            CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
            BEGIN
                SELECT RAISE(ABORT, 'audit_log ist anhaengend: DELETE nicht erlaubt');
            END
            """,
            """
            CREATE TABLE rate_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                capability TEXT    NOT NULL,
                ts_epoch   REAL    NOT NULL,
                audit_id   INTEGER REFERENCES audit_log (id)
            )
            """,
            "CREATE INDEX ix_rate_capability ON rate_events (capability, ts_epoch)",
            """
            CREATE TABLE meta (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """,
        ),
    ),
]

SCHEMA_VERSION = MIGRATIONS[-1][0]


def connect(path: Path | str) -> sqlite3.Connection:
    """Oeffnet die Datenbank mit den Einstellungen, die JARVIS ueberall erwartet.

    `isolation_level=None` schaltet die implizite Transaktionssteuerung von
    Python ab. Protokoll und Ratenbegrenzung brauchen `BEGIN IMMEDIATE`, um
    zwischen mehreren Prozessen korrekt zu bleiben; das geht nur, wenn niemand
    sonst heimlich Transaktionen oeffnet.
    """
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Schreibtransaktion mit sofortiger Sperre.

    `BEGIN IMMEDIATE` nimmt die Schreibsperre schon beim Start, nicht erst beim
    ersten Schreibbefehl. Ohne das koennten zwei Prozesse gleichzeitig den
    Zaehler lesen und beide unter der Obergrenze landen.
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> int:
    """Bringt die Datenbank auf `SCHEMA_VERSION`. Gibt die neue Version zurueck."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, statements in MIGRATIONS:
        if version <= current:
            continue
        with transaction(conn):
            for statement in statements:
                conn.execute(statement)
            # PRAGMA vertraegt keine Parameterbindung.
            conn.execute(f"PRAGMA user_version = {int(version)}")
        current = version
    return current


def open_database(path: Path | str) -> sqlite3.Connection:
    """Oeffnet und migriert in einem Schritt. Der uebliche Einstieg."""
    conn = connect(path)
    migrate(conn)
    return conn
