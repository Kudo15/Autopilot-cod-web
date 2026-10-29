"""Durable, process-safe Daily Radar schedule ledger.

The scheduler is deliberately request-driven: it owns only a SQLite lease and
local ``daily_radar`` recomputation. It never starts threads, opens sockets, or
publishes/verifies application data.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone, tzinfo

from .daily import REFRESH_HOUR_LOCAL, daily_radar, local_timezone

RUNNING = "RUNNING"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
EXHAUSTED = "EXHAUSTED"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return _aware(value).astimezone(timezone.utc).isoformat()


def run_identity_for(now: datetime, *, tz: tzinfo | None = None) -> str:
    return _aware(now).astimezone(tz or local_timezone()).date().isoformat()


def _due(now: datetime, tz: tzinfo | None = None) -> bool:
    local = _aware(now).astimezone(tz or local_timezone())
    return (local.hour, local.minute, local.second, local.microsecond) >= (REFRESH_HOUR_LOCAL, 0, 0, 0)


def is_due_local(now: datetime, *, tz: tzinfo | None = None) -> bool:
    """Public testable due predicate for the 07:00 local boundary."""
    return _due(now, tz=tz)


def get_schedule_snapshot(conn: sqlite3.Connection, now: datetime, *, tz: tzinfo | None = None) -> dict:
    """Return a small durable schedule projection for API responses."""
    ensure_ledger(conn)
    zone = tz or local_timezone()
    identity = run_identity_for(now, tz=zone)
    row = conn.execute(
        "SELECT status, attempts, completed_at, lease_expires_at FROM radar_schedule_runs WHERE run_identity = ?",
        (identity,),
    ).fetchone()
    local = _aware(now).astimezone(zone)
    scheduled = local.replace(hour=REFRESH_HOUR_LOCAL, minute=0, second=0, microsecond=0)
    if local >= scheduled:
        scheduled += timedelta(days=1)
    return {
        "run_identity": identity,
        "status": row["status"] if row else None,
        "attempts": row["attempts"] if row else 0,
        "completed_at": row["completed_at"] if row else None,
        "lease_expires_at": row["lease_expires_at"] if row else None,
        "due": _due(now, tz=zone),
        "next_local_run": scheduled.isoformat(),
    }


def ensure_ledger(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS radar_schedule_runs (
        run_identity TEXT PRIMARY KEY,
        status TEXT NOT NULL CHECK (status IN ('RUNNING','COMPLETED','FAILED','EXHAUSTED')),
        owner TEXT, attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
        claimed_at TEXT, lease_expires_at TEXT, completed_at TEXT, last_error TEXT,
        summary TEXT, data_origin TEXT NOT NULL DEFAULT 'REAL' CHECK (data_origin IN ('REAL','SAMPLE'))
    )""")
    conn.commit()


def claim_run(conn: sqlite3.Connection, identity: str, owner: str, now: datetime,
              *, lease_seconds: int = 300, max_attempts: int = 3) -> dict:
    now = _aware(now)
    stamp = _iso(now)
    expires = _iso(now + timedelta(seconds=lease_seconds))
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT * FROM radar_schedule_runs WHERE run_identity = ?", (identity,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO radar_schedule_runs (run_identity,status,owner,attempts,claimed_at,lease_expires_at) VALUES (?, ?, ?, 1, ?, ?)", (identity, RUNNING, owner, stamp, expires))
            conn.commit()
            return {"claimed": True, "reason": "new", "run_identity": identity}
        status = row["status"]
        if status == COMPLETED:
            conn.rollback(); return {"claimed": False, "reason": "already_completed", "run_identity": identity}
        attempts = int(row["attempts"] or 0)
        if attempts >= max_attempts and status in {FAILED, EXHAUSTED}:
            if status != EXHAUSTED:
                conn.execute("UPDATE radar_schedule_runs SET status = ? WHERE run_identity = ?", (EXHAUSTED, identity))
                conn.commit()
            else:
                conn.rollback()
            return {"claimed": False, "reason": "attempts_exhausted", "run_identity": identity}
        lease = row["lease_expires_at"]
        if status == RUNNING and lease:
            try:
                if datetime.fromisoformat(lease) > now.astimezone(timezone.utc):
                    conn.rollback(); return {"claimed": False, "reason": "active_lease", "run_identity": identity}
            except ValueError:
                pass
        next_attempt = attempts + 1
        if next_attempt > max_attempts:
            conn.execute("UPDATE radar_schedule_runs SET status = ? WHERE run_identity = ?", (EXHAUSTED, identity)); conn.commit()
            return {"claimed": False, "reason": "attempts_exhausted", "run_identity": identity}
        reason = "reclaimed" if row["status"] in {RUNNING, FAILED} else "new"
        conn.execute("UPDATE radar_schedule_runs SET status=?, owner=?, attempts=?, claimed_at=?, lease_expires_at=?, last_error=NULL WHERE run_identity=?", (RUNNING, owner, next_attempt, stamp, expires, identity))
        conn.commit()
        return {"claimed": True, "reason": reason, "run_identity": identity}
    except Exception:
        conn.rollback()
        raise


def complete_run(conn: sqlite3.Connection, identity: str, owner: str, now: datetime, *, summary: str | None = None) -> dict:
    row = conn.execute("SELECT status, owner FROM radar_schedule_runs WHERE run_identity = ?", (identity,)).fetchone()
    if row is None or row["status"] != RUNNING or row["owner"] != owner:
        return {"completed": False, "run_identity": identity}
    conn.execute("UPDATE radar_schedule_runs SET status=?, completed_at=?, summary=?, lease_expires_at=NULL WHERE run_identity=? AND status=? AND owner=?", (COMPLETED, _iso(now), summary, identity, RUNNING, owner))
    conn.commit()
    return {"completed": True, "run_identity": identity, "status": COMPLETED}


def fail_run(conn: sqlite3.Connection, identity: str, owner: str, now: datetime, *, error: str, max_attempts: int = 3) -> dict:
    row = conn.execute("SELECT status, owner, attempts FROM radar_schedule_runs WHERE run_identity = ?", (identity,)).fetchone()
    if row is None or row["status"] != RUNNING or row["owner"] != owner:
        return {"failed": False, "run_identity": identity}
    status = EXHAUSTED if int(row["attempts"] or 0) >= max_attempts else FAILED
    conn.execute("UPDATE radar_schedule_runs SET status=?, last_error=?, lease_expires_at=NULL WHERE run_identity=? AND owner=?", (status, str(error)[:1000], identity, owner))
    conn.commit()
    return {"failed": True, "run_identity": identity, "status": status}


def run_daily_radar_once(conn: sqlite3.Connection, *, owner: str, now: datetime, window: str = "today", tz: tzinfo | None = None, lease_seconds: int = 300, max_attempts: int = 3) -> dict:
    identity = run_identity_for(now, tz=tz)
    if not _due(now, tz=tz):
        return {"ran": False, "reason": "not_due", "run_identity": identity}
    ensure_ledger(conn)
    claim = claim_run(conn, identity, owner, now, lease_seconds=lease_seconds, max_attempts=max_attempts)
    if not claim["claimed"]:
        return {"ran": False, "reason": claim["reason"], "run_identity": identity}
    try:
        radar = daily_radar(conn, window=window, now=now, tz=tz)
        complete_run(conn, identity, owner, now, summary=f"window={window};status={radar.get('status')}")
        return {"ran": True, "reason": "completed", "run_identity": identity, "radar": radar}
    except Exception as error:
        fail_run(conn, identity, owner, now, error=str(error), max_attempts=max_attempts)
        raise
