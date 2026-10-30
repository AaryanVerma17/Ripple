"""SQLite persistence for analyses, review decisions and engineer-supplied values.

Decisions are append-only: recording a second decision never erases the first, so the
review history stays auditable.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from .config import settings

_lock = Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
  analysis_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'analysis',
  body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id TEXT NOT NULL,
  decision TEXT NOT NULL,
  reviewer TEXT NOT NULL,
  comments TEXT NOT NULL DEFAULT '',
  recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS overrides (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  entity_id TEXT NOT NULL,
  param TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT NOT NULL,
  source_note TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn():
    path = Path(settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        con = sqlite3.connect(str(path), timeout=10)
        con.row_factory = sqlite3.Row
        try:
            con.executescript(SCHEMA)
            yield con
            con.commit()
        finally:
            con.close()


def save_analysis(report: dict, kind: str = "analysis") -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO analyses (analysis_id, created_at, kind, body) VALUES (?,?,?,?)",
            (report["analysis_id"], report["created_at"], kind, json.dumps(report)),
        )


def _decisions_for(con, analysis_id: str) -> list[dict]:
    rows = con.execute(
        "SELECT decision, reviewer, comments, recorded_at FROM decisions WHERE analysis_id=? ORDER BY id",
        (analysis_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_analysis(analysis_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT body, kind FROM analyses WHERE analysis_id=?", (analysis_id,)).fetchone()
        if not row:
            return None
        report = json.loads(row["body"])
        report["kind"] = row["kind"]
        decisions = _decisions_for(con, analysis_id)
        report["decisions"] = decisions
        report["review_decision"] = decisions[-1] if decisions else None
        return report


def list_analyses(limit: int = 100) -> list[dict]:
    """Compact summaries, newest first."""
    out = []
    with _conn() as con:
        rows = con.execute(
            "SELECT analysis_id, created_at, kind, body FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        for r in rows:
            b = json.loads(r["body"])
            decisions = _decisions_for(con, r["analysis_id"])
            out.append({
                "analysis_id": r["analysis_id"], "created_at": r["created_at"], "kind": r["kind"],
                "change_summary": b.get("change_summary"), "overall_status": b.get("overall_status"),
                "headline": b.get("headline"), "counts": b.get("counts"), "risk": b.get("risk"),
                "review_decision": decisions[-1] if decisions else None, "decision_count": len(decisions),
            })
    return out


def save_decision(analysis_id: str, decision: dict) -> dict:
    record = {"decision": decision["decision"], "reviewer": decision["reviewer"],
              "comments": decision.get("comments", ""), "recorded_at": _now()}
    with _conn() as con:
        con.execute(
            "INSERT INTO decisions (analysis_id, decision, reviewer, comments, recorded_at) VALUES (?,?,?,?,?)",
            (analysis_id, record["decision"], record["reviewer"], record["comments"], record["recorded_at"]),
        )
    return {"analysis_id": analysis_id, **record}


def add_override(entity_id: str, param: str, value: float, unit: str, source_note: str, author: str) -> dict:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO overrides (entity_id, param, value, unit, source_note, author, created_at) VALUES (?,?,?,?,?,?,?)",
            (entity_id, param, value, unit, source_note, author, _now()),
        )
        return {"id": cur.lastrowid, "entity_id": entity_id, "param": param, "value": value, "unit": unit,
                "source_note": source_note, "author": author}


def list_overrides() -> list[dict]:
    """Latest value per (entity, parameter), oldest first."""
    with _conn() as con:
        rows = con.execute("SELECT * FROM overrides ORDER BY id").fetchall()
    latest: dict[tuple[str, str], dict] = {}
    for r in rows:
        latest[(r["entity_id"], r["param"])] = dict(r)
    return sorted(latest.values(), key=lambda x: x["id"])


def clear_overrides() -> int:
    with _conn() as con:
        return con.execute("DELETE FROM overrides").rowcount
