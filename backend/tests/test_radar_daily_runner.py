"""TDD — one-shot Daily Radar runner + Task Scheduler registration (s2-windows-scheduler).

Hợp đồng:
- Runner (``backend.app.radar.run_daily``) mở database cục bộ đã cấu hình
  (hoặc override ``--db-path``), gọi ``run_daily_radar_once`` ĐÚNG MỘT LẦN với
  thời điểm hiện tại thực và owner tất định, in status JSON không secret,
  exit khác 0 khi job thất bại bất ngờ.
- Không mạng (socket bị chặn), không server, không thread, không publish.
- Failure của job (exception từ ``run_daily_radar_once``) phải được truyền thành
  exit code != 0, và ledger bền ghi FAILED (bounded retry theo hợp đồng s1).
- Script ``scripts/register_radar_task.ps1``: đăng ký idempotent task per-user
  ``VuHocAIRadar-Daily`` (daily 07:00, đường dẫn repo tuyệt đối + uv), có chế độ
  query/status, KHÔNG BAO GIỜ unregister/xoá task, không remote, không 0.0.0.0.

Tất cả test chạy trên SQLite tạm — không đụng backend/data/radar.db,
không đăng/xoá Task Scheduler thật.
"""
from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from backend.app.radar import run_daily, scheduler

ROOT = Path(__file__).resolve().parents[2]

#: Múi giờ cố định UTC+7 (Việt Nam không DST) — test tất định.
VN = timezone(timedelta(hours=7))
IDENTITY = "2026-10-25"
BEFORE_DUE = datetime(2026, 10, 25, 6, 59, 59, tzinfo=VN)
DUE = datetime(2026, 10, 25, 7, 30, 0, tzinfo=VN)


class RunnerTempDbTests(unittest.TestCase):
    """Fixture: DB SQLite tạm qua --db-path/run_job — radar.db thật không đụng."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.db_path = Path(self._tmpdir.name) / "data" / "radar.db"
        self.db_path.parent.mkdir(parents=True)

    def _ledger_row(self, identity: str = IDENTITY):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        return conn.execute(
            "SELECT * FROM radar_schedule_runs WHERE run_identity = ?", (identity,)
        ).fetchone()


class RunnerInvocationTests(RunnerTempDbTests):
    """CLI/runner gọi đúng MỘT LẦN logic lease bền và truyền thất bại job."""

    def test_run_job_invokes_durable_lease_logic_exactly_once(self) -> None:
        spy = Mock(return_value={
            "ran": True, "reason": "completed", "run_identity": IDENTITY,
            "radar": {"status": "CURRENT", "counts": {"articles": 1, "change_events": 0}},
        })
        with patch.object(run_daily.scheduler, "run_daily_radar_once", spy):
            status = run_daily.run_job(db_path=self.db_path, now=DUE)
        spy.assert_called_once()
        args, kwargs = spy.call_args
        self.assertIsInstance(args[0], sqlite3.Connection)
        self.assertEqual(kwargs["owner"], run_daily.DEFAULT_OWNER)
        self.assertEqual(kwargs["now"], DUE)
        self.assertEqual(kwargs["window"], "today")
        self.assertTrue(status["ok"])
        self.assertEqual(status["reason"], "completed")
        self.assertEqual(status["radar_status"], "CURRENT")

    def test_run_job_propagates_job_failure_with_single_invocation(self) -> None:
        spy = Mock(side_effect=RuntimeError("local recompute exploded"))
        with patch.object(run_daily.scheduler, "run_daily_radar_once", spy):
            status = run_daily.run_job(db_path=self.db_path, now=DUE)
        self.assertEqual(spy.call_count, 1)
        self.assertFalse(status["ok"])
        self.assertEqual(status["status"], "FAILED")
        self.assertIn("local recompute exploded", status["error"])

    def test_main_exit_zero_when_not_due_and_one_on_job_failure(self) -> None:
        ok_spy = Mock(return_value={
            "ran": False, "reason": "not_due", "run_identity": IDENTITY,
        })
        with patch.object(run_daily.scheduler, "run_daily_radar_once", ok_spy):
            out = io.StringIO()
            with redirect_stdout(out):
                code = run_daily.main(["--db-path", str(self.db_path)])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue().strip().splitlines()[-1])
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["reason"], "not_due")

        bad = io.StringIO()
        with patch.object(run_daily.scheduler, "run_daily_radar_once",
                          Mock(side_effect=RuntimeError("boom"))):
            with redirect_stdout(bad):
                code = run_daily.main(["--db-path", str(self.db_path)])
        self.assertEqual(code, 1)
        self.assertIn("FAILED", bad.getvalue())

    def test_main_uses_actual_clock_and_prints_no_secret(self) -> None:
        fake_datetime = Mock(wraps=datetime)
        fake_datetime.now.return_value = DUE
        token = "secret-token-value-0123456789"
        with patch.object(run_daily, "datetime", fake_datetime):
            with patch.dict("os.environ", {"ADMIN_TOKEN": token}):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = run_daily.main(["--db-path", str(self.db_path)])
        self.assertEqual(code, 0)
        text = out.getvalue()
        self.assertNotIn(token, text)  # giá trị env không bao giờ bị in
        payload = json.loads(text.strip().splitlines()[-1])
        self.assertEqual(payload["status"], "OK")
        self.assertEqual(payload["reason"], "completed")

    def test_run_job_never_touches_network(self) -> None:
        with patch("socket.socket", side_effect=AssertionError("network used")):
            status = run_daily.run_job(db_path=self.db_path, now=DUE)
        self.assertTrue(status["ok"])


class RunnerIntegrationTests(RunnerTempDbTests):
    """Logic lease bền THẬT (không mock scheduler) trên DB tạm."""

    def test_due_run_completes_once_then_is_durable(self) -> None:
        first = run_daily.run_job(db_path=self.db_path, now=DUE)
        self.assertTrue(first["ok"])
        self.assertEqual(first["reason"], "completed")
        row = self._ledger_row()
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["owner"], run_daily.DEFAULT_OWNER)
        # Lần hai cùng identity: bền — không chạy lại.
        again = run_daily.run_job(db_path=self.db_path, now=DUE + timedelta(hours=1))
        self.assertTrue(again["ok"])
        self.assertFalse(again["ran"])
        self.assertEqual(again["reason"], "already_completed")

    def test_before_local_seven_is_not_due_and_writes_no_ledger(self) -> None:
        status = run_daily.run_job(db_path=self.db_path, now=BEFORE_DUE)
        self.assertTrue(status["ok"])
        self.assertFalse(status["ran"])
        self.assertEqual(status["reason"], "not_due")
        self.assertIsNone(self._ledger_row())

    def test_real_job_failure_marks_ledger_failed_and_bounded_retry(self) -> None:
        with patch.object(scheduler, "daily_radar",
                          Mock(side_effect=RuntimeError("recompute exploded"))):
            status = run_daily.run_job(db_path=self.db_path, now=DUE)
        self.assertFalse(status["ok"])
        self.assertEqual(status["status"], "FAILED")
        row = self._ledger_row()
        self.assertEqual(row["status"], "FAILED")
        self.assertIn("recompute exploded", row["last_error"])
        # Attempt 2 (vẫn trong trần): reclaim được, vẫn thất bại -> attempts=2.
        with patch.object(scheduler, "daily_radar",
                          Mock(side_effect=RuntimeError("still down"))):
            status2 = run_daily.run_job(db_path=self.db_path, now=DUE + timedelta(minutes=5))
        self.assertFalse(status2["ok"])
        row2 = self._ledger_row()
        self.assertEqual(row2["attempts"], 2)
        self.assertEqual(row2["status"], "FAILED")

    def test_invalid_window_reports_failed_without_crash(self) -> None:
        status = run_daily.run_job(db_path=self.db_path, now=DUE, window="bogus")
        self.assertFalse(status["ok"])
        self.assertIn("invalid window", status["error"])


class RegisterTaskScriptContractTests(unittest.TestCase):
    """Script PowerShell: nội dung đúng hợp đồng (pattern test_backup_scripts.py)."""

    SCRIPT = ROOT / "scripts" / "register_radar_task.ps1"

    def _text(self) -> str:
        return self.SCRIPT.read_text(encoding="utf-8")

    def test_registers_daily_seven_task_with_repo_and_uv(self) -> None:
        text = self._text()
        self.assertIn("VuHocAIRadar-Daily", text)
        self.assertIn("New-ScheduledTaskTrigger -Daily", text)
        self.assertIn("07:00:00", text)
        self.assertIn("Register-ScheduledTask", text)
        self.assertIn("backend.app.radar.run_daily", text)
        self.assertIn("WorkingDirectory", text)
        self.assertIn("Get-Command 'uv'", text)
        self.assertIn("$PSScriptRoot", text)  # đường dẫn repo tuyệt đối từ vị trí script

    def test_idempotent_guard_and_explicit_status_mode(self) -> None:
        text = self._text()
        self.assertIn("-Status", text)
        self.assertIn("Get-ScheduledTask", text)
        self.assertIn("Get-ScheduledTaskInfo", text)
        self.assertIn("already registered", text)

    def test_never_unregisters_never_reaches_out(self) -> None:
        text = self._text()
        self.assertNotIn("Unregister-ScheduledTask", text)
        self.assertNotIn("Remove-Item", text)
        self.assertNotIn("CimSession", text)
        self.assertNotIn("Invoke-Command", text)
        self.assertNotIn("-ComputerName", text)
        self.assertNotIn("0.0.0.0", text)


if __name__ == "__main__":
    unittest.main()
