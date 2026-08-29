"""Datenbank, Migrationen und die Hash-Kette des Protokolls."""

from __future__ import annotations

import sqlite3

import pytest

from jarvis.core.audit import GENESIS_HASH, AuditLog
from jarvis.core.db import SCHEMA_VERSION, connect, migrate, open_database


def test_migration_legt_das_schema_an(home):
    conn = open_database(home / "state.db")
    tabellen = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"audit_log", "rate_events", "meta"} <= tabellen
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    conn.close()


def test_migration_ist_wiederholbar(home):
    conn = connect(home / "state.db")
    assert migrate(conn) == SCHEMA_VERSION
    assert migrate(conn) == SCHEMA_VERSION
    conn.close()


def test_protokoll_laesst_sich_nicht_aendern(conn):
    """Anhaengend auf Datenbankebene, nicht nur per Konvention."""
    audit = AuditLog(conn)
    audit.record(capability="mail", kind="action", outcome="act")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE audit_log SET outcome = 'blocked' WHERE id = 1")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM audit_log WHERE id = 1")


def test_kette_beginnt_am_ursprung(conn):
    entry = AuditLog(conn).record(capability="mail", kind="system", outcome="start")
    assert entry.prev_hash == GENESIS_HASH


def test_jeder_eintrag_haengt_am_vorigen(conn):
    audit = AuditLog(conn)
    erst = audit.record(capability="mail", kind="action", outcome="act")
    zweit = audit.record(capability="mail", kind="action", outcome="act")
    assert zweit.prev_hash == erst.entry_hash
    assert audit.verify().ok


def test_verify_zaehlt_die_geprueften_eintraege(conn):
    audit = AuditLog(conn)
    for _ in range(5):
        audit.record(capability="mail", kind="decision", outcome="ok")
    check = audit.verify()
    assert check.ok and check.checked == 5


def test_leeres_protokoll_ist_intakt(conn):
    assert AuditLog(conn).verify().ok


def test_verify_entdeckt_eine_veraenderte_zeile(conn):
    """Wer die Trigger entfernt, kommt an der Kette trotzdem nicht vorbei."""
    audit = AuditLog(conn)
    for _ in range(3):
        audit.record(capability="mail", kind="action", outcome="act")

    conn.execute("DROP TRIGGER audit_log_no_update")
    conn.execute("UPDATE audit_log SET outcome = 'blocked' WHERE id = 2")

    check = audit.verify()
    assert not check.ok
    assert check.broken_at == 2
    assert check.checked == 1


def test_verify_entdeckt_eine_geloeschte_zeile(conn):
    audit = AuditLog(conn)
    for _ in range(3):
        audit.record(capability="mail", kind="action", outcome="act")

    conn.execute("DROP TRIGGER audit_log_no_delete")
    conn.execute("DELETE FROM audit_log WHERE id = 2")

    check = audit.verify()
    assert not check.ok
    assert check.broken_at == 3


def test_unbekannte_eintragsart_wird_abgelehnt(conn):
    with pytest.raises(ValueError):
        AuditLog(conn).record(capability="mail", kind="geplauder", outcome="ok")


def test_langer_fremdtext_wird_gekuerzt(conn):
    """Das Protokoll ist ein Nachweis, kein Zwischenspeicher fuer E-Mails."""
    entry = AuditLog(conn).record(
        capability="mail", kind="decision", outcome="ok", detail={"text": "x" * 50_000}
    )
    assert len(entry.detail["text"]) <= 2000
    assert AuditLog(conn).verify().ok


def test_filter_nach_faehigkeit(conn):
    audit = AuditLog(conn)
    audit.record(capability="mail", kind="action", outcome="act")
    audit.record(capability="calendar", kind="action", outcome="act")
    assert len(audit.recent(10, capability="mail")) == 1
    assert audit.count(capability="calendar") == 1
    assert audit.count(kind="action") == 2
