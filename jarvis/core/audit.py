"""Protokoll jeder Entscheidung und jeder Aktion (Prinzip 2.4).

Jeder Eintrag traegt den Hash seines Vorgaengers. Wer eine Zeile nachtraeglich
aendert oder entfernt, bricht die Kette, und `verify()` nennt die erste Stelle,
an der es nicht mehr passt. Das ersetzt keine Sicherung, aber es macht den
Unterschied zwischen "das Protokoll sagt nichts" und "das Protokoll wurde
angefasst" sichtbar.

`kind` trennt drei Arten von Eintraegen sauber voneinander:
  decision  was das Modell vorgeschlagen hat
  action    was tatsaechlich nach aussen ging (oder im Trockenlauf gegangen waere)
  system    Zustandswechsel: Stopp, Freigabe, Start
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from jarvis.core.db import transaction

__all__ = ["GENESIS_HASH", "AuditEntry", "AuditLog", "ChainCheck"]

GENESIS_HASH = "0" * 64

KIND_DECISION = "decision"
KIND_ACTION = "action"
KIND_SYSTEM = "system"
KINDS = frozenset({KIND_DECISION, KIND_ACTION, KIND_SYSTEM})

# Schutz gegen versehentlich mitprotokollierten Fremdtext. Das Protokoll ist
# ein Nachweis, kein Zwischenspeicher fuer E-Mail-Inhalte.
MAX_DETAIL_STRING = 2000
MAX_DETAIL_JSON = 8000


@dataclass(frozen=True)
class AuditEntry:
    id: int
    ts: str
    ts_epoch: float
    capability: str
    kind: str
    outcome: str
    dry_run: bool
    subject: str | None
    detail: dict[str, Any]
    prev_hash: str
    entry_hash: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> AuditEntry:
        return cls(
            id=row["id"],
            ts=row["ts"],
            ts_epoch=row["ts_epoch"],
            capability=row["capability"],
            kind=row["kind"],
            outcome=row["outcome"],
            dry_run=bool(row["dry_run"]),
            subject=row["subject"],
            detail=json.loads(row["detail"]),
            prev_hash=row["prev_hash"],
            entry_hash=row["entry_hash"],
        )


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    checked: int
    broken_at: int | None = None
    message: str = ""


def _canonical(payload: dict[str, Any]) -> str:
    """Eine Darstellung, die sich nicht aendert, solange der Inhalt gleich bleibt."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
    material = f"{prev_hash}\n{_canonical(payload)}".encode()
    return hashlib.sha256(material).hexdigest()


def _trim(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_DETAIL_STRING]
    if isinstance(value, dict):
        return {str(k): _trim(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_trim(v) for v in value[:50]]
    if isinstance(value, int | float | bool) or value is None:
        return value
    return str(value)[:MAX_DETAIL_STRING]


class AuditLog:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def record(
        self,
        *,
        capability: str,
        kind: str,
        outcome: str,
        subject: str | None = None,
        detail: dict[str, Any] | None = None,
        dry_run: bool = False,
    ) -> AuditEntry:
        if kind not in KINDS:
            raise ValueError(f"Unbekannte Eintragsart: {kind!r}")
        trimmed = _trim(detail or {})
        encoded = _canonical(trimmed)
        if len(encoded) > MAX_DETAIL_JSON:
            trimmed = {"gekuerzt": True, "laenge": len(encoded)}
            encoded = _canonical(trimmed)

        now = datetime.now(UTC)
        payload = {
            "ts": now.isoformat(timespec="microseconds"),
            "capability": capability,
            "kind": kind,
            "outcome": outcome,
            "dry_run": bool(dry_run),
            "subject": subject,
            "detail": trimmed,
        }
        # Lesen des letzten Hashes und Schreiben des neuen muessen in derselben
        # Transaktion liegen, sonst haengen zwei Eintraege am selben Vorgaenger.
        with transaction(self._conn):
            row = self._conn.execute(
                "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = row["entry_hash"] if row else GENESIS_HASH
            entry_hash = compute_hash(prev_hash, payload)
            cur = self._conn.execute(
                """
                INSERT INTO audit_log
                    (ts, ts_epoch, capability, kind, outcome, dry_run, subject,
                     detail, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["ts"],
                    now.timestamp(),
                    capability,
                    kind,
                    outcome,
                    int(bool(dry_run)),
                    subject,
                    encoded,
                    prev_hash,
                    entry_hash,
                ),
            )
            entry_id = int(cur.lastrowid or 0)

        return AuditEntry(
            id=entry_id,
            ts=str(payload["ts"]),
            ts_epoch=now.timestamp(),
            capability=capability,
            kind=kind,
            outcome=outcome,
            dry_run=bool(dry_run),
            subject=subject,
            detail=trimmed,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )

    def last(self) -> AuditEntry | None:
        row = self._conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        return AuditEntry.from_row(row) if row else None

    def recent(self, limit: int = 20, *, capability: str | None = None) -> list[AuditEntry]:
        if capability:
            rows = self._conn.execute(
                "SELECT * FROM audit_log WHERE capability = ? ORDER BY id DESC LIMIT ?",
                (capability, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [AuditEntry.from_row(row) for row in rows]

    def count(self, *, capability: str | None = None, kind: str | None = None) -> int:
        clauses, params = [], []
        if capability:
            clauses.append("capability = ?")
            params.append(capability)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        row = self._conn.execute(f"SELECT COUNT(*) FROM audit_log{where}", params).fetchone()
        return int(row[0])

    def verify(self) -> ChainCheck:
        """Laeuft die Kette vom Anfang durch und prueft jeden Hash neu."""
        prev_hash = GENESIS_HASH
        checked = 0
        for row in self._conn.execute("SELECT * FROM audit_log ORDER BY id ASC"):
            if row["prev_hash"] != prev_hash:
                return ChainCheck(
                    ok=False,
                    checked=checked,
                    broken_at=row["id"],
                    message=f"Eintrag {row['id']}: Vorgaengerhash passt nicht",
                )
            payload = {
                "ts": row["ts"],
                "capability": row["capability"],
                "kind": row["kind"],
                "outcome": row["outcome"],
                "dry_run": bool(row["dry_run"]),
                "subject": row["subject"],
                "detail": json.loads(row["detail"]),
            }
            expected = compute_hash(prev_hash, payload)
            if expected != row["entry_hash"]:
                return ChainCheck(
                    ok=False,
                    checked=checked,
                    broken_at=row["id"],
                    message=f"Eintrag {row['id']}: Inhalt stimmt nicht mit dem Hash ueberein",
                )
            prev_hash = row["entry_hash"]
            checked += 1
        return ChainCheck(ok=True, checked=checked, message="Kette intakt")
