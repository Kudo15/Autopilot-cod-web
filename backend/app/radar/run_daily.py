"""One-shot Daily Radar runner cho Windows Task Scheduler (s2-windows-scheduler).

Chạy bằng::

    uv run python -m backend.app.radar.run_daily

Hợp đồng:
- Một lần chạy rồi thoát: migration idempotent, mở database cục bộ đã cấu hình
  (hoặc override ``--db-path``), gọi ``run_daily_radar_once`` ĐÚNG MỘT LẦN với
  thời điểm hiện tại thực và owner tất định (``DEFAULT_OWNER``).
- In MỘT DÒNG status JSON không secret rồi thoát: exit 0 = job diễn ra đúng hợp
  đồng (kể cả ``not_due`` / ``already_completed``), exit khác 0 = thất bại bất
  ngờ của job (``run_daily_radar_once`` re-raise sau khi đã ghi FAILED vào ledger
  bền — bounded retry theo hợp đồng s1).
- Không bao giờ: gọi mạng, mở socket, chạy server, mở thread, publish nội dung,
  in giá trị biến môi trường hay nội dung database.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from backend.app import database, migrate
from backend.app.radar import scheduler
from backend.app.radar.daily import WINDOWS

#: Owner tất định cho job Task Scheduler — ổn định qua mọi lần chạy cùng task.
DEFAULT_OWNER = "windows-task:radar-daily"
DEFAULT_WINDOW = "today"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.app.radar.run_daily",
        description=(
            "One-shot Daily Radar runner (local SQLite only: no network, "
            "no server, no publish). Exit 0 = job per contract; exit 1 = job failed."
        ),
    )
    parser.add_argument(
        "--db-path",
        default=None,
        help="Override the configured SQLite path (default: backend/data/radar.db).",
    )
    parser.add_argument(
        "--window",
        default=DEFAULT_WINDOW,
        choices=list(WINDOWS),
        help="Radar window (default: %(default)s).",
    )
    parser.add_argument(
        "--owner",
        default=DEFAULT_OWNER,
        help="Deterministic lease owner for this job (default: %(default)s).",
    )
    return parser


@contextmanager
def _override_db_path(db_path: Path):
    """Trỏ đường dẫn DB cấu hình sang ``db_path`` chỉ trong scope (restore khi xong)."""
    previous = (database.DATA_DIR, database.DB_PATH, migrate.DATA_DIR, migrate.DB_PATH)
    try:
        database.DATA_DIR = db_path.parent
        database.DB_PATH = db_path
        migrate.DATA_DIR = db_path.parent
        migrate.DB_PATH = db_path
        yield
    finally:
        database.DATA_DIR, database.DB_PATH, migrate.DATA_DIR, migrate.DB_PATH = previous


@contextmanager
def _connection(db_path: str | Path | None):
    """Migration idempotent rồi mở connection (đóng sạch khi xong)."""
    if db_path is None:
        migrate.apply_migration()
        conn = database.get_connection()
    else:
        target = Path(db_path)
        with _override_db_path(target):
            migrate.apply_migration()
            conn = database.get_connection()
    try:
        yield conn
    finally:
        conn.close()


def run_job(
    *,
    db_path: str | Path | None = None,
    window: str = DEFAULT_WINDOW,
    owner: str = DEFAULT_OWNER,
    now: datetime | None = None,
) -> dict:
    """Chạy Daily Radar đúng một lần; trả status dict không secret (không in).

    ``now=None`` dùng thời điểm hiện tại thực (aware UTC) — tham số này tồn tại
    để test có đồng hồ giả; CLI không bao giờ truyền.
    """
    try:
        moment = now if now is not None else datetime.now(timezone.utc)
        with _connection(db_path) as conn:
            result = scheduler.run_daily_radar_once(
                conn, owner=owner, now=moment, window=window
            )
    except Exception as exc:  # Thất bại bất ngờ của job -> FAILED, không crash.
        return {
            "status": "FAILED",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}"[:500],
        }
    status = {
        "status": "OK",
        "ok": True,
        "ran": bool(result.get("ran")),
        "reason": result.get("reason"),
        "run_identity": result.get("run_identity"),
    }
    radar = result.get("radar")
    if isinstance(radar, dict):
        # Chỉ lấy trạng thái + số lượng (đang được expose ở API public) —
        # không in nội dung bài viết/sự kiện.
        status["radar_status"] = radar.get("status")
        status["counts"] = radar.get("counts")
    return status


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    status = run_job(
        db_path=args.db_path,
        window=args.window,
        owner=args.owner,
    )
    print(json.dumps(status, ensure_ascii=False, sort_keys=True))
    return 0 if status.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
