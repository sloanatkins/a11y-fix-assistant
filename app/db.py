"""
Database
========
SQLite storage for scans, suggestions, and my review decisions.

Dependencies:
    - sqlite3 (standard library)
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app import config
from app.scanner import get_level
from app.models import (
    DecisionRequest,
    DecisionResponse,
    FixSuggestion,
    IssueGroup,
    ReviewStatus,
    ScanResponse,
    ScanSummary,
    SuggestionResponse,
    ValidationResult,
)


# ── Connection ──

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    final_url TEXT,
    error TEXT,
    groups_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    group_key TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    occurrences INTEGER NOT NULL,
    model TEXT NOT NULL,
    suggestion_json TEXT NOT NULL,
    validation_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (scan_id, group_key)
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_id INTEGER NOT NULL UNIQUE REFERENCES suggestions(id),
    decision TEXT NOT NULL,
    final_html TEXT,
    reason TEXT,
    seconds_spent REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit if things went fine, and always close it."""
    Path(config.DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(config.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    """Create the tables, and fail any scan that was cut off by a restart."""
    with connect() as db:
        db.executescript(SCHEMA)

        # databases made before browser IDs won't have this column yet
        columns = [row["name"] for row in db.execute("PRAGMA table_info(scans)")]
        if "client_id" not in columns:
            db.execute("ALTER TABLE scans ADD COLUMN client_id TEXT")

        db.execute(
            "UPDATE scans SET status = 'failed', error = 'Server restarted during scan' "
            "WHERE status = 'running'"
        )


# ── Scans ──

def create_scan(url: str, client_id: str) -> int:
    with connect() as db:
        return db.execute(
            "INSERT INTO scans (url, status, client_id) VALUES (?, 'running', ?)",
            (url, client_id),
        ).lastrowid


def scan_belongs_to(scan_id: int, client_id: str) -> bool:
    with connect() as db:
        row = db.execute(
            "SELECT 1 FROM scans WHERE id = ? AND client_id = ?", (scan_id, client_id)
        ).fetchone()
    return row is not None


def complete_scan(scan_id: int, final_url: str, groups: list[IssueGroup]) -> None:
    groups_json = json.dumps([group.model_dump() for group in groups])
    with connect() as db:
        db.execute(
            "UPDATE scans SET status = 'complete', final_url = ?, groups_json = ? WHERE id = ?",
            (final_url, groups_json, scan_id),
        )


def fail_scan(scan_id: int, error: str) -> None:
    with connect() as db:
        db.execute(
            "UPDATE scans SET status = 'failed', error = ? WHERE id = ?",
            (error, scan_id),
        )


def get_scan(scan_id: int) -> ScanResponse | None:
    with connect() as db:
        row = db.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    if row is None:
        return None
    groups = [IssueGroup(**group) for group in json.loads(row["groups_json"])]

    # old scans should follow the current rule levels, not the ones they were saved with
    for group in groups:
        group.level = get_level(group.rule_id)
        group.example.level = group.level

    return ScanResponse(
        id=row["id"],
        url=row["url"],
        status=row["status"],
        final_url=row["final_url"],
        error=row["error"],
        groups=groups,
    )


def adopt_unowned_scans(client_id: str) -> None:
    """Scans from before browser IDs go to the first browser that asks."""
    with connect() as db:
        db.execute("UPDATE scans SET client_id = ? WHERE client_id IS NULL", (client_id,))


def list_scans(client_id: str, limit: int = 20) -> list[ScanSummary]:
    """This browser's newest scans first, for the recent scans list."""
    with connect() as db:
        rows = db.execute(
            "SELECT id, url, status, created_at, groups_json FROM scans "
            "WHERE client_id = ? ORDER BY id DESC LIMIT ?",
            (client_id, limit),
        ).fetchall()
    return [
        ScanSummary(
            id=row["id"],
            url=row["url"],
            status=row["status"],
            created_at=row["created_at"],
            flagged=sum(group["count"] for group in json.loads(row["groups_json"])),
        )
        for row in rows
    ]


# ── Suggestions ──

def _to_suggestion(row: sqlite3.Row) -> SuggestionResponse:
    return SuggestionResponse(
        id=row["id"],
        scan_id=row["scan_id"],
        group_key=row["group_key"],
        model=row["model"],
        suggestion=FixSuggestion(**json.loads(row["suggestion_json"])),
        validation=ValidationResult(**json.loads(row["validation_json"])),
    )


def get_suggestion(scan_id: int, group_key: str) -> SuggestionResponse | None:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM suggestions WHERE scan_id = ? AND group_key = ?",
            (scan_id, group_key),
        ).fetchone()
    return _to_suggestion(row) if row else None


def save_suggestion(
    scan_id: int,
    group: IssueGroup,
    model: str,
    suggestion: FixSuggestion,
    validation: ValidationResult,
) -> SuggestionResponse:
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO suggestions "
            "(scan_id, group_key, rule_id, occurrences, model, suggestion_json, validation_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                scan_id,
                group.key,
                group.rule_id,
                group.count,
                model,
                suggestion.model_dump_json(),
                validation.model_dump_json(),
            ),
        )
    return get_suggestion(scan_id, group.key)


# ── Decisions ──

def suggestion_belongs_to(suggestion_id: int, client_id: str) -> bool:
    with connect() as db:
        row = db.execute(
            "SELECT 1 FROM suggestions s JOIN scans c ON c.id = s.scan_id "
            "WHERE s.id = ? AND c.client_id = ?",
            (suggestion_id, client_id),
        ).fetchone()
    return row is not None


def save_decision(suggestion_id: int, decision: DecisionRequest) -> DecisionResponse:
    """Save my decision. Deciding again on a suggestion replaces the old one."""
    with connect() as db:
        db.execute(
            "INSERT INTO decisions (suggestion_id, decision, final_html, reason, seconds_spent) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (suggestion_id) DO UPDATE SET "
            "decision = excluded.decision, final_html = excluded.final_html, "
            "reason = excluded.reason, seconds_spent = excluded.seconds_spent",
            (
                suggestion_id,
                decision.decision,
                decision.final_html,
                decision.reason,
                decision.seconds_spent,
            ),
        )
        row = db.execute(
            "SELECT * FROM decisions WHERE suggestion_id = ?", (suggestion_id,)
        ).fetchone()
    return DecisionResponse(
        id=row["id"],
        suggestion_id=row["suggestion_id"],
        decision=row["decision"],
        final_html=row["final_html"],
        reason=row["reason"],
        seconds_spent=row["seconds_spent"],
    )


def get_review_statuses(scan_id: int) -> list[ReviewStatus]:
    """Lets the results screen show which groups I've already looked at."""
    with connect() as db:
        rows = db.execute(
            "SELECT s.id, s.group_key, d.decision FROM suggestions s "
            "LEFT JOIN decisions d ON d.suggestion_id = s.id WHERE s.scan_id = ?",
            (scan_id,),
        ).fetchall()
    return [
        ReviewStatus(group_key=r["group_key"], suggestion_id=r["id"], decision=r["decision"])
        for r in rows
    ]


# ── Evaluation ──

def get_evaluation_rows(client_id: str) -> tuple[int, list[sqlite3.Row]]:
    """
    Pull what the evaluation summary needs.

    Returns:
    --------
    Number of scans, plus one row per suggestion with its decision if it has one
    """
    with connect() as db:
        scans = db.execute(
            "SELECT COUNT(*) FROM scans WHERE client_id = ?", (client_id,)
        ).fetchone()[0]
        rows = db.execute(
            "SELECT s.rule_id, s.occurrences, s.validation_json, d.decision "
            "FROM suggestions s JOIN scans c ON c.id = s.scan_id "
            "LEFT JOIN decisions d ON d.suggestion_id = s.id WHERE c.client_id = ?",
            (client_id,),
        ).fetchall()
    return scans, rows
