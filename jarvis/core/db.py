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

from jarvis.core.files import secure_db, secure_dir

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
    (
        2,
        (
            # Merkt sich, welche Nachricht schon beurteilt wurde. Ohne das
            # klassifiziert jeder Durchlauf dasselbe erneut -- teuer, und das
            # Protokoll waere voller Wiederholungen.
            """
            CREATE TABLE mail_messages (
                message_id  TEXT    PRIMARY KEY,
                thread_id   TEXT,
                first_seen  TEXT    NOT NULL,
                last_seen   TEXT    NOT NULL,
                category    TEXT,
                decided_by  TEXT,
                labelled    INTEGER NOT NULL DEFAULT 0 CHECK (labelled IN (0, 1)),
                audit_id    INTEGER REFERENCES audit_log (id)
            )
            """,
            "CREATE INDEX ix_mail_category ON mail_messages (category)",
            "CREATE INDEX ix_mail_labelled ON mail_messages (labelled)",
        ),
    ),
    (
        3,
        (
            "ALTER TABLE mail_messages ADD COLUMN needs_reply INTEGER NOT NULL DEFAULT 0",
            # Was geantwortet werden soll, was daraus wurde, und der Fingerabdruck
            # dazwischen. Der Fingerabdruck ist der Grund, warum sich Trockenlauf
            # und tatsaechlicher Entwurf spaeter vergleichen lassen.
            """
            CREATE TABLE mail_replies (
                message_id        TEXT    PRIMARY KEY,
                thread_id         TEXT,
                recipient         TEXT    NOT NULL,
                subject           TEXT    NOT NULL,
                fingerprint       TEXT    NOT NULL,
                planned_at        TEXT    NOT NULL,
                disposition       TEXT    NOT NULL,
                needs_human       INTEGER NOT NULL DEFAULT 0,
                draft_id          TEXT,
                drafted_at        TEXT,
                draft_fingerprint TEXT,
                sent_at           TEXT,
                audit_id          INTEGER REFERENCES audit_log (id)
            )
            """,
            "CREATE INDEX ix_replies_disposition ON mail_replies (disposition)",
            # Die Allowlist mit ihrem Beleg: wie oft und wann zuletzt. Ohne den
            # Beleg waere sie eine Liste ohne Begruendung.
            """
            CREATE TABLE mail_allowlist (
                address    TEXT    PRIMARY KEY,
                sent_count INTEGER NOT NULL DEFAULT 0,
                first_seen TEXT,
                last_seen  TEXT,
                source     TEXT    NOT NULL
            )
            """,
            # Genau eine Zeile. Die abgeleiteten Stilmerkmale, nie ein Originaltext.
            """
            CREATE TABLE style_profile (
                id           INTEGER PRIMARY KEY CHECK (id = 1),
                updated_at   TEXT    NOT NULL,
                sample_count INTEGER NOT NULL,
                profile      TEXT    NOT NULL
            )
            """,
        ),
    ),
    (
        4,
        (
            # Anstehende Entscheidungen. Enthaelt beide Haelften der urspruenglichen
            # Entscheidung getrennt, damit sie sich spaeter unveraendert
            # wiederherstellen laesst -- samt der Pruefung, dass in der
            # Modellhaelfte kein Ziel steckt.
            """
            CREATE TABLE approvals (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                skill      TEXT    NOT NULL,
                event_key  TEXT    NOT NULL,
                action     TEXT    NOT NULL,
                reason     TEXT    NOT NULL DEFAULT '',
                decided_by TEXT    NOT NULL DEFAULT '',
                summary    TEXT    NOT NULL DEFAULT '',
                fields     TEXT    NOT NULL DEFAULT '{}',
                targets    TEXT    NOT NULL DEFAULT '{}',
                model      TEXT,
                state      TEXT    NOT NULL DEFAULT 'pending',
                created_at TEXT    NOT NULL,
                settled_at TEXT,
                note       TEXT,
                audit_id   INTEGER REFERENCES audit_log (id)
            )
            """,
            # Ein Vorgang steht hoechstens einmal offen. Ohne das sammeln sich
            # bei jedem Durchlauf neue Kopien derselben Entscheidung.
            """
            CREATE UNIQUE INDEX ux_approvals_offen ON approvals (skill, event_key)
            WHERE state = 'pending'
            """,
            "CREATE INDEX ix_approvals_state ON approvals (state, created_at)",
        ),
    ),
    (
        5,
        (
            # Zustandsmodell statt "steht in der Tabelle, also erledigt".
            #   seen      geholt, noch nicht beurteilt
            #   analysed  beurteilt, aber nichts getan (Trockenlauf, Gatter zu)
            #   acted     tatsaechlich gehandelt
            #   skipped   endgueltig nichts zu tun (eigene Post, schon eingeordnet)
            # Nur acted und skipped schliessen eine Nachricht aus; analysed wird
            # wieder aufgegriffen, sobald wirklich gehandelt werden darf.
            "ALTER TABLE mail_messages ADD COLUMN state TEXT NOT NULL DEFAULT 'seen'",
            "UPDATE mail_messages SET state = 'acted' WHERE labelled = 1",
            "UPDATE mail_messages SET state = 'analysed' "
            "WHERE labelled = 0 AND category IS NOT NULL",
            "CREATE INDEX ix_mail_state ON mail_messages (state)",
            # Langzeitgedaechtnis: wenige, ausdruecklich abgelegte Tatsachen.
            # Keine Gespraechsgeschichte, kein Protokoll.
            """
            CREATE TABLE memory_facts (
                key        TEXT    PRIMARY KEY,
                value      TEXT    NOT NULL,
                category   TEXT    NOT NULL DEFAULT 'sonstiges',
                source     TEXT    NOT NULL DEFAULT '',
                weight     REAL    NOT NULL DEFAULT 1.0,
                created_at TEXT    NOT NULL,
                updated_at TEXT    NOT NULL
            )
            """,
            "CREATE INDEX ix_memory_category ON memory_facts (category, weight)",
            # Kurzzeitkontext: ein knapper, beschnittener Verlauf je Bereich.
            # Waechst nicht unbegrenzt -- aeltere Eintraege fallen heraus.
            """
            CREATE TABLE context_entries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                scope      TEXT    NOT NULL,
                kind       TEXT    NOT NULL,
                text       TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
            """,
            "CREATE INDEX ix_context_scope ON context_entries (scope, id)",
        ),
    ),
    (
        6,
        (
            # Termine. Dasselbe Zustandsmodell wie bei Mail -- ein Trockenlauf
            # darf auch hier nichts verbrennen.
            """
            CREATE TABLE calendar_events (
                event_id    TEXT    PRIMARY KEY,
                calendar_id TEXT    NOT NULL,
                starts_at   TEXT,
                ends_at     TEXT,
                all_day     INTEGER NOT NULL DEFAULT 0,
                summary     TEXT    NOT NULL DEFAULT '',
                state       TEXT    NOT NULL DEFAULT 'seen',
                finding     TEXT,
                first_seen  TEXT    NOT NULL,
                last_seen   TEXT    NOT NULL,
                audit_id    INTEGER REFERENCES audit_log (id)
            )
            """,
            "CREATE INDEX ix_events_start ON calendar_events (starts_at)",
            "CREATE INDEX ix_events_state ON calendar_events (state)",
            # Ein Briefing je Tag. Der Text ist das Ergebnis, die Kennzahlen
            # daneben machen nachvollziehbar, woraus er entstand.
            """
            CREATE TABLE briefings (
                day        TEXT    PRIMARY KEY,
                created_at TEXT    NOT NULL,
                text       TEXT    NOT NULL,
                facts      TEXT    NOT NULL DEFAULT '{}',
                model      TEXT
            )
            """,
        ),
    ),
    (
        7,
        (
            # Rechercheauftraege. Die Frage steht normalisiert darin -- sie kann
            # aus einer Mail stammen und ist damit Fremdtext.
            """
            CREATE TABLE research_questions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                question   TEXT    NOT NULL,
                asked_at   TEXT    NOT NULL,
                state      TEXT    NOT NULL DEFAULT 'seen',
                category   TEXT,
                keywords   TEXT    NOT NULL DEFAULT '',
                origin     TEXT    NOT NULL DEFAULT 'cli',
                audit_id   INTEGER REFERENCES audit_log (id)
            )
            """,
            "CREATE INDEX ix_research_state ON research_questions (state)",
            # Was gefunden wurde. `source` ist der Name einer freigegebenen
            # Quelle, nie eine vom Modell genannte Adresse.
            """
            CREATE TABLE research_findings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL REFERENCES research_questions (id),
                source      TEXT    NOT NULL,
                title       TEXT    NOT NULL DEFAULT '',
                snippet     TEXT    NOT NULL DEFAULT '',
                reference   TEXT    NOT NULL DEFAULT '',
                found_at    TEXT    NOT NULL
            )
            """,
            "CREATE INDEX ix_findings_question ON research_findings (question_id)",
        ),
    ),
    (
        8,
        (
            # SEC-2: `claimed` ist der Zustand zwischen Anspruch und Abschluss
            # einer Freigabe. Er zaehlt als offen: solange eine Ausfuehrung
            # laeuft, darf kein zweiter Vorgang zu derselben Frage entstehen.
            "DROP INDEX ux_approvals_offen",
            """
            CREATE UNIQUE INDEX ux_approvals_offen ON approvals (skill, event_key)
            WHERE state IN ('pending', 'claimed')
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
        secure_dir(Path(path).parent)
    conn = sqlite3.connect(path, isolation_level=None, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = FULL")
    # Erst hier: die WAL-Begleitdateien entstehen mit `journal_mode`, und sie
    # enthalten dieselben Daten wie die Datenbank. Jeder Verbindungsaufbau zieht
    # die Rechte nach, damit auch eine aeltere Ablage geschlossen wird.
    secure_db(path)
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
